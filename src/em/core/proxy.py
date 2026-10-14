"""动态代理池：TTL 内复用、失败即淘汰换 IP、池内备选。

与 LoongSoar 的 ProxyPool 同构，但只保留抓取所需的判据（不引入连接层跨 origin 启发式）。
"""

import logging
import re
import threading
import time
from dataclasses import dataclass
from typing import Any, Literal

import requests

from em.core.errors import ConfigError

log = logging.getLogger(__name__)

_PROXY_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}:\d+$")
# 回源空返回（IP 资源不足/限频）后的负缓存窗口：此期间排队线程直接退化直连，
# 不再连环调用代理 API（单飞只能合并同刻等待，挡不住前一个回源结束后的后继线程）
_EMPTY_REFILL_COOLDOWN_SEC = 1.0
# 代理 API 回源的连接超时（秒）：读取仍用 ProxySettings.timeout_sec，二者分别计时
_PROXY_API_CONNECT_TIMEOUT_SEC = 3
ProxyMode = Literal["auto", "always", "never"]
_VALID_MODES = ("auto", "always", "never")


@dataclass(frozen=True)
class ProxySettings:
    api: str
    enabled: bool = True
    num: int = 1
    ttl_sec: int = 30
    safety_margin_sec: int = 3
    timeout_sec: int = 8
    mode: ProxyMode = "auto"
    direct_fails: int = 3
    proxy_successes: int = 5
    cooldown_sec: int = 300

    def __post_init__(self) -> None:
        if self.num < 1:
            raise ConfigError("num 必须 >= 1")
        if self.ttl_sec <= self.safety_margin_sec:
            raise ConfigError("ttl_sec 必须大于 safety_margin_sec")
        if self.mode not in _VALID_MODES:
            raise ConfigError(f"mode 必须是 {','.join(_VALID_MODES)}")
        if self.direct_fails < 1:
            raise ConfigError("direct_fails 必须 >= 1")
        if self.proxy_successes < 1:
            raise ConfigError("proxy_successes 必须 >= 1")
        if self.cooldown_sec < 0:
            raise ConfigError("cooldown_sec 不能为负")


def fetch_proxies(settings: ProxySettings, session: requests.Session) -> list[str]:
    """从代理源取一批 'ip:port'；失败返回空列表（退化直连，不抛异常）。"""
    try:
        text = session.get(
            settings.api, timeout=(_PROXY_API_CONNECT_TIMEOUT_SEC, settings.timeout_sec)
        ).text.strip()
    except requests.RequestException as exc:
        log.debug("获取代理失败: %s", exc)
        return []
    lines = [ln.strip() for ln in text.splitlines() if _PROXY_RE.match(ln.strip())]
    if not lines and text:
        log.warning("代理源返回非预期格式，退化直连: %s", text[:80])
    return lines[: settings.num]


class ProxyPool:
    """短效动态代理池。``enabled=False`` 时 ``acquire`` 返回 None（走直连）。"""

    def __init__(self, settings: ProxySettings, session: requests.Session) -> None:
        self._settings = settings
        self._session = session
        self._current: str | None = None
        self._fetched_at = 0.0
        self._standby: list[str] = []
        self._failed_at: dict[str, float] = {}
        self._in_flight: dict[str, int] = {}  # 各 IP 当前在飞请求数（最少在飞优先分发依据）
        self._lock = threading.Lock()  # 仅保护上述内存状态，临界区内禁止网络调用
        self._refill_lock = threading.Lock()  # 回源单飞：并发缺 IP 时只发起一次代理 API 请求
        self._empty_at = -float("inf")  # 最近一次回源空返回时刻（负缓存哨兵，见模块常量）
        # 健康指标（只读快照见 stats()）：回源调用/空返回、采纳 IP 数、失败上报次数
        self._stats = {"fetch_calls": 0, "fetch_empty": 0, "ips_adopted": 0, "ip_failures": 0}

    @property
    def enabled(self) -> bool:
        return self._settings.enabled

    def acquire(self) -> str | None:
        """取一个可用代理 'ip:port'；不可用或关闭时返回 None。

        快速路径（current/standby 命中）只瞬时持状态锁；需要回源时改用独立的
        ``_refill_lock`` 单飞——回源期间不阻塞其他线程的失败上报与状态读取，
        同样缺 IP 的线程在锁外等待同一批结果，避免并发打代理 API 浪费提取配额。
        """
        if not self._settings.enabled:
            return None
        proxy = self._take_live()
        if proxy is not None:
            return proxy
        with self._refill_lock:
            # double-check：等待回源期间可能已有其他线程填充
            return self._take_live() or self._refill()

    def _take_live(self) -> str | None:
        """快速路径：在存活 IP 中选在飞请求数最少的分发，无可用返回 None。

        最少在飞优先（并列保序）：多 worker 并发不挤同一个 IP，
        单 IP 并发压平，降低上游限频概率；单个坏 IP 也只影响一个 worker。
        """
        with self._lock:
            if not self._is_live(self._current):
                self._current = None  # current 过期：同批 standby 一并过期
            self._standby = [p for p in self._standby if self._is_live(p)]
            pool_ips = ([self._current] if self._current else []) + self._standby
            if not pool_ips:
                return None
            pick = min(pool_ips, key=lambda p: self._in_flight.get(p, 0))
            self._current = pick
            self._standby = [p for p in pool_ips if p != pick]
            self._in_flight[pick] = self._in_flight.get(pick, 0) + 1
            return pick

    def release(self, proxy: str | None) -> None:
        """归还取用（与 acquire/refill 发出配对）：在飞计数减一，归零清除。"""
        if proxy is None:
            return
        with self._lock:
            count = self._in_flight.get(proxy, 0) - 1
            if count <= 0:
                self._in_flight.pop(proxy, None)
            else:
                self._in_flight[proxy] = count

    def report_failure(self, proxy: str | None) -> None:
        """上报失败：淘汰当前与备用中的同 IP，并记入近期黑名单避免立即重用。"""
        with self._lock:
            if proxy is not None and proxy == self._current:
                self._current = None
            if proxy is not None:
                self._standby = [p for p in self._standby if p != proxy]
                self._in_flight.pop(proxy, None)  # 失败即释放其在飞占用
                self._failed_at[proxy] = time.monotonic()
                self._stats["ip_failures"] += 1

    def stats(self) -> dict[str, int]:
        """只读健康指标快照（回源次数/空返回/采纳 IP 数/失败上报次数）。"""
        with self._lock:
            return dict(self._stats)

    def _is_live(self, proxy: str | None) -> bool:
        if not proxy:
            return False
        expire_at = self._fetched_at + self._settings.ttl_sec - self._settings.safety_margin_sec
        return time.monotonic() < expire_at

    def _refill(self) -> str | None:
        """回源拉取，跳过近期失败 IP（最多重拉 3 次避免死循环）。

        调用方已持 ``_refill_lock``；网络请求在 ``_lock`` 外发起，
        回源慢/超时时不阻塞其他线程的状态读写与失败上报。
        """
        with self._lock:
            # 负缓存：上一轮回源刚拿到空返回，短时间内直接放弃，避免连环打 API
            if time.monotonic() - self._empty_at < _EMPTY_REFILL_COOLDOWN_SEC:
                return None
            self._purge_failures()
        fetched: list[str] = []
        for _ in range(3):
            fetched = fetch_proxies(self._settings, self._session)
            with self._lock:
                self._stats["fetch_calls"] += 1
            if not fetched:
                with self._lock:
                    self._empty_at = time.monotonic()
                    self._stats["fetch_empty"] += 1
                return None
            with self._lock:
                blacklist = set(self._failed_at)
            fresh = [ip for ip in fetched if ip not in blacklist]
            if fresh:
                return self._adopt(fresh)
        # 连续 3 批全在黑名单（IP 池太小），硬用最后一批避免拿不到代理
        return self._adopt(fetched)

    def _adopt(self, ips: list[str]) -> str:
        """把一批回源 IP 写为 current + standby，并给发出的首个计入飞。"""
        with self._lock:
            self._current = ips[0]
            self._standby = ips[1:]
            self._fetched_at = time.monotonic()
            self._in_flight[ips[0]] = self._in_flight.get(ips[0], 0) + 1
            self._stats["ips_adopted"] += len(ips)
        return ips[0]

    def _purge_failures(self) -> None:
        """清除过期失败记录：超过一个 TTL 的 IP 视为可重新尝试（调用方持锁）。"""
        cutoff = time.monotonic() - self._settings.ttl_sec
        self._failed_at = {ip: t for ip, t in self._failed_at.items() if t > cutoff}


@dataclass
class HostState:
    """单个上游 host 的代理路由状态机。"""

    host: str
    mode: Literal["direct", "proxy", "probe"] = "direct"
    direct_fails: int = 0
    proxy_successes: int = 0
    proxy_since: float = 0.0
    probe_in_flight: bool = False  # probe 态下是否已放行一个直连探测请求


class ProxyRouter:
    """按 host 维度的智能代理路由。

    - ``never``：全程直连；
    - ``always``：全程代理（等价旧行为）；
    - ``auto``：默认直连，某 host 连续失败达阈值后切代理，代理下稳定后周期探测回退直连。
    """

    def __init__(self, pool: ProxyPool, settings: ProxySettings) -> None:
        self._pool = pool
        self._settings = settings
        self._hosts: dict[str, HostState] = {}
        self._lock = threading.Lock()  # 保护 host 状态机（并发请求共享路由）
        self._stats = {"switches_to_proxy": 0, "probes_issued": 0, "probe_failures": 0}

    @property
    def enabled(self) -> bool:
        return self._pool.enabled

    def _effective_mode(self) -> ProxyMode:
        if not self._settings.enabled:
            return "never"
        return self._settings.mode

    def acquire(self, host: str) -> str | None:
        """取该 host 当前应使用的代理；None 表示直连。"""
        mode = self._effective_mode()
        if mode == "never":
            return None
        if mode == "always":
            return self._pool.acquire()
        # auto：锁内只判定模式（瞬时），实际取代理（可能触发回源等待）在锁外。
        # probe 态只放行一个直连探测请求，其余并发请求继续走代理，避免并发探测抖动。
        with self._lock:
            state = self._hosts.setdefault(host, HostState(host))
            if state.mode == "direct":
                use_proxy = False
            elif state.mode == "proxy":
                use_proxy = True
            elif state.probe_in_flight:
                use_proxy = True
            else:
                state.probe_in_flight = True
                self._stats["probes_issued"] += 1
                use_proxy = False
        return self._pool.acquire() if use_proxy else None

    def report_result(
        self, host: str, proxy: str | None, success: bool, banned: bool = False
    ) -> None:
        """上报本次请求结果，驱动状态机。``banned`` 表示确定封禁（403/429）。"""
        with self._lock:
            mode = self._effective_mode()
            if mode == "never":
                return
            if mode == "always":
                if not success and proxy is not None:
                    self._pool.report_failure(proxy)
                return
            # auto
            state = self._hosts.setdefault(host, HostState(host))
            if state.mode == "direct":
                self._on_direct(state, success, banned)
            elif state.mode == "proxy":
                self._on_proxy(state, proxy, success)
            elif proxy is not None:
                # probe 态下在途代理请求的结果：按代理逻辑处理，
                # 不得冒充探测结果（探测一定走直连，proxy 为 None）
                self._on_proxy(state, proxy, success)
            else:  # 探测请求归来，解除单飞并据结果切换
                state.probe_in_flight = False
                if not success:
                    self._stats["probe_failures"] += 1
                self._on_probe(state, success)

    def report_proxy_failure(self, proxy: str | None) -> None:
        """仅淘汰代理 IP，不改路由状态机。

        供应用层发现的坏 IP 使用（如代理节点返回旧快照）：请求本身"成功"，
        但该 IP 不该继续用，下次 acquire 换新 IP。
        """
        if proxy is not None:
            self._pool.report_failure(proxy)

    def release(self, proxy: str | None) -> None:
        """归还取用的代理（配合 acquire 的在飞计数）；直连/never 为空操作。"""
        if proxy is not None:
            self._pool.release(proxy)

    def _on_direct(self, state: HostState, success: bool, banned: bool) -> None:
        if success:
            state.direct_fails = 0
            return
        state.direct_fails += 1
        if banned or state.direct_fails >= self._settings.direct_fails:
            self._switch_to_proxy(state)

    def _on_proxy(self, state: HostState, proxy: str | None, success: bool) -> None:
        if proxy is None:
            return  # 代理池不可用退化直连，不改变状态
        if success:
            state.proxy_successes += 1
            if self._should_probe(state):
                state.mode = "probe"
        else:
            state.proxy_successes = 0
            self._pool.report_failure(proxy)

    def _on_probe(self, state: HostState, success: bool) -> None:
        if success:
            state.mode = "direct"
            state.direct_fails = 0
            state.proxy_successes = 0
        else:
            self._switch_to_proxy(state)

    def _should_probe(self, state: HostState) -> bool:
        cooldown_passed = time.monotonic() - state.proxy_since >= self._settings.cooldown_sec
        return cooldown_passed and state.proxy_successes >= self._settings.proxy_successes

    def _switch_to_proxy(self, state: HostState) -> None:
        if state.mode != "proxy":
            log.info("host %s 切换到代理模式", state.host)
            self._stats["switches_to_proxy"] += 1
        state.mode = "proxy"
        state.direct_fails = 0
        state.proxy_successes = 0
        state.probe_in_flight = False
        state.proxy_since = time.monotonic()

    def host_state(self, host: str) -> HostState | None:
        """测试/观测用：取某 host 当前状态。"""
        return self._hosts.get(host)

    def stats(self) -> dict[str, Any]:
        """只读健康指标：路由计数 + 各 host 状态 + 代理池指标。"""
        with self._lock:
            hosts = {
                h: {"mode": s.mode, "probe_in_flight": s.probe_in_flight}
                for h, s in self._hosts.items()
            }
            out = dict(self._stats)
        out["hosts"] = hosts
        out["pool"] = self._pool.stats()
        return out

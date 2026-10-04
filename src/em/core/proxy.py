"""动态代理池：TTL 内复用、失败即淘汰换 IP、池内备选。

与 LoongSoar 的 ProxyPool 同构，但只保留抓取所需的判据（不引入连接层跨 origin 启发式）。
"""

import logging
import re
import time
from dataclasses import dataclass
from typing import Literal

import requests

from em.core.errors import ConfigError

log = logging.getLogger(__name__)

_PROXY_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}:\d+$")
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
        text = session.get(settings.api, timeout=settings.timeout_sec).text.strip()
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

    @property
    def enabled(self) -> bool:
        return self._settings.enabled

    def acquire(self) -> str | None:
        """取一个可用代理 'ip:port'；不可用或关闭时返回 None。"""
        if not self._settings.enabled:
            return None
        if self._is_live(self._current):
            return self._current
        # 当前不可用：优先复用 standby 中未过期代理（本地、瞬时），
        # 再回源拉取（网络、慢）——避免每次失效都调代理 API 导致换 IP 越来越慢。
        if self._standby and self._is_live(self._standby[0]):
            self._current = self._standby.pop(0)
            return self._current
        return self._refill()

    def report_failure(self, proxy: str | None) -> None:
        """上报失败：淘汰当前与备用中的同 IP，并记入近期黑名单避免立即重用。"""
        if proxy is not None and proxy == self._current:
            self._current = None
        if proxy is not None:
            self._standby = [p for p in self._standby if p != proxy]
            self._failed_at[proxy] = time.monotonic()

    def _is_live(self, proxy: str | None) -> bool:
        if not proxy:
            return False
        expire_at = self._fetched_at + self._settings.ttl_sec - self._settings.safety_margin_sec
        return time.monotonic() < expire_at

    def _refill(self) -> str | None:
        """回源拉取，跳过近期失败 IP（最多重拉 3 次避免死循环）。"""
        self._purge_failures()
        fetched: list[str] = []
        for _ in range(3):
            fetched = fetch_proxies(self._settings, self._session)
            if not fetched:
                return None
            fresh = [ip for ip in fetched if ip not in self._failed_at]
            if fresh:
                self._current = fresh[0]
                self._standby = fresh[1:]
                self._fetched_at = time.monotonic()
                return self._current
        # 连续 3 批全在黑名单（IP 池太小），硬用最后一批避免拿不到代理
        self._current = fetched[0]
        self._standby = fetched[1:]
        self._fetched_at = time.monotonic()
        return self._current

    def _purge_failures(self) -> None:
        """清除过期失败记录：超过一个 TTL 的 IP 视为可重新尝试。"""
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
        # auto：按 host 状态机
        state = self._hosts.setdefault(host, HostState(host))
        if state.mode in ("direct", "probe"):
            return None
        return self._pool.acquire()

    def report_result(
        self, host: str, proxy: str | None, success: bool, banned: bool = False
    ) -> None:
        """上报本次请求结果，驱动状态机。``banned`` 表示确定封禁（403/429）。"""
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
        else:  # probe
            self._on_probe(state, success)

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
        state.mode = "proxy"
        state.direct_fails = 0
        state.proxy_successes = 0
        state.proxy_since = time.monotonic()

    def host_state(self, host: str) -> HostState | None:
        """测试/观测用：取某 host 当前状态。"""
        return self._hosts.get(host)

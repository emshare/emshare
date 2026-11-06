"""动态代理池：TTL 内复用、失败即淘汰换 IP、池内备选。

与 LoongSoar 的 ProxyPool 同构，但只保留抓取所需的判据（不引入连接层跨 origin 启发式）。
"""

import concurrent.futures
import hashlib
import logging
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlparse

import requests

from em.core.errors import ConfigError

log = logging.getLogger(__name__)

# 代理条目：ip:port，可选 http(s):// 前缀与 user:pass@ 认证（厂商裸返回 ip:port 为主）。
# 不接受 socks：requests 需要 PySocks 才能用，本项目不引新依赖。
_PROXY_RE = re.compile(r"^(?:https?://)?(?:[^@\s]+@)?\d{1,3}(?:\.\d{1,3}){3}:\d+$")
# 回源空返回（IP 资源不足/限频）后的负缓存窗口：此期间排队线程直接退化直连，
# 不再连环调用代理 API（单飞只能合并同刻等待，挡不住前一个回源结束后的后继线程）
_EMPTY_REFILL_COOLDOWN_SEC = 1.0
# 回源轮间短退避：整批不可用后立刻重拉等于连打限流中的 API，0.2s 与连接类退避同量级
_REFILL_ROUND_BACKOFF_SEC = 0.2
# 代理 API 回源的连接超时（秒）：读取仍用 ProxySettings.timeout_sec，二者分别计时
_PROXY_API_CONNECT_TIMEOUT_SEC = 3
# proxy 态池空时的重试等待：回源单飞通常零点几秒产出新批次，
# 短等一次再取，避免静默退化直连（此刻直连多半正是被封才切的代理）
_POOL_EMPTY_RETRY_SEC = 0.3
ProxyMode = Literal["auto", "always", "never"]
_VALID_MODES = ("auto", "always", "never")
# 整批探测全死后的处置：adopt=暂停预筛（批次直接进池，旧行为）；
# lenient=改用更短读超时的快筛继续过滤，避免把未验证的 hang IP 交给业务侧鉴死
DegradedMode = Literal["adopt", "lenient"]
_VALID_DEGRADED = ("adopt", "lenient")


@dataclass(frozen=True)
class ProxySettings:
    api: str
    enabled: bool = True
    num: int = 1
    ttl_sec: int = 30
    safety_margin_sec: int = 3
    timeout_sec: int = 8
    mode: ProxyMode = "auto"
    direct_fails: int = 2
    proxy_successes: int = 5
    cooldown_sec: int = 300
    # 参与回源预筛的源数量（按 ``api`` 书写顺序，前 N 个）。
    # 收费备用源默认不预筛：淘汰等于把付费配额直接扔掉，死 IP 交给业务请求自然淘汰
    prefilter_sources: int = 1
    # 默认降级快筛：实测同窗口对照下失败数 4→1 / 11→5 / 10→0，采购从未更高；
    # adopt（暂停预筛直接放行）保留为回退路径，出问题可用环境变量切回
    degraded_mode: DegradedMode = "lenient"

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
        if self.prefilter_sources < 0:
            raise ConfigError("prefilter_sources 不能为负")
        if self.degraded_mode not in _VALID_DEGRADED:
            raise ConfigError(f"degraded_mode 必须是 {','.join(_VALID_DEGRADED)}")


def proxy_url(entry: str) -> str:
    """把代理条目规范成 requests 可用的 URL：裸 ``ip:port`` 补 ``http://`` 前缀。

    显式 schema 或带认证的原样返回——``https://`` 表示"到代理本身的连接走 TLS"，
    与目标站点是否 HTTPS 无关。
    """
    return entry if "://" in entry else f"http://{entry}"


def fetch_proxies(
    settings: ProxySettings, session: requests.Session, url: str | None = None
) -> list[str]:
    """从代理源取一批 'ip:port'；失败返回空列表（退化直连，不抛异常）。

    ``url`` 缺省取 ``settings.api`` 首个源（多源逗号分隔，主源在前）。
    返回**解析出的全部行**，按 ``num`` 截断由调用方处理——厂商按返回条数计费，
    重复行与超量行同样计费，账本需要看到原始交付量才能对上后台消耗。
    """
    url = url or settings.api.split(",")[0].strip()
    try:
        text = session.get(url, timeout=(_PROXY_API_CONNECT_TIMEOUT_SEC, settings.timeout_sec)).text.strip()
    except requests.RequestException as exc:
        log.debug("获取代理失败: %s", exc)
        return []
    lines = [ln.strip() for ln in text.splitlines() if _PROXY_RE.match(ln.strip())]
    if not lines and text:
        log.warning("代理源返回非预期格式，退化直连: %s", text[:80])
    # 原样返回（不去重）：采购账本要按交付行数对账，重复行同样计费；
    # 去重只影响"可用名额"，在 _fetch_batch 截断前做
    return lines


class ProxyPool:
    """短效动态代理池。``enabled=False`` 时 ``acquire`` 返回 None（走直连）。

    ``prober`` 为可选的回源预筛回调（``ip -> bool``，True=可用）：死 IP 高发时段
    在进池前并发探测，判死的直接记黑名单，避免死 IP 的识别成本由业务请求承担。
    渠道无关：探测目标由调用方（应用层）注入，``None`` 时完全不预筛。
    """

    # 预筛并发度与超时由探测回调自持，池内仅控制并发线程上限。
    # 需 >= EM_PROXY_NUM（默认 5）：单波并发探测整批，两波串行会倍增单飞锁持有时间
    _PREFILTER_WORKERS = 6
    # 预筛降级窗口：整批筛死时进入降级，窗口过后自动恢复严格探测。
    # adopt 模式窗口内完全不探测（直接进池，由业务自然淘汰）；lenient 模式窗口内
    # 改用短超时快筛继续过滤——实测放行未验证 IP 的代价（每个 hang 撞 2 次业务超时
    # ≈3.5s）远高于一次快筛（≈1.5s），因此 lenient 窗口可以更短
    _PREFILTER_OFF_WINDOW_SEC = 10.0
    _PREFILTER_LENIENT_WINDOW_SEC = 5.0
    # 连败熔断：某源连续若干批"整批不可用"后冷却一段时间，不再回源。
    # 实测全死窗口里一次运行可买 45 个 IP 只为 2 个有产出（且占住单飞锁 34s），
    # 而连续 3 批全死的概率已很低；阈值 2 让它尽早停手，60s 冷却给源恢复时间
    _ALL_DEAD_LIMIT = 2
    _SOURCE_DEAD_COOLDOWN_SEC = 60.0
    # 多源降级：主源（如免费源）空返回/异常/回源超慢（疑似限流）时改用备用源，
    # 降级窗口内跳过主源避免每轮回源都先撞一次慢源，窗口过后自动试探恢复
    _PRIMARY_SLOW_SEC = 3.0
    _PRIMARY_FAILOVER_SEC = 60.0
    # 软失败（读超时）容忍次数：一次读超时既可能是出口坏了，也可能是单页慢，
    # 换 IP 对后者只是再付一次握手并把好出口黑掉一个 TTL，因此连续两次才淘汰
    _SOFT_FAIL_LIMIT = 2
    # 续期提前量：回源 + 预筛实测 2.4~3.2s，提前 3s 触发才能保证新批次在旧 IP
    # 硬到期（TTL - 安全余量）之前就绪，把"全体 worker 停在回源锁上"的悬崖变成平滑交接
    _RENEW_LEAD_SEC = 3.0
    # 续期失败后的重试间隔：空返回已有 1s 负缓存，这里再退避一次避免每个 acquire 都起线程
    _RENEW_RETRY_SEC = 1.0

    def __init__(
        self,
        settings: ProxySettings,
        session: requests.Session,
        prober: Callable[[str], bool] | None = None,
        fallback_prober: Callable[[str], bool] | None = None,
    ) -> None:
        self._settings = settings
        self._session = session
        self._prober = prober
        # 降级窗口内使用的快筛（读超时更短）；None 或非 lenient 模式时退回 adopt 行为
        self._fallback_prober = fallback_prober
        self._lenient = settings.degraded_mode == "lenient" and fallback_prober is not None
        # 多源：EM_PROXY_API 逗号分隔，首个为主源（免费），其余备用（收费）
        self._apis: list[str] = [u.strip() for u in settings.api.split(",") if u.strip()]
        self._source_index = {url: i for i, url in enumerate(self._apis)}
        # 只有配了备用源，主源降级才有意义：单源时"跳过主源"等于禁用整个回源
        self._has_backup = len(self._apis) > 1
        self._primary_off_until = -float("inf")  # 主源降级截止时刻
        self._current: str | None = None
        # 逐 IP 采纳时刻：批内 IP 共享同一个时刻会让它们同时到期，
        # 5 个 worker 会在同一瞬间一起等回源；按 IP 记录才能分别续期与分别过期
        self._adopted_at: dict[str, float] = {}
        self._standby: list[str] = []
        self._renewing = False  # 后台续期在飞（单飞，避免每个 acquire 起一个线程）
        self._renew_after = 0.0  # 续期失败后的下次允许时刻
        self._failed_at: dict[str, float] = {}
        self._in_flight: dict[str, int] = {}  # 各 IP 当前在飞请求数（最少在飞优先分发依据）
        self._lock = threading.Lock()  # 仅保护上述内存状态，临界区内禁止网络调用
        self._refill_lock = threading.Lock()  # 回源单飞：并发缺 IP 时只发起一次代理 API 请求
        self._empty_at = -float("inf")  # 最近一次回源空返回时刻（负缓存哨兵，见模块常量）
        # 预筛降级截止时刻：整批筛死后进入窗口，窗口内按 degraded_mode 处置
        self._prefilter_degraded_until = -float("inf")
        self._strikes: dict[str, int] = {}  # 各 IP 连续软失败次数（读超时，两次才淘汰）
        # 连败熔断：某源连续"整批不可用"的次数与冷却截止时刻（逐源，避免拖累备用源）
        self._dead_streak: dict[str, int] = {}
        self._source_dead_until: dict[str, float] = {}
        # 采购账本：厂商按"返回条数"计费，与是否使用无关，因此把"交付 → 去重 → 进池
        # → 服役 → 有产出"五段都记下来，否则只能靠后台面板反推消耗了多少配额
        self._ips_unique: set[str] = set()
        self._ips_served: set[str] = set()  # 真正发出过业务请求的 IP
        self._ips_productive: set[str] = set()  # 至少成功过一次业务请求的 IP
        # 分源账本：主备顺序目前是静态配置，质量（淘汰率）只能靠分源统计判断
        self._source_labels = {
            url: f"src{i}:{urlparse(url).hostname or '?'}#{hashlib.sha1(url.encode()).hexdigest()[:6]}"
            for i, url in enumerate(self._apis)
        }
        self._source_stats: dict[str, dict[str, int]] = {
            label: {"calls": 0, "returned": 0, "rejected": 0, "adopted": 0}
            for label in self._source_labels.values()
        }
        # 健康指标（只读快照见 stats()）：回源调用/空返回/耗时、采纳 IP 数、失败上报次数
        self._stats = {
            "fetch_calls": 0,
            "fetch_empty": 0,
            "ips_returned": 0,  # 厂商交付行数合计（计费口径）
            "ips_adopted": 0,
            "ip_failures": 0,  # 淘汰（硬失败或连续两次软失败）
            "soft_failures": 0,  # 读超时次数（首次软失败不淘汰）
            "prefilter_rejected": 0,  # 预筛判死未进池的 IP 数
            "prefilter_lenient_rejected": 0,  # 其中由降级快筛判死的（用于评估降级策略）
            "degraded_adopted": 0,  # adopt 模式下未探测就进池的 IP 数（降级策略的暴露面）
            "degraded_events": 0,  # 整批全死进入降级窗口的次数（两种模式的共同触发口径）
            "source_breaker_trips": 0,  # 连续全死触发熔断的次数
            "refill_sec": 0.0,  # 代理 API 回源耗时累计（含在单飞锁内，并发线程等待会放大）
            "prefilter_sec": 0.0,  # 回源预筛探测的墙钟耗时累计（批次内并发）
        }
        if prober is not None and settings.prefilter_sources < len(self._apis):
            log.info(
                "预筛只作用于前 %d 个源（共 %d 个），其余源直接进池",
                settings.prefilter_sources,
                len(self._apis),
            )

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
            # 快路径命中后顺便触发后台续期：旧 IP 继续发放，业务线程不等回源
            self._maybe_renew()
            return proxy
        with self._refill_lock:
            # double-check：等待回源期间可能已有其他线程填充
            return self._take_live() or self._refill()

    def _maybe_renew(self) -> None:
        """临近过期时起一个后台线程续期（单飞）。

        续期不占用业务线程：新批次就绪前旧 IP 照常发放，失败也只是不换血——
        已经证明有产出的旧 IP 比"退化到没 IP"更值钱。
        """
        now = time.monotonic()
        with self._lock:
            if self._renewing or now < self._renew_after or not self._renew_due_locked(now):
                return
            self._renewing = True
            self._renew_after = now + self._RENEW_RETRY_SEC
        threading.Thread(target=self._renew_worker, name="proxy-renew", daemon=True).start()

    def _renew_due_locked(self, now: float) -> bool:
        """是否有在池 IP 已进入续期窗口（调用方持 ``_lock``）。"""
        lead = self._settings.ttl_sec - self._settings.safety_margin_sec - self._RENEW_LEAD_SEC
        if lead <= 0:
            return False  # TTL 太短，提前量覆盖不了回源成本：退回阻塞式换血，避免连环续期
        pool = ([self._current] if self._current else []) + self._standby
        return any(now >= self._adopted_at.get(ip, 0.0) + lead for ip in pool)

    def _renew_worker(self) -> None:
        try:
            with self._refill_lock:
                # double-check：排队等锁期间可能已有别的线程完成续期
                if self._renew_due():
                    proxy = self._refill()
                    # 成功=已换血；失败=继续用旧批次到硬到期（不阻塞业务线程）
                    log.info("代理池后台续期：%s", proxy or "失败，沿用旧批次")
        finally:
            with self._lock:
                self._renewing = False

    def _renew_due(self) -> bool:
        with self._lock:
            return self._renew_due_locked(time.monotonic())

    def available(self) -> int:
        """当前可分发（未到硬到期）的 IP 数。

        供上层按"每出口 N 个并发"收敛：实测把并发压到与出口数 1:1 会砍掉一半吞吐
        却降不下失败率，因此收敛只用来避免少数出口被打爆，不追求 1:1 对齐。
        """
        with self._lock:
            pool = ([self._current] if self._current else []) + self._standby
            return sum(1 for ip in pool if self._is_live(ip))

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
            self._ips_served.add(pick)
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

    def report_failure(self, proxy: str | None, hard: bool = True) -> None:
        """上报失败：``hard`` 立即淘汰；软失败（读超时）累计到阈值才淘汰。

        软失败第一次不把 IP 移出池子，也不动在飞计数——留给同 IP 重试行消化。
        这样"出口坏了"（连接失败）与"这一页慢了"（读超时）不再按同一力度惩罚，
        避免一次抖动就黑掉一个好 IP 一个 TTL、再回源买一批新 IP。
        """
        with self._lock:
            if proxy is None:
                return
            if not hard:
                strikes = self._strikes.get(proxy, 0) + 1
                self._strikes[proxy] = strikes
                self._stats["soft_failures"] += 1
                if strikes < self._SOFT_FAIL_LIMIT:
                    return
            if proxy == self._current:
                self._current = None
            self._standby = [p for p in self._standby if p != proxy]
            # 不动 _in_flight：同一 IP 可能还有别的 worker 在飞，整条 pop 会让计数
            # 凭空归零（该 IP 复采后分发把它当空闲，新请求全压上去）；
            # 本次占用由调用方 finally 里的 release 归还，那里才是唯一的减员点
            self._failed_at[proxy] = time.monotonic()
            self._strikes.pop(proxy, None)
            self._adopted_at.pop(proxy, None)
            self._stats["ip_failures"] += 1

    def report_success(self, proxy: str | None) -> None:
        """上报一次业务成功：计入"有产出"，并清空软失败计数（抖动已恢复）。"""
        if proxy is None:
            return
        with self._lock:
            self._ips_productive.add(proxy)
            self._strikes.pop(proxy, None)

    def hold(self, proxy: str | None) -> bool:
        """软失败后继续占用同一 IP 重试（在飞计数 +1）；该 IP 已不可用返回 False。

        复用同一出口能省掉一次 TCP/TLS 握手（实测代理页均 0.87s 中握手占大头），
        也让"同 IP 重试一次"不必先归还再重新分发到别的出口。
        """
        if proxy is None:
            return False
        with self._lock:
            pool = ([self._current] if self._current else []) + self._standby
            if proxy not in pool or not self._is_live(proxy):
                return False
            self._in_flight[proxy] = self._in_flight.get(proxy, 0) + 1
            self._ips_served.add(proxy)
            return True

    def stats(self) -> dict[str, Any]:
        """只读快照：健康指标 + 采购账本（五段 IP 漏斗与分源统计）。

        厂商按次计费，``fetch_calls × num`` 才是账单口径，``ips_adopted`` 只是
        "进池数"——两者之差就是预筛淘汰与重复返回带来的浪费。
        """
        with self._lock:
            out: dict[str, Any] = dict(self._stats)
            out["ips_unique"] = len(self._ips_unique)
            out["ips_served"] = len(self._ips_served)
            out["ips_productive"] = len(self._ips_productive)
            out["source_stats"] = {k: dict(v) for k, v in self._source_stats.items()}
            # 哪些源参与预筛：未预筛的源"淘汰率恒为 0"是构造出来的，不能与预筛源比质量
            out["prefiltered"] = (
                [
                    self._source_labels[url]
                    for i, url in enumerate(self._apis)
                    if i < self._settings.prefilter_sources
                ]
                if self._prober is not None
                else []
            )
            return out

    def _is_live(self, proxy: str | None) -> bool:
        """按该 IP 自己的采纳时刻判断是否过期（调用方持 ``_lock``）。"""
        if not proxy:
            return False
        adopted = self._adopted_at.get(proxy)
        if adopted is None:
            return False
        expire_at = adopted + self._settings.ttl_sec - self._settings.safety_margin_sec
        return time.monotonic() < expire_at

    def _fetch_batch(self) -> tuple[list[str], str | None]:
        """按源顺序回源取一批 IP：主源空返回/异常/超慢 → 降级备用源并设窗口。

        降级窗口内跳过主源（每轮回源不再先撞一次慢源）；单源配置行为与旧版一致。
        回源调用计数、耗时与交付量在此累计（多源重试的时间全部计入 refill_sec）。
        返回值第二项是该批的源，供分源账本归因预筛淘汰与进池数。
        """
        now = time.monotonic()
        # 单源配置必须忽略降级窗口，否则窗口内 urls 为空、整段时间一个 IP 都拿不到
        primary_off = self._has_backup and now < self._primary_off_until
        primary = self._apis[0] if self._apis else ""
        with self._lock:
            urls: list[str] = []
            for url in self._apis:
                if primary_off and url == primary:
                    continue
                if url in self._source_dead_until:
                    if now < self._source_dead_until[url]:
                        continue
                    # 冷却到期：恢复该源，并给它一次全新的连败计数
                    self._source_dead_until.pop(url, None)
                    self._dead_streak.pop(url, None)
                urls.append(url)
        if not urls:
            log.debug("所有代理源处于熔断冷却期，本轮不回源")
            return [], None
        for url in urls:
            t0 = time.monotonic()
            lines = fetch_proxies(self._settings, self._session, url)
            # 计费按原始交付量算；去重只影响可用名额——同一 IP 重复返回不该占掉 num，
            # 但它确实被计费了，所以"交付"与"进池"要分开记账
            ips = list(dict.fromkeys(lines))[: self._settings.num]
            elapsed = time.monotonic() - t0
            with self._lock:
                self._stats["fetch_calls"] += 1
                self._stats["refill_sec"] += elapsed
                self._record_purchase(url, lines)
            if ips:
                if (
                    url == primary
                    and not primary_off
                    and self._has_backup
                    and elapsed > self._PRIMARY_SLOW_SEC
                ):
                    with self._lock:
                        self._primary_off_until = now + self._PRIMARY_FAILOVER_SEC
                    log.warning(
                        "主源回源 %.1fs 超过 %.0fs（疑似限流），降级备用源 %.0fs",
                        elapsed, self._PRIMARY_SLOW_SEC, self._PRIMARY_FAILOVER_SEC,
                    )
                return ips, url
            if url == primary and not primary_off and self._has_backup:
                with self._lock:
                    self._primary_off_until = time.monotonic() + self._PRIMARY_FAILOVER_SEC
                log.warning("主源回源空返回/异常，降级备用源 %.0fs", self._PRIMARY_FAILOVER_SEC)
        return [], None

    def _record_purchase(self, url: str, lines: list[str]) -> None:
        """记一次回源交付（调用方持 ``self._lock``）：厂商按返回条数计费。"""
        self._stats["ips_returned"] += len(lines)
        self._ips_unique.update(lines)
        label = self._source_labels.get(url)
        if label is not None:
            stat = self._source_stats[label]
            stat["calls"] += 1
            stat["returned"] += len(lines)

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
        source: str | None = None
        for round_no in range(3):
            fetched, source = self._fetch_batch()
            if not fetched:
                with self._lock:
                    self._empty_at = time.monotonic()
                    self._stats["fetch_empty"] += 1
                return None
            with self._lock:
                blacklist = set(self._failed_at)
                degraded = time.monotonic() < self._prefilter_degraded_until
            fresh = [ip for ip in fetched if ip not in blacklist]
            if fresh:
                if not self._prefilter_enabled(source):
                    # 该源不参与预筛（收费源，淘汰等于浪费配额）
                    self._reset_dead_streak(source)
                    return self._adopt(fresh, source)
                if degraded and not self._lenient:
                    # adopt 模式：降级窗口内不探测，直接进池由业务自然淘汰。
                    # 未探测的放行没有质量结论，按"交付成功"中断连败——否则死/活交替
                    # 的源会每两轮被熔断，而 adopt 本来就靠业务侧兜底，不需要这层保护。
                    # 单独计数：这是"未验证就放行"的暴露面，评估降级策略时必须能看到
                    with self._lock:
                        self._stats["degraded_adopted"] += len(fresh)
                    self._reset_dead_streak(source)
                    return self._adopt(fresh, source)
                # lenient 模式在降级窗口内改用快筛，仍然过滤，只是判据更短
                alive = self._prefilter(fresh, source, lenient=degraded)
                if alive:
                    self._reset_dead_streak(source)
                    return self._adopt(alive, source)
            # 本批不可用（整批黑名单/筛死）：计入连败，短退避后再拉下一轮。
            # 不退避会连打正在限流的代理 API，把冷却窗口拖得更长
            self._note_dead_batch(source)
            if round_no < 2:
                time.sleep(_REFILL_ROUND_BACKOFF_SEC)
        # 3 轮仍不可用（多源各自失败一次等）：硬用最后一批，避免彻底拿不到代理
        return self._adopt(fetched, source)

    def _note_dead_batch(self, source: str | None) -> None:
        """记一轮"整批不可用"；连续到阈值即熔断该源，冷却期内不再回源。

        全死窗口里每一轮回源都是纯支出：实测一次运行可买 45 个 IP 只换来 2 个有产出，
        还把单飞锁占住 34s。熔断把"继续买"换成"停手 60s"，让代价从 O(轮数) 收敛到 O(阈值)。
        """
        if source is None:
            return
        now = time.monotonic()
        with self._lock:
            streak = self._dead_streak.get(source, 0) + 1
            self._dead_streak[source] = streak
            if streak < self._ALL_DEAD_LIMIT:
                return
            self._source_dead_until[source] = now + self._SOURCE_DEAD_COOLDOWN_SEC
            self._dead_streak.pop(source, None)
            self._stats["source_breaker_trips"] += 1
        log.warning(
            "源连续 %d 批全死，熔断 %.0fs",
            self._ALL_DEAD_LIMIT,
            self._SOURCE_DEAD_COOLDOWN_SEC,
        )

    def _reset_dead_streak(self, source: str | None) -> None:
        """该源产出了可用 IP：连败计数清零。"""
        if source is None:
            return
        with self._lock:
            self._dead_streak.pop(source, None)

    def _prefilter_enabled(self, source: str | None) -> bool:
        """该源是否参与预筛：``prefilter_sources`` 限定前 N 个源（书写顺序）。

        免费主源死 IP 率高，筛掉能省业务重试；收费备用源本身质量较好且按个计费，
        预筛淘汰等于把买来的 IP 直接扔掉，因此默认只筛主源。
        """
        if self._prober is None:
            return False
        return self._source_index.get(source or "", 0) < self._settings.prefilter_sources

    def _prefilter(
        self, ips: list[str], source: str | None = None, lenient: bool = False
    ) -> list[str]:
        """回源预筛：并发探测批次 IP，判死的记黑名单不进池；无 prober 原样返回。

        判死即等同一次失败上报（黑名单 TTL 内不再取用）。整批全死时进入降级窗口：
        ``adopt`` 模式窗口内完全不探测，``lenient`` 模式窗口内改用快筛继续过滤——
        后者用 1.5s 左右的读预算仍能卡住"连上但不响应"的 hang，而放行这类 IP
        的代价是业务侧两次超时（≈3.5s），远高于一次快筛（≈1.5s）。
        ``source`` 只用于分源账本：淘汰率是判断"哪个源的 IP 更值钱"的直接依据。
        """
        use_fallback = lenient and self._fallback_prober is not None
        prober = self._fallback_prober if use_fallback else self._prober
        if prober is None:
            return ips
        t0 = time.monotonic()
        with concurrent.futures.ThreadPoolExecutor(max_workers=self._PREFILTER_WORKERS) as ex:
            alive_flags = list(ex.map(prober, ips))
        alive = [ip for ip, ok in zip(ips, alive_flags, strict=True) if ok]
        dead = [ip for ip, ok in zip(ips, alive_flags, strict=True) if not ok]
        if dead:
            now = time.monotonic()
            with self._lock:
                for ip in dead:
                    self._failed_at[ip] = now
                self._stats["prefilter_rejected"] += len(dead)
                if lenient:
                    self._stats["prefilter_lenient_rejected"] += len(dead)
                label = self._source_labels.get(source) if source else None
                if label is not None:
                    self._source_stats[label]["rejected"] += len(dead)
                if not alive:
                    # 整批全死：进入降级窗口，窗口长度按处置方式区分
                    window = (
                        self._PREFILTER_LENIENT_WINDOW_SEC
                        if self._lenient
                        else self._PREFILTER_OFF_WINDOW_SEC
                    )
                    self._prefilter_degraded_until = now + window
                    self._stats["degraded_events"] += 1
                    log.info(
                        "预筛整批全死，%s %.0fs",
                        "降级为快筛" if self._lenient else "暂停预筛由业务请求自然淘汰",
                        window,
                    )
            log.info(
                "预筛%s淘汰 %d/%d 个死 IP（本批存活 %d）",
                "(快筛)" if lenient else "",
                len(dead),
                len(ips),
                len(alive),
            )
        with self._lock:
            self._stats["prefilter_sec"] += time.monotonic() - t0
        return alive

    def _adopt(self, ips: list[str], source: str | None = None) -> str:
        """把一批回源 IP 写为 current + standby，并给发出的首个计入飞。"""
        with self._lock:
            self._current = ips[0]
            self._standby = ips[1:]
            # 逐 IP 记采纳时刻：整批共享一个时刻会让它们同时到期（悬崖）
            now = time.monotonic()
            self._adopted_at = {ip: now for ip in ips}
            self._in_flight[ips[0]] = self._in_flight.get(ips[0], 0) + 1
            self._ips_served.add(ips[0])
            self._stats["ips_adopted"] += len(ips)
            label = self._source_labels.get(source) if source else None
            if label is not None:
                self._source_stats[label]["adopted"] += len(ips)
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

    def available(self, host: str) -> int:
        """该 host 当前可用的代理数；直连态为 0（上层据此保持原并发）。

        必须按 host 判断：``auto`` 模式下 pool 里可能存着别的 host 换来的 IP，
        但对本 host 尚未切代理——按池子计数会把直连并发也压下去。
        """
        mode = self._effective_mode()
        if mode == "never":
            return 0
        if mode == "always":
            return self._pool.available()
        with self._lock:
            state = self._hosts.get(host)
            on_proxy = state is not None and state.mode in ("proxy", "probe")
        return self._pool.available() if on_proxy else 0

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
            elif state.mode == "proxy" or state.probe_in_flight:
                use_proxy = True
            else:
                state.probe_in_flight = True
                self._stats["probes_issued"] += 1
                use_proxy = False
        if use_proxy:
            proxy = self._pool.acquire()
            if proxy is not None:
                return proxy
            # 池空（回源空返回/负缓存窗口）：短暂等待回源产出后再取一次，
            # 不静默退化直连——切到代理意味着直连已被封，退化只会白烧重试预算
            time.sleep(_POOL_EMPTY_RETRY_SEC)
            return self._pool.acquire()
        return None

    def report_result(
        self,
        host: str,
        proxy: str | None,
        success: bool,
        banned: bool = False,
        soft: bool = False,
    ) -> None:
        """上报本次请求结果，驱动状态机。

        ``banned`` 表示确定封禁（403/429）；``soft`` 表示读超时这类"可能是慢页"
        的失败——出口先留在池里（首次不淘汰），由传输层同 IP 重试一次消化。
        """
        with self._lock:
            mode = self._effective_mode()
            if mode == "never":
                return
            if mode == "always":
                if success:
                    self._pool.report_success(proxy)
                elif proxy is not None:
                    self._report_pool_failure(proxy, soft)
                return
            # auto
            state = self._hosts.setdefault(host, HostState(host))
            if state.mode == "direct":
                self._on_direct(state, success, banned)
            elif state.mode == "proxy":
                self._on_proxy(state, proxy, success, soft)
            elif proxy is not None:
                # probe 态下在途代理请求的结果：按代理逻辑处理，
                # 不得冒充探测结果（探测一定走直连，proxy 为 None）
                self._on_proxy(state, proxy, success, soft)
            else:  # 探测请求归来，解除单飞并据结果切换
                state.probe_in_flight = False
                if not success:
                    self._stats["probe_failures"] += 1
                self._on_probe(state, success)

    def _report_pool_failure(self, proxy: str | None, soft: bool) -> None:
        """把失败交给池子：硬失败按原样上报，软失败走降档（首次不淘汰）。"""
        if soft:
            self._pool.report_failure(proxy, hard=False)
        else:
            self._pool.report_failure(proxy)

    def report_proxy_failure(self, proxy: str | None) -> None:
        """仅淘汰代理 IP，不改路由状态机。

        供应用层发现的坏 IP 使用（如代理节点返回旧快照）：请求本身"成功"，
        但该 IP 不该继续用，下次 acquire 换新 IP。
        """
        if proxy is not None:
            self._pool.report_failure(proxy)

    def abandon(self, host: str, proxy: str | None) -> None:
        """请求因非渠道异常中断、没有成败结论时的兜底：仅解除 probe 单飞。

        ``report_result`` 只覆盖成功与 ``ChannelError`` 路径；探测请求若抛出
        其他异常（如协议校验回调自身 bug），``probe_in_flight`` 会永久卡在
        True，该 host 再无自动回退直连的机会。此处不淘汰 IP、不累计失败
        （原因可能在本地）；探测无结论时保守退回代理态，冷却后重新探测。
        probe 态在途代理请求（``proxy`` 非空）不触碰单飞——单飞属于另一条
        尚未归来的直连探测请求。
        """
        with self._lock:
            if self._effective_mode() != "auto":
                return
            state = self._hosts.get(host)
            if state is None or state.mode != "probe" or proxy is not None:
                return
            state.probe_in_flight = False
            self._switch_to_proxy(state)

    def release(self, proxy: str | None) -> None:
        """归还取用的代理（配合 acquire 的在飞计数）；直连/never 为空操作。"""
        if proxy is not None:
            self._pool.release(proxy)

    def hold(self, proxy: str | None) -> bool:
        """软失败后继续占用同一出口重试（在飞计数 +1）；不可用返回 False。

        供传输层"同一 IP 重试一次"使用：省一次 TCP/TLS 握手，也避免重试被
        最少在飞分发到另一个出口、把本轮软失败当成无发生。
        """
        return self._pool.hold(proxy)

    def _on_direct(self, state: HostState, success: bool, banned: bool) -> None:
        if success:
            state.direct_fails = 0
            return
        state.direct_fails += 1
        if banned or state.direct_fails >= self._settings.direct_fails:
            self._switch_to_proxy(state)

    def _on_proxy(
        self, state: HostState, proxy: str | None, success: bool, soft: bool = False
    ) -> None:
        if proxy is None:
            return  # 代理池不可用退化直连，不改变状态
        if success:
            self._pool.report_success(proxy)
            state.proxy_successes += 1
            if self._should_probe(state):
                state.mode = "probe"
        else:
            state.proxy_successes = 0
            self._report_pool_failure(proxy, soft)

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
            out: dict[str, Any] = dict(self._stats)
        out["hosts"] = hosts
        out["pool"] = self._pool.stats()
        return out

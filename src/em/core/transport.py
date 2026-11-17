"""传输层：封装 HTTP 请求，接入重试与动态代理路由，并把失败归类为 ``core.errors``。"""

import logging
import math
import threading
import time
from collections import deque
from collections.abc import Callable, Mapping
from http.client import RemoteDisconnected
from typing import Any
from urllib.parse import urlparse

import requests
from urllib3.exceptions import ReadTimeoutError

from em.core import budget, defaults
from em.core.errors import (
    ChannelError,
    EgressRetryStopped,
    EmptyResponseError,
    HttpStatusError,
    InvalidContentError,
    NetworkError,
    ProxyConnectError,
    ProxyUnavailableError,
    RemoteDisconnectError,
    UpstreamReadTimeout,
)
from em.core.fixed_proxy import FixedProxyRouter
from em.core.proxy import ProxyRouter, proxy_url
from em.core.resilience import RetryPolicy, should_retry, sleep_backoff
from em.core.session import ExplicitProxySession, network_failure_phase

log = logging.getLogger(__name__)


def _is_banned(exc: Exception) -> bool:
    """确定封禁信号* 403/429 视为出口 IP 被目标封禁。"""
    if isinstance(exc, HttpStatusError):
        return exc.status_code in (403, 429)
    return False


def _classify(exc: requests.RequestException) -> NetworkError:
    """把 requests 异常按"换 IP 是否有用"分档，供池子决定淘汰力度。

    受控连接先提供阶段证据；CONNECT/TLS 也可能被 requests 包成 ReadTimeout。
    仅响应头/体读取超时视为软失败，未知阶段不推断建链完成。
    """
    pending: list[BaseException] = [exc]
    visited: set[int] = set()
    chain: list[BaseException] = []
    while pending:
        cause = pending.pop()
        if id(cause) in visited:
            continue
        visited.add(id(cause))
        chain.append(cause)
        pending.extend(value for value in cause.args if isinstance(value, BaseException))
        if cause.__cause__ is not None:
            pending.append(cause.__cause__)
        if cause.__context__ is not None:
            pending.append(cause.__context__)
    phase = network_failure_phase(exc)
    classified: NetworkError
    if phase in {"tcp", "proxy_connect", "proxy_tls", "tls", "request_send"}:
        classified = ProxyConnectError(str(exc))
    elif any(isinstance(e, (requests.ReadTimeout, ReadTimeoutError)) for e in chain):
        classified = (
            UpstreamReadTimeout(str(exc))
            if phase in {"response_headers", "response_body"}
            else NetworkError(str(exc))
        )
    elif isinstance(exc, requests.ConnectionError):
        # 代理隧道和 TLS 失败也会包断连，不能拿它们判定目标疑似限流。
        if not any(
            isinstance(e, (requests.exceptions.ProxyError, requests.exceptions.SSLError))
            for e in chain
        ) and any(isinstance(e, (RemoteDisconnected, ConnectionResetError)) for e in chain):
            classified = RemoteDisconnectError(str(exc))
        else:
            classified = ProxyConnectError(str(exc))
    else:
        classified = NetworkError(str(exc))
    classified.network_phase = phase
    return classified


class HttpClient:
    """带换 IP 重试的 HTTP 客户端；耗尽重试则抛出最后一次异常。"""

    # 已验证出口集合的上限：它只用来省一次"首次使用"收紧的连接超时，
    # 超限直接清空等价于回到默认（新 IP 都按 1.5s 连接超时判死），无正确性影响
    _PROVEN_CAP = 1024

    def __init__(
        self,
        session: ExplicitProxySession,
        router: ProxyRouter | FixedProxyRouter,
        policy: RetryPolicy,
        timeout_sec: int = 15,
        connect_timeout_sec: int = 3,
        dynamic_timeout: bool = False,
        exhausted_hint: Callable[[str, ChannelError], str | None] | None = None,
        disconnect_may_be_limited: Callable[[str], bool] | None = None,
    ) -> None:
        self._session = session
        self._router = router
        self._policy = policy
        self._closed = False
        # 重试耗尽时向调用方要一条处置建议（如"出口疑似被封且没配代理源"）挂到异常上。
        # 入参是 (host, 最后一次异常)；文案由应用层给，传输层不认识具体的配置项
        self._exhausted_hint = exhausted_hint
        # 渠道注入域名判据；core 不硬编码站点。计数仅属于一次 get_text 调用。
        self._disconnect_may_be_limited = disconnect_may_be_limited
        # requests 的元组超时：(连接, 读取) 分别计时。
        # 坏代理多卡在连接阶段，短 connect 可快速判死，避免 connect+read 叠加到近两倍。
        self._timeout = (connect_timeout_sec, timeout_sec)
        self._dynamic_timeout = dynamic_timeout
        # 成功请求耗时滑动窗口，按直连/代理分桶：各自 P95 驱动动态读超时
        self._rtt: dict[str, deque[float]] = {
            "direct": deque(maxlen=defaults.DYNAMIC_TIMEOUT_WINDOW),
            "proxy": deque(maxlen=defaults.DYNAMIC_TIMEOUT_WINDOW),
        }
        # 本线程最近一次请求的 (host, proxy)：应用层发现旧快照时定点淘汰。
        # 必须线程本地：全量翻页多 worker 同打一个 host，host->单值 会被并发
        # 请求互相覆盖，导致 A 线程淘汰掉 B 线程正在用的好 IP
        self._local = threading.local()
        # 已通过业务请求验证存活的代理 IP：首次使用用收紧的连接超时快速判死
        self._proven_proxies: set[str] = set()
        # 直连/代理分桶耗时（含失败尝试）+ 代理获取等待耗时，供链路优化定位
        self._timing_lock = threading.Lock()
        self._timing = {
            "direct_requests": 0,
            "direct_sec": 0.0,
            "proxy_requests": 0,
            "proxy_sec": 0.0,
            "proxy_wait_sec": 0.0,  # acquire 阻塞时长（代理 API 回源等待）
            "backoff_sec": 0.0,  # 换 IP 重试的退避等待累计
            "failed_attempts": 0,
        }

    def get_text(
        self,
        url: str,
        params: Mapping[str, Any],
        headers: Mapping[str, str],
        validator: Callable[[str], bool] | None = None,
        read_timeout: float | None = None,
    ) -> str:
        """发起 GET 并返回文本。

        ``validator`` 在 HTTP 200 文本上做协议级校验（如是否合法 JSONP）；
        不通过视为出口代理劫持，按失败上报并换 IP 重试——避免 200 错误页被误记为成功。
        ``read_timeout`` 是端点级读预算下限（大响应体用），**允许超过静态上限**：
        它是"这个接口需要多久"的声明，与按历史耗时自适应的动态值不是一回事。
        代理请求仍受剩余租期和外层 deadline 限制，实际超时可能低于端点提示。
        """
        host = urlparse(url).hostname or ""
        if self._closed:
            raise RuntimeError("HTTP 客户端已关闭")
        last_exc: ChannelError | None = None
        proxy: str | None = None
        reuse = False  # 软失败（读超时）后沿用同一出口重试：省一次握手，也避免误判淘汰
        reuse_budget = 1  # 每个出口只复用一次，第二次软失败即换 IP
        same_egress_failures = 0
        for attempt in range(self._policy.max_retries + 1):
            budget.remaining()
            minimum = sum(
                budget.timeouts(self._timeout[0], self._read_timeout("proxy", read_timeout))
            )
            t0 = time.monotonic()
            try:
                if reuse and proxy is not None and self._router.hold(proxy, minimum):
                    reuse = False
                    wait = 0.0
                else:
                    proxy = self._router.acquire(host, minimum)
                    reuse = False
                    reuse_budget = 1
                    wait = time.monotonic() - t0
            except ProxyUnavailableError as exc:
                last_exc = exc
                with self._timing_lock:
                    self._timing["proxy_wait_sec"] += time.monotonic() - t0
                if attempt >= self._policy.max_retries:
                    break
                delay = sleep_backoff(self._policy, attempt, exc)
                with self._timing_lock:
                    self._timing["backoff_sec"] += delay
                continue
            self._local.last_route = (host, proxy)
            try:
                t1 = time.monotonic()
                text = self._attempt(
                    url,
                    params,
                    headers,
                    proxy,
                    validator,
                    self._read_timeout(proxy, read_timeout),
                    self._connect_timeout(proxy),
                )
                elapsed = time.monotonic() - t1
                budget.remaining()
                self._record_timing(proxy, wait, elapsed, failed=False)
                self._record_rtt(proxy, elapsed)
                if proxy is not None:
                    self._remember_proven(proxy)
                self._router.report_result(host, proxy, success=True)
                return text
            except ChannelError as exc:
                if isinstance(exc, ProxyUnavailableError):
                    with self._timing_lock:
                        self._timing["proxy_wait_sec"] += wait
                else:
                    self._record_timing(proxy, wait, time.monotonic() - t1, failed=True)
                soft = isinstance(exc, UpstreamReadTimeout)
                if isinstance(exc, ProxyUnavailableError) or (
                    isinstance(exc, HttpStatusError) and not _is_banned(exc)
                ):
                    self._router.abandon(host, proxy)
                else:
                    self._router.report_result(
                        host, proxy, success=False, banned=_is_banned(exc), soft=soft
                    )
                last_exc = exc
                fixed = isinstance(self._router, FixedProxyRouter) and proxy is not None
                suspect_direct = (
                    proxy is None
                    and isinstance(exc, RemoteDisconnectError)
                    and self._disconnect_may_be_limited is not None
                    and self._disconnect_may_be_limited(host)
                )
                fixed_failure = fixed and (
                    isinstance(exc, (NetworkError, EmptyResponseError)) or _is_banned(exc)
                )
                if not self._router.can_rotate and (suspect_direct or fixed_failure):
                    same_egress_failures += 1
                else:
                    same_egress_failures = 0
                if same_egress_failures >= 2:
                    reason = (
                        "固定代理连续两次连接/读取/限流失败"
                        if fixed
                        else "同一出口连续两次远端断连，疑似限流"
                    )
                    stopped = EgressRetryStopped(
                        f"对 {host} 的{reason}；当前无法切换出口，停止本次调用及分页重试"
                    )
                    if self._exhausted_hint is not None:
                        stopped.hint = self._exhausted_hint(host, stopped)
                    raise stopped from exc
                if not should_retry(exc):
                    raise
                if attempt >= self._policy.max_retries:
                    break
                if soft and proxy is not None and reuse_budget > 0:
                    reuse_budget -= 1
                    reuse = True
                # 没有代理源可换时只是原样重试，写"换 IP"会让没配代理的人以为代理在工作
                how = "同 IP " if reuse else ("换 IP " if self._router.can_rotate else "")
                log.warning(
                    "请求失败(%s, stage=%s): %s，%s重试 [%d/%d]",
                    type(exc).__name__,
                    getattr(exc, "network_phase", "unknown"),
                    str(exc)[:120],
                    how,
                    attempt + 1,
                    self._policy.max_retries,
                )
            except Exception:
                # 非渠道异常（如校验回调自身抛错）不重试、不淘汰 IP，
                # 但必须解除探测单飞，否则该 host 的 probe_in_flight 永久卡死
                self._router.abandon(host, proxy)
                raise
            finally:
                # 无论成败归还取用，驱动代理池"最少在飞优先"的分发计数
                self._router.release(proxy)
            delay = sleep_backoff(self._policy, attempt, last_exc)
            if delay > 0:
                with self._timing_lock:
                    self._timing["backoff_sec"] += delay
        if last_exc is None:
            raise RuntimeError("未执行请求（max_retries < 0）")
        if self._exhausted_hint is not None:
            last_exc.hint = self._exhausted_hint(host, last_exc)
        raise last_exc

    def _record_timing(self, proxy: str | None, wait: float, elapsed: float, failed: bool) -> None:
        """按直连/代理分桶累计单次尝试耗时（含失败尝试，IP 质量成本在此显形）。"""
        with self._timing_lock:
            if proxy is None:
                self._timing["direct_requests"] += 1
                self._timing["direct_sec"] += elapsed
            else:
                self._timing["proxy_requests"] += 1
                self._timing["proxy_sec"] += elapsed
                self._timing["proxy_wait_sec"] += wait
            if failed:
                self._timing["failed_attempts"] += 1

    def _record_rtt(self, proxy: str | None, elapsed: float) -> None:
        """成功请求耗时入滑动窗口（失败尝试不入窗，避免慢请求拉高 P95 的正反馈）。"""
        with self._timing_lock:
            self._rtt["proxy" if proxy else "direct"].append(elapsed)

    def _remember_proven(self, proxy: str) -> None:
        """记住已验证出口；超过上限即清空，回到"新 IP 收紧连接超时"的默认。"""
        self._proven_proxies.add(proxy)
        if len(self._proven_proxies) > self._PROVEN_CAP:
            self._proven_proxies.clear()

    def _read_timeout(self, proxy: str | None, hint: float | None = None) -> float:
        """动态读超时：本桶成功耗时 P95 × 余量，clamp 到 [下限, 静态配置]。

        ``hint`` 为端点级下限（如 K 线一次返回全量序列），结果取 ``max``——
        只会放宽、不会收紧，且允许超过静态上限。

        好窗口收紧后快速判死边缘慢 IP；差窗口 P95 抬高后自动放宽到静态上限，
        不误杀仍能响应的 IP。样本不足（冷启动）或功能关闭时退静态值。
        拷贝在 ``_timing_lock`` 内完成：``sorted()`` 会迭代 deque，与并发 append
        撞上会抛 ``RuntimeError: deque mutated during iteration``。
        """
        static = float(self._timeout[1])
        value = static
        if self._dynamic_timeout:
            with self._timing_lock:
                win = list(self._rtt["proxy" if proxy else "direct"])
            if len(win) >= defaults.DYNAMIC_TIMEOUT_MIN_SAMPLES:
                ordered = sorted(win)
                p95 = ordered[math.ceil(0.95 * len(ordered)) - 1]
                value = min(
                    max(p95 * defaults.DYNAMIC_TIMEOUT_FACTOR, defaults.DYNAMIC_TIMEOUT_FLOOR_SEC),
                    static,
                )
        return max(value, hint) if hint is not None else value

    def _connect_timeout(self, proxy: str | None) -> float:
        """代理 IP 首次业务使用时收紧连接超时：未经业务验证的 IP 多卡在连接阶段，
        短超时快速判死（好 IP connect <0.5s，余量 3 倍不误杀）；已验证或直连用静态值。"""
        if (
            proxy is None
            or isinstance(self._router, FixedProxyRouter)
            or proxy in self._proven_proxies
        ):
            return self._timeout[0]
        return defaults.FIRST_USE_CONNECT_TIMEOUT_SEC

    def timing_stats(self) -> dict[str, float]:
        """只读耗时统计快照：直连/代理分桶请求数与耗时、代理获取等待、失败尝试数。"""
        with self._timing_lock:
            return dict(self._timing)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._router.close()
        finally:
            self._session.close()

    def available_proxies(self, url: str) -> int:
        """该 URL 所属 host 的可用出口数（0=直连态或池空）：分页并发按它收敛。"""
        return self._router.available(urlparse(url).hostname or "")

    def proxy_stats(self) -> dict[str, Any]:
        """代理池健康指标透传（回源/预筛耗时等），供上层日志归因。"""
        out: dict[str, Any] = self._router.stats().get("pool") or {}
        return out

    def evict_last_proxy(self, url: str) -> None:
        """淘汰本线程最近一次请求使用的代理 IP（如应用层检测到旧快照），不动路由状态机。

        按线程而非 host 查找：多 worker 并发打同一 host 时，host->单值 的旧
        实现会被别的线程覆盖，误伤其正在用的 IP；host 不一致时不淘汰。
        """
        record: tuple[str, str | None] | None = getattr(self._local, "last_route", None)
        if record is None:
            return
        host, proxy = record
        if proxy is not None and host == (urlparse(url).hostname or ""):
            self._router.report_proxy_failure(proxy)

    def _attempt(
        self,
        url: str,
        params: Mapping[str, Any],
        headers: Mapping[str, str],
        proxy: str | None,
        validator: Callable[[str], bool] | None = None,
        read_timeout: float | None = None,
        connect_timeout: float | None = None,
    ) -> str:
        proxies = {"http": proxy_url(proxy), "https": proxy_url(proxy)} if proxy else None
        timeout = budget.timeouts(
            connect_timeout if connect_timeout is not None else self._timeout[0],
            read_timeout if read_timeout is not None else self._timeout[1],
        )
        if proxy is not None:
            remaining = self._router.remaining_lifetime(proxy)
            if remaining <= self._router.lifetime_requirement(sum(timeout)):
                raise ProxyUnavailableError("代理剩余有效期不足以发起本次请求")
            connect = min(timeout[0], remaining / 2)
            timeout = (connect, min(timeout[1], remaining - connect))
        timeout = budget.timeouts(*timeout)
        if proxy is not None:
            remaining = self._router.remaining_lifetime(proxy)
            if remaining <= 0:
                raise ProxyUnavailableError("代理租期已到期")
            connect = min(timeout[0], remaining / 2)
            timeout = (connect, min(timeout[1], remaining - connect))
        try:
            resp = self._session.get(
                url, params=params, headers=headers, proxies=proxies, timeout=timeout
            )
        except requests.RequestException as exc:
            classified = _classify(exc)
            if proxy is not None and isinstance(self._router, FixedProxyRouter):
                # requests 的异常可能含代理 URL/用户名密码；不把原始异常链带入日志或回溯。
                classified.args = (f"固定出口请求失败（{type(exc).__name__}）",)
                raise classified from None
            raise classified from exc
        if resp.status_code != 200:
            raise HttpStatusError(resp.status_code)
        if not resp.text:
            raise EmptyResponseError("空响应(Empty reply)")
        if validator is not None and not validator(resp.text):
            if proxy is not None and isinstance(self._router, FixedProxyRouter):
                raise InvalidContentError("固定出口响应体未通过协议校验")
            raise InvalidContentError(f"响应体未通过协议校验: {resp.text[:80]!r}")
        return resp.text

"""HttpClient 行为锁：重试次数、换 IP、off-by-one 日志边界。"""

import threading
from unittest.mock import MagicMock

import pytest
import requests

from em.core.errors import NetworkError
from em.core.proxy import ProxyPool, ProxyRouter, ProxySettings
from em.core.resilience import RetryPolicy
from em.core.transport import HttpClient


def _response_read_timeout(message):
    error = requests.ReadTimeout(message)
    error._em_network_phase = "response_headers"
    return error


def _router_returning(ips: list[str], mode: str = "always") -> ProxyRouter:
    session = MagicMock(spec=requests.Session)
    session.get.return_value = MagicMock(text="\n".join(ips))
    ps = ProxySettings(api="http://x", num=len(ips), ttl_sec=30, mode=mode)  # type: ignore[arg-type]
    pool = ProxyPool(ps, session)
    return ProxyRouter(pool, ps)


def _client_always_failing(max_retries: int) -> tuple[HttpClient, MagicMock]:
    router = _router_returning([f"1.1.1.{i}:8080" for i in range(1, 20)])
    session = MagicMock(spec=requests.Session)
    session.get.side_effect = requests.ConnectionError("boom")
    policy = RetryPolicy(max_retries=max_retries, backoff_sec=0.0)
    return HttpClient(session, router, policy, timeout_sec=5), session


def test_attempts_equal_max_retries_plus_one():
    client, session = _client_always_failing(max_retries=3)
    with pytest.raises(NetworkError):
        client.get_text("http://x", {}, {})
    # 初试 + 3 次重试 = 4 次
    assert session.get.call_count == 4


def test_no_retry_when_not_retryable():
    from em.core.errors import HttpStatusError

    router = _router_returning(["1.1.1.1:8080"])
    session = MagicMock(spec=requests.Session)
    session.get.return_value = MagicMock(status_code=404, text="")
    policy = RetryPolicy(max_retries=5, backoff_sec=0.0)
    client = HttpClient(session, router, policy, timeout_sec=5)
    with pytest.raises(HttpStatusError):
        client.get_text("http://x", {}, {})
    # 404 不可重试，立即上抛，只调一次
    assert session.get.call_count == 1


def test_last_attempt_does_not_log_beyond_max(caplog):
    client, _ = _client_always_failing(max_retries=2)
    caplog.set_level("WARNING", logger="em.core.transport")
    with pytest.raises(NetworkError):
        client.get_text("http://x", {}, {})
    msgs = [r.message for r in caplog.records if "换 IP 重试" in r.message]
    assert len(msgs) == 2
    assert "[1/2]" in msgs[0]
    assert "[2/2]" in msgs[1]
    assert all("[3/2]" not in m for m in msgs)


def test_invalid_content_reported_as_failure_and_retried():
    # HTTP 200 但协议校验不过（代理劫持页）：记失败、换 IP 重试，最终成功
    session_for_pool = MagicMock(spec=requests.Session)
    session_for_pool.get.return_value = MagicMock(text="1.1.1.1:8080\n2.2.2.2:8080\n3.3.3.3:8080")
    ps = ProxySettings(api="http://x", num=3, ttl_sec=30, mode="always")
    router = ProxyRouter(ProxyPool(ps, session_for_pool), ps)
    session = MagicMock(spec=requests.Session)
    session.get.side_effect = [
        MagicMock(status_code=200, text="<html>代理错误页</html>"),
        MagicMock(status_code=200, text='{"rc":0,"data":{}}'),
    ]
    client = HttpClient(session, router, RetryPolicy(max_retries=3, backoff_sec=0.0), timeout_sec=5)

    def validator(text: str) -> bool:
        return text.startswith("{")

    assert client.get_text("http://x", {}, {}, validator=validator) == '{"rc":0,"data":{}}'
    # 坏代理 IP 被真实 ProxyPool 记入黑名单并计数，第二次换新 IP
    assert "1.1.1.1:8080" in router._pool._failed_at
    assert router._pool.stats()["ip_failures"] == 1
    used = [c.kwargs["proxies"]["https"] for c in session.get.call_args_list]
    assert used == ["http://1.1.1.1:8080", "http://2.2.2.2:8080"]


def test_auto_mode_starts_direct():
    # auto 模式默认直连，acquire 返回 None → 不走代理
    router = _router_returning(["1.1.1.1:8080"], mode="auto")
    session = MagicMock(spec=requests.Session)
    session.get.return_value = MagicMock(status_code=200, text="ok")
    client = HttpClient(session, router, RetryPolicy(max_retries=0), timeout_sec=5)
    assert client.get_text("http://x", {}, {}) == "ok"
    # 直连：proxies=None
    _, kwargs = session.get.call_args
    assert kwargs["proxies"] is None


def test_timing_stats_buckets_direct_and_proxy():
    # 直连/代理分桶统计：请求数与耗时分别累计
    session_for_pool = MagicMock(spec=requests.Session)
    session_for_pool.get.return_value = MagicMock(text="1.1.1.1:8080")
    ps = ProxySettings(api="http://x", num=1, ttl_sec=30, mode="always")
    router = ProxyRouter(ProxyPool(ps, session_for_pool), ps)
    session = MagicMock(spec=requests.Session)
    session.get.return_value = MagicMock(status_code=200, text="ok")
    client = HttpClient(session, router, RetryPolicy(max_retries=0), timeout_sec=5)
    client.get_text("http://x", {}, {})
    stats = client.timing_stats()
    assert stats["proxy_requests"] == 1
    assert stats["direct_requests"] == 0
    assert stats["proxy_sec"] >= 0.0
    assert stats["failed_attempts"] == 0


def test_backoff_sec_accumulated_on_retry():
    # 换 IP 重试的退避等待累计进 timing（IP 质量成本的等待分量）
    router = _router_returning([f"1.1.1.{i}:8080" for i in range(1, 20)])
    session = MagicMock(spec=requests.Session)
    session.get.side_effect = requests.ConnectionError("boom")
    client = HttpClient(
        session, router, RetryPolicy(max_retries=2, backoff_sec=0.05, jitter_sec=0.0), timeout_sec=5
    )
    with pytest.raises(NetworkError):
        client.get_text("http://x", {}, {})
    # NetworkError 非限流类：每次固定 connect_backoff 0.1s，2 次重试共 0.2s
    assert client.timing_stats()["backoff_sec"] == pytest.approx(0.2)


def test_evict_last_proxy_removes_ip_without_touching_router_state():
    # 应用层发现坏 IP（如旧快照）时定点淘汰，路由状态机不动（不创建 host 态、不计失败）
    session_for_pool = MagicMock(spec=requests.Session)
    session_for_pool.get.return_value = MagicMock(text="1.1.1.1:8080")
    ps = ProxySettings(api="http://x", num=1, ttl_sec=30, mode="always")
    router = ProxyRouter(ProxyPool(ps, session_for_pool), ps)
    session = MagicMock(spec=requests.Session)
    session.get.return_value = MagicMock(status_code=200, text="ok")
    client = HttpClient(session, router, RetryPolicy(max_retries=0), timeout_sec=5)
    client.get_text("http://x", {}, {})
    client.evict_last_proxy("http://x")
    assert "1.1.1.1:8080" in router._pool._failed_at
    assert router._pool.stats()["ip_failures"] == 1
    assert router.host_state("x") is None  # 路由状态机未动


# --- 动态读超时（P95 滑动窗口）---


def _dynamic_client(timeout_sec: int = 2) -> HttpClient:
    router = _router_returning(["1.1.1.1:8080"], mode="always")
    return HttpClient(
        MagicMock(spec=requests.Session),
        router,
        RetryPolicy(max_retries=0),
        timeout_sec=timeout_sec,
        dynamic_timeout=True,
    )


def test_dynamic_timeout_disabled_or_cold_returns_static():
    client = _dynamic_client()
    assert client._read_timeout("1.1.1.1:8080") == 2.0  # 冷启动样本不足 → 静态
    off = HttpClient(
        MagicMock(spec=requests.Session),
        _router_returning(["1.1.1.1:8080"], mode="always"),
        RetryPolicy(max_retries=0),
        timeout_sec=2,
        dynamic_timeout=False,
    )
    for _ in range(10):
        off._record_rtt("1.1.1.1:8080", 0.2)
    assert off._read_timeout("1.1.1.1:8080") == 2.0  # 关闭 → 始终静态


def test_dynamic_timeout_tightens_on_fast_window():
    client = _dynamic_client()
    for _ in range(6):
        client._record_rtt("1.1.1.1:8080", 0.2)  # 好窗口 P95=0.2s
    # clamp(0.2×3, 1.5, 2) = 1.5s：下限覆盖整页均值，不再把正常页判成超时
    assert client._read_timeout("1.1.1.1:8080") == pytest.approx(1.5)


def test_dynamic_timeout_floors_and_caps():
    client = _dynamic_client(timeout_sec=2)
    for t in (0.1, 0.1, 0.1, 0.1, 0.1):
        client._record_rtt("1.1.1.1:8080", t)  # P95×3=0.3 < 下限
    assert client._read_timeout("1.1.1.1:8080") == pytest.approx(1.5)  # 触底防误杀
    for t in (1.9, 1.9, 1.9, 1.9, 1.9):
        client._record_rtt(None, t)  # 直连桶 P95×3=5.7 > 静态上限
    assert client._read_timeout(None) == 2.0  # 封顶到静态配置


def test_dynamic_timeout_buckets_are_independent():
    client = _dynamic_client()
    for _ in range(6):
        client._record_rtt("1.1.1.1:8080", 0.2)  # 代理桶热身
    # 直连桶仍冷：不受代理桶样本影响
    assert client._read_timeout(None) == 2.0
    assert client._read_timeout("1.1.1.1:8080") == pytest.approx(1.5)


def test_dynamic_timeout_passed_to_request():
    # 端到端：好窗口热身后，实际请求的读超时被收紧
    session_for_pool = MagicMock(spec=requests.Session)
    session_for_pool.get.return_value = MagicMock(text="1.1.1.1:8080")
    ps = ProxySettings(api="http://x", num=1, ttl_sec=30, mode="always")
    router = ProxyRouter(ProxyPool(ps, session_for_pool), ps)
    session = MagicMock(spec=requests.Session)
    session.get.return_value = MagicMock(status_code=200, text="ok")
    client = HttpClient(
        session, router, RetryPolicy(max_retries=0), timeout_sec=2, dynamic_timeout=True
    )
    client.get_text("http://x", {}, {})  # 首次：读超时冷启动静态 2s
    _, kwargs = session.get.call_args
    assert kwargs["timeout"] == (1.5, 2.0)  # 连接超时首次使用收紧到 1.5s
    for _ in range(6):
        client._record_rtt("1.1.1.1:8080", 0.2)
    client.get_text("http://x", {}, {})  # 同一 IP 已验证存活
    _, kwargs = session.get.call_args
    assert kwargs["timeout"] == pytest.approx((3, 1.5))  # 连接超时回静态 3s，读超时收到下限


def test_proven_proxies_set_is_bounded() -> None:
    # 长时间运行不该无限累积：超上限直接清空，等价回到"新 IP 收紧连接超时"的默认
    client, _ = _client_always_failing(max_retries=0)
    client._PROVEN_CAP = 2
    for ip in ("1.1.1.1:8080", "2.2.2.2:8080", "3.3.3.3:8080"):
        client._remember_proven(ip)
    assert client._proven_proxies == set()


def test_read_timeout_hint_raises_budget() -> None:
    # 端点级下限：只放宽不收紧，且允许超过静态上限（大响应体接口声明自己的预算）
    client = _dynamic_client(timeout_sec=2)
    assert client._read_timeout("1.1.1.1:8080") == 2.0
    assert client._read_timeout("1.1.1.1:8080", 8.0) == 8.0
    assert client._read_timeout("1.1.1.1:8080", 1.2) == 2.0


def test_read_timeout_hint_passed_to_request() -> None:
    session_for_pool = MagicMock(spec=requests.Session)
    session_for_pool.get.return_value = MagicMock(text="1.1.1.1:8080")
    ps = ProxySettings(api="http://x", num=1, ttl_sec=30, mode="always")
    router = ProxyRouter(ProxyPool(ps, session_for_pool), ps)
    session = MagicMock(spec=requests.Session)
    session.get.return_value = MagicMock(status_code=200, text="ok")
    client = HttpClient(session, router, RetryPolicy(max_retries=0), timeout_sec=2)

    client.get_text("http://x", {}, {}, read_timeout=8.0)
    _, kwargs = session.get.call_args
    assert kwargs["timeout"] == (1.5, 8.0)  # 首次使用连接 1.5s，读预算用端点声明


def test_first_use_connect_timeout_only_for_unproven_proxy():
    # 首次使用的代理 IP 收紧连接超时快速判死；已验证 IP 与直连用静态值
    client = _dynamic_client()
    assert client._connect_timeout("9.9.9.9:8080") == 1.5  # 未验证
    client._proven_proxies.add("9.9.9.9:8080")
    assert client._connect_timeout("9.9.9.9:8080") == 3  # 已验证 → 静态
    assert client._connect_timeout(None) == 3  # 直连不受影响


# --- 非渠道异常的探测单飞兜底 / evict 线程隔离 ---


def test_non_channel_error_releases_probe_single_flight():
    # 探测请求路径上 validator 自身抛 ValueError（非 ChannelError）：
    # 异常原样上抛，同时 probe 单飞必须被解除（保守退回代理态）
    router = _router_returning(["1.1.1.1:8080"], mode="auto")
    router.report_result("x", None, success=False, banned=True)
    router.host_state("x").mode = "probe"
    session = MagicMock(spec=requests.Session)
    session.get.return_value = MagicMock(status_code=200, text="ok")
    client = HttpClient(session, router, RetryPolicy(max_retries=0), timeout_sec=5)

    def boom(_text: str) -> bool:
        raise ValueError("校验回调自身 bug")

    with pytest.raises(ValueError, match="校验回调自身 bug"):
        client.get_text("http://x", {}, {}, validator=boom)
    state = router.host_state("x")
    assert state.probe_in_flight is False
    assert state.mode == "proxy"


def test_evict_last_proxy_uses_thread_local_route():
    # 两个 worker 先后打同一 host：A 淘汰自己的旧快照 IP 时，
    # 不得误淘汰 B 刚记录的在途 IP（旧 host->单值 实现会互踩）
    class _ThreadRouter:
        def __init__(self) -> None:
            self.evicted: list[str] = []

        def acquire(self, host: str, min_lifetime: float = 0.0) -> str | None:
            return {
                "worker-A": "1.1.1.1:8080",
                "worker-B": "2.2.2.2:8080",
            }[threading.current_thread().name]

        def report_result(self, *args: object, **kwargs: object) -> None:
            pass

        def remaining_lifetime(self, proxy: str) -> float:
            return 27.0

        def lifetime_requirement(self, requested: float) -> float:
            return min(requested, 13.5)

        def report_proxy_failure(self, proxy: str | None) -> None:
            if proxy is not None:
                self.evicted.append(proxy)

        def release(self, proxy: str | None) -> None:
            pass

    fake = _ThreadRouter()
    session = MagicMock(spec=requests.Session)
    session.get.return_value = MagicMock(status_code=200, text="ok")
    client = HttpClient(session, fake, RetryPolicy(max_retries=0), timeout_sec=5)  # type: ignore[arg-type]

    def worker_b() -> None:
        client.get_text("http://x", {}, {})  # 旧实现在此覆盖 host->单值

    # 关键时序：A 先取数，B 恰好在 A「取数之后、淘汰之前」完成——
    # 模拟全量翻页时另一页 worker 在该窗口内覆盖共享记录
    this = threading.current_thread()
    orig_name = this.name
    this.name = "worker-A"
    try:
        client.get_text("http://x", {}, {})
        t = threading.Thread(target=worker_b, name="worker-B")
        t.start()
        t.join()
        client.evict_last_proxy("http://x")
    finally:
        this.name = orig_name
    assert fake.evicted == ["1.1.1.1:8080"]


# --- 失败分级：读超时软失败（同 IP 重试一次），连接失败硬淘汰 ---


def _always_client(session: MagicMock, num: int = 2, max_retries: int = 3):
    pool_session = MagicMock(spec=requests.Session)
    pool_session.get.return_value = MagicMock(
        text="\n".join(f"1.1.1.{i}:8080" for i in range(1, num + 1))
    )
    ps = ProxySettings(api="http://x", num=num, ttl_sec=30, mode="always")
    router = ProxyRouter(ProxyPool(ps, pool_session), ps)
    client = HttpClient(
        session,
        router,
        RetryPolicy(max_retries=max_retries, backoff_sec=0.0, connect_backoff_sec=0.0),
        timeout_sec=5,
    )
    return client, router


def test_read_timeout_retries_same_proxy_once() -> None:
    # 读超时多为慢页/抖动：同一出口重试一次（省一次握手），IP 不淘汰
    session = MagicMock(spec=requests.Session)
    session.get.side_effect = [
        _response_read_timeout("slow"),
        MagicMock(status_code=200, text="ok"),
    ]
    client, router = _always_client(session)
    assert client.get_text("http://h/x", {}, {}) == "ok"
    used = [c.kwargs["proxies"]["https"] for c in session.get.call_args_list]
    assert used == ["http://1.1.1.1:8080", "http://1.1.1.1:8080"]
    assert router._pool.stats()["soft_failures"] == 1
    assert router._pool.stats()["ip_failures"] == 0


def test_two_read_timeouts_switch_proxy() -> None:
    # 同一出口连续两次读超时才淘汰换 IP：软失败有额度，不是无限复用
    session = MagicMock(spec=requests.Session)
    session.get.side_effect = [
        _response_read_timeout("slow"),
        _response_read_timeout("slow"),
        MagicMock(status_code=200, text="ok"),
    ]
    client, router = _always_client(session)
    assert client.get_text("http://h/x", {}, {}) == "ok"
    used = [c.kwargs["proxies"]["https"] for c in session.get.call_args_list]
    assert used == ["http://1.1.1.1:8080", "http://1.1.1.1:8080", "http://1.1.1.2:8080"]
    assert router._pool.stats()["soft_failures"] == 2
    assert router._pool.stats()["ip_failures"] == 1


def test_connect_error_evicts_proxy_immediately() -> None:
    # 连接失败说明出口不可用：不重试同 IP，直接换新的
    session = MagicMock(spec=requests.Session)
    session.get.side_effect = [
        requests.ConnectionError("boom"),
        MagicMock(status_code=200, text="ok"),
    ]
    client, router = _always_client(session)
    assert client.get_text("http://h/x", {}, {}) == "ok"
    used = [c.kwargs["proxies"]["https"] for c in session.get.call_args_list]
    assert used == ["http://1.1.1.1:8080", "http://1.1.1.2:8080"]
    assert router._pool.stats()["ip_failures"] == 1
    assert router._pool.stats()["soft_failures"] == 0


def test_request_exception_classification_order() -> None:
    # ConnectTimeout 同时是 ConnectionError：必须先判 connect 档，否则会被错归为软失败
    from em.core.errors import ProxyConnectError, UpstreamReadTimeout
    from em.core.transport import _classify

    assert isinstance(_classify(requests.ConnectTimeout("t")), ProxyConnectError)
    assert isinstance(_classify(_response_read_timeout("t")), UpstreamReadTimeout)
    assert type(_classify(requests.ReadTimeout("unobserved"))) is NetworkError
    assert isinstance(_classify(requests.ConnectionError("c")), ProxyConnectError)
    assert isinstance(_classify(requests.RequestException("x")), NetworkError)

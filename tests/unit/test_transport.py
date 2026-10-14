"""HttpClient 行为锁：重试次数、换 IP、off-by-one 日志边界。"""

from unittest.mock import MagicMock

import pytest
import requests

from em.core.errors import NetworkError
from em.core.proxy import ProxyPool, ProxyRouter, ProxySettings
from em.core.resilience import RetryPolicy
from em.core.transport import HttpClient


def _router_returning(ips: list[str], mode: str = "always") -> ProxyRouter:
    session = MagicMock(spec=requests.Session)
    session.get.return_value = MagicMock(text="\n".join(ips))
    ps = ProxySettings(api="http://x", num=1, ttl_sec=30, mode=mode)  # type: ignore[arg-type]
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
    session_for_pool.get.return_value = MagicMock(
        text="1.1.1.1:8080\n2.2.2.2:8080\n3.3.3.3:8080"
    )
    ps = ProxySettings(api="http://x", num=3, ttl_sec=30, mode="always")
    router = ProxyRouter(ProxyPool(ps, session_for_pool), ps)
    session = MagicMock(spec=requests.Session)
    session.get.side_effect = [
        MagicMock(status_code=200, text="<html>代理错误页</html>"),
        MagicMock(status_code=200, text='{"rc":0,"data":{}}'),
    ]
    client = HttpClient(
        session, router, RetryPolicy(max_retries=3, backoff_sec=0.0), timeout_sec=5
    )
    validator = lambda text: text.startswith("{")
    assert client.get_text("http://x", {}, {}, validator=validator) == '{"rc":0,"data":{}}'
    # 坏代理 IP 被真实 ProxyPool 记入黑名单并计数，第二次换新 IP
    assert "1.1.1.1:8080" in router._pool._failed_at  # noqa: SLF001
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
    assert "1.1.1.1:8080" in router._pool._failed_at  # noqa: SLF001
    assert router._pool.stats()["ip_failures"] == 1  # noqa: SLF001
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
    # clamp(0.2×3, 0.5, 2) = 0.6s：快速判死边缘慢 IP
    assert client._read_timeout("1.1.1.1:8080") == pytest.approx(0.6)


def test_dynamic_timeout_floors_and_caps():
    client = _dynamic_client(timeout_sec=2)
    for t in (0.1, 0.1, 0.1, 0.1, 0.1):
        client._record_rtt("1.1.1.1:8080", t)  # P95×3=0.3 < 下限
    assert client._read_timeout("1.1.1.1:8080") == pytest.approx(0.5)  # 触底防误杀
    for t in (1.9, 1.9, 1.9, 1.9, 1.9):
        client._record_rtt(None, t)  # 直连桶 P95×3=5.7 > 静态上限
    assert client._read_timeout(None) == 2.0  # 封顶到静态配置


def test_dynamic_timeout_buckets_are_independent():
    client = _dynamic_client()
    for _ in range(6):
        client._record_rtt("1.1.1.1:8080", 0.2)  # 代理桶热身
    # 直连桶仍冷：不受代理桶样本影响
    assert client._read_timeout(None) == 2.0
    assert client._read_timeout("1.1.1.1:8080") == pytest.approx(0.6)


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
    client.get_text("http://x", {}, {})  # 首次：冷启动静态 2s
    _, kwargs = session.get.call_args
    assert kwargs["timeout"] == (3, 2.0)
    for _ in range(6):
        client._record_rtt("1.1.1.1:8080", 0.2)
    client.get_text("http://x", {}, {})
    _, kwargs = session.get.call_args
    assert kwargs["timeout"] == pytest.approx((3, 0.6))  # 第二次：动态收紧

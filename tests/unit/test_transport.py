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

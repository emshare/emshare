"""全量拉取页级兜底的行为锁：传输全失败时兜底重试之间有短退避，末次失败不再退避。"""

from unittest.mock import MagicMock

import pytest
import requests

from em.application.market_data import _PAGE_RETRY_BACKOFF_SEC, stock_list_all_em
from em.core.errors import NetworkError
from em.core.proxy import ProxyPool, ProxyRouter, ProxySettings
from em.core.resilience import RetryPolicy
from em.core.transport import HttpClient


def test_page_retry_backoff_between_attempts(monkeypatch):
    # 首页 3 次兜底尝试全失败：退避 2 次（末次失败直接返回，不多等 0.5s），最终抛最后异常
    session = MagicMock(spec=requests.Session)
    session.get.side_effect = requests.ConnectionError("boom")
    ps = ProxySettings(api="http://x", num=1, ttl_sec=30, mode="always")
    router = ProxyRouter(ProxyPool(ps, session), ps)
    client = HttpClient(
        session, router, RetryPolicy(max_retries=0, backoff_sec=0.0), timeout_sec=2
    )
    monkeypatch.setattr("em.application.market_data._build_client", lambda s: client)
    slept: list[float] = []
    monkeypatch.setattr("em.application.market_data.time.sleep", slept.append)

    with pytest.raises(NetworkError):
        stock_list_all_em(max_rounds=1)

    assert slept == [_PAGE_RETRY_BACKOFF_SEC] * 2

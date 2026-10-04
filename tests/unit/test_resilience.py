"""RetryPolicy 退避行为锁：指数退避 + cap 封顶，避免换 IP 重试越等越久。"""

import pytest

from em.core.errors import EmptyResponseError, HttpStatusError, NetworkError
from em.core.resilience import RetryPolicy, should_retry, sleep_backoff


def test_backoff_grows_exponentially_without_cap() -> None:
    p = RetryPolicy(backoff_sec=0.2, backoff_cap_sec=None)
    assert p.backoff_for(0) == pytest.approx(0.2)
    assert p.backoff_for(3) == pytest.approx(1.6)
    assert p.backoff_for(9) == pytest.approx(102.4)


def test_backoff_capped() -> None:
    p = RetryPolicy(backoff_sec=0.2, backoff_cap_sec=2.0)
    assert p.backoff_for(0) == pytest.approx(0.2)
    assert p.backoff_for(3) == pytest.approx(1.6)
    # 第 4 次 3.2 被 cap 到 2.0，之后不再增长
    assert p.backoff_for(4) == pytest.approx(2.0)
    assert p.backoff_for(9) == pytest.approx(2.0)


def test_backoff_cap_equals_base() -> None:
    p = RetryPolicy(backoff_sec=0.5, backoff_cap_sec=0.5)
    for attempt in range(10):
        assert p.backoff_for(attempt) == pytest.approx(0.5)


def test_should_retry_only_retryable_channel_errors() -> None:
    assert should_retry(NetworkError("x")) is True
    assert should_retry(EmptyResponseError("x")) is True
    assert should_retry(HttpStatusError(503)) is True
    assert should_retry(HttpStatusError(404)) is False
    assert should_retry(ValueError("x")) is False


def test_sleep_backoff_actually_sleeps(monkeypatch: pytest.MonkeyPatch) -> None:
    slept: list[float] = []
    monkeypatch.setattr("em.core.resilience.time.sleep", slept.append)
    sleep_backoff(RetryPolicy(backoff_sec=0.2, backoff_cap_sec=2.0), 9)
    assert slept == [2.0]

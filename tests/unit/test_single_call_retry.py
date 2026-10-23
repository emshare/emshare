"""单发接口的外层补试：传输层耗尽 5 个出口后，整轮再换一批试一次。

stock_list_all 有页级重试兜底，单发接口此前没有——soak 实测 7 个接口里 2 个各失败
1 次（全部 ProxyConnectError：连续 5 个出口都连不上目标 host）。
"""

import pytest

import em.application.market_data as md
from em.core.errors import HttpStatusError, NetworkError
from em.domain.models import Quote, QuotePage


class _FailThenOk:
    """前 ``failures`` 次抛 NetworkError，之后返回一页数据。"""

    def __init__(self, client, failures: int) -> None:
        self.calls = 0
        self._failures = failures

    def fetch_page(self, request, flow_field: str = "f62") -> QuotePage:
        self.calls += 1
        if self.calls <= self._failures:
            raise NetworkError("boom")
        return QuotePage(total=1, items=(Quote(code="000001", name="x"),))


class _AlwaysFail:
    """任何 fetch_* 调用都抛异常，用于确认补试覆盖到所有单发接口。"""

    def __init__(self, client) -> None:
        self.calls = 0

    def __getattr__(self, name: str):
        def _call(*args: object, **kwargs: object) -> None:
            self.calls += 1
            raise NetworkError("boom")

        return _call


def _patch(monkeypatch, source_factory):
    made: list = []

    def _factory(client):
        source = source_factory(client)
        made.append(source)
        return source

    monkeypatch.setattr(md, "_build_client", lambda s: object())
    monkeypatch.setattr(md.registry, "EastMoneySource", _factory)
    return made


def test_single_call_retries_once_on_network_error(monkeypatch) -> None:
    slept: list[float] = []
    monkeypatch.setattr(md.time, "sleep", slept.append)
    made = _patch(monkeypatch, lambda client: _FailThenOk(client, failures=1))

    page = md.stock_list_em()

    assert len(page.items) == 1
    assert made[0].calls == 2
    assert slept == [md._SINGLE_RETRY_BACKOFF_SEC]  # 补试前等一个换血窗口


def test_single_call_gives_up_after_one_retry(monkeypatch) -> None:
    monkeypatch.setattr(md.time, "sleep", lambda _s: None)
    made = _patch(monkeypatch, lambda client: _FailThenOk(client, failures=2))

    with pytest.raises(NetworkError):
        md.stock_list_em()

    assert made[0].calls == 2  # 外层只补一次，不无限重试


def test_single_call_does_not_retry_non_retryable(monkeypatch) -> None:
    calls: list[int] = []

    class _NotFound:
        def __init__(self, client) -> None:
            pass

        def fetch_page(self, request, flow_field: str = "f62") -> None:
            calls.append(1)
            raise HttpStatusError(404)

    monkeypatch.setattr(md.time, "sleep", lambda _s: None)
    _patch(monkeypatch, _NotFound)

    with pytest.raises(HttpStatusError):
        md.stock_list_em()

    assert len(calls) == 1


_SINGLE_CALL_APIS = [
    md.stock_list_em,
    md.board_constituent_em,
    md.board_industry_list_em,
    md.stock_kline_em,
    md.stock_trends_em,
    md.stock_fund_flow_em,
    md.board_fund_flow_em,
]


@pytest.mark.parametrize("func", _SINGLE_CALL_APIS, ids=[f.__name__ for f in _SINGLE_CALL_APIS])
def test_every_single_call_api_is_wrapped(monkeypatch, func) -> None:
    # 少包一个接口就等于少一层兜底：用参数化锁住"7 个单发接口全部有补试"
    monkeypatch.setattr(md.time, "sleep", lambda _s: None)
    made = _patch(monkeypatch, _AlwaysFail)

    with pytest.raises(NetworkError):
        func()

    assert made[0].calls == 2

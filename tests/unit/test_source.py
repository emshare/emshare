"""EastMoneySource 5 个 fetch 的错误路径覆盖。

两条路径 × 5 方法 = 10 用例：
  - 非 JSONP 响应（代理错误页等）→ EmptyResponseError
  - rc != 0（上游报错）→ ChannelError
"""

import pytest

from em.application import registry
from em.channels.eastmoney.source import EastMoneySource
from em.core.errors import ChannelError, EmptyResponseError
from em.domain.queries import (
    BoardFundFlowQuery,
    BoardListQuery,
    FundFlowQuery,
    KlineQuery,
    MarketQuery,
    TrendQuery,
)


class FakeClient:
    """返回预设文本的 HttpClient 桩。"""

    def __init__(self, text: str) -> None:
        self._text = text

    def get_text(self, url: str, params: object, headers: object) -> str:
        return self._text


_FETCH_NAMES = [
    "fetch_page",
    "fetch_kline",
    "fetch_trends",
    "fetch_fund_flow",
    "fetch_board_fund_flow",
    "fetch_board_list",
]
_REQUESTS = [
    registry.stock_list_request(MarketQuery()),
    registry.kline_request(KlineQuery()),
    registry.trends_request(TrendQuery()),
    registry.fund_flow_request(FundFlowQuery()),
    registry.board_fund_flow_request(BoardFundFlowQuery()),
    registry.board_industry_list_request(BoardListQuery()),
]


@pytest.mark.parametrize(
    "name,req", list(zip(_FETCH_NAMES, _REQUESTS, strict=True)), ids=_FETCH_NAMES
)
def test_non_jsonp_raises_empty(name: str, req: object) -> None:
    """非 JSONP 响应（代理错误页等）→ EmptyResponseError。"""
    source = EastMoneySource(FakeClient("<html>502 Bad Gateway</html>"))
    with pytest.raises(EmptyResponseError):
        getattr(source, name)(req)


@pytest.mark.parametrize(
    "name,req", list(zip(_FETCH_NAMES, _REQUESTS, strict=True)), ids=_FETCH_NAMES
)
def test_invalid_rc_raises_channel(name: str, req: object) -> None:
    """rc != 0（上游报错）→ ChannelError。"""
    source = EastMoneySource(FakeClient('{"rc": 1, "data": null}'))
    with pytest.raises(ChannelError):
        getattr(source, name)(req)

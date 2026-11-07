"""EastMoneySource 8 个 fetch 的协议校验路径覆盖。

非 JSONP 错误页与 rc != 0 现在由传输层在返回文本前用 validator 拦截并换 IP
（InvalidContentError）；本文件用执行真实 validator 的 HttpClient 桩锁住该契约。
"""

import pytest

from em.application import registry
from em.channels.eastmoney import config
from em.channels.eastmoney.source import EastMoneySource, _is_valid_payload
from em.core.errors import InvalidContentError
from em.domain.queries import (
    BoardFundFlowQuery,
    BoardListQuery,
    FundFlowQuery,
    HkStockListQuery,
    IndexListQuery,
    KlineQuery,
    MarketQuery,
    TrendQuery,
)


class FakeClient:
    """返回预设文本的 HttpClient 桩：与真实传输层一致地执行协议校验。"""

    def __init__(self, text: str, timeouts: list[float | None] | None = None) -> None:
        self._text = text
        self.timeouts = timeouts if timeouts is not None else []

    def get_text(
        self,
        url: str,
        params: object,
        headers: object,
        validator: object = None,
        read_timeout: float | None = None,
    ) -> str:
        self.timeouts.append(read_timeout)
        if validator is not None and not validator(self._text):
            raise InvalidContentError(f"桩：未通过校验: {self._text[:40]!r}")
        return self._text


_FETCH_NAMES = [
    "fetch_page",
    "fetch_kline",
    "fetch_trends",
    "fetch_fund_flow",
    "fetch_board_fund_flow",
    "fetch_board_list",
    "fetch_index_list",
    "fetch_hk_stock_list",
]
_REQUESTS = [
    registry.stock_list_request(MarketQuery()),
    registry.kline_request(KlineQuery()),
    registry.trends_request(TrendQuery()),
    registry.fund_flow_request(FundFlowQuery()),
    registry.board_fund_flow_request(BoardFundFlowQuery()),
    registry.board_industry_list_request(BoardListQuery()),
    registry.index_list_request(IndexListQuery()),
    registry.hk_stock_list_request(HkStockListQuery()),
]


@pytest.mark.parametrize(
    "name,req", list(zip(_FETCH_NAMES, _REQUESTS, strict=True)), ids=_FETCH_NAMES
)
def test_non_jsonp_raises_invalid(name: str, req: object) -> None:
    """非 JSONP 响应（代理错误页等）→ InvalidContentError。"""
    source = EastMoneySource(FakeClient("<html>502 Bad Gateway</html>"))
    with pytest.raises(InvalidContentError):
        getattr(source, name)(req)


@pytest.mark.parametrize(
    "name,req", list(zip(_FETCH_NAMES, _REQUESTS, strict=True)), ids=_FETCH_NAMES
)
def test_invalid_rc_raises_invalid(name: str, req: object) -> None:
    """rc != 0（上游报错）→ InvalidContentError。"""
    source = EastMoneySource(FakeClient('{"rc": 1, "data": null}'))
    with pytest.raises(InvalidContentError):
        getattr(source, name)(req)


def test_valid_payload_predicate() -> None:
    assert _is_valid_payload('{"rc":0,"data":{}}') is True
    assert _is_valid_payload('{"rc":1,"data":null}') is False
    assert _is_valid_payload("<html>bad gateway</html>") is False


def test_kline_declares_larger_read_budget() -> None:
    # K 线一次返回全量序列（实测 8502 行）：必须声明更大的读预算；
    # 其余接口不传（None），沿用按历史耗时自适应的动态值
    timeouts: list[float | None] = []
    EastMoneySource(FakeClient('{"rc":0,"data":{"klines":[]}}', timeouts)).fetch_kline(
        registry.kline_request(KlineQuery())
    )
    assert timeouts == [config.KLINE_READ_TIMEOUT_SEC]

    EastMoneySource(FakeClient('{"rc":0,"data":{"diff":[]}}', timeouts)).fetch_page(
        registry.stock_list_request(MarketQuery())
    )
    assert timeouts[-1] is None

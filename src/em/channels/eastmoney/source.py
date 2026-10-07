"""东财列表取数来源：请求 -> 传输 -> 映射，返回领域模型。"""

from em.channels.eastmoney import config
from em.channels.eastmoney.mapping import (
    is_ok,
    parse_jsonp,
    to_board_fund_flow_series,
    to_board_list_page,
    to_fund_flow_series,
    to_kline_series,
    to_quote_page,
    to_trend_series,
)
from em.channels.eastmoney.request import (
    ClistRequest,
    FundFlowRequest,
    KlineRequest,
    TrendsRequest,
)
from em.core.errors import ChannelError, EmptyResponseError
from em.core.transport import HttpClient
from em.domain.models import (
    BoardFundFlowSeries,
    BoardListPage,
    FundFlowSeries,
    KlineSeries,
    QuotePage,
    TrendSeries,
)


class EastMoneySource:
    """单个 clist 请求的取数来源（分页由上层驱动）。"""

    name = "eastmoney"

    def __init__(self, client: HttpClient) -> None:
        self._client = client

    def fetch_page(self, request: ClistRequest, flow_field: str = "f62") -> QuotePage:
        text = self._client.get_text(request.url(), request.params(), config.HEADERS)
        data = parse_jsonp(text)
        if data is None:
            # 非 JSONP（多为代理返回错误页）：视为可换 IP 重试的传输异常
            raise EmptyResponseError(f"非 JSONP 响应: {text[:80]!r}")
        if not is_ok(data):
            raise ChannelError(f"响应无效: rc={data.get('rc')}")
        return to_quote_page(data, flow_field)

    def fetch_kline(self, request: KlineRequest) -> KlineSeries:
        text = self._client.get_text(request.url(), request.params(), config.HEADERS)
        data = parse_jsonp(text)
        if data is None:
            # 非 JSONP（多为代理返回错误页）：视为可换 IP 重试的传输异常
            raise EmptyResponseError(f"非 JSONP 响应: {text[:80]!r}")
        if not is_ok(data):
            raise ChannelError(f"响应无效: rc={data.get('rc')}")
        return to_kline_series(data, request.period, request.adjust)

    def fetch_trends(self, request: TrendsRequest) -> TrendSeries:
        text = self._client.get_text(request.url(), request.params(), config.HEADERS)
        data = parse_jsonp(text)
        if data is None:
            # 非 JSONP（多为代理返回错误页）：视为可换 IP 重试的传输异常
            raise EmptyResponseError(f"非 JSONP 响应: {text[:80]!r}")
        if not is_ok(data):
            raise ChannelError(f"响应无效: rc={data.get('rc')}")
        return to_trend_series(data, request.ndays)

    def fetch_fund_flow(self, request: FundFlowRequest) -> FundFlowSeries:
        text = self._client.get_text(request.url(), request.params(), config.HEADERS)
        data = parse_jsonp(text)
        if data is None:
            # 非 JSONP（多为代理返回错误页）：视为可换 IP 重试的传输异常
            raise EmptyResponseError(f"非 JSONP 响应: {text[:80]!r}")
        if not is_ok(data):
            raise ChannelError(f"响应无效: rc={data.get('rc')}")
        return to_fund_flow_series(data, request.market)

    def fetch_board_fund_flow(self, request: FundFlowRequest) -> BoardFundFlowSeries:
        text = self._client.get_text(request.url(), request.params(), config.HEADERS)
        data = parse_jsonp(text)
        if data is None:
            # 非 JSONP（多为代理返回错误页）：视为可换 IP 重试的传输异常
            raise EmptyResponseError(f"非 JSONP 响应: {text[:80]!r}")
        if not is_ok(data):
            raise ChannelError(f"响应无效: rc={data.get('rc')}")
        return to_board_fund_flow_series(data)

    def fetch_board_list(self, request: ClistRequest) -> BoardListPage:
        text = self._client.get_text(request.url(), request.params(), config.HEADERS)
        data = parse_jsonp(text)
        if data is None:
            # 非 JSONP（多为代理返回错误页）：视为可换 IP 重试的传输异常
            raise EmptyResponseError(f"非 JSONP 响应: {text[:80]!r}")
        if not is_ok(data):
            raise ChannelError(f"响应无效: rc={data.get('rc')}")
        return to_board_list_page(data)

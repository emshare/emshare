"""东财列表取数来源：请求 -> 传输 -> 映射，返回领域模型。"""

from collections.abc import Callable
from typing import Any

from em.channels.eastmoney import config
from em.channels.eastmoney.mapping import (
    is_ok,
    is_security_not_found,
    parse_jsonp,
    to_board_changes_page,
    to_board_fund_flow_series,
    to_board_list_page,
    to_fund_flow_series,
    to_fund_list_page,
    to_hk_stock_list_page,
    to_index_list_page,
    to_kline_series,
    to_limit_pool_page,
    to_quote_page,
    to_stock_bid_ask,
    to_stock_changes_page,
    to_stock_info,
    to_trend_series,
)
from em.channels.eastmoney.request import (
    BoardChangesRequest,
    ClistRequest,
    FundFlowRequest,
    KlineRequest,
    LimitPoolRequest,
    StockChangesRequest,
    StockGetRequest,
    TrendsRequest,
)
from em.core.errors import SecurityNotFoundError
from em.core.transport import HttpClient
from em.domain.models import (
    BoardChangesPage,
    BoardFundFlowSeries,
    BoardListPage,
    FundFlowSeries,
    FundListPage,
    HkStockListPage,
    IndexListPage,
    KlineSeries,
    LimitPoolPage,
    QuotePage,
    StockBidAsk,
    StockChangesPage,
    StockInfo,
    TrendSeries,
)


def _is_valid_payload(text: str) -> bool:
    """传输层协议校验：东财所有接口成功时均为 JSON/JSONP 且 rc==0。

    放在传输层而非映射层：HTTP 200 的代理劫持页在此即判失败，
    让路由把坏代理 IP 拉黑并换 IP，而不是误记一次成功。
    """
    return is_ok(parse_jsonp(text))


def _is_valid_stock_get(text: str) -> bool:
    """stock/get 的协议校验：rc==0，或上游明确回复“查无此券”（rc 100 / 102 且 data 为 null）。

    后者是正常协议而非劫持页：若按 rc!=0 判失败，会把好 IP 拉黑并换 IP 重试到耗尽。
    """
    data = parse_jsonp(text)
    return is_ok(data) or is_security_not_found(data)


def _fetch_json(
    client: HttpClient,
    request: Any,
    read_timeout: float | None = None,
    validator: Callable[[str], bool] = _is_valid_payload,
) -> dict[str, Any]:
    """取文本 → 解析为 JSON 字典（协议校验已在传输层完成，此处只做解析）。

    ``read_timeout`` 端点级读预算下限，供大响应体接口（如 K 线全量序列）声明。
    """
    text = client.get_text(
        request.url(),
        request.params(),
        config.HEADERS,
        validator,
        read_timeout=read_timeout,
    )
    return parse_jsonp(text)  # type: ignore[return-value]


def _fetch_stock_get(client: HttpClient, request: StockGetRequest) -> dict[str, Any]:
    data = _fetch_json(client, request, validator=_is_valid_stock_get)
    if is_security_not_found(data):
        raise SecurityNotFoundError(
            f"证券不存在：secid={request.secid}（上游 rc={data.get('rc')}）"
        )
    return data


class EastMoneySource:
    """单个 clist 请求的取数来源（分页由上层驱动）。"""

    name = "eastmoney"

    def __init__(self, client: HttpClient) -> None:
        self._client = client

    def fetch_page(self, request: ClistRequest, flow_field: str = "f62") -> QuotePage:
        data = _fetch_json(self._client, request)
        return to_quote_page(data, flow_field)

    def fetch_kline(self, request: KlineRequest) -> KlineSeries:
        # 全量序列（单请求无分页）：用更大的读预算，避免首轮就被判超时
        data = _fetch_json(self._client, request, config.KLINE_READ_TIMEOUT_SEC)
        return to_kline_series(data, request.period, request.adjust)

    def fetch_trends(self, request: TrendsRequest) -> TrendSeries:
        data = _fetch_json(self._client, request)
        return to_trend_series(data, request.ndays)

    def fetch_fund_flow(self, request: FundFlowRequest) -> FundFlowSeries:
        data = _fetch_json(self._client, request)
        return to_fund_flow_series(data, request.market)

    def fetch_board_fund_flow(self, request: FundFlowRequest) -> BoardFundFlowSeries:
        data = _fetch_json(self._client, request)
        return to_board_fund_flow_series(data)

    def fetch_board_list(self, request: ClistRequest) -> BoardListPage:
        data = _fetch_json(self._client, request)
        return to_board_list_page(data)

    def fetch_index_list(self, request: ClistRequest) -> IndexListPage:
        data = _fetch_json(self._client, request)
        return to_index_list_page(data)

    def fetch_hk_stock_list(self, request: ClistRequest) -> HkStockListPage:
        data = _fetch_json(self._client, request)
        return to_hk_stock_list_page(data)

    def fetch_fund_list(self, request: ClistRequest) -> FundListPage:
        data = _fetch_json(self._client, request)
        return to_fund_list_page(data)

    def fetch_limit_pool(self, request: LimitPoolRequest) -> LimitPoolPage:
        data = _fetch_json(self._client, request)
        return to_limit_pool_page(data, request.pool_type, request.date)

    def fetch_stock_info(self, request: StockGetRequest) -> StockInfo:
        return to_stock_info(_fetch_stock_get(self._client, request), request.market)

    def fetch_stock_bid_ask(self, request: StockGetRequest) -> StockBidAsk:
        return to_stock_bid_ask(_fetch_stock_get(self._client, request), request.market)

    def fetch_stock_changes(self, request: StockChangesRequest) -> StockChangesPage:
        # 一次取全量，响应体与 K 线同量级：声明更大的读预算
        data = _fetch_json(self._client, request, config.CHANGES_READ_TIMEOUT_SEC)
        return to_stock_changes_page(data, request.change_type)

    def fetch_board_changes(self, request: BoardChangesRequest) -> BoardChangesPage:
        data = _fetch_json(self._client, request, config.CHANGES_READ_TIMEOUT_SEC)
        return to_board_changes_page(data)

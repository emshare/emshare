"""个股五档盘口（push2 stock/get，默认字段集）。"""

from em.channels.eastmoney import config
from em.channels.eastmoney.ashare_stocks.stock_info.stock_info_em import normalize_market
from em.channels.eastmoney.request import StockGetRequest
from em.domain.queries import StockBidAskQuery


def secid_of(query: StockBidAskQuery) -> str:
    """把「市场 + 代码」拼成东财 secid；未知市场回退深市。"""
    return f"{config.MARKET_IDS[normalize_market(query.market)]}.{query.code}"


def stock_bid_ask_request(query: StockBidAskQuery) -> StockGetRequest:
    # 不传 fields：五档 f11–f40 只在默认字段集里，显式列出反而拿不到（实测）
    return StockGetRequest(
        host=config.GUEST_HOST,
        secid=secid_of(query),
        fields=None,
        market=normalize_market(query.market),
    )

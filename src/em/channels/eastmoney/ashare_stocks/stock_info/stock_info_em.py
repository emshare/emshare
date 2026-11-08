"""个股基本信息（push2 stock/get，显式字段集）。"""

from em.channels.eastmoney import config
from em.channels.eastmoney.request import StockGetRequest
from em.domain.queries import StockInfoQuery


def normalize_market(market: str) -> str:
    """把市场规范为已知值；未知市场回退深市（与 secid 前缀的回退一致）。"""
    return market if market in config.MARKET_IDS else "sz"


def secid_of(query: StockInfoQuery) -> str:
    """把「市场 + 代码」拼成东财 secid；未知市场回退深市。"""
    return f"{config.MARKET_IDS[normalize_market(query.market)]}.{query.code}"


def stock_info_request(query: StockInfoQuery) -> StockGetRequest:
    return StockGetRequest(
        host=config.GUEST_HOST,
        secid=secid_of(query),
        fields=config.STOCK_INFO_FIELDS,
        market=normalize_market(query.market),
    )

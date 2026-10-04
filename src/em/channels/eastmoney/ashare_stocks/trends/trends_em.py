"""个股 / 指数分时行情（trends2，ndays 日分时）。"""

from em.channels.eastmoney import config
from em.channels.eastmoney.request import TrendsRequest
from em.domain.queries import TrendQuery


def secid_of(query: TrendQuery) -> str:
    """把「市场 + 代码」拼成东财 secid；未知市场回退深市。"""
    return f"{config.MARKET_IDS.get(query.market, '0')}.{query.code}"


def trends_request(query: TrendQuery) -> TrendsRequest:
    return TrendsRequest(
        host=config.KLINE_HOST,
        secid=secid_of(query),
        ndays=query.ndays,
        iscr=query.iscr,
        iscca=query.iscca,
    )

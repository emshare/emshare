"""个股历史资金流（fflow/daykline，日线）。"""

from em.channels.eastmoney import config
from em.channels.eastmoney.request import FundFlowRequest
from em.domain.queries import FundFlowQuery


def secid_of(query: FundFlowQuery) -> str:
    """把「市场 + 代码」拼成东财 secid；未知市场回退深市。"""
    return f"{config.MARKET_IDS.get(query.market, '0')}.{query.code}"


def fund_flow_request(query: FundFlowQuery) -> FundFlowRequest:
    return FundFlowRequest(
        host=config.KLINE_HOST,
        secid=secid_of(query),
        market=query.market,
    )

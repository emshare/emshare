"""板块历史资金流（fflow/daykline，行业 / 概念 / 地域板块，日线）。"""

from em.channels.eastmoney import config
from em.channels.eastmoney.request import FundFlowRequest
from em.domain.queries import BoardFundFlowQuery


def secid_of(query: BoardFundFlowQuery) -> str:
    """把板块代码拼成东财 secid；板块统一 90 前缀。"""
    return f"{config.BOARD_MARKET_ID}.{query.board}"


def board_fund_flow_request(query: BoardFundFlowQuery) -> FundFlowRequest:
    return FundFlowRequest(
        host=config.KLINE_HOST,
        secid=secid_of(query),
        market="bk",
    )

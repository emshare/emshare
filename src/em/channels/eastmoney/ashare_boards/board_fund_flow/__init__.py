"""板块历史资金流接口族。"""

from em.channels.eastmoney.ashare_boards.board_fund_flow.board_fund_flow_em import (
    board_fund_flow_request,
    secid_of,
)

__all__ = ["board_fund_flow_request", "secid_of"]

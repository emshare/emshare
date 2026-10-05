"""渠道注册表：应用层唯一允许接触具体渠道的地方，按能力解析请求构建器与来源。

新增渠道时只改这里与 ``channels/``，``market_data`` / ``cli`` 无需改动。
"""

from em.channels.eastmoney.ashare_boards.board_constituent.board_constituent_em import (
    board_constituent_request,
    flow_field,
)
from em.channels.eastmoney.ashare_boards.board_fund_flow.board_fund_flow_em import (
    board_fund_flow_request,
)
from em.channels.eastmoney.ashare_stocks.stock_fund_flow.stock_fund_flow_em import fund_flow_request
from em.channels.eastmoney.ashare_stocks.stock_kline.stock_kline_em import kline_request
from em.channels.eastmoney.ashare_stocks.stock_list.stock_list_em import stock_list_request
from em.channels.eastmoney.ashare_stocks.stock_trends.stock_trends_em import trends_request
from em.channels.eastmoney.source import EastMoneySource

__all__ = [
    "EastMoneySource",
    "board_constituent_request",
    "board_fund_flow_request",
    "flow_field",
    "fund_flow_request",
    "kline_request",
    "stock_list_request",
    "trends_request",
]

"""渠道注册表：应用层唯一允许接触具体渠道的地方，按能力解析请求构建器与来源。

新增渠道时只改这里与 ``channels/``，``market_data`` / ``cli`` 无需改动。
"""

from em.channels.eastmoney.ashare_billboard.billboard_detail.billboard_detail_em import (
    billboard_detail_request,
)
from em.channels.eastmoney.ashare_boards.board_changes.board_changes_em import (
    board_changes_request,
)
from em.channels.eastmoney.ashare_boards.board_constituent.board_constituent_em import (
    board_constituent_request,
    flow_field,
)
from em.channels.eastmoney.ashare_boards.board_fund_flow.board_fund_flow_em import (
    board_fund_flow_request,
)
from em.channels.eastmoney.ashare_boards.board_industry_list.board_industry_list_em import (
    board_industry_list_request,
)
from em.channels.eastmoney.ashare_boards.board_kline.board_kline_em import board_kline_request
from em.channels.eastmoney.ashare_indices.index_list.index_list_em import index_list_request
from em.channels.eastmoney.ashare_stocks.stock_bid_ask.stock_bid_ask_em import (
    stock_bid_ask_request,
)
from em.channels.eastmoney.ashare_stocks.stock_changes.stock_changes_em import (
    stock_changes_request,
)
from em.channels.eastmoney.ashare_stocks.stock_fund_flow.stock_fund_flow_em import fund_flow_request
from em.channels.eastmoney.ashare_stocks.stock_info.stock_info_em import stock_info_request
from em.channels.eastmoney.ashare_stocks.stock_kline.stock_kline_em import kline_request
from em.channels.eastmoney.ashare_stocks.stock_limit_pool.stock_limit_pool_em import (
    stock_limit_pool_request,
)
from em.channels.eastmoney.ashare_stocks.stock_list.stock_list_em import stock_list_request
from em.channels.eastmoney.ashare_stocks.stock_trends.stock_trends_em import trends_request
from em.channels.eastmoney.fund_market.fund_list.fund_list_em import fund_list_request
from em.channels.eastmoney.hk_market.hk_stock_list.hk_stock_list_em import hk_stock_list_request
from em.channels.eastmoney.source import EastMoneySource

__all__ = [
    "EastMoneySource",
    "billboard_detail_request",
    "board_changes_request",
    "board_constituent_request",
    "board_fund_flow_request",
    "board_industry_list_request",
    "board_kline_request",
    "flow_field",
    "fund_flow_request",
    "fund_list_request",
    "hk_stock_list_request",
    "index_list_request",
    "kline_request",
    "stock_bid_ask_request",
    "stock_changes_request",
    "stock_info_request",
    "stock_limit_pool_request",
    "stock_list_request",
    "trends_request",
]

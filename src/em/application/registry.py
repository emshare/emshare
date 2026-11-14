"""渠道注册表：应用层唯一允许接触具体渠道的地方，按能力解析请求构建器与来源。

新增渠道时只改这里与 ``channels/``，``market_data`` / ``cli`` 无需改动。
"""

from em.channels.eastmoney.ashare_billboard.billboard_branch_active.billboard_branch_active_em import (
    billboard_branch_active_request,
)
from em.channels.eastmoney.ashare_billboard.billboard_branch_rank.billboard_branch_rank_em import (
    billboard_branch_rank_request,
)
from em.channels.eastmoney.ashare_billboard.billboard_branch_stats.billboard_branch_stats_em import (
    billboard_branch_stats_request,
)
from em.channels.eastmoney.ashare_billboard.billboard_branch_trades.billboard_branch_trades_em import (
    billboard_branch_trades_request,
)
from em.channels.eastmoney.ashare_billboard.billboard_detail.billboard_detail_em import (
    billboard_detail_request,
)
from em.channels.eastmoney.ashare_billboard.billboard_institution.billboard_institution_em import (
    billboard_institution_request,
)
from em.channels.eastmoney.ashare_billboard.billboard_institution_stats.billboard_institution_stats_em import (
    billboard_institution_stats_request,
)
from em.channels.eastmoney.ashare_billboard.billboard_stock.billboard_stock_em import (
    billboard_stock_request,
)
from em.channels.eastmoney.ashare_billboard.billboard_stock_dates.billboard_stock_dates_em import (
    billboard_stock_dates_request,
)
from em.channels.eastmoney.ashare_billboard.billboard_stock_stats.billboard_stock_stats_em import (
    billboard_stock_stats_request,
)
from em.channels.eastmoney.ashare_block_trade.block_trade_branch_active.block_trade_branch_active_em import (
    block_trade_branch_active_request,
)
from em.channels.eastmoney.ashare_block_trade.block_trade_branch_rank.block_trade_branch_rank_em import (
    block_trade_branch_rank_request,
)
from em.channels.eastmoney.ashare_block_trade.block_trade_detail.block_trade_detail_em import (
    block_trade_detail_request,
)
from em.channels.eastmoney.ashare_block_trade.block_trade_market_daily.block_trade_market_daily_em import (
    block_trade_market_daily_request,
)
from em.channels.eastmoney.ashare_block_trade.block_trade_stock_daily.block_trade_stock_daily_em import (
    block_trade_stock_daily_request,
)
from em.channels.eastmoney.ashare_block_trade.block_trade_stock_stats.block_trade_stock_stats_em import (
    block_trade_stock_stats_request,
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
from em.channels.eastmoney.ashare_earnings.earnings_express.earnings_express_em import (
    earnings_express_request,
)
from em.channels.eastmoney.ashare_earnings.earnings_forecast.earnings_forecast_em import (
    earnings_forecast_request,
)
from em.channels.eastmoney.ashare_earnings.earnings_report.earnings_report_em import (
    earnings_report_request,
)
from em.channels.eastmoney.ashare_earnings.earnings_schedule.earnings_schedule_em import (
    earnings_schedule_request,
)
from em.channels.eastmoney.ashare_financial_statements.balance_sheet.balance_sheet_em import (
    balance_sheet_request,
)
from em.channels.eastmoney.ashare_financial_statements.cash_flow_statement.cash_flow_statement_em import (
    cash_flow_statement_request,
)
from em.channels.eastmoney.ashare_financial_statements.income_statement.income_statement_em import (
    income_statement_request,
)
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
    "balance_sheet_request",
    "billboard_branch_active_request",
    "billboard_branch_rank_request",
    "billboard_branch_stats_request",
    "billboard_branch_trades_request",
    "billboard_detail_request",
    "billboard_institution_request",
    "billboard_institution_stats_request",
    "billboard_stock_dates_request",
    "billboard_stock_request",
    "billboard_stock_stats_request",
    "block_trade_branch_active_request",
    "block_trade_branch_rank_request",
    "block_trade_detail_request",
    "block_trade_market_daily_request",
    "block_trade_stock_daily_request",
    "block_trade_stock_stats_request",
    "board_changes_request",
    "board_constituent_request",
    "board_fund_flow_request",
    "board_industry_list_request",
    "board_kline_request",
    "cash_flow_statement_request",
    "earnings_express_request",
    "earnings_forecast_request",
    "earnings_report_request",
    "earnings_schedule_request",
    "flow_field",
    "fund_flow_request",
    "fund_list_request",
    "hk_stock_list_request",
    "income_statement_request",
    "index_list_request",
    "kline_request",
    "stock_bid_ask_request",
    "stock_changes_request",
    "stock_info_request",
    "stock_limit_pool_request",
    "stock_list_request",
    "trends_request",
]

"""em：东方财富行情抓取包。

分层：domain（领域模型）← core（基座）← channels（渠道）← application（组合根）。
对外公共面统一从本模块导出，渠道明细从 ``em.channels`` 子包取。
``*_em`` 返回领域模型（``QuotePage`` / ``KlineSeries`` / ``TrendSeries`` / ``FundFlowSeries`` 等，
``board_kline_em`` 与 ``stock_kline_em`` 共用 ``KlineSeries``，``index_list_em`` 返回 ``IndexListPage``，``hk_stock_list_em`` 返回 ``HkStockListPage``，``fund_list_em`` 返回 ``FundListPage``，``stock_limit_pool_em`` 返回 ``LimitPoolPage``，``stock_info_em`` / ``stock_bid_ask_em`` 返回
``StockInfo`` / ``StockBidAsk``，``stock_changes_em`` / ``board_changes_em`` 返回 ``StockChangesPage`` / ``BoardChangesPage``），
``df_*_em`` 返回 pandas DataFrame（需 pandas）。
``search`` / ``interface_info`` / ``list_categories`` 提供离线接口检索（对齐 akshare）。
``resolve_code`` / ``resolve_board`` 提供中文名→代码解析（东财搜索接口，单请求）；
``*_by_name`` 为面向自然语言的便捷层（先 resolve 再调 ``*_em``，供 LLM/Agent 场景）。
"""

from pathlib import Path

from em.application.catalog import (
    interface_info,
    interface_info_df,
    list_categories,
    list_categories_df,
    search,
    search_df,
)
from em.application.convenience import (
    board_constituent_by_name,
    board_fund_flow_by_name,
    kline_by_name,
    stock_fund_flow_by_name,
    trends_by_name,
)
from em.application.dataframe import (
    to_board_changes_dataframe,
    to_board_fund_flow_dataframe,
    to_board_list_dataframe,
    to_dataframe,
    to_fund_flow_dataframe,
    to_fund_list_dataframe,
    to_hk_stock_list_dataframe,
    to_index_list_dataframe,
    to_kline_dataframe,
    to_limit_pool_dataframe,
    to_stock_bid_ask_dataframe,
    to_stock_changes_dataframe,
    to_stock_info_dataframe,
    to_trend_dataframe,
)
from em.application.market_data import (
    board_changes_em,
    board_constituent_em,
    board_fund_flow_em,
    board_industry_list_em,
    board_kline_em,
    df_board_changes_em,
    df_board_constituent_em,
    df_board_fund_flow_em,
    df_board_industry_list_em,
    df_board_kline_em,
    df_fund_list_em,
    df_hk_stock_list_em,
    df_index_list_em,
    df_stock_bid_ask_em,
    df_stock_changes_em,
    df_stock_fund_flow_em,
    df_stock_info_em,
    df_stock_kline_em,
    df_stock_limit_pool_em,
    df_stock_list_all_em,
    df_stock_list_em,
    df_stock_trends_em,
    fund_list_em,
    hk_stock_list_em,
    index_list_em,
    stock_bid_ask_em,
    stock_changes_em,
    stock_fund_flow_em,
    stock_info_em,
    stock_kline_em,
    stock_limit_pool_em,
    stock_list_all_em,
    stock_list_em,
    stock_trends_em,
)
from em.application.resolve import (
    BoardRef,
    StockRef,
    reset_resolve_cache,
    resolve_board,
    resolve_code,
)
from em.core.env import load_dotenv

for _candidate in (Path(".env"), Path(__file__).resolve().parents[2] / ".env"):
    load_dotenv(_candidate)

__all__ = [
    "BoardRef",
    "StockRef",
    "board_changes_em",
    "board_constituent_by_name",
    "board_constituent_em",
    "board_fund_flow_by_name",
    "board_fund_flow_em",
    "board_industry_list_em",
    "board_kline_em",
    "df_board_changes_em",
    "df_board_constituent_em",
    "df_board_fund_flow_em",
    "df_board_industry_list_em",
    "df_board_kline_em",
    "df_fund_list_em",
    "df_hk_stock_list_em",
    "df_index_list_em",
    "df_stock_bid_ask_em",
    "df_stock_changes_em",
    "df_stock_fund_flow_em",
    "df_stock_info_em",
    "df_stock_kline_em",
    "df_stock_limit_pool_em",
    "df_stock_list_all_em",
    "df_stock_list_em",
    "df_stock_trends_em",
    "fund_list_em",
    "hk_stock_list_em",
    "index_list_em",
    "interface_info",
    "interface_info_df",
    "kline_by_name",
    "list_categories",
    "list_categories_df",
    "reset_resolve_cache",
    "resolve_board",
    "resolve_code",
    "search",
    "search_df",
    "stock_bid_ask_em",
    "stock_changes_em",
    "stock_fund_flow_by_name",
    "stock_fund_flow_em",
    "stock_info_em",
    "stock_kline_em",
    "stock_limit_pool_em",
    "stock_list_all_em",
    "stock_list_em",
    "stock_trends_em",
    "to_board_changes_dataframe",
    "to_board_fund_flow_dataframe",
    "to_board_list_dataframe",
    "to_dataframe",
    "to_fund_flow_dataframe",
    "to_fund_list_dataframe",
    "to_hk_stock_list_dataframe",
    "to_index_list_dataframe",
    "to_kline_dataframe",
    "to_limit_pool_dataframe",
    "to_stock_bid_ask_dataframe",
    "to_stock_changes_dataframe",
    "to_stock_info_dataframe",
    "to_trend_dataframe",
    "trends_by_name",
]

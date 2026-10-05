"""em：东方财富行情抓取包。

分层：domain（领域模型）← core（基座）← channels（渠道）← application（组合根）。
对外公共面统一从本模块导出，渠道明细从 ``em.channels`` 子包取。
``*_em`` 返回领域模型（``QuotePage`` / ``KlineSeries`` / ``TrendSeries`` / ``FundFlowSeries``），
``df_*_em`` 返回 pandas DataFrame（需 pandas）。
``search`` / ``interface_info`` / ``list_categories`` 提供离线接口检索（对齐 akshare）。
"""

from em.application.catalog import (
    interface_info,
    interface_info_df,
    list_categories,
    list_categories_df,
    search,
    search_df,
)
from em.application.dataframe import (
    to_board_fund_flow_dataframe,
    to_dataframe,
    to_fund_flow_dataframe,
    to_kline_dataframe,
    to_trend_dataframe,
)
from em.application.market_data import (
    board_constituent_em,
    board_fund_flow_em,
    df_board_constituent_em,
    df_board_fund_flow_em,
    df_stock_fund_flow_em,
    df_stock_kline_em,
    df_stock_list_em,
    df_stock_trends_em,
    stock_fund_flow_em,
    stock_kline_em,
    stock_list_em,
    stock_trends_em,
)

__all__ = [
    "board_constituent_em",
    "board_fund_flow_em",
    "df_board_constituent_em",
    "df_board_fund_flow_em",
    "df_stock_fund_flow_em",
    "df_stock_kline_em",
    "df_stock_list_em",
    "df_stock_trends_em",
    "interface_info",
    "interface_info_df",
    "list_categories",
    "list_categories_df",
    "search",
    "search_df",
    "stock_fund_flow_em",
    "stock_kline_em",
    "stock_list_em",
    "stock_trends_em",
    "to_board_fund_flow_dataframe",
    "to_dataframe",
    "to_fund_flow_dataframe",
    "to_kline_dataframe",
    "to_trend_dataframe",
]

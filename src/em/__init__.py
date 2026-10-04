"""em：东方财富行情抓取包。

分层：domain（领域模型）← core（基座）← channels（渠道）← application（组合根）。
对外公共面统一从本模块导出，渠道明细从 ``em.channels`` 子包取。
``fetch_*`` 返回领域模型（``QuotePage`` / ``KlineSeries`` / ``TrendSeries`` / ``FundFlowSeries``），
``fetch_*_df`` 返回 pandas DataFrame（需 pandas）。
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
    fetch_board,
    fetch_board_df,
    fetch_board_fund_flow,
    fetch_board_fund_flow_df,
    fetch_fund_flow,
    fetch_fund_flow_df,
    fetch_kline,
    fetch_kline_df,
    fetch_market,
    fetch_market_df,
    fetch_trends,
    fetch_trends_df,
)

__all__ = [
    "fetch_board",
    "fetch_board_df",
    "fetch_board_fund_flow",
    "fetch_board_fund_flow_df",
    "fetch_fund_flow",
    "fetch_fund_flow_df",
    "fetch_kline",
    "fetch_kline_df",
    "fetch_market",
    "fetch_market_df",
    "fetch_trends",
    "fetch_trends_df",
    "interface_info",
    "interface_info_df",
    "list_categories",
    "list_categories_df",
    "search",
    "search_df",
    "to_board_fund_flow_dataframe",
    "to_dataframe",
    "to_fund_flow_dataframe",
    "to_kline_dataframe",
    "to_trend_dataframe",
]

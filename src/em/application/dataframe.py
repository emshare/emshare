"""DataFrame 适配：把领域模型 ``QuotePage`` 转为 pandas DataFrame。

pandas 为可选依赖（``pip install emshare[pandas]``），此处延迟导入，缺失时给清晰错误。
默认列名对齐 akshare 传统中文风格（代码 / 名称 / 最新价 / 涨跌幅 ...），传 ``columns`` 可覆盖。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from em.domain.models import (
    BalanceSheet,
    BillboardBranchActive,
    BillboardBranchRank,
    BillboardBranchStats,
    BillboardBranchTrade,
    BillboardEntry,
    BillboardInstitutionStats,
    BillboardInstitutionTrade,
    BillboardSeat,
    BillboardStockDate,
    BillboardStockStats,
    BlockTrade,
    BlockTradeBranchActive,
    BlockTradeBranchRank,
    BlockTradeMarketDaily,
    BlockTradeStockDaily,
    BlockTradeStockStats,
    BoardChangesPage,
    BoardFundFlowSeries,
    BoardListPage,
    CashFlowStatement,
    EarningsExpress,
    EarningsForecast,
    EarningsReport,
    EarningsSchedule,
    FundFlowSeries,
    FundListPage,
    HkStockListPage,
    IncomeStatement,
    IndexListPage,
    KlineSeries,
    LimitPoolPage,
    QuotePage,
    ReportPage,
    StockBidAsk,
    StockChangesPage,
    StockInfo,
    TrendSeries,
)

if TYPE_CHECKING:
    import pandas as pd

# 领域字段 -> 默认中文列名（对齐 akshare）
COLUMNS_ZH: dict[str, str] = {
    "code": "代码",
    "name": "名称",
    "price": "最新价",
    "change_pct": "涨跌幅",
    "change": "涨跌额",
    "main_net_inflow": "主力净流入",
    "turnover": "成交额",
    "turnover_rate": "换手率",
}

# K 线字段 -> 默认中文列名（对齐 akshare stock_zh_a_hist）
KLINES_COLUMNS_ZH: dict[str, str] = {
    "date": "日期",
    "open": "开盘",
    "close": "收盘",
    "high": "最高",
    "low": "最低",
    "volume": "成交量",
    "amount": "成交额",
    "amplitude": "振幅",
    "change_pct": "涨跌幅",
    "change": "涨跌额",
    "turnover_rate": "换手率",
}

# 分时字段 -> 默认中文列名
TRENDS_COLUMNS_ZH: dict[str, str] = {
    "time": "时间",
    "price": "最新价",
    "avg_price": "均价",
    "high": "最高",
    "low": "最低",
    "volume": "成交量",
    "amount": "成交额",
    "avg_price2": "均价2",
}

# 资金流字段 -> 默认中文列名（对齐 akshare stock_individual_fund_flow）
FUND_FLOW_COLUMNS_ZH: dict[str, str] = {
    "date": "日期",
    "close": "收盘价",
    "change_pct": "涨跌幅",
    "main_net_inflow": "主力净流入-净额",
    "main_net_pct": "主力净流入-净占比",
    "xlarge_net_inflow": "超大单净流入-净额",
    "xlarge_net_pct": "超大单净流入-净占比",
    "large_net_inflow": "大单净流入-净额",
    "large_net_pct": "大单净流入-净占比",
    "medium_net_inflow": "中单净流入-净额",
    "medium_net_pct": "中单净流入-净占比",
    "small_net_inflow": "小单净流入-净额",
    "small_net_pct": "小单净流入-净占比",
}

_FIELD_ORDER = tuple(COLUMNS_ZH.keys())
_KLINE_FIELD_ORDER = tuple(KLINES_COLUMNS_ZH.keys())
_TREND_FIELD_ORDER = tuple(TRENDS_COLUMNS_ZH.keys())
_FUND_FLOW_FIELD_ORDER = tuple(FUND_FLOW_COLUMNS_ZH.keys())


def to_dataframe(
    page: QuotePage,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """把 ``QuotePage`` 转为 ``DataFrame``；默认中文列名，传 ``columns`` 覆盖。

    列顺序固定为 ``COLUMNS_ZH`` 的字段顺序，空页也保留列头。
    """
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - 环境依赖
        raise ImportError(
            "pandas 未安装：pip install emshare[pandas] 或 pip install pandas"
        ) from exc

    naming = columns or COLUMNS_ZH
    ordered_cols = [naming[f] for f in _FIELD_ORDER]
    rows = [{naming[f]: getattr(q, f) for f in _FIELD_ORDER} for q in page.items]
    return pd.DataFrame(rows, columns=ordered_cols)  # type: ignore[no-any-return]


def to_kline_dataframe(
    series: KlineSeries,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """把 ``KlineSeries`` 转为 ``DataFrame``；默认 akshare 风格中文列名。

    列顺序固定为 ``KLINES_COLUMNS_ZH`` 的字段顺序，空序列也保留列头。
    """
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - 环境依赖
        raise ImportError(
            "pandas 未安装：pip install emshare[pandas] 或 pip install pandas"
        ) from exc

    naming = columns or KLINES_COLUMNS_ZH
    ordered_cols = [naming[f] for f in _KLINE_FIELD_ORDER]
    rows = [{naming[f]: getattr(k, f) for f in _KLINE_FIELD_ORDER} for k in series.items]
    return pd.DataFrame(rows, columns=ordered_cols)  # type: ignore[no-any-return]


def to_trend_dataframe(
    series: TrendSeries,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """把 ``TrendSeries`` 转为 ``DataFrame``；默认中文列名。

    列顺序固定为 ``TRENDS_COLUMNS_ZH`` 的字段顺序，空序列也保留列头。
    """
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - 环境依赖
        raise ImportError(
            "pandas 未安装：pip install emshare[pandas] 或 pip install pandas"
        ) from exc

    naming = columns or TRENDS_COLUMNS_ZH
    ordered_cols = [naming[f] for f in _TREND_FIELD_ORDER]
    rows = [{naming[f]: getattr(t, f) for f in _TREND_FIELD_ORDER} for t in series.items]
    return pd.DataFrame(rows, columns=ordered_cols)  # type: ignore[no-any-return]


def to_fund_flow_dataframe(
    series: FundFlowSeries,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """把 ``FundFlowSeries`` 转为 ``DataFrame``；默认 akshare 风格中文列名。

    列顺序固定为 ``FUND_FLOW_COLUMNS_ZH`` 的字段顺序，空序列也保留列头。
    """
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - 环境依赖
        raise ImportError(
            "pandas 未安装：pip install emshare[pandas] 或 pip install pandas"
        ) from exc

    naming = columns or FUND_FLOW_COLUMNS_ZH
    ordered_cols = [naming[f] for f in _FUND_FLOW_FIELD_ORDER]
    rows = [{naming[f]: getattr(x, f) for f in _FUND_FLOW_FIELD_ORDER} for x in series.items]
    return pd.DataFrame(rows, columns=ordered_cols)  # type: ignore[no-any-return]


# 板块资金流字段 -> 默认中文列名（对齐 akshare stock_sector_fund_flow_hist，不含收盘价 / 涨跌幅）
BOARD_FUND_FLOW_COLUMNS_ZH: dict[str, str] = {
    "date": "日期",
    "main_net_inflow": "主力净流入-净额",
    "main_net_pct": "主力净流入-净占比",
    "xlarge_net_inflow": "超大单净流入-净额",
    "xlarge_net_pct": "超大单净流入-净占比",
    "large_net_inflow": "大单净流入-净额",
    "large_net_pct": "大单净流入-净占比",
    "medium_net_inflow": "中单净流入-净额",
    "medium_net_pct": "中单净流入-净占比",
    "small_net_inflow": "小单净流入-净额",
    "small_net_pct": "小单净流入-净占比",
}
_BOARD_FUND_FLOW_FIELD_ORDER = tuple(BOARD_FUND_FLOW_COLUMNS_ZH.keys())


def to_board_fund_flow_dataframe(
    series: BoardFundFlowSeries,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """把 ``BoardFundFlowSeries`` 转为 ``DataFrame``；默认 akshare 风格中文列名。

    列顺序固定为 ``BOARD_FUND_FLOW_COLUMNS_ZH`` 的字段顺序，空序列也保留列头。
    """
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - 环境依赖
        raise ImportError(
            "pandas 未安装：pip install emshare[pandas] 或 pip install pandas"
        ) from exc

    naming = columns or BOARD_FUND_FLOW_COLUMNS_ZH
    ordered_cols = [naming[f] for f in _BOARD_FUND_FLOW_FIELD_ORDER]
    rows = [{naming[f]: getattr(x, f) for f in _BOARD_FUND_FLOW_FIELD_ORDER} for x in series.items]
    return pd.DataFrame(rows, columns=ordered_cols)  # type: ignore[no-any-return]


# 板块列表字段 -> 默认中文列名（对齐 akshare stock_board_industry_name_em）
BOARD_LIST_COLUMNS_ZH: dict[str, str] = {
    "code": "板块代码",
    "name": "板块名称",
    "price": "最新价",
    "change_pct": "涨跌幅",
    "change": "涨跌额",
    "turnover": "成交额",
    "turnover_rate": "换手率",
    "up_count": "上涨家数",
    "down_count": "下跌家数",
    "leader_code": "领涨股票代码",
    "leader_name": "领涨股票",
    "leader_change_pct": "领涨股票-涨跌幅",
    "laggard_code": "领跌股票代码",
    "laggard_name": "领跌股票",
    "laggard_change_pct": "领跌股票-涨跌幅",
}
_BOARD_LIST_FIELD_ORDER = tuple(BOARD_LIST_COLUMNS_ZH.keys())


def to_board_list_dataframe(
    page: BoardListPage,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """把 ``BoardListPage`` 转为 ``DataFrame``；默认 akshare 风格中文列名。

    列顺序固定为 ``BOARD_LIST_COLUMNS_ZH`` 的字段顺序，空页也保留列头。
    """
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - 环境依赖
        raise ImportError(
            "pandas 未安装：pip install emshare[pandas] 或 pip install pandas"
        ) from exc

    naming = columns or BOARD_LIST_COLUMNS_ZH
    ordered_cols = [naming[f] for f in _BOARD_LIST_FIELD_ORDER]
    rows = [{naming[f]: getattr(b, f) for f in _BOARD_LIST_FIELD_ORDER} for b in page.items]
    return pd.DataFrame(rows, columns=ordered_cols)  # type: ignore[no-any-return]


# 指数列表字段 -> 默认中文列名（对齐 akshare stock_zh_index_spot_em，另加“市场”消歧代码）
INDEX_LIST_COLUMNS_ZH: dict[str, str] = {
    "code": "代码",
    "name": "名称",
    "market": "市场",
    "price": "最新价",
    "change_pct": "涨跌幅",
    "change": "涨跌额",
    "volume": "成交量",
    "turnover": "成交额",
    "amplitude": "振幅",
    "high": "最高",
    "low": "最低",
    "open": "今开",
    "pre_close": "昨收",
    "volume_ratio": "量比",
}

_INDEX_LIST_FIELD_ORDER = tuple(INDEX_LIST_COLUMNS_ZH.keys())


def to_index_list_dataframe(
    page: IndexListPage,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """把 ``IndexListPage`` 转为 ``DataFrame``；默认 akshare 风格中文列名。

    列顺序固定为 ``INDEX_LIST_COLUMNS_ZH`` 的字段顺序，空页也保留列头。
    """
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - 环境依赖
        raise ImportError(
            "pandas 未安装：pip install emshare[pandas] 或 pip install pandas"
        ) from exc

    naming = columns or INDEX_LIST_COLUMNS_ZH
    ordered_cols = [naming[f] for f in _INDEX_LIST_FIELD_ORDER]
    rows = [{naming[f]: getattr(i, f) for f in _INDEX_LIST_FIELD_ORDER} for i in page.items]
    return pd.DataFrame(rows, columns=ordered_cols)  # type: ignore[no-any-return]


# 港股列表字段 -> 默认中文列名（对齐 akshare stock_hk_spot_em 的列与顺序）
HK_STOCK_LIST_COLUMNS_ZH: dict[str, str] = {
    "code": "代码",
    "name": "名称",
    "price": "最新价",
    "change": "涨跌额",
    "change_pct": "涨跌幅",
    "open": "今开",
    "high": "最高",
    "low": "最低",
    "pre_close": "昨收",
    "volume": "成交量",
    "turnover": "成交额",
}

_HK_STOCK_LIST_FIELD_ORDER = tuple(HK_STOCK_LIST_COLUMNS_ZH.keys())


def to_hk_stock_list_dataframe(
    page: HkStockListPage,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """把 ``HkStockListPage`` 转为 ``DataFrame``；默认 akshare 风格中文列名。

    列顺序固定为 ``HK_STOCK_LIST_COLUMNS_ZH`` 的字段顺序，空页也保留列头。
    """
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - 环境依赖
        raise ImportError(
            "pandas 未安装：pip install emshare[pandas] 或 pip install pandas"
        ) from exc

    naming = columns or HK_STOCK_LIST_COLUMNS_ZH
    ordered_cols = [naming[f] for f in _HK_STOCK_LIST_FIELD_ORDER]
    rows = [{naming[f]: getattr(q, f) for f in _HK_STOCK_LIST_FIELD_ORDER} for q in page.items]
    return pd.DataFrame(rows, columns=ordered_cols)  # type: ignore[no-any-return]


# 场内基金字段 -> 默认中文列名（对齐 akshare fund_etf_spot_em / fund_lof_spot_em，另加“市场”）
FUND_LIST_COLUMNS_ZH: dict[str, str] = {
    "code": "代码",
    "name": "名称",
    "market": "市场",
    "price": "最新价",
    "iopv": "IOPV实时估值",
    "discount_rate": "基金折价率",
    "change": "涨跌额",
    "change_pct": "涨跌幅",
    "volume": "成交量",
    "turnover": "成交额",
    "open": "开盘价",
    "high": "最高价",
    "low": "最低价",
    "pre_close": "昨收",
    "turnover_rate": "换手率",
    "float_market_cap": "流通市值",
    "total_market_cap": "总市值",
}

_FUND_LIST_FIELD_ORDER = tuple(FUND_LIST_COLUMNS_ZH.keys())


def to_fund_list_dataframe(
    page: FundListPage,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """把 ``FundListPage`` 转为 ``DataFrame``；默认 akshare 风格中文列名。

    列顺序固定为 ``FUND_LIST_COLUMNS_ZH`` 的字段顺序，空页也保留列头。
    """
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - 环境依赖
        raise ImportError(
            "pandas 未安装：pip install emshare[pandas] 或 pip install pandas"
        ) from exc

    naming = columns or FUND_LIST_COLUMNS_ZH
    ordered_cols = [naming[f] for f in _FUND_LIST_FIELD_ORDER]
    rows = [{naming[f]: getattr(q, f) for f in _FUND_LIST_FIELD_ORDER} for q in page.items]
    return pd.DataFrame(rows, columns=ordered_cols)  # type: ignore[no-any-return]


# 涨跌停股池字段 -> 默认中文列名（对齐 akshare stock_zt_pool_*_em）
LIMIT_POOL_COLUMNS_ZH: dict[str, str] = {
    "code": "代码",
    "name": "名称",
    "market": "市场",
    "change_pct": "涨跌幅",
    "price": "最新价",
    "limit_up_price": "涨停价",
    "turnover": "成交额",
    "float_market_cap": "流通市值",
    "total_market_cap": "总市值",
    "pe": "动态市盈率",
    "turnover_rate": "换手率",
    "seal_fund": "封板资金",
    "first_seal_time": "首次封板时间",
    "last_seal_time": "最后封板时间",
    "board_turnover": "板上成交额",
    "broken_count": "炸板次数",
    "limit_up_streak": "连板数",
    "prev_seal_time": "昨日封板时间",
    "prev_limit_up_streak": "昨日连板数",
    "limit_down_streak": "连续跌停",
    "open_count": "开板次数",
    "speed": "涨速",
    "amplitude": "振幅",
    "volume_ratio": "量比",
    "new_high": "是否新高",
    "open_days": "开板几日",
    "open_date": "开板日期",
    "listing_date": "上市日期",
    "stat_days": "涨停统计-天数",
    "stat_limit_ups": "涨停统计-板数",
    "reason": "入选理由",
    "industry": "所属行业",
}

# 各股池输出哪些列、什么顺序（对齐 akshare 各接口，另在名称后加“市场”）
LIMIT_POOL_FIELDS_BY_TYPE: dict[str, tuple[str, ...]] = {
    "limit_up": (
        "code", "name", "market", "change_pct", "price", "turnover", "float_market_cap",
        "total_market_cap", "turnover_rate", "seal_fund", "first_seal_time", "last_seal_time",
        "broken_count", "stat_days", "stat_limit_ups", "limit_up_streak", "industry",
    ),
    "prev_limit_up": (
        "code", "name", "market", "change_pct", "price", "limit_up_price", "turnover",
        "float_market_cap", "total_market_cap", "turnover_rate", "speed", "amplitude",
        "prev_seal_time", "prev_limit_up_streak", "stat_days", "stat_limit_ups", "industry",
    ),
    "strong": (
        "code", "name", "market", "change_pct", "price", "limit_up_price", "turnover",
        "float_market_cap", "total_market_cap", "turnover_rate", "speed", "new_high",
        "volume_ratio", "stat_days", "stat_limit_ups", "reason", "industry",
    ),
    "sub_new": (
        "code", "name", "market", "change_pct", "price", "limit_up_price", "turnover",
        "float_market_cap", "total_market_cap", "turnover_rate", "open_days", "open_date",
        "listing_date", "new_high", "stat_days", "stat_limit_ups", "industry",
    ),
    "broken": (
        "code", "name", "market", "change_pct", "price", "limit_up_price", "turnover",
        "float_market_cap", "total_market_cap", "turnover_rate", "speed", "first_seal_time",
        "broken_count", "stat_days", "stat_limit_ups", "amplitude", "industry",
    ),
    "limit_down": (
        "code", "name", "market", "change_pct", "price", "turnover", "float_market_cap",
        "total_market_cap", "pe", "turnover_rate", "seal_fund", "last_seal_time",
        "board_turnover", "limit_down_streak", "open_count", "industry",
    ),
}  # fmt: skip

# 同一字段在个别股池里叫法不同（对齐 akshare）
_LIMIT_POOL_LABEL_OVERRIDES: dict[str, dict[str, str]] = {
    "limit_down": {"seal_fund": "封单资金"},
}


def to_limit_pool_dataframe(
    page: LimitPoolPage,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """把 ``LimitPoolPage`` 转为 ``DataFrame``；只输出该股池适用的列，默认 akshare 风格中文列名。

    列顺序固定为 ``LIMIT_POOL_FIELDS_BY_TYPE[page.pool_type]``，空池也保留列头。
    """
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - 环境依赖
        raise ImportError(
            "pandas 未安装：pip install emshare[pandas] 或 pip install pandas"
        ) from exc

    fields = LIMIT_POOL_FIELDS_BY_TYPE.get(page.pool_type, LIMIT_POOL_FIELDS_BY_TYPE["limit_up"])
    naming = columns or {
        **LIMIT_POOL_COLUMNS_ZH,
        **_LIMIT_POOL_LABEL_OVERRIDES.get(page.pool_type, {}),
    }
    ordered_cols = [naming[f] for f in fields]
    rows = [{naming[f]: getattr(s, f) for f in fields} for s in page.items]
    return pd.DataFrame(rows, columns=ordered_cols)  # type: ignore[no-any-return]


def _item_value_frame(rows: list[tuple[str, object]]) -> pd.DataFrame:
    """两列 ``item`` / ``value`` 的纵表（对齐 akshare stock_individual_info_em / stock_bid_ask_em）。"""
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - 环境依赖
        raise ImportError(
            "pandas 未安装：pip install emshare[pandas] 或 pip install pandas"
        ) from exc
    return pd.DataFrame(rows, columns=["item", "value"])  # type: ignore[no-any-return]


# 个股信息字段 -> item 名（对齐 akshare stock_individual_info_em，另加“市场”）
STOCK_INFO_ITEMS_ZH: dict[str, str] = {
    "code": "股票代码",
    "name": "股票简称",
    "market": "市场",
    "price": "最新",
    "total_shares": "总股本",
    "float_shares": "流通股",
    "total_market_cap": "总市值",
    "float_market_cap": "流通市值",
    "industry": "行业",
    "listing_date": "上市时间",
}


def to_stock_info_dataframe(info: StockInfo) -> pd.DataFrame:
    """把 ``StockInfo`` 转为 ``item`` / ``value`` 纵表。"""
    return _item_value_frame([(zh, getattr(info, f)) for f, zh in STOCK_INFO_ITEMS_ZH.items()])


# 五档之外的行情项 -> item 名（对齐 akshare stock_bid_ask_em；上游默认字段集没有涨幅 / 涨跌 / 换手 / 内盘）
_BID_ASK_QUOTE_ITEMS_ZH: dict[str, str] = {
    "price": "最新",
    "avg_price": "均价",
    "volume": "总手",
    "turnover": "金额",
    "volume_ratio": "量比",
    "high": "最高",
    "low": "最低",
    "open": "今开",
    "pre_close": "昨收",
    "limit_up": "涨停",
    "limit_down": "跌停",
    "outer_volume": "外盘",
}


def to_stock_bid_ask_dataframe(book: StockBidAsk) -> pd.DataFrame:
    """把 ``StockBidAsk`` 转为 ``item`` / ``value`` 纵表：卖五 → 卖一、买一 → 买五，再接行情项。

    挂单量单位为手（akshare 乘 100 换成股，本表不换）。
    """
    rows: list[tuple[str, object]] = []
    for i in range(len(book.asks), 0, -1):
        level = book.asks[i - 1]
        rows += [(f"卖{i}", level.price), (f"卖{i}量", level.volume)]
    for i, level in enumerate(book.bids, start=1):
        rows += [(f"买{i}", level.price), (f"买{i}量", level.volume)]
    rows += [(zh, getattr(book, f)) for f, zh in _BID_ASK_QUOTE_ITEMS_ZH.items()]
    return _item_value_frame(rows)


# 异动类型 -> 中文名（东财页面 / akshare 的叫法）
CHANGE_TYPE_LABELS_ZH: dict[str, str] = {
    "rocket_launch": "火箭发射",
    "quick_rebound": "快速反弹",
    "big_buy": "大笔买入",
    "limit_up_sealed": "封涨停板",
    "limit_down_opened": "打开跌停板",
    "big_bid": "有大买盘",
    "auction_up": "竞价上涨",
    "open_above_ma5": "高开5日线",
    "gap_up": "向上缺口",
    "new_high_60d": "60日新高",
    "big_rise_60d": "60日大幅上涨",
    "accelerated_drop": "加速下跌",
    "high_dive": "高台跳水",
    "big_sell": "大笔卖出",
    "limit_down_sealed": "封跌停板",
    "limit_up_opened": "打开涨停板",
    "big_ask": "有大卖盘",
    "auction_down": "竞价下跌",
    "open_below_ma5": "低开5日线",
    "gap_down": "向下缺口",
    "new_low_60d": "60日新低",
    "big_drop_60d": "60日大幅下跌",
}


def _change_label(change_type: str | None) -> str | None:
    return CHANGE_TYPE_LABELS_ZH.get(change_type) if change_type else None


# 盘口异动字段 -> 默认中文列名（akshare 只有 时间/代码/名称/板块/相关信息，其“板块”列实为异动类型）
STOCK_CHANGES_COLUMNS_ZH: dict[str, str] = {
    "time": "时间",
    "code": "代码",
    "name": "名称",
    "market": "市场",
    "change_type": "异动类型",
    "price": "价格",
    "change_pct": "涨跌幅",
    "volume": "数量",
    "amount": "金额",
    "info": "相关信息",
}
# 数量 / 金额只有这四类有（成交量 / 成交额或挂单量 / 挂单金额），其余类型不输出这两列
STOCK_CHANGES_TRADE_TYPES = frozenset({"big_buy", "big_sell", "big_bid", "big_ask"})


def stock_changes_fields(change_type: str) -> tuple[str, ...]:
    """某类盘口异动在 DataFrame 中输出的字段与顺序。"""
    trade = ("volume", "amount") if change_type in STOCK_CHANGES_TRADE_TYPES else ()
    return (
        "time",
        "code",
        "name",
        "market",
        "change_type",
        "price",
        "change_pct",
        *trade,
        "info",
    )


def to_stock_changes_dataframe(
    page: StockChangesPage,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """把 ``StockChangesPage`` 转为 ``DataFrame``；异动类型显示中文名，空页也保留列头。"""
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - 环境依赖
        raise ImportError(
            "pandas 未安装：pip install emshare[pandas] 或 pip install pandas"
        ) from exc

    fields = stock_changes_fields(page.change_type)
    naming = columns or STOCK_CHANGES_COLUMNS_ZH
    rows = [
        {
            naming[f]: _change_label(c.change_type) if f == "change_type" else getattr(c, f)
            for f in fields
        }
        for c in page.items
    ]
    return pd.DataFrame(rows, columns=[naming[f] for f in fields])  # type: ignore[no-any-return]


# 板块异动字段 -> 默认中文列名（对齐 akshare stock_board_change_em；另加板块代码与最频繁个股的市场，
# akshare 的“买卖方向”实为把市场前缀 m 误当方向，这里换成该股的异动类型）
BOARD_CHANGES_COLUMNS_ZH: dict[str, str] = {
    "code": "板块代码",
    "name": "板块名称",
    "change_pct": "涨跌幅",
    "main_net_inflow": "主力净流入",
    "change_count": "板块异动总次数",
    "top_stock_code": "板块异动最频繁个股及所属类型-股票代码",
    "top_stock_name": "板块异动最频繁个股及所属类型-股票名称",
    "top_stock_market": "板块异动最频繁个股及所属类型-市场",
    "top_stock_change_type": "板块异动最频繁个股及所属类型-异动类型",
    "type_counts": "板块具体异动类型列表及出现次数",
}


def to_board_changes_dataframe(
    page: BoardChangesPage,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """把 ``BoardChangesPage`` 转为 ``DataFrame``；各类异动次数放成 ``{中文类型: 次数}`` 字典。"""
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - 环境依赖
        raise ImportError(
            "pandas 未安装：pip install emshare[pandas] 或 pip install pandas"
        ) from exc

    naming = columns or BOARD_CHANGES_COLUMNS_ZH
    rows: list[dict[str, object]] = []
    for b in page.items:
        row = {naming[f]: getattr(b, f) for f in BOARD_CHANGES_COLUMNS_ZH}
        row[naming["top_stock_change_type"]] = _change_label(b.top_stock_change_type)
        row[naming["type_counts"]] = {
            CHANGE_TYPE_LABELS_ZH.get(t.change_type, t.change_type): t.count for t in b.type_counts
        }
        rows.append(row)
    return pd.DataFrame(  # type: ignore[no-any-return]
        rows, columns=[naming[f] for f in BOARD_CHANGES_COLUMNS_ZH]
    )


def _records_frame(
    items: tuple[object, ...], naming: dict[str, str], fields: tuple[str, ...]
) -> pd.DataFrame:
    """把一组领域对象按 ``fields`` 顺序转成 DataFrame；空结果也保留列头。"""
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - 环境依赖
        raise ImportError(
            "pandas 未安装：pip install emshare[pandas] 或 pip install pandas"
        ) from exc
    rows = [{naming[f]: getattr(item, f) for f in fields} for item in items]
    return pd.DataFrame(rows, columns=[naming[f] for f in fields])  # type: ignore[no-any-return]


# 龙虎榜详情字段 -> 默认中文列名（对齐 akshare stock_lhb_detail_em，另在名称后加“市场”）
BILLBOARD_DETAIL_COLUMNS_ZH: dict[str, str] = {
    "code": "代码",
    "name": "名称",
    "market": "市场",
    "trade_date": "上榜日",
    "interpretation": "解读",
    "close": "收盘价",
    "change_pct": "涨跌幅",
    "net_buy": "龙虎榜净买额",
    "buy": "龙虎榜买入额",
    "sell": "龙虎榜卖出额",
    "billboard_turnover": "龙虎榜成交额",
    "turnover": "市场总成交额",
    "net_buy_ratio": "净买额占总成交比",
    "billboard_turnover_ratio": "成交额占总成交比",
    "turnover_rate": "换手率",
    "float_market_cap": "流通市值",
    "reason": "上榜原因",
    "change_after_1d": "上榜后1日",
    "change_after_2d": "上榜后2日",
    "change_after_5d": "上榜后5日",
    "change_after_10d": "上榜后10日",
}


def to_billboard_detail_dataframe(
    page: ReportPage[BillboardEntry], columns: dict[str, str] | None = None
) -> pd.DataFrame:
    """把龙虎榜详情转为 ``DataFrame``，列顺序同 akshare（另加“市场”）。"""
    naming = columns or BILLBOARD_DETAIL_COLUMNS_ZH
    return _records_frame(page.items, naming, tuple(BILLBOARD_DETAIL_COLUMNS_ZH))


# 个股上榜统计字段 -> 默认中文列名（对齐 akshare stock_lhb_stock_statistic_em，另在名称后加“市场”）
BILLBOARD_STOCK_STATS_COLUMNS_ZH: dict[str, str] = {
    "code": "代码",
    "name": "名称",
    "market": "市场",
    "latest_date": "最近上榜日",
    "close": "收盘价",
    "change_pct": "涨跌幅",
    "billboard_times": "上榜次数",
    "net_buy": "龙虎榜净买额",
    "buy": "龙虎榜买入额",
    "sell": "龙虎榜卖出额",
    "billboard_turnover": "龙虎榜总成交额",
    "institution_buy_times": "买方机构次数",
    "institution_sell_times": "卖方机构次数",
    "institution_net_buy": "机构买入净额",
    "institution_buy": "机构买入总额",
    "institution_sell": "机构卖出总额",
    "change_1mo": "近1个月涨跌幅",
    "change_3mo": "近3个月涨跌幅",
    "change_6mo": "近6个月涨跌幅",
    "change_1y": "近1年涨跌幅",
}


def to_billboard_stock_stats_dataframe(
    page: ReportPage[BillboardStockStats], columns: dict[str, str] | None = None
) -> pd.DataFrame:
    """把个股上榜统计转为 ``DataFrame``，列顺序同 akshare。"""
    naming = columns or BILLBOARD_STOCK_STATS_COLUMNS_ZH
    return _records_frame(page.items, naming, tuple(BILLBOARD_STOCK_STATS_COLUMNS_ZH))


# 机构买卖每日统计字段 -> 默认中文列名（对齐 akshare stock_lhb_jgmmtj_em，另在名称后加“市场”，末尾加上榜后 1 / 2 / 3 / 5 / 10 日涨跌幅）
BILLBOARD_INSTITUTION_COLUMNS_ZH: dict[str, str] = {
    "code": "代码",
    "name": "名称",
    "market": "市场",
    "close": "收盘价",
    "change_pct": "涨跌幅",
    "buy_institutions": "买方机构数",
    "sell_institutions": "卖方机构数",
    "institution_buy": "机构买入总额",
    "institution_sell": "机构卖出总额",
    "institution_net_buy": "机构买入净额",
    "turnover": "市场总成交额",
    "net_buy_ratio": "机构净买额占总成交额比",
    "turnover_rate": "换手率",
    "float_market_cap": "流通市值",
    "reason": "上榜原因",
    "trade_date": "上榜日期",
    "change_after_1d": "上榜后1日",
    "change_after_2d": "上榜后2日",
    "change_after_3d": "上榜后3日",
    "change_after_5d": "上榜后5日",
    "change_after_10d": "上榜后10日",
}


def to_billboard_institution_dataframe(
    page: ReportPage[BillboardInstitutionTrade], columns: dict[str, str] | None = None
) -> pd.DataFrame:
    """把机构买卖每日统计转为 ``DataFrame``，列顺序同 akshare。"""
    naming = columns or BILLBOARD_INSTITUTION_COLUMNS_ZH
    return _records_frame(page.items, naming, tuple(BILLBOARD_INSTITUTION_COLUMNS_ZH))


# 机构席位追踪字段 -> 默认中文列名（对齐 akshare stock_lhb_jgstatistic_em，另在名称后加“市场”）
BILLBOARD_INSTITUTION_STATS_COLUMNS_ZH: dict[str, str] = {
    "code": "代码",
    "name": "名称",
    "market": "市场",
    "close": "收盘价",
    "change_pct": "涨跌幅",
    "billboard_turnover": "龙虎榜成交金额",
    "billboard_times": "上榜次数",
    "institution_buy": "机构买入额",
    "institution_buy_times": "机构买入次数",
    "institution_sell": "机构卖出额",
    "institution_sell_times": "机构卖出次数",
    "institution_net_buy": "机构净买额",
    "change_1mo": "近1个月涨跌幅",
    "change_3mo": "近3个月涨跌幅",
    "change_6mo": "近6个月涨跌幅",
    "change_1y": "近1年涨跌幅",
}


def to_billboard_institution_stats_dataframe(
    page: ReportPage[BillboardInstitutionStats], columns: dict[str, str] | None = None
) -> pd.DataFrame:
    """把机构席位追踪转为 ``DataFrame``，列顺序同 akshare。"""
    naming = columns or BILLBOARD_INSTITUTION_STATS_COLUMNS_ZH
    return _records_frame(page.items, naming, tuple(BILLBOARD_INSTITUTION_STATS_COLUMNS_ZH))


# 每日活跃营业部字段 -> 默认中文列名（对齐 akshare stock_lhb_hyyyb_em，末尾加“买入股票代码”）。
# “买入股票”是 akshare 与东财页面的列名，实际含只卖出的股票，模型字段因此叫 stocks / stock_codes
BILLBOARD_BRANCH_ACTIVE_COLUMNS_ZH: dict[str, str] = {
    "branch_name": "营业部名称",
    "trade_date": "上榜日",
    "buy_stock_count": "买入个股数",
    "sell_stock_count": "卖出个股数",
    "buy": "买入总金额",
    "sell": "卖出总金额",
    "net_buy": "总买卖净额",
    "stocks": "买入股票",
    "branch_code": "营业部代码",
    "stock_codes": "买入股票代码",
}


def to_billboard_branch_active_dataframe(
    page: ReportPage[BillboardBranchActive], columns: dict[str, str] | None = None
) -> pd.DataFrame:
    """把每日活跃营业部转为 ``DataFrame``，列顺序同 akshare。"""
    naming = columns or BILLBOARD_BRANCH_ACTIVE_COLUMNS_ZH
    return _records_frame(page.items, naming, tuple(BILLBOARD_BRANCH_ACTIVE_COLUMNS_ZH))


# 营业部排行字段 -> 默认中文列名（对齐 akshare stock_lhb_yybph_em，末尾加“营业部代码”）
BILLBOARD_BRANCH_RANK_COLUMNS_ZH: dict[str, str] = {
    "branch_name": "营业部名称",
    "buy_times_1d": "上榜后1天-买入次数",
    "avg_change_1d": "上榜后1天-平均涨幅",
    "rise_prob_1d": "上榜后1天-上涨概率",
    "buy_times_2d": "上榜后2天-买入次数",
    "avg_change_2d": "上榜后2天-平均涨幅",
    "rise_prob_2d": "上榜后2天-上涨概率",
    "buy_times_3d": "上榜后3天-买入次数",
    "avg_change_3d": "上榜后3天-平均涨幅",
    "rise_prob_3d": "上榜后3天-上涨概率",
    "buy_times_5d": "上榜后5天-买入次数",
    "avg_change_5d": "上榜后5天-平均涨幅",
    "rise_prob_5d": "上榜后5天-上涨概率",
    "buy_times_10d": "上榜后10天-买入次数",
    "avg_change_10d": "上榜后10天-平均涨幅",
    "rise_prob_10d": "上榜后10天-上涨概率",
    "branch_code": "营业部代码",
}


def to_billboard_branch_rank_dataframe(
    page: ReportPage[BillboardBranchRank], columns: dict[str, str] | None = None
) -> pd.DataFrame:
    """把营业部排行转为 ``DataFrame``，列顺序同 akshare。"""
    naming = columns or BILLBOARD_BRANCH_RANK_COLUMNS_ZH
    return _records_frame(page.items, naming, tuple(BILLBOARD_BRANCH_RANK_COLUMNS_ZH))


# 营业部统计字段 -> 默认中文列名（对齐 akshare stock_lhb_traderstatistic_em，末尾加“营业部代码”）
BILLBOARD_BRANCH_STATS_COLUMNS_ZH: dict[str, str] = {
    "branch_name": "营业部名称",
    "billboard_turnover": "龙虎榜成交金额",
    "billboard_times": "上榜次数",
    "buy": "买入额",
    "buy_times": "买入次数",
    "sell": "卖出额",
    "sell_times": "卖出次数",
    "branch_code": "营业部代码",
}


def to_billboard_branch_stats_dataframe(
    page: ReportPage[BillboardBranchStats], columns: dict[str, str] | None = None
) -> pd.DataFrame:
    """把营业部统计转为 ``DataFrame``，列顺序同 akshare。"""
    naming = columns or BILLBOARD_BRANCH_STATS_COLUMNS_ZH
    return _records_frame(page.items, naming, tuple(BILLBOARD_BRANCH_STATS_COLUMNS_ZH))


# 营业部详情字段 -> 默认中文列名（对齐 akshare stock_lhb_yyb_detail_em，另在股票名称后加“市场”）
BILLBOARD_BRANCH_TRADES_COLUMNS_ZH: dict[str, str] = {
    "branch_code": "营业部代码",
    "branch_name": "营业部名称",
    "branch_short_name": "营业部简称",
    "trade_date": "交易日期",
    "code": "股票代码",
    "name": "股票名称",
    "market": "市场",
    "change_pct": "涨跌幅",
    "buy": "买入金额",
    "sell": "卖出金额",
    "net_buy": "净额",
    "reason": "上榜原因",
    "change_after_1d": "1日后涨跌幅",
    "change_after_2d": "2日后涨跌幅",
    "change_after_3d": "3日后涨跌幅",
    "change_after_5d": "5日后涨跌幅",
    "change_after_10d": "10日后涨跌幅",
    "change_after_20d": "20日后涨跌幅",
    "change_after_30d": "30日后涨跌幅",
}


def to_billboard_branch_trades_dataframe(
    page: ReportPage[BillboardBranchTrade], columns: dict[str, str] | None = None
) -> pd.DataFrame:
    """把营业部详情转为 ``DataFrame``，列顺序同 akshare。"""
    naming = columns or BILLBOARD_BRANCH_TRADES_COLUMNS_ZH
    return _records_frame(page.items, naming, tuple(BILLBOARD_BRANCH_TRADES_COLUMNS_ZH))


# 个股上榜日期字段 -> 默认中文列名（对齐 akshare stock_lhb_stock_detail_date_em）
BILLBOARD_STOCK_DATES_COLUMNS_ZH: dict[str, str] = {
    "code": "股票代码",
    "trade_date": "交易日",
}


def to_billboard_stock_dates_dataframe(
    page: ReportPage[BillboardStockDate], columns: dict[str, str] | None = None
) -> pd.DataFrame:
    """把个股上榜日期转为 ``DataFrame``，列顺序同 akshare。"""
    naming = columns or BILLBOARD_STOCK_DATES_COLUMNS_ZH
    return _records_frame(page.items, naming, tuple(BILLBOARD_STOCK_DATES_COLUMNS_ZH))


# 个股龙虎榜详情字段 -> 默认中文列名（对齐 akshare stock_lhb_stock_detail_em，末尾加营业部代码、代码、市场、上榜日、收盘价、涨跌幅、总成交额）
BILLBOARD_STOCK_COLUMNS_ZH: dict[str, str] = {
    "branch_name": "交易营业部名称",
    "buy": "买入金额",
    "buy_ratio": "买入金额-占总成交比例",
    "sell": "卖出金额",
    "sell_ratio": "卖出金额-占总成交比例",
    "net_buy": "净额",
    "reason": "类型",
    "branch_code": "营业部代码",
    "code": "代码",
    "market": "市场",
    "trade_date": "上榜日",
    "close": "收盘价",
    "change_pct": "涨跌幅",
    "turnover": "总成交额",
}


def to_billboard_stock_dataframe(
    page: ReportPage[BillboardSeat], columns: dict[str, str] | None = None
) -> pd.DataFrame:
    """把个股龙虎榜详情转为 ``DataFrame``，列顺序同 akshare。"""
    naming = columns or BILLBOARD_STOCK_COLUMNS_ZH
    return _records_frame(page.items, naming, tuple(BILLBOARD_STOCK_COLUMNS_ZH))


# 大宗交易市场统计字段 -> 默认中文列名（对齐 akshare stock_dzjy_sctj）
BLOCK_TRADE_MARKET_DAILY_COLUMNS_ZH: dict[str, str] = {
    "trade_date": "交易日期",
    "sh_index": "上证指数",
    "sh_index_change_pct": "上证指数涨跌幅",
    "amount": "大宗交易成交总额",
    "premium_amount": "溢价成交总额",
    "premium_ratio": "溢价成交总额占比",
    "discount_amount": "折价成交总额",
    "discount_ratio": "折价成交总额占比",
}


def to_block_trade_market_daily_dataframe(
    page: ReportPage[BlockTradeMarketDaily], columns: dict[str, str] | None = None
) -> pd.DataFrame:
    """把大宗交易市场统计转为 ``DataFrame``，列顺序同 akshare。"""
    naming = columns or BLOCK_TRADE_MARKET_DAILY_COLUMNS_ZH
    return _records_frame(page.items, naming, tuple(BLOCK_TRADE_MARKET_DAILY_COLUMNS_ZH))


# 大宗交易每日明细字段 -> 默认中文列名（对齐 akshare stock_dzjy_mrmx 的 A 股列，另在证券简称后加“市场”，
# 末尾加买卖方营业部代码与 1 / 5 / 10 / 20 日后涨跌幅）
BLOCK_TRADE_DETAIL_COLUMNS_ZH: dict[str, str] = {
    "trade_date": "交易日期",
    "code": "证券代码",
    "name": "证券简称",
    "market": "市场",
    "change_pct": "涨跌幅",
    "close": "收盘价",
    "price": "成交价",
    "premium_rate": "折溢率",
    "volume": "成交量",
    "amount": "成交额",
    "float_market_cap_ratio": "成交额/流通市值",
    "buyer_name": "买方营业部",
    "seller_name": "卖方营业部",
    "buyer_code": "买方营业部代码",
    "seller_code": "卖方营业部代码",
    "change_after_1d": "1日后涨跌幅",
    "change_after_5d": "5日后涨跌幅",
    "change_after_10d": "10日后涨跌幅",
    "change_after_20d": "20日后涨跌幅",
}


def to_block_trade_detail_dataframe(
    page: ReportPage[BlockTrade], columns: dict[str, str] | None = None
) -> pd.DataFrame:
    """把大宗交易每日明细转为 ``DataFrame``，列顺序同 akshare。"""
    naming = columns or BLOCK_TRADE_DETAIL_COLUMNS_ZH
    return _records_frame(page.items, naming, tuple(BLOCK_TRADE_DETAIL_COLUMNS_ZH))


# 大宗交易每日统计字段 -> 默认中文列名（对齐 akshare stock_dzjy_mrtj，另在证券简称后加“市场”，
# 末尾加溢价 / 折价笔数与 1 / 5 / 10 / 20 日后涨跌幅）。“成交价”是 akshare 的列名，实际是成交均价
BLOCK_TRADE_STOCK_DAILY_COLUMNS_ZH: dict[str, str] = {
    "trade_date": "交易日期",
    "code": "证券代码",
    "name": "证券简称",
    "market": "市场",
    "change_pct": "涨跌幅",
    "close": "收盘价",
    "avg_price": "成交价",
    "premium_rate": "折溢率",
    "deal_times": "成交笔数",
    "volume": "成交总量",
    "amount": "成交总额",
    "float_market_cap_ratio": "成交总额/流通市值",
    "premium_times": "溢价笔数",
    "discount_times": "折价笔数",
    "change_after_1d": "1日后涨跌幅",
    "change_after_5d": "5日后涨跌幅",
    "change_after_10d": "10日后涨跌幅",
    "change_after_20d": "20日后涨跌幅",
}


def to_block_trade_stock_daily_dataframe(
    page: ReportPage[BlockTradeStockDaily], columns: dict[str, str] | None = None
) -> pd.DataFrame:
    """把大宗交易每日统计转为 ``DataFrame``，列顺序同 akshare。"""
    naming = columns or BLOCK_TRADE_STOCK_DAILY_COLUMNS_ZH
    return _records_frame(page.items, naming, tuple(BLOCK_TRADE_STOCK_DAILY_COLUMNS_ZH))


# 活跃 A 股统计字段 -> 默认中文列名（对齐 akshare stock_dzjy_hygtj，另在证券简称后加“市场”）。
# “最新价”“上榜次数”是 akshare 的列名，实际是最近上榜日的收盘价与成交笔数
BLOCK_TRADE_STOCK_STATS_COLUMNS_ZH: dict[str, str] = {
    "code": "证券代码",
    "name": "证券简称",
    "market": "市场",
    "close": "最新价",
    "change_pct": "涨跌幅",
    "latest_date": "最近上榜日",
    "deal_times": "上榜次数-总计",
    "premium_times": "上榜次数-溢价",
    "discount_times": "上榜次数-折价",
    "amount": "总成交额",
    "premium_rate": "折溢率",
    "float_market_cap_ratio": "成交总额/流通市值",
    "avg_change_after_1d": "上榜日后平均涨跌幅-1日",
    "avg_change_after_5d": "上榜日后平均涨跌幅-5日",
    "avg_change_after_10d": "上榜日后平均涨跌幅-10日",
    "avg_change_after_20d": "上榜日后平均涨跌幅-20日",
}


def to_block_trade_stock_stats_dataframe(
    page: ReportPage[BlockTradeStockStats], columns: dict[str, str] | None = None
) -> pd.DataFrame:
    """把活跃 A 股统计转为 ``DataFrame``，列顺序同 akshare。"""
    naming = columns or BLOCK_TRADE_STOCK_STATS_COLUMNS_ZH
    return _records_frame(page.items, naming, tuple(BLOCK_TRADE_STOCK_STATS_COLUMNS_ZH))


# 活跃营业部统计字段 -> 默认中文列名（对齐 akshare stock_dzjy_hyyybtj，末尾加“营业部代码”“买入股票代码”）
BLOCK_TRADE_BRANCH_ACTIVE_COLUMNS_ZH: dict[str, str] = {
    "latest_date": "最近上榜日",
    "branch_name": "营业部名称",
    "buy_times": "次数总计-买入",
    "sell_times": "次数总计-卖出",
    "buy": "成交金额统计-买入",
    "sell": "成交金额统计-卖出",
    "net_buy": "成交金额统计-净买入额",
    "buy_stocks": "买入的股票",
    "branch_code": "营业部代码",
    "buy_stock_codes": "买入股票代码",
}


def to_block_trade_branch_active_dataframe(
    page: ReportPage[BlockTradeBranchActive], columns: dict[str, str] | None = None
) -> pd.DataFrame:
    """把活跃营业部统计转为 ``DataFrame``，列顺序同 akshare。"""
    naming = columns or BLOCK_TRADE_BRANCH_ACTIVE_COLUMNS_ZH
    return _records_frame(page.items, naming, tuple(BLOCK_TRADE_BRANCH_ACTIVE_COLUMNS_ZH))


# 大宗交易营业部排行字段 -> 默认中文列名（对齐 akshare stock_dzjy_yybph，末尾加“营业部代码”）
BLOCK_TRADE_BRANCH_RANK_COLUMNS_ZH: dict[str, str] = {
    "branch_name": "营业部名称",
    "buy_times_1d": "上榜后1天-买入次数",
    "avg_change_1d": "上榜后1天-平均涨幅",
    "rise_prob_1d": "上榜后1天-上涨概率",
    "buy_times_5d": "上榜后5天-买入次数",
    "avg_change_5d": "上榜后5天-平均涨幅",
    "rise_prob_5d": "上榜后5天-上涨概率",
    "buy_times_10d": "上榜后10天-买入次数",
    "avg_change_10d": "上榜后10天-平均涨幅",
    "rise_prob_10d": "上榜后10天-上涨概率",
    "buy_times_20d": "上榜后20天-买入次数",
    "avg_change_20d": "上榜后20天-平均涨幅",
    "rise_prob_20d": "上榜后20天-上涨概率",
    "branch_code": "营业部代码",
}


def to_block_trade_branch_rank_dataframe(
    page: ReportPage[BlockTradeBranchRank], columns: dict[str, str] | None = None
) -> pd.DataFrame:
    """把大宗交易营业部排行转为 ``DataFrame``，列顺序同 akshare。"""
    naming = columns or BLOCK_TRADE_BRANCH_RANK_COLUMNS_ZH
    return _records_frame(page.items, naming, tuple(BLOCK_TRADE_BRANCH_RANK_COLUMNS_ZH))


# 业绩报告字段 -> 默认中文列名（akshare 有的列沿用其列名）
EARNINGS_REPORT_COLUMNS_ZH: dict[str, str] = {
    "code": "股票代码",
    "name": "股票简称",
    "market": "市场",
    "report_date": "报告期",
    "eps": "每股收益",
    "deducted_eps": "扣非每股收益",
    "revenue": "营业总收入-营业总收入",
    "revenue_yoy": "营业总收入-同比增长",
    "revenue_qoq": "营业总收入-季度环比增长",
    "net_profit": "净利润-净利润",
    "net_profit_yoy": "净利润-同比增长",
    "net_profit_qoq": "净利润-季度环比增长",
    "bps": "每股净资产",
    "roe": "净资产收益率",
    "cash_flow_per_share": "每股经营现金流量",
    "gross_margin": "销售毛利率",
    "dividend_plan": "利润分配",
    "dividend_yield": "股息率",
    "industry": "所处行业",
    "notice_date": "首次公告日期",
    "update_date": "最新公告日期",
}


def to_earnings_report_dataframe(
    page: ReportPage[EarningsReport], columns: dict[str, str] | None = None
) -> pd.DataFrame:
    """把业绩报告转为 ``DataFrame``（中文列名）。"""
    naming = columns or EARNINGS_REPORT_COLUMNS_ZH
    return _records_frame(page.items, naming, tuple(EARNINGS_REPORT_COLUMNS_ZH))


# 业绩快报字段 -> 默认中文列名（akshare 有的列沿用其列名）
EARNINGS_EXPRESS_COLUMNS_ZH: dict[str, str] = {
    "code": "股票代码",
    "name": "股票简称",
    "market": "市场",
    "report_date": "报告期",
    "eps": "每股收益",
    "revenue": "营业收入-营业收入",
    "revenue_prev_year": "营业收入-去年同期",
    "revenue_yoy": "营业收入-同比增长",
    "revenue_qoq": "营业收入-季度环比增长",
    "net_profit": "净利润-净利润",
    "net_profit_prev_year": "净利润-去年同期",
    "net_profit_yoy": "净利润-同比增长",
    "net_profit_qoq": "净利润-季度环比增长",
    "bps": "每股净资产",
    "roe": "净资产收益率",
    "industry": "所处行业",
    "notice_date": "公告日期",
    "update_date": "最新公告日期",
}


def to_earnings_express_dataframe(
    page: ReportPage[EarningsExpress], columns: dict[str, str] | None = None
) -> pd.DataFrame:
    """把业绩快报转为 ``DataFrame``（中文列名）。"""
    naming = columns or EARNINGS_EXPRESS_COLUMNS_ZH
    return _records_frame(page.items, naming, tuple(EARNINGS_EXPRESS_COLUMNS_ZH))


# 业绩预告字段 -> 默认中文列名（akshare 有的列沿用其列名）
EARNINGS_FORECAST_COLUMNS_ZH: dict[str, str] = {
    "code": "股票代码",
    "name": "股票简称",
    "market": "市场",
    "report_date": "报告期",
    "notice_date": "公告日期",
    "indicator": "预测指标",
    "summary": "业绩变动",
    "forecast_value": "预测数值",
    "lower": "预测下限",
    "upper": "预测上限",
    "change_pct": "业绩变动幅度",
    "change_pct_lower": "变动幅度下限",
    "change_pct_upper": "变动幅度上限",
    "reason": "业绩变动原因",
    "forecast_type": "预告类型",
    "prev_year": "上年同期值",
}


def to_earnings_forecast_dataframe(
    page: ReportPage[EarningsForecast], columns: dict[str, str] | None = None
) -> pd.DataFrame:
    """把业绩预告转为 ``DataFrame``（中文列名）。"""
    naming = columns or EARNINGS_FORECAST_COLUMNS_ZH
    return _records_frame(page.items, naming, tuple(EARNINGS_FORECAST_COLUMNS_ZH))


# 预约披露时间字段 -> 默认中文列名（akshare 有的列沿用其列名）
EARNINGS_SCHEDULE_COLUMNS_ZH: dict[str, str] = {
    "code": "股票代码",
    "name": "股票简称",
    "market": "市场",
    "report_date": "报告期",
    "first_appoint_date": "首次预约时间",
    "first_change_date": "一次变更日期",
    "second_change_date": "二次变更日期",
    "third_change_date": "三次变更日期",
    "appoint_date": "最新预约时间",
    "actual_date": "实际披露时间",
}


def to_earnings_schedule_dataframe(
    page: ReportPage[EarningsSchedule], columns: dict[str, str] | None = None
) -> pd.DataFrame:
    """把预约披露时间转为 ``DataFrame``（中文列名）。"""
    naming = columns or EARNINGS_SCHEDULE_COLUMNS_ZH
    return _records_frame(page.items, naming, tuple(EARNINGS_SCHEDULE_COLUMNS_ZH))


# 资产负债表字段 -> 默认中文列名（akshare 有的列沿用其列名）
BALANCE_SHEET_COLUMNS_ZH: dict[str, str] = {
    "code": "股票代码",
    "name": "股票简称",
    "market": "市场",
    "industry": "所处行业",
    "report_date": "报告期",
    "notice_date": "公告日期",
    "cash": "资产-货币资金",
    "cash_yoy": "资产-货币资金同比",
    "accounts_receivable": "资产-应收账款",
    "accounts_receivable_yoy": "资产-应收账款同比",
    "inventory": "资产-存货",
    "inventory_yoy": "资产-存货同比",
    "fixed_assets": "资产-固定资产",
    "total_assets": "资产-总资产",
    "total_assets_yoy": "资产-总资产同比",
    "accounts_payable": "负债-应付账款",
    "accounts_payable_yoy": "负债-应付账款同比",
    "advance_receipts": "负债-预收账款",
    "advance_receipts_yoy": "负债-预收账款同比",
    "total_liabilities": "负债-总负债",
    "total_liabilities_yoy": "负债-总负债同比",
    "debt_asset_ratio": "资产负债率",
    "current_ratio": "流动比率",
    "total_equity": "股东权益合计",
    "total_equity_yoy": "股东权益同比",
    "cash_deposit_pbc": "银行-现金及存放中央银行款项",
    "cash_deposit_pbc_yoy": "银行-现金及存放中央银行款项同比",
    "loans_advances": "银行-发放贷款及垫款",
    "loans_advances_yoy": "银行-发放贷款及垫款同比",
    "available_for_sale_assets": "银行-可供出售金融资产",
    "available_for_sale_assets_yoy": "银行-可供出售金融资产同比",
    "borrowings_from_pbc": "银行-向中央银行借款",
    "borrowings_from_pbc_yoy": "银行-向中央银行借款同比",
    "deposits": "银行-吸收存款",
    "deposits_yoy": "银行-吸收存款同比",
    "repo_sold": "金融-卖出回购金融资产款",
    "repo_sold_yoy": "金融-卖出回购金融资产款同比",
    "settlement_reserves": "券商-结算备付金",
    "settlement_reserves_yoy": "券商-结算备付金同比",
    "interbank_borrowings": "券商-拆入资金",
    "interbank_borrowings_yoy": "券商-拆入资金同比",
    "customer_brokerage_deposits": "券商-代理买卖证券款",
    "customer_brokerage_deposits_yoy": "券商-代理买卖证券款同比",
    "premiums_receivable": "保险-应收保费",
    "premiums_receivable_yoy": "保险-应收保费同比",
    "short_term_loans": "保险-短期借款",
    "short_term_loans_yoy": "保险-短期借款同比",
    "advance_premiums": "保险-预收保费",
    "advance_premiums_yoy": "保险-预收保费同比",
}


def to_balance_sheet_dataframe(
    page: ReportPage[BalanceSheet], columns: dict[str, str] | None = None
) -> pd.DataFrame:
    """把资产负债表转为 ``DataFrame``（中文列名）。"""
    naming = columns or BALANCE_SHEET_COLUMNS_ZH
    return _records_frame(page.items, naming, tuple(BALANCE_SHEET_COLUMNS_ZH))


# 利润表字段 -> 默认中文列名（akshare 有的列沿用其列名）
INCOME_STATEMENT_COLUMNS_ZH: dict[str, str] = {
    "code": "股票代码",
    "name": "股票简称",
    "market": "市场",
    "industry": "所处行业",
    "report_date": "报告期",
    "notice_date": "公告日期",
    "net_profit": "净利润",
    "net_profit_yoy": "净利润同比",
    "deducted_net_profit": "扣非净利润",
    "deducted_net_profit_yoy": "扣非净利润同比",
    "revenue": "营业总收入",
    "revenue_yoy": "营业总收入同比",
    "operating_expense": "营业总支出-营业支出",
    "operating_expense_yoy": "营业总支出-营业支出同比",
    "operating_cost": "营业总支出-营业成本",
    "selling_expense": "营业总支出-销售费用",
    "admin_expense": "营业总支出-管理费用",
    "finance_expense": "营业总支出-财务费用",
    "taxes_and_surcharges": "营业总支出-税金及附加",
    "total_operating_cost": "营业总支出-营业总支出",
    "total_operating_cost_yoy": "营业总支出-营业总支出同比",
    "operating_profit": "营业利润",
    "operating_profit_yoy": "营业利润同比",
    "total_profit": "利润总额",
    "income_tax": "所得税",
    "operating_income": "金融-营业收入",
    "net_interest_income": "金融-利息净收入",
    "net_interest_income_yoy": "金融-利息净收入同比",
    "net_fee_income": "金融-手续费及佣金净收入",
    "net_fee_income_yoy": "金融-手续费及佣金净收入同比",
    "business_admin_expense": "银行-业务及管理费",
    "earned_premiums": "保险-已赚保费",
    "earned_premiums_yoy": "保险-已赚保费同比",
    "investment_income": "保险-投资收益",
    "surrenders": "保险-退保金",
    "claims_expense": "保险-赔付支出",
}


def to_income_statement_dataframe(
    page: ReportPage[IncomeStatement], columns: dict[str, str] | None = None
) -> pd.DataFrame:
    """把利润表转为 ``DataFrame``（中文列名）。"""
    naming = columns or INCOME_STATEMENT_COLUMNS_ZH
    return _records_frame(page.items, naming, tuple(INCOME_STATEMENT_COLUMNS_ZH))


# 现金流量表字段 -> 默认中文列名（akshare 有的列沿用其列名）
CASH_FLOW_STATEMENT_COLUMNS_ZH: dict[str, str] = {
    "code": "股票代码",
    "name": "股票简称",
    "market": "市场",
    "industry": "所处行业",
    "report_date": "报告期",
    "notice_date": "公告日期",
    "net_cash_flow": "净现金流-净现金流",
    "net_cash_flow_yoy": "净现金流-同比增长",
    "operating_net": "经营性现金流-现金流量净额",
    "operating_net_share": "经营性现金流-净现金流占比",
    "sales_cash": "经营性现金流-销售商品收到的现金",
    "sales_cash_share": "经营性现金流-销售商品收到的现金占比",
    "staff_cash_paid": "经营性现金流-支付给职工的现金",
    "staff_cash_paid_share": "经营性现金流-支付给职工的现金占比",
    "investing_net": "投资性现金流-现金流量净额",
    "investing_net_share": "投资性现金流-净现金流占比",
    "investment_income_cash": "投资性现金流-取得投资收益收到的现金",
    "investment_income_cash_share": "投资性现金流-取得投资收益收到的现金占比",
    "capex": "投资性现金流-购建长期资产支付的现金",
    "capex_share": "投资性现金流-购建长期资产支付的现金占比",
    "financing_net": "融资性现金流-现金流量净额",
    "financing_net_share": "融资性现金流-净现金流占比",
    "customer_deposits_increase": "银行-客户存款净增加额",
    "customer_deposits_increase_share": "银行-客户存款净增加额占比",
    "interbank_deposits_increase": "银行-同业及其他金融机构存放款净增加额",
    "interbank_deposits_increase_share": "银行-同业及其他金融机构存放款净增加额占比",
    "loans_increase": "银行-客户贷款及垫款净增加额",
    "loans_increase_share": "银行-客户贷款及垫款净增加额占比",
    "interest_commission_cash": "券商-收取利息手续费及佣金的现金",
    "interest_commission_cash_share": "券商-收取利息手续费及佣金的现金占比",
    "investment_cash_paid": "金融-投资支付的现金",
    "investment_cash_paid_share": "金融-投资支付的现金占比",
    "begin_cash": "券商-期初现金及现金等价物余额",
    "begin_cash_share": "券商-期初现金及现金等价物余额占比",
    "end_cash": "券商-期末现金及现金等价物余额",
    "end_cash_share": "券商-期末现金及现金等价物余额占比",
    "premiums_cash": "保险-收到原保险合同保费取得的现金",
    "premiums_cash_share": "保险-收到原保险合同保费取得的现金占比",
    "claims_cash_paid": "保险-支付原保险合同赔付款项的现金",
    "claims_cash_paid_share": "保险-支付原保险合同赔付款项的现金占比",
}


def to_cash_flow_statement_dataframe(
    page: ReportPage[CashFlowStatement], columns: dict[str, str] | None = None
) -> pd.DataFrame:
    """把现金流量表转为 ``DataFrame``（中文列名）。"""
    naming = columns or CASH_FLOW_STATEMENT_COLUMNS_ZH
    return _records_frame(page.items, naming, tuple(CASH_FLOW_STATEMENT_COLUMNS_ZH))

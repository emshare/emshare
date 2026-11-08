"""DataFrame 适配：把领域模型 ``QuotePage`` 转为 pandas DataFrame。

pandas 为可选依赖（``pip install em[pandas]``），此处延迟导入，缺失时给清晰错误。
默认列名对齐 akshare 传统中文风格（代码 / 名称 / 最新价 / 涨跌幅 ...），传 ``columns`` 可覆盖。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from em.domain.models import (
    BoardFundFlowSeries,
    BoardListPage,
    FundFlowSeries,
    FundListPage,
    HkStockListPage,
    IndexListPage,
    KlineSeries,
    LimitPoolPage,
    QuotePage,
    StockBidAsk,
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
        raise ImportError("pandas 未安装：pip install em[pandas] 或 pip install pandas") from exc

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
        raise ImportError("pandas 未安装：pip install em[pandas] 或 pip install pandas") from exc

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
        raise ImportError("pandas 未安装：pip install em[pandas] 或 pip install pandas") from exc

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
        raise ImportError("pandas 未安装：pip install em[pandas] 或 pip install pandas") from exc

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
        raise ImportError("pandas 未安装：pip install em[pandas] 或 pip install pandas") from exc

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
        raise ImportError("pandas 未安装：pip install em[pandas] 或 pip install pandas") from exc

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
        raise ImportError("pandas 未安装：pip install em[pandas] 或 pip install pandas") from exc

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
        raise ImportError("pandas 未安装：pip install em[pandas] 或 pip install pandas") from exc

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
        raise ImportError("pandas 未安装：pip install em[pandas] 或 pip install pandas") from exc

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
        raise ImportError("pandas 未安装：pip install em[pandas] 或 pip install pandas") from exc

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
        raise ImportError("pandas 未安装：pip install em[pandas] 或 pip install pandas") from exc
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

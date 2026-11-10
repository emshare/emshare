"""DataFrame 适配：把领域模型 ``QuotePage`` 转为 pandas DataFrame。

pandas 为可选依赖（``pip install em[pandas]``），此处延迟导入，缺失时给清晰错误。
默认列名对齐 akshare 传统中文风格（代码 / 名称 / 最新价 / 涨跌幅 ...），传 ``columns`` 可覆盖。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from em.domain.models import (
    BillboardEntry,
    BoardChangesPage,
    BoardFundFlowSeries,
    BoardListPage,
    FundFlowSeries,
    FundListPage,
    HkStockListPage,
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
        raise ImportError("pandas 未安装：pip install em[pandas] 或 pip install pandas") from exc

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
        raise ImportError("pandas 未安装：pip install em[pandas] 或 pip install pandas") from exc

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
        raise ImportError("pandas 未安装：pip install em[pandas] 或 pip install pandas") from exc
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

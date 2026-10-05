"""DataFrame 适配：把领域模型 ``QuotePage`` 转为 pandas DataFrame。

pandas 为可选依赖（``pip install em[pandas]``），此处延迟导入，缺失时给清晰错误。
默认列名对齐 akshare 传统中文风格（代码 / 名称 / 最新价 / 涨跌幅 ...），传 ``columns`` 可覆盖。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from em.domain.models import (
    BoardFundFlowSeries,
    FundFlowSeries,
    KlineSeries,
    QuotePage,
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

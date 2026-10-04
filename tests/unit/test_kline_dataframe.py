"""K 线 DataFrame 适配的行为锁（用固定 KlineSeries，不触网）。"""

import pytest

from em.application.dataframe import KLINES_COLUMNS_ZH, to_kline_dataframe
from em.domain.models import Kline, KlineSeries

pd = pytest.importorskip("pandas")


def _sample() -> KlineSeries:
    return KlineSeries(
        code="000001",
        name="平安银行",
        period="day",
        adjust="qfq",
        items=(
            Kline(date="2024-12-30", open=11.35, close=11.40, change_pct=0.53),
            Kline(date="2024-12-31", open=11.40, close=11.32, change_pct=-0.70),
        ),
    )


def test_default_chinese_columns() -> None:
    df = to_kline_dataframe(_sample())
    assert list(df.columns) == [
        "日期",
        "开盘",
        "收盘",
        "最高",
        "最低",
        "成交量",
        "成交额",
        "振幅",
        "涨跌幅",
        "涨跌额",
        "换手率",
    ]
    assert len(df) == 2
    assert df.iloc[0]["日期"] == "2024-12-30"
    assert df.iloc[0]["开盘"] == pytest.approx(11.35)
    assert df.iloc[1]["涨跌幅"] == pytest.approx(-0.70)


def test_missing_fields_become_nan() -> None:
    df = to_kline_dataframe(_sample())
    assert pd.isna(df.iloc[0]["最高"])
    assert pd.isna(df.iloc[1]["成交量"])


def test_empty_series_keeps_columns() -> None:
    df = to_kline_dataframe(KlineSeries(code="x", name="y", period="day", adjust="qfq", items=()))
    assert list(df.columns) == list(KLINES_COLUMNS_ZH.values())
    assert len(df) == 0


def test_custom_columns_override() -> None:
    custom = {f: f.upper() for f in KLINES_COLUMNS_ZH}
    df = to_kline_dataframe(_sample(), columns=custom)
    assert list(df.columns) == [f.upper() for f in KLINES_COLUMNS_ZH]
    assert df.iloc[0]["DATE"] == "2024-12-30"

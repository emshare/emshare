"""分时 DataFrame 适配的行为锁（用固定 TrendSeries，不触网）。"""

import pytest

from em.application.dataframe import TRENDS_COLUMNS_ZH, to_trend_dataframe
from em.domain.models import Trend, TrendSeries

pd = pytest.importorskip("pandas")


def _sample() -> TrendSeries:
    return TrendSeries(
        code="000001",
        name="平安银行",
        pre_close=11.35,
        pre_price=11.35,
        ndays=1,
        items=(
            Trend(time="2026-09-30 09:30", price=11.36, avg_price=11.36, volume=2625),
            Trend(time="2026-09-30 09:31", price=11.34, avg_price=11.39, volume=18271),
        ),
    )


def test_default_chinese_columns() -> None:
    df = to_trend_dataframe(_sample())
    assert list(df.columns) == [
        "时间",
        "最新价",
        "均价",
        "最高",
        "最低",
        "成交量",
        "成交额",
        "均价2",
    ]
    assert len(df) == 2
    assert df.iloc[0]["时间"] == "2026-09-30 09:30"
    assert df.iloc[0]["最新价"] == pytest.approx(11.36)


def test_missing_fields_become_nan() -> None:
    df = to_trend_dataframe(_sample())
    assert pd.isna(df.iloc[0]["最高"])
    assert pd.isna(df.iloc[1]["成交额"])


def test_empty_series_keeps_columns() -> None:
    df = to_trend_dataframe(
        TrendSeries(code="x", name="y", pre_close=1.0, pre_price=1.0, ndays=1, items=())
    )
    assert list(df.columns) == list(TRENDS_COLUMNS_ZH.values())
    assert len(df) == 0


def test_custom_columns_override() -> None:
    custom = {f: f.upper() for f in TRENDS_COLUMNS_ZH}
    df = to_trend_dataframe(_sample(), columns=custom)
    assert list(df.columns) == [f.upper() for f in TRENDS_COLUMNS_ZH]
    assert df.iloc[0]["TIME"] == "2026-09-30 09:30"

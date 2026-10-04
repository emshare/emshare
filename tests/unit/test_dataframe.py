"""DataFrame 适配的行为锁（用固定 QuotePage，不触网）。"""

import pytest

from em.application.dataframe import COLUMNS_ZH, to_dataframe
from em.domain.models import Quote, QuotePage

pd = pytest.importorskip("pandas")


def _sample() -> QuotePage:
    return QuotePage(
        total=2,
        items=(
            Quote(code="600887", name="伊利股份", price=27.30, change_pct=0.22),
            Quote(code="600059", name="古越龙山", price=12.27, main_net_inflow=611398864.0),
        ),
    )


def test_default_chinese_columns() -> None:
    df = to_dataframe(_sample())
    assert list(df.columns) == [
        "代码",
        "名称",
        "最新价",
        "涨跌幅",
        "涨跌额",
        "主力净流入",
        "成交额",
        "换手率",
    ]
    assert len(df) == 2
    assert df.iloc[0]["代码"] == "600887"
    assert df.iloc[0]["最新价"] == pytest.approx(27.30)
    assert df.iloc[1]["主力净流入"] == pytest.approx(611398864.0)


def test_missing_fields_become_nan() -> None:
    df = to_dataframe(_sample())
    assert pd.isna(df.iloc[0]["主力净流入"])
    assert pd.isna(df.iloc[1]["涨跌幅"])


def test_empty_page_keeps_columns() -> None:
    df = to_dataframe(QuotePage(total=0, items=()))
    assert list(df.columns) == list(COLUMNS_ZH.values())
    assert len(df) == 0


def test_custom_columns_override() -> None:
    custom = {f: f.upper() for f in COLUMNS_ZH}
    df = to_dataframe(_sample(), columns=custom)
    assert list(df.columns) == [f.upper() for f in COLUMNS_ZH]
    assert df.iloc[0]["CODE"] == "600887"

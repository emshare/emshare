"""资金流 DataFrame 适配的行为锁（用固定 FundFlowSeries，不触网）。"""

import pytest

from em.application.dataframe import FUND_FLOW_COLUMNS_ZH, to_fund_flow_dataframe
from em.domain.models import FundFlow, FundFlowSeries

pd = pytest.importorskip("pandas")


def _sample() -> FundFlowSeries:
    return FundFlowSeries(
        code="000001",
        name="平安银行",
        market="sz",
        items=(
            FundFlow(
                date="2026-04-09",
                close=10.49,
                change_pct=-1.13,
                main_net_inflow=-30314508.0,
                main_net_pct=-4.53,
            ),
            FundFlow(
                date="2026-04-10",
                close=10.48,
                change_pct=-0.10,
                main_net_inflow=29167268.0,
                main_net_pct=5.46,
            ),
        ),
    )


def test_default_chinese_columns() -> None:
    df = to_fund_flow_dataframe(_sample())
    assert list(df.columns) == [
        "日期",
        "收盘价",
        "涨跌幅",
        "主力净流入-净额",
        "主力净流入-净占比",
        "超大单净流入-净额",
        "超大单净流入-净占比",
        "大单净流入-净额",
        "大单净流入-净占比",
        "中单净流入-净额",
        "中单净流入-净占比",
        "小单净流入-净额",
        "小单净流入-净占比",
    ]
    assert len(df) == 2
    assert df.iloc[0]["日期"] == "2026-04-09"
    assert df.iloc[0]["收盘价"] == pytest.approx(10.49)
    assert df.iloc[1]["主力净流入-净额"] == pytest.approx(29167268.0)


def test_missing_fields_become_nan() -> None:
    df = to_fund_flow_dataframe(_sample())
    assert pd.isna(df.iloc[0]["超大单净流入-净额"])
    assert pd.isna(df.iloc[1]["小单净流入-净占比"])


def test_empty_series_keeps_columns() -> None:
    df = to_fund_flow_dataframe(FundFlowSeries(code="x", name="y", market="sz", items=()))
    assert list(df.columns) == list(FUND_FLOW_COLUMNS_ZH.values())
    assert len(df) == 0


def test_custom_columns_override() -> None:
    custom = {f: f.upper() for f in FUND_FLOW_COLUMNS_ZH}
    df = to_fund_flow_dataframe(_sample(), columns=custom)
    assert list(df.columns) == [f.upper() for f in FUND_FLOW_COLUMNS_ZH]
    assert df.iloc[0]["DATE"] == "2026-04-09"

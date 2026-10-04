"""板块资金流 DataFrame 适配的行为锁（用固定 BoardFundFlowSeries，不触网）。"""

import pytest

from em.application.dataframe import BOARD_FUND_FLOW_COLUMNS_ZH, to_board_fund_flow_dataframe
from em.domain.models import BoardFundFlow, BoardFundFlowSeries

pd = pytest.importorskip("pandas")


def _sample() -> BoardFundFlowSeries:
    return BoardFundFlowSeries(
        code="BK0438",
        name="食品饮料",
        items=(
            BoardFundFlow(
                date="2026-04-09",
                main_net_inflow=-1435059744.0,
                main_net_pct=-6.80,
                xlarge_net_inflow=-557692240.0,
                xlarge_net_pct=-2.64,
            ),
            BoardFundFlow(
                date="2026-04-10",
                main_net_inflow=-22437264.0,
                main_net_pct=-0.10,
                xlarge_net_inflow=41863024.0,
                xlarge_net_pct=0.18,
            ),
        ),
    )


def test_default_chinese_columns() -> None:
    df = to_board_fund_flow_dataframe(_sample())
    assert list(df.columns) == [
        "日期",
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
    assert df.iloc[0]["主力净流入-净额"] == pytest.approx(-1435059744.0)
    assert df.iloc[1]["超大单净流入-净额"] == pytest.approx(41863024.0)


def test_no_close_or_change_pct_columns() -> None:
    df = to_board_fund_flow_dataframe(_sample())
    assert "收盘价" not in df.columns
    assert "涨跌幅" not in df.columns


def test_missing_fields_become_nan() -> None:
    df = to_board_fund_flow_dataframe(_sample())
    assert pd.isna(df.iloc[0]["大单净流入-净额"])
    assert pd.isna(df.iloc[1]["小单净流入-净占比"])


def test_empty_series_keeps_columns() -> None:
    df = to_board_fund_flow_dataframe(BoardFundFlowSeries(code="x", name="y", items=()))
    assert list(df.columns) == list(BOARD_FUND_FLOW_COLUMNS_ZH.values())
    assert len(df) == 0


def test_custom_columns_override() -> None:
    custom = {f: f.upper() for f in BOARD_FUND_FLOW_COLUMNS_ZH}
    df = to_board_fund_flow_dataframe(_sample(), columns=custom)
    assert list(df.columns) == [f.upper() for f in BOARD_FUND_FLOW_COLUMNS_ZH]
    assert df.iloc[0]["DATE"] == "2026-04-09"

"""板块列表 DataFrame 适配的行为锁（用固定 BoardListPage，不触网）。"""

import pytest

from em.application.dataframe import BOARD_LIST_COLUMNS_ZH, to_board_list_dataframe
from em.domain.models import Board, BoardListPage

pd = pytest.importorskip("pandas")


def _sample() -> BoardListPage:
    return BoardListPage(
        total=31,
        items=(
            Board(
                code="BK1216",
                name="医药生物",
                price=4767.98,
                change_pct=2.03,
                change=95.04,
                turnover=6901833728000.0,
                turnover_rate=2.54,
                up_count=429,
                down_count=70,
                leader_code="000710",
                leader_name="贝瑞基因",
                leader_change_pct=10.02,
                laggard_code="920201",
                laggard_name="百瑞吉",
                laggard_change_pct=-8.58,
            ),
            Board(
                code="BK0438",
                name="食品饮料",
                change_pct=-1.50,
                up_count=30,
                down_count=50,
            ),
        ),
    )


def test_default_chinese_columns() -> None:
    df = to_board_list_dataframe(_sample())
    assert list(df.columns) == list(BOARD_LIST_COLUMNS_ZH.values())
    assert len(df) == 2
    assert df.iloc[0]["板块代码"] == "BK1216"
    assert df.iloc[0]["板块名称"] == "医药生物"
    assert df.iloc[0]["最新价"] == pytest.approx(4767.98)
    assert df.iloc[0]["上涨家数"] == 429
    assert df.iloc[0]["领涨股票"] == "贝瑞基因"


def test_missing_fields_become_nan() -> None:
    df = to_board_list_dataframe(_sample())
    assert pd.isna(df.iloc[1]["最新价"])
    assert pd.isna(df.iloc[1]["成交额"])
    assert pd.isna(df.iloc[1]["领涨股票"])
    assert pd.isna(df.iloc[1]["领跌股票-涨跌幅"])


def test_empty_page_keeps_columns() -> None:
    df = to_board_list_dataframe(BoardListPage(total=0, items=()))
    assert list(df.columns) == list(BOARD_LIST_COLUMNS_ZH.values())
    assert len(df) == 0


def test_custom_columns_override() -> None:
    custom = {f: f.upper() for f in BOARD_LIST_COLUMNS_ZH}
    df = to_board_list_dataframe(_sample(), columns=custom)
    assert list(df.columns) == [f.upper() for f in BOARD_LIST_COLUMNS_ZH]
    assert df.iloc[0]["CODE"] == "BK1216"

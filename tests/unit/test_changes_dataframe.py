"""盘口异动 / 板块异动 DataFrame 适配的行为锁（不触网）。"""

import json
from pathlib import Path

import pytest

from em.application.dataframe import (
    BOARD_CHANGES_COLUMNS_ZH,
    CHANGE_TYPE_LABELS_ZH,
    STOCK_CHANGES_TRADE_TYPES,
    to_board_changes_dataframe,
    to_stock_changes_dataframe,
)
from em.channels.eastmoney.ashare_stocks.stock_changes import STOCK_CHANGE_TYPES
from em.channels.eastmoney.mapping import to_board_changes_page, to_stock_changes_page
from em.domain.models import StockChangesPage

pd = pytest.importorskip("pandas")

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "eastmoney" / "push2ex_changes.json"


def _fx() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _stock_page(change_type: str) -> StockChangesPage:
    return to_stock_changes_page(_fx()["stock"][change_type], change_type)


def test_labels_cover_every_change_type_in_order() -> None:
    assert list(CHANGE_TYPE_LABELS_ZH) == list(STOCK_CHANGE_TYPES)


@pytest.mark.parametrize("change_type", list(STOCK_CHANGE_TYPES))
def test_trade_columns_match_mapping(change_type: str) -> None:
    # 有数量 / 金额的类型，DataFrame 才输出这两列（与映射层保持一致）
    has_volume = _stock_page(change_type).items[0].volume is not None
    assert has_volume == (change_type in STOCK_CHANGES_TRADE_TYPES)
    df = to_stock_changes_dataframe(_stock_page(change_type))
    assert ("数量" in df.columns) == has_volume
    assert df.iloc[0]["异动类型"] == CHANGE_TYPE_LABELS_ZH[change_type]


def test_big_buy_columns() -> None:
    df = to_stock_changes_dataframe(_stock_page("big_buy"))
    assert list(df.columns) == [
        "时间",
        "代码",
        "名称",
        "市场",
        "异动类型",
        "价格",
        "涨跌幅",
        "数量",
        "金额",
        "相关信息",
    ]
    row = df.iloc[0]
    assert (row["时间"], row["代码"], row["异动类型"]) == ("14:55:04", "301513", "大笔买入")
    assert row["数量"] == 29500
    assert row["相关信息"] == "29500,55.59000,-0.062342,1639905.00"


def test_non_trade_type_omits_volume_and_amount() -> None:
    df = to_stock_changes_dataframe(_stock_page("rocket_launch"))
    assert "数量" not in df.columns and "金额" not in df.columns
    assert len(df.columns) == 8


def test_empty_stock_page_keeps_header() -> None:
    df = to_stock_changes_dataframe(StockChangesPage(change_type="big_sell", total=0, items=()))
    assert df.empty
    assert len(df.columns) == 10


def test_board_columns_and_values() -> None:
    df = to_board_changes_dataframe(to_board_changes_page(_fx()["board"]))
    assert list(df.columns) == list(BOARD_CHANGES_COLUMNS_ZH.values())
    assert len(df) == 3
    row = df.iloc[0]
    assert (row["板块代码"], row["板块名称"]) == ("BK0596", "融资融券")
    assert row["主力净流入"] == -50364710912.0  # 元（akshare 原样输出万元）
    assert row["板块异动最频繁个股及所属类型-市场"] == "bj"
    assert row["板块异动最频繁个股及所属类型-异动类型"] == "大笔卖出"
    counts = row["板块具体异动类型列表及出现次数"]
    assert list(counts.items())[:2] == [("快速反弹", 1903), ("低开5日线", 1565)]
    # 最频繁个股为未公开类型的板块，类型列为空（pandas 3 的字符串列把 None 存成 NaN）
    assert pd.isna(df.iloc[2]["板块异动最频繁个股及所属类型-异动类型"])

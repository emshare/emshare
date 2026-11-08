"""个股信息与五档盘口 DataFrame 版的行为锁：akshare 风格 item / value 纵表（不触网）。"""

import json
from pathlib import Path

import pytest

from em.application.dataframe import to_stock_bid_ask_dataframe, to_stock_info_dataframe
from em.channels.eastmoney.mapping import to_stock_bid_ask, to_stock_info

pd = pytest.importorskip("pandas")

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "eastmoney" / "stock_get.json"


def _fx() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_stock_info_item_value_table() -> None:
    df = to_stock_info_dataframe(to_stock_info(_fx()["info"]["0.000001"], "sz"))
    assert list(df.columns) == ["item", "value"]
    items = dict(zip(df["item"], df["value"], strict=True))
    assert list(items) == [
        "股票代码",
        "股票简称",
        "市场",
        "最新",
        "总股本",
        "流通股",
        "总市值",
        "流通市值",
        "行业",
        "上市时间",
    ]
    assert items["股票简称"] == "平安银行"
    assert items["行业"] == "银行Ⅱ"
    assert items["上市时间"] == "1991-04-03"


def test_bid_ask_item_value_table_order() -> None:
    df = to_stock_bid_ask_dataframe(to_stock_bid_ask(_fx()["bid_ask"]["0.000001"], "sz"))
    assert list(df.columns) == ["item", "value"]
    items = list(df["item"])
    # 卖五 → 卖一、买一 → 买五（同 akshare），再接行情项
    assert items[:4] == ["卖5", "卖5量", "卖4", "卖4量"]
    assert items[8:12] == ["卖1", "卖1量", "买1", "买1量"]
    assert items[18:20] == ["买5", "买5量"]
    assert items[20:] == [
        "最新",
        "均价",
        "总手",
        "金额",
        "量比",
        "最高",
        "最低",
        "今开",
        "昨收",
        "涨停",
        "跌停",
        "外盘",
    ]
    values = dict(zip(df["item"], df["value"], strict=True))
    assert values["卖1"] == pytest.approx(11.82)
    assert values["买1量"] == pytest.approx(4384)

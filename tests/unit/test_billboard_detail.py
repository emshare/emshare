"""龙虎榜详情的映射、请求构建与 DataFrame 行为锁（不触网）。

固定报文见 ``test_datacenter.py``；``same_stock_two_reasons`` 是 000530 冰山冷热 11-02
因两个原因上榜的两条记录（TRADE_ID 不同）。
"""

import json
from pathlib import Path

import pytest

from em.application import registry
from em.channels.eastmoney.ashare_billboard.billboard_detail import (
    BILLBOARD_DETAIL,
    billboard_detail_request,
)
from em.channels.eastmoney.datacenter import to_report_chunk
from em.domain.models import BillboardEntry, ReportPage
from em.domain.queries import BillboardDetailQuery

FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "eastmoney" / "datacenter_billboard.json"
)


def _entries(name: str) -> tuple[BillboardEntry, ...]:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))[name]
    return to_report_chunk(raw, BILLBOARD_DETAIL.map_row).items


def test_entry_fields() -> None:
    e = _entries("detail_page")[0]
    assert (e.code, e.name, e.market, e.trade_date) == ("000525", "红太阳", "sz", "2026-11-06")
    assert e.reason == "日涨幅偏离值达到7%的前5只证券"
    assert e.interpretation == "普通席位买入，成功率38.49%"
    assert e.close == pytest.approx(5.02)
    assert e.change_pct == pytest.approx(10.0877)
    assert e.net_buy == pytest.approx(98694262.06)
    assert e.buy - e.sell == pytest.approx(e.net_buy)
    assert e.billboard_turnover == pytest.approx(e.buy + e.sell)
    # 两个占比都是 %：龙虎榜成交额 / 市场总成交额
    assert e.billboard_turnover_ratio == pytest.approx(100 * e.billboard_turnover / e.turnover)
    assert e.net_buy_ratio == pytest.approx(100 * e.net_buy / e.turnover)
    assert e.float_market_cap == pytest.approx(5581035225.1)


def test_after_change_is_none_until_due() -> None:
    # 11-09 抓取时 11-06 上榜后的 1 日已到期、2 日及以后尚未到期
    e = _entries("detail_page")[0]
    assert e.change_after_1d is not None
    assert (e.change_after_2d, e.change_after_5d, e.change_after_10d) == (None, None, None)


def test_same_stock_same_day_two_reasons_are_two_entries() -> None:
    first, second = _entries("same_stock_two_reasons")
    assert (
        (first.code, first.trade_date)
        == (second.code, second.trade_date)
        == ("000530", "2026-11-02")
    )
    assert first.reason != second.reason


def test_request_with_range() -> None:
    request = billboard_detail_request(BillboardDetailQuery("20261102", "20261106"))
    params = request.params()
    assert params["reportName"] == "RPT_DAILYBILLBOARD_DETAILSNEW"
    assert params["filter"] == "(TRADE_DATE>='2026-11-02')(TRADE_DATE<='2026-11-06')"
    # TRADE_ID 补在排序末尾：同股同日多条记录时翻页顺序仍稳定
    assert (params["sortColumns"], params["sortTypes"]) == (
        "SECURITY_CODE,TRADE_DATE,TRADE_ID",
        "1,-1,1",
    )
    assert "TRADE_ID" in params["columns"].split(",")
    assert request.latest_of == ""


def test_request_without_dates_takes_latest_day() -> None:
    request = billboard_detail_request(BillboardDetailQuery())
    assert request.latest_of == "TRADE_DATE"
    assert request.filter == ""


def test_malformed_date_raises() -> None:
    with pytest.raises(ValueError, match="YYYYMMDD"):
        billboard_detail_request(BillboardDetailQuery("2026-11-06"))


def test_registry_exposes_request() -> None:
    assert registry.billboard_detail_request is billboard_detail_request


def test_dataframe_columns() -> None:
    pd = pytest.importorskip("pandas")
    from em.application.dataframe import to_billboard_detail_dataframe

    entries = _entries("detail_page")
    df = to_billboard_detail_dataframe(ReportPage(total=79, items=entries))
    assert list(df.columns)[:5] == ["代码", "名称", "市场", "上榜日", "解读"]
    assert "上榜原因" in df.columns and len(df) == 4
    empty = to_billboard_detail_dataframe(ReportPage(total=0, items=()))
    assert empty.empty and len(empty.columns) == len(df.columns)
    assert isinstance(df, pd.DataFrame)

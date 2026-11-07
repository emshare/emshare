"""指数列表的映射与请求构建行为锁（用固定报文，不触网）。

固定报文由 2026-11-06 真实返回的行拼成，分别取自上证、深证、中证系列和沪深重要指数，
并保留一条停牌 / 未开盘指数（上游字段为 ``"-"``）。
"""

import json
from pathlib import Path

import pytest

from em.application import registry
from em.channels.eastmoney import config
from em.channels.eastmoney.ashare_indices.index_list.index_list_em import (
    INDEX_SERIES_FS,
    index_list_request,
    normalize_series,
)
from em.channels.eastmoney.mapping import to_index_list_page
from em.domain.models import IndexQuote
from em.domain.queries import IndexListQuery

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "eastmoney" / "clist_index.json"


def _load() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _by_code() -> dict[str, IndexQuote]:
    return {i.code: i for i in to_index_list_page(_load()).items}


def test_to_index_list_page_maps_total_and_items() -> None:
    page = to_index_list_page(_load())
    assert page.total == 1787
    assert len(page.items) == 5
    assert all(isinstance(i, IndexQuote) for i in page.items)


def test_index_prices_are_unscaled_points() -> None:
    sh = _by_code()["000001"]
    assert sh.name == "上证指数"
    assert sh.price == pytest.approx(3649.18)
    assert sh.change_pct == pytest.approx(-1.10)
    assert sh.change == pytest.approx(-40.73)
    assert sh.volume == pytest.approx(477042561.0)
    assert sh.turnover == pytest.approx(772634566231.1)
    assert sh.amplitude == pytest.approx(1.36)
    assert sh.high == pytest.approx(3660.49)
    assert sh.low == pytest.approx(3610.20)
    assert sh.open == pytest.approx(3612.15)
    assert sh.pre_close == pytest.approx(3689.91)
    assert sh.volume_ratio == pytest.approx(0.86)


@pytest.mark.parametrize(
    ("code", "market"),
    [("000001", "sh"), ("399001", "sz"), ("899050", "bj"), ("932000", "csi")],
)
def test_market_disambiguates_codes(code: str, market: str) -> None:
    # 000001 在沪市是上证指数、在深市是平安银行：market 必须随行带出；
    # 北证指数挂在 0 前缀下，按 899 代码段识别为 bj
    assert _by_code()[code].market == market


def test_unknown_market_prefix_maps_to_none() -> None:
    data = {"rc": 0, "data": {"total": 1, "diff": [{"f12": "X1", "f14": "x", "f13": 9}]}}
    assert to_index_list_page(data).items[0].market is None


def test_suspended_index_fields_become_none() -> None:
    idle = _by_code()["988201"]
    assert idle.price is None
    assert idle.change_pct is None
    assert idle.volume is None
    assert idle.turnover is None
    assert idle.volume_ratio is None
    assert idle.pre_close == pytest.approx(1661.20)


def test_empty_index_list() -> None:
    page = to_index_list_page({"rc": 0, "data": None})
    assert page.total == 0
    assert page.items == ()


@pytest.mark.parametrize(
    ("series", "fs"),
    [("main", "b:MK0010"), ("sh", "m:1+t:1"), ("sz", "m:0+t:5"), ("csi", "m:2")],
)
def test_index_list_request_series_to_fs(series: str, fs: str) -> None:
    request = index_list_request(IndexListQuery(series=series, sort="f6", page=2, size=50))
    assert request.url() == f"{config.GUEST_HOST}{config.CLIST_PATH}"
    params = request.params()
    assert params["fs"] == fs
    assert params["fields"] == config.INDEX_LIST_FIELDS
    assert params["fid"] == "f6"
    assert params["pn"] == "2"
    assert params["pz"] == "50"


def test_fields_include_market_prefix() -> None:
    # f13 是消歧 000001 的唯一依据，字段集里不能漏
    assert "f13" in config.INDEX_LIST_FIELDS.split(",")


def test_unknown_series_falls_back_to_main() -> None:
    assert normalize_series("hk") == "main"
    assert index_list_request(IndexListQuery(series="hk")).fs == INDEX_SERIES_FS["main"]


def test_registry_exposes_index_list_request() -> None:
    assert registry.index_list_request is index_list_request

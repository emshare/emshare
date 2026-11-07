"""港股列表的映射与请求构建行为锁（用固定报文，不触网）。

固定报文是 2026-11-06 真实返回的 4 行：主板成交额前 2（腾讯、阿里）、创业板成交额第 1，
以及一只停牌股（上游字段为 ``"-"``）。
"""

import json
from pathlib import Path

import pytest

from em.application import registry
from em.channels.eastmoney import config
from em.channels.eastmoney.hk_market.hk_stock_list.hk_stock_list_em import (
    HK_SCOPE_FS,
    hk_stock_list_request,
    normalize_scope,
)
from em.channels.eastmoney.mapping import to_hk_stock_list_page, to_quote_page
from em.domain.models import HkQuote
from em.domain.queries import HkStockListQuery

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "eastmoney" / "clist_hk_stock.json"


def _load() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _by_code() -> dict[str, HkQuote]:
    return {q.code: q for q in to_hk_stock_list_page(_load()).items}


def test_to_hk_stock_list_page_maps_total_and_items() -> None:
    page = to_hk_stock_list_page(_load())
    assert page.total == 2933
    assert [q.code for q in page.items] == ["00700", "09988", "08646", "00007"]
    assert all(isinstance(q, HkQuote) for q in page.items)


def test_hk_prices_use_three_decimals() -> None:
    # 港股 f1=3：价格放大 1000 倍。按 A 股的 100 倍还原会把腾讯算成 4198 港元
    tencent = _by_code()["00700"]
    assert tencent.name == "腾讯控股"
    assert tencent.price == pytest.approx(419.8)
    assert tencent.change == pytest.approx(-10.6)
    assert tencent.open == pytest.approx(421.0)
    assert tencent.high == pytest.approx(428.6)
    assert tencent.low == pytest.approx(416.2)
    assert tencent.pre_close == pytest.approx(430.4)


def test_hk_change_pct_still_scaled_by_100() -> None:
    assert _by_code()["00700"].change_pct == pytest.approx(-2.46)
    assert _by_code()["08646"].change_pct == pytest.approx(5.71)


def test_hk_volume_and_turnover_are_raw() -> None:
    tencent = _by_code()["00700"]
    assert tencent.volume == pytest.approx(29605485.0)  # 单位股
    assert tencent.turnover == pytest.approx(12502715648.0)  # 单位港元


def test_sub_one_dollar_price_keeps_precision() -> None:
    # 仙股 0.370 港元：三位小数正是 f1=3 存在的原因
    gem = _by_code()["08646"]
    assert gem.price == pytest.approx(0.37)
    assert gem.low == pytest.approx(0.335)


def test_suspended_stock_fields_become_none() -> None:
    idle = _by_code()["00007"]
    assert idle.price is None
    assert idle.change_pct is None
    assert idle.volume is None
    assert idle.turnover is None
    assert idle.pre_close == pytest.approx(0.032)


def test_missing_f1_falls_back_to_two_decimals() -> None:
    data = {"rc": 0, "data": {"total": 1, "diff": [{"f12": "X", "f14": "x", "f2": 1234}]}}
    assert to_hk_stock_list_page(data).items[0].price == pytest.approx(12.34)


def test_a_share_mapping_is_unaffected() -> None:
    # A 股映射不读 f1，仍按 100 倍还原
    data = {
        "rc": 0,
        "data": {"total": 1, "diff": [{"f12": "000001", "f14": "平安银行", "f2": 1164}]},
    }
    assert to_quote_page(data).items[0].price == pytest.approx(11.64)


def test_empty_hk_stock_list() -> None:
    page = to_hk_stock_list_page({"rc": 0, "data": None})
    assert page.total == 0
    assert page.items == ()


@pytest.mark.parametrize(
    ("scope", "fs"),
    [("all", "m:128+t:3,m:128+t:4"), ("main", "m:128+t:3"), ("gem", "m:128+t:4")],
)
def test_hk_stock_list_request_scope_to_fs(scope: str, fs: str) -> None:
    request = hk_stock_list_request(HkStockListQuery(scope=scope, sort="f6", page=2, size=50))
    assert request.url() == f"{config.GUEST_HOST}{config.CLIST_PATH}"
    params = request.params()
    assert params["fs"] == fs
    assert params["fields"] == config.HK_STOCK_LIST_FIELDS
    assert params["fid"] == "f6"
    assert params["pn"] == "2"
    assert params["pz"] == "50"


def test_scopes_exclude_etf_and_bond_segments() -> None:
    # t:1 是 ETF 与基金、t:2 是债券，不是股票
    all_parts = ",".join(HK_SCOPE_FS.values())
    assert "t:1" not in all_parts
    assert "t:2" not in all_parts


def test_fields_include_price_decimals() -> None:
    assert "f1" in config.HK_STOCK_LIST_FIELDS.split(",")


def test_unknown_scope_falls_back_to_all() -> None:
    assert normalize_scope("etf") == "all"
    assert hk_stock_list_request(HkStockListQuery(scope="etf")).fs == HK_SCOPE_FS["all"]


def test_registry_exposes_hk_stock_list_request() -> None:
    assert registry.hk_stock_list_request is hk_stock_list_request

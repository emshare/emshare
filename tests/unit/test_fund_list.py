"""场内基金列表的映射与请求构建行为锁（用固定报文，不触网）。

固定报文是 2026-11-06 真实返回的 4 行：深市 ETF（创业板ETF易方达，有 IOPV）、
高溢价的沪市 ETF（中韩半导体ETF，折价率为负）、沪市 LOF（无 IOPV），
以及一只停牌 LOF（上游字段为 ``"-"``）。
"""

import json
from pathlib import Path

import pytest

from em.application import registry
from em.channels.eastmoney import config
from em.channels.eastmoney.fund_market.fund_list.fund_list_em import (
    FUND_TYPE_FS,
    fund_list_request,
    normalize_fund_type,
)
from em.channels.eastmoney.mapping import to_fund_list_page
from em.domain.models import FundQuote
from em.domain.queries import FundListQuery

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "eastmoney" / "clist_fund.json"


def _load() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _by_code() -> dict[str, FundQuote]:
    return {q.code: q for q in to_fund_list_page(_load()).items}


def test_to_fund_list_page_maps_total_and_items() -> None:
    page = to_fund_list_page(_load())
    assert page.total == 2055
    assert [q.code for q in page.items] == ["159915", "513310", "501018", "160142"]
    assert all(isinstance(q, FundQuote) for q in page.items)


def test_fund_prices_use_three_decimals() -> None:
    # 基金 f1=3：价格放大 1000 倍。按 100 倍还原会把 2.480 元算成 24.8 元
    etf = _by_code()["159915"]
    assert etf.name == "创业板ETF易方达"
    assert etf.price == pytest.approx(2.48)
    assert etf.change == pytest.approx(-0.104)
    assert etf.open == pytest.approx(2.485)
    assert etf.high == pytest.approx(2.524)
    assert etf.low == pytest.approx(2.465)
    assert etf.pre_close == pytest.approx(2.584)


def test_percent_fields_scaled_by_100() -> None:
    etf = _by_code()["159915"]
    assert etf.change_pct == pytest.approx(-4.02)
    assert etf.turnover_rate == pytest.approx(12.37)
    assert etf.discount_rate == pytest.approx(0.04)


def test_iopv_is_raw_not_scaled() -> None:
    # 实测 f441 在 fltt=1 下也是原值（与 fltt=2 返回一致），不能再除
    assert _by_code()["159915"].iopv == pytest.approx(2.4809)
    assert _by_code()["513310"].iopv == pytest.approx(3.2077)


def test_negative_discount_means_premium() -> None:
    # 价格 3.541 高于 IOPV 3.2077：溢价约 10.39%，上游折价率记为负值
    premium = _by_code()["513310"]
    assert premium.price == pytest.approx(3.541)
    assert premium.discount_rate == pytest.approx(-10.39)
    assert premium.discount_rate == pytest.approx(
        (premium.iopv - premium.price) / premium.iopv * 100, abs=0.01
    )


def test_volume_turnover_and_caps_are_raw() -> None:
    etf = _by_code()["159915"]
    assert etf.volume == pytest.approx(55565896.0)  # 单位手
    assert etf.turnover == pytest.approx(13843109694.811)
    assert etf.float_market_cap == pytest.approx(111387848499.0)
    assert etf.total_market_cap == pytest.approx(111387848499.0)


@pytest.mark.parametrize(
    ("code", "market"), [("159915", "sz"), ("513310", "sh"), ("501018", "sh"), ("160142", "sz")]
)
def test_market_from_secid_prefix(code: str, market: str) -> None:
    assert _by_code()[code].market == market


def test_lof_has_no_iopv() -> None:
    lof = _by_code()["501018"]
    assert lof.iopv is None
    assert lof.price == pytest.approx(2.062)
    assert lof.discount_rate == pytest.approx(-1.74)


def test_suspended_fund_fields_become_none() -> None:
    idle = _by_code()["160142"]
    assert idle.price is None
    assert idle.change_pct is None
    assert idle.volume is None
    assert idle.discount_rate is None
    assert idle.pre_close == pytest.approx(0.993)
    assert idle.total_market_cap == pytest.approx(31809308.0)


def test_unknown_market_prefix_maps_to_none() -> None:
    data = {"rc": 0, "data": {"total": 1, "diff": [{"f12": "X", "f14": "x", "f13": 9}]}}
    assert to_fund_list_page(data).items[0].market is None


def test_empty_fund_list() -> None:
    page = to_fund_list_page({"rc": 0, "data": None})
    assert page.total == 0
    assert page.items == ()


@pytest.mark.parametrize(
    ("fund_type", "fs"),
    [
        ("etf", "b:MK0021,b:MK0022,b:MK0023,b:MK0024,b:MK0827"),
        ("lof", "b:MK0404,b:MK0405,b:MK0406,b:MK0407"),
        (
            "all",
            "b:MK0021,b:MK0022,b:MK0023,b:MK0024,b:MK0827,b:MK0404,b:MK0405,b:MK0406,b:MK0407",
        ),
    ],
)
def test_fund_list_request_type_to_fs(fund_type: str, fs: str) -> None:
    request = fund_list_request(FundListQuery(fund_type=fund_type, sort="f6", page=2, size=50))
    assert request.url() == f"{config.GUEST_HOST}{config.CLIST_PATH}"
    params = request.params()
    assert params["fs"] == fs
    assert params["fields"] == config.FUND_LIST_FIELDS
    assert params["fid"] == "f6"
    assert params["pn"] == "2"
    assert params["pz"] == "50"


def test_fields_include_decimals_market_and_iopv() -> None:
    fields = config.FUND_LIST_FIELDS.split(",")
    for f in ("f1", "f13", "f402", "f441"):
        assert f in fields


def test_unknown_fund_type_falls_back_to_etf() -> None:
    assert normalize_fund_type("reits") == "etf"
    assert fund_list_request(FundListQuery(fund_type="reits")).fs == FUND_TYPE_FS["etf"]


def test_registry_exposes_fund_list_request() -> None:
    assert registry.fund_list_request is fund_list_request

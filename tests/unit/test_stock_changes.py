"""盘口异动的映射与请求构建行为锁（用固定报文，不触网）。

固定报文是 2026-11-08（周日）抓取的 22 种异动各自的前两行真实返回（push2ex getAllStockChanges），
数据属于最近交易日 11-06；``empty`` 是当天无记录时上游的返回（rc=0、data 为 null）。
"""

import json
import re
from pathlib import Path

import pytest

from em.application import registry
from em.channels.eastmoney import config
from em.channels.eastmoney.ashare_stocks.stock_changes.stock_changes_em import (
    STOCK_CHANGE_TYPES,
    normalize_change_type,
    stock_changes_request,
)
from em.channels.eastmoney.mapping import to_stock_changes_page
from em.channels.eastmoney.source import _is_valid_payload
from em.domain.models import StockChange, StockChangesPage
from em.domain.queries import StockChangesQuery

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "eastmoney" / "push2ex_changes.json"
# 东财页面（changes_index.js）的 22 种类型及顺序，akshare stock_changes_em 同
PAGE_TYPE_CODES = [8201, 8202, 8193, 4, 32, 64, 8207, 8209, 8211, 8213, 8215,
                   8204, 8203, 8194, 8, 16, 128, 8208, 8210, 8212, 8214, 8216]  # fmt: skip
TRADE_TYPES = {"big_buy", "big_sell", "big_bid", "big_ask"}


def _raw(change_type: str) -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["stock"][change_type]


def _page(change_type: str) -> StockChangesPage:
    return to_stock_changes_page(_raw(change_type), change_type)


def _first(change_type: str) -> StockChange:
    return _page(change_type).items[0]


def test_change_types_match_eastmoney_page() -> None:
    assert list(STOCK_CHANGE_TYPES.values()) == PAGE_TYPE_CODES
    assert len(set(STOCK_CHANGE_TYPES)) == 22


@pytest.mark.parametrize("change_type", list(STOCK_CHANGE_TYPES))
def test_every_type_maps_price_pct_and_market(change_type: str) -> None:
    page = _page(change_type)
    assert page.change_type == change_type
    assert page.total >= len(page.items) >= 1
    for c in page.items:
        assert c.change_type == change_type
        assert re.fullmatch(r"\d{2}:\d{2}:\d{2}", c.time)
        assert c.market in ("sh", "sz", "bj")
        assert c.price is not None and c.price > 0  # 位置错了会拿到比例或封单量
        assert c.change_pct is not None and abs(c.change_pct) < 300
        assert (c.volume is not None) == (change_type in TRADE_TYPES)
        assert (c.amount is not None) == (change_type in TRADE_TYPES)
        assert c.info


@pytest.mark.parametrize("change_type", list(STOCK_CHANGE_TYPES))
def test_push2ex_payload_passes_protocol_check(change_type: str) -> None:
    assert _is_valid_payload(json.dumps(_raw(change_type)))


def test_big_buy_trade_fields() -> None:
    page = _page("big_buy")
    assert page.total == 1374
    c = page.items[0]
    assert (c.time, c.code, c.name, c.market) == ("14:55:04", "301513", "尚水智能", "sz")
    assert c.info == "29500,55.59000,-0.062342,1639905.00"
    assert c.volume == 29500  # 单位股（东财页面除以 100 显示为 295 手）
    assert c.price == pytest.approx(55.59)
    assert c.change_pct == pytest.approx(-6.2342)  # 上游是比例 -0.062342
    assert c.amount == pytest.approx(1639905.0)
    assert c.volume * c.price == pytest.approx(c.amount)  # 大笔买卖：金额 = 股数 × 成交价


def test_big_bid_amount_is_book_depth() -> None:
    # 有大买盘是多档挂单合计：金额不等于股数 × 价格，均价落在价格下方
    c = _first("big_bid")
    assert (c.code, c.market) == ("603216", "sh")
    assert c.volume == 594800
    assert c.price == pytest.approx(18.18)
    assert c.amount == pytest.approx(10783763.0)
    assert c.amount / c.volume < c.price


def test_rocket_launch_change_layout() -> None:
    c = _first("rocket_launch")
    assert (c.time, c.code, c.market) == ("14:51:19", "688135", "sh")
    assert c.price == pytest.approx(28.68)  # 第 2 位
    assert c.change_pct == pytest.approx(4.4048)  # 第 3 位
    assert c.volume is None and c.amount is None


def test_big_rise_60d_uses_third_field_as_change_pct() -> None:
    # 首位与第 3 位不同（0.037618 / 0.034483）：涨跌幅取与价格配对的第 3 位
    c = _first("big_rise_60d")
    assert c.info == "0.037618,6.60000,0.034483"
    assert c.price == pytest.approx(6.60)
    assert c.change_pct == pytest.approx(3.4483)


def test_limit_up_sealed_layout() -> None:
    # 封板价,?,价格,涨跌幅：第 2 位（封单相关，未核实）不映射
    c = _first("limit_up_sealed")
    assert c.info == "11.090000,329088,11.09000,0.100198"
    assert c.price == pytest.approx(11.09)
    assert c.change_pct == pytest.approx(10.0198)
    assert c.volume is None


def test_limit_down_opened_layout() -> None:
    c = _first("limit_down_opened")
    assert c.info == "6.320000,-0.099715"
    assert c.price == pytest.approx(6.32)
    assert c.change_pct == pytest.approx(-9.9715)


def test_new_high_60d_price_is_trade_price_not_high() -> None:
    # 首位 6.93 是 60 日新高价，第 2 位 6.92 才是价格
    c = _first("new_high_60d")
    assert c.price == pytest.approx(6.92)
    assert c.change_pct == pytest.approx(2.0649)


def test_bj_market_and_short_time() -> None:
    # 北交所挂在 m=0 下按代码段识别；tm=92403 补零为 09:24:03；新股首日无涨跌幅限制
    c = _first("auction_up")
    assert (c.code, c.name, c.market) == ("920085", "N森峰", "bj")
    assert c.time == "09:24:03"
    assert c.change_pct == pytest.approx(119.2243)


def test_change_pct_has_no_float_tail() -> None:
    # 0.100198 * 100 会出现 10.019799999999998 一类尾差，按原值精度取整
    assert _first("limit_up_sealed").change_pct == 10.0198


def test_empty_type_returns_empty_page() -> None:
    page = to_stock_changes_page(_raw("empty"), "open_above_ma5")
    assert (page.change_type, page.total, page.items) == ("open_above_ma5", 0, ())


def test_malformed_info_maps_to_none() -> None:
    data = {"rc": 0, "data": {"tc": 2, "allstock": [
        {"tm": 93000, "c": "000001", "m": 0, "n": "平安银行", "t": 8193, "i": "100"},
        {"tm": 93000, "c": "600000", "m": 1, "n": "浦发银行", "t": 8219, "i": "9.4,0.07"},
    ]}}  # fmt: skip
    short, unknown = to_stock_changes_page(data, "big_buy").items
    assert short.volume == 100
    assert (short.price, short.change_pct, short.amount) == (None, None, None)
    assert unknown.change_type is None  # 8219 是未公开类型
    assert unknown.market == "sh"


def test_request_params() -> None:
    request = stock_changes_request(StockChangesQuery(change_type="rocket_launch"))
    assert request.url() == f"{config.PUSH2EX_HOST}/getAllStockChanges"
    assert request.params() == {
        "type": "8201",
        "ut": config.PUSH2EX_UT,
        "dpt": "wzchanges",
        "pageindex": "0",
        "pagesize": str(config.CHANGES_PAGE_SIZE),
    }
    assert request.change_type == "rocket_launch"


def test_page_size_covers_busiest_type() -> None:
    # 一次取全量：pagesize 要远大于实测单类型单日条数（11-06 快速反弹 2576 条）
    assert _page("quick_rebound").total == 2576
    assert config.CHANGES_PAGE_SIZE >= 10 * 2576


def test_unknown_change_type_falls_back_to_big_buy() -> None:
    assert normalize_change_type("大笔买入") == "big_buy"
    request = stock_changes_request(StockChangesQuery(change_type="8193"))
    assert (request.type_code, request.change_type) == (8193, "big_buy")


def test_registry_exposes_stock_changes_request() -> None:
    assert registry.stock_changes_request is stock_changes_request

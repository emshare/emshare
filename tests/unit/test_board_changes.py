"""板块异动的映射与请求构建行为锁（用固定报文，不触网）。

固定报文是 2026-11-08（周日）抓取的 getAllBKChanges 真实返回（数据时间 11-06 15:00:00，共 1052 个板块），
保留前两个板块，另挑了一个“异动最频繁个股”类型为未公开类型（8220）的板块 BK0552。
"""

import json
from pathlib import Path

import pytest

from em.application import registry
from em.channels.eastmoney import config
from em.channels.eastmoney.ashare_boards.board_changes.board_changes_em import (
    board_changes_request,
)
from em.channels.eastmoney.mapping import to_board_changes_page
from em.channels.eastmoney.source import _is_valid_payload
from em.domain.models import BoardChangesPage
from em.domain.queries import BoardChangesQuery

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "eastmoney" / "push2ex_changes.json"


def _raw() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["board"]


def _page() -> BoardChangesPage:
    return to_board_changes_page(_raw())


def test_page_date_time_and_total() -> None:
    page = _page()
    assert (page.date, page.time) == ("2026-11-06", "15:00:00")  # dt=20261106150000
    assert page.total == 1052
    assert [b.code for b in page.items] == ["BK0596", "BK0804", "BK0552"]


def test_push2ex_payload_passes_protocol_check() -> None:
    assert _is_valid_payload(json.dumps(_raw()))


def test_board_fields() -> None:
    b = _page().items[0]
    assert (b.code, b.name) == ("BK0596", "融资融券")
    assert b.change_pct == pytest.approx(-1.99)  # 上游是字符串 "-1.99"
    # zjl 单位万元：-5036471.0912 万元，与 board_fund_flow_em 当日主力净额 -50364710912 元一致
    assert b.main_net_inflow == -50364710912.0
    assert b.change_count == 10998


def test_top_stock_market_is_not_trade_direction() -> None:
    # akshare 把 ms.m 当买卖方向（0 大笔买入 / 1 大笔卖出），实为市场前缀；类型在 ms.t
    first, second, _ = _page().items
    assert (first.top_stock_code, first.top_stock_name) == ("920085", "N森峰")
    assert first.top_stock_market == "bj"  # m=0，按代码段识别为北交所
    assert first.top_stock_change_type == "big_sell"  # t=8194，akshare 会显示成“大笔买入”
    assert (second.top_stock_code, second.top_stock_market) == ("301697", "sz")
    assert second.top_stock_change_type == "big_buy"


def test_unpublished_top_stock_type_is_none() -> None:
    b = _page().items[2]
    assert (b.code, b.top_stock_code, b.top_stock_market) == ("BK0552", "603228", "sh")
    assert b.top_stock_change_type is None  # t=8220 东财页面与 akshare 都没有名字


def test_type_counts_keep_upstream_order_and_drop_unpublished_types() -> None:
    raw = _raw()["data"]["allbk"][0]["ydl"]
    b = _page().items[0]
    # 上游前三是 快速反弹 1903 / 低开5日线 1565 / 8218（未公开）1562
    assert [(t.change_type, t.count) for t in b.type_counts[:3]] == [
        ("quick_rebound", 1903),
        ("open_below_ma5", 1565),
        ("big_buy", 984),
    ]
    published = [x for x in raw if x["t"] < 8217]
    assert len(b.type_counts) == len(published)
    # change_count 是上游原值，含未公开类型，所以大于各类之和
    assert sum(x["ct"] for x in raw) == b.change_count
    assert sum(t.count for t in b.type_counts) == sum(x["ct"] for x in published) < b.change_count


def test_malformed_board_entries() -> None:
    data = {"rc": 0, "data": {"dt": None, "tc": 1, "allbk": [
        {"c": "BK0001", "n": "测试", "u": "-", "zjl": None, "ct": 3, "ms": None,
         "ydl": [{"t": 8217, "ct": 2}, {"t": 8193}, "bad", {"t": 4, "ct": 1}]},
    ]}}  # fmt: skip
    page = to_board_changes_page(data)
    assert (page.date, page.time) == ("", "")
    b = page.items[0]
    assert (b.change_pct, b.main_net_inflow) == (None, None)
    assert (b.top_stock_code, b.top_stock_market, b.top_stock_change_type) == (None, None, None)
    assert [(t.change_type, t.count) for t in b.type_counts] == [("limit_up_sealed", 1)]


def test_missing_data_block() -> None:
    page = to_board_changes_page({"rc": 0, "data": None})
    assert (page.date, page.time, page.total, page.items) == ("", "", 0, ())


def test_request_params() -> None:
    request = board_changes_request(BoardChangesQuery())
    assert request.url() == f"{config.PUSH2EX_HOST}/getAllBKChanges"
    assert request.params() == {
        "ut": config.PUSH2EX_UT,
        "dpt": "wzchanges",
        "pageindex": "0",
        "pagesize": str(config.CHANGES_PAGE_SIZE),
    }


def test_registry_exposes_board_changes_request() -> None:
    assert registry.board_changes_request is board_changes_request

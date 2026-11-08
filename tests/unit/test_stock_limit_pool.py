"""涨跌停股池的映射与请求构建行为锁（用固定报文，不触网）。

固定报文是 2026-11-06 六个股池各自的前两行真实返回（push2ex）。
次新股池第一行是北交所新股首日（N森峰），上游涨停价给哨兵值 1000000000。
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from em.application import registry
from em.channels.eastmoney import config
from em.channels.eastmoney.ashare_stocks.stock_limit_pool.stock_limit_pool_em import (
    LIMIT_POOL_ENDPOINTS,
    normalize_pool_type,
    resolve_date,
    stock_limit_pool_request,
)
from em.channels.eastmoney.mapping import to_limit_pool_page
from em.channels.eastmoney.source import _is_valid_payload
from em.domain.models import LimitPoolStock
from em.domain.queries import LimitPoolQuery

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "eastmoney" / "push2ex_limit_pool.json"
POOLS = ("limit_up", "prev_limit_up", "strong", "sub_new", "broken", "limit_down")


def _raw(pool_type: str) -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))[pool_type]


def _first(pool_type: str) -> LimitPoolStock:
    return to_limit_pool_page(_raw(pool_type), pool_type, "20261106").items[0]


@pytest.mark.parametrize(
    ("pool_type", "total"),
    [
        ("limit_up", 32),
        ("prev_limit_up", 84),
        ("strong", 151),
        ("sub_new", 161),
        ("broken", 14),
        ("limit_down", 15),
    ],
)
def test_page_carries_pool_type_date_and_total(pool_type: str, total: int) -> None:
    page = to_limit_pool_page(_raw(pool_type), pool_type, "20261106")
    assert page.pool_type == pool_type
    assert page.date == "2026-11-06"
    assert page.total == total
    assert len(page.items) == 2


@pytest.mark.parametrize("pool_type", POOLS)
def test_push2ex_payload_passes_protocol_check(pool_type: str) -> None:
    # push2ex 与 push2 同样是 rc==0 的 JSON，传输层校验无需特判
    assert _is_valid_payload(json.dumps(_raw(pool_type)))


def test_limit_up_fields() -> None:
    s = _first("limit_up")
    assert (s.code, s.name, s.market) == ("002578", "闽发铝业", "sz")
    assert s.price == pytest.approx(5.01)  # p=5010，固定除以 1000
    assert s.change_pct == pytest.approx(10.11, abs=0.01)
    assert s.turnover == pytest.approx(538747056.0)
    assert s.turnover_rate == pytest.approx(12.50, abs=0.01)
    assert s.seal_fund == pytest.approx(220341804.0)
    assert s.first_seal_time == "09:25:00"
    assert s.last_seal_time == "09:30:09"
    assert s.broken_count == 1
    assert s.limit_up_streak == 5
    assert (s.stat_days, s.stat_limit_ups) == (10, 6)
    assert s.industry == "工业金属"
    assert s.limit_up_price is None  # 涨停池上游不给涨停价


def test_prev_limit_up_fields_and_bj_market() -> None:
    s = _first("prev_limit_up")
    assert (s.code, s.market) == ("920007", "bj")  # 北交所挂在 m=0 下，按代码段识别
    assert s.price == pytest.approx(42.33)
    assert s.limit_up_price == pytest.approx(51.33)
    assert s.prev_seal_time == "09:54:08"
    assert s.prev_limit_up_streak == 1
    assert s.amplitude == pytest.approx(23.55, abs=0.01)
    assert s.speed == pytest.approx(0.79, abs=0.01)


def test_strong_fields() -> None:
    s = _first("strong")
    assert s.new_high is True
    assert s.reason == "60日新高"
    assert s.volume_ratio == pytest.approx(8.97, abs=0.01)
    assert s.limit_up_price == pytest.approx(2.82)  # ztp=2820
    assert s.price == s.limit_up_price  # 美晨科技当日 20cm 涨停


def test_sub_new_sentinel_limit_price_is_none() -> None:
    s = _first("sub_new")
    assert s.name == "N森峰"
    assert s.limit_up_price is None  # 北交所新股首日不设涨停价，上游哨兵 1000000000
    assert s.price == pytest.approx(39.25)
    assert s.listing_date == "2026-11-06"
    assert s.open_date == "2026-11-06"
    assert s.open_days == 1
    assert s.new_high is False


def test_broken_fields() -> None:
    s = _first("broken")
    assert s.limit_up_price == pytest.approx(10.89)
    assert s.first_seal_time == "09:25:00"
    assert s.broken_count == 2
    assert s.change_pct < 0


def test_limit_down_fields() -> None:
    s = _first("limit_down")
    assert s.seal_fund == pytest.approx(3550372.0)
    assert s.last_seal_time == "14:30:51"
    assert s.board_turnover == pytest.approx(86085114.0)
    assert s.limit_down_streak == 1
    assert s.open_count == 4
    assert s.pe == pytest.approx(115.43, abs=0.01)


def test_sh_market() -> None:
    page = to_limit_pool_page(_raw("limit_up"), "limit_up", "20261106")
    assert page.items[1].code.startswith("60")
    assert page.items[1].market == "sh"


@pytest.mark.parametrize(
    ("requested", "expected"),
    [
        ("20261106", "2026-11-06"),  # 当天
        ("20261107", "2026-11-06"),  # 周六 / 今天之后：上游给最近交易日
        ("20261120", "2026-11-06"),  # 未来
        ("20261030", "2026-10-30"),  # 过去：数据属于请求日期
    ],
)
def test_actual_date_is_earlier_of_requested_and_qdate(requested: str, expected: str) -> None:
    # 上游 qdate 恒为最近交易日（实测 20261106），与请求日期无关
    assert to_limit_pool_page(_raw("limit_up"), "limit_up", requested).date == expected


def test_empty_pool() -> None:
    data = {"rc": 0, "data": {"tc": 0, "qdate": 20261106, "pool": []}}
    page = to_limit_pool_page(data, "limit_up", "20261016")
    assert page.total == 0
    assert page.items == ()
    assert page.date == "2026-10-16"


def test_missing_data_block() -> None:
    page = to_limit_pool_page({"rc": 0, "data": None}, "broken", "20261106")
    assert (page.total, page.items, page.date) == (0, (), "2026-11-06")


@pytest.mark.parametrize("pool_type", POOLS)
def test_request_uses_pool_endpoint(pool_type: str) -> None:
    request = stock_limit_pool_request(LimitPoolQuery(pool_type=pool_type, date="20261106"))
    path, sort = LIMIT_POOL_ENDPOINTS[pool_type]
    assert request.url() == f"{config.PUSH2EX_HOST}{path}"
    params = request.params()
    assert params["sort"] == sort
    assert params["date"] == "20261106"
    assert params["ut"] == config.PUSH2EX_UT
    assert params["pagesize"] == str(config.LIMIT_POOL_PAGE_SIZE)
    assert request.pool_type == pool_type


def test_sub_new_path_keeps_upstream_spelling() -> None:
    assert LIMIT_POOL_ENDPOINTS["sub_new"][0] == "/getTopicCXPooll"


def test_unknown_pool_type_falls_back_to_limit_up() -> None:
    assert normalize_pool_type("zt") == "limit_up"
    request = stock_limit_pool_request(LimitPoolQuery(pool_type="zt", date="20261106"))
    assert request.path == LIMIT_POOL_ENDPOINTS["limit_up"][0]


def test_empty_date_defaults_to_beijing_today() -> None:
    # 2026-11-06 20:00 UTC 已是北京时间 11-07
    now = datetime(2026, 11, 6, 20, 0, tzinfo=timezone.utc)
    assert resolve_date(None, now) == "20261107"
    assert resolve_date("", now) == "20261107"
    beijing = timezone(timedelta(hours=8))
    assert resolve_date(None, datetime(2026, 11, 6, 9, 0, tzinfo=beijing)) == "20261106"


@pytest.mark.parametrize("bad", ["2026-11-06", "261106", "2026116", "abcdefgh"])
def test_malformed_date_raises(bad: str) -> None:
    # 上游对错误格式不报错、只返回空数据，所以在本地拦住
    with pytest.raises(ValueError, match="YYYYMMDD"):
        resolve_date(bad)


def test_registry_exposes_stock_limit_pool_request() -> None:
    assert registry.stock_limit_pool_request is stock_limit_pool_request

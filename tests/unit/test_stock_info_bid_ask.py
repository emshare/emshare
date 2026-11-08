"""个股信息与五档盘口的映射、请求构建与“查无此券”处理行为锁（不触网）。

固定报文是 2026-11-06 收盘后（11-07 抓取）的真实返回：
- info：000001 平安银行 / 600519 贵州茅台 / 920085 N森峰（北交所新股首日）的显式字段集；
- bid_ask：000001 / 920085 的默认字段集（不传 fields，五档只在这里）；
- not_found：不存在的代码 0.999999（rc=100，data=null）。
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

from em.application import registry
from em.channels.eastmoney import config
from em.channels.eastmoney.ashare_stocks.stock_bid_ask.stock_bid_ask_em import (
    stock_bid_ask_request,
)
from em.channels.eastmoney.ashare_stocks.stock_info.stock_info_em import (
    normalize_market,
    stock_info_request,
)
from em.channels.eastmoney.mapping import is_security_not_found, to_stock_bid_ask, to_stock_info
from em.channels.eastmoney.source import EastMoneySource, _is_valid_payload, _is_valid_stock_get
from em.core.errors import ChannelError, SecurityNotFoundError
from em.core.proxy import ProxyPool, ProxyRouter, ProxySettings
from em.core.resilience import RetryPolicy
from em.core.transport import HttpClient
from em.domain.queries import StockBidAskQuery, StockInfoQuery

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "eastmoney" / "stock_get.json"


def _fx() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- stock_info_em


def test_stock_info_maps_akshare_items() -> None:
    info = to_stock_info(_fx()["info"]["1.600519"], "sh")
    assert (info.code, info.name, info.market) == ("600519", "贵州茅台", "sh")
    assert info.industry == "白酒Ⅱ"
    assert info.listing_date == "2001-08-27"
    assert info.price == pytest.approx(1453.0)  # f43=145300，按 10**f59 还原
    assert info.total_shares == pytest.approx(1250081601.0)  # 单位股
    assert info.float_shares == pytest.approx(1250081601.0)
    assert info.total_market_cap == pytest.approx(1816368566253.0)
    assert info.float_market_cap == pytest.approx(1816368566253.0)


def test_stock_info_bj_new_listing() -> None:
    info = to_stock_info(_fx()["info"]["0.920085"], "bj")
    assert info.name == "N森峰"
    assert info.listing_date == "2026-11-06"
    assert info.price == pytest.approx(39.25)
    assert info.float_shares < info.total_shares


def test_stock_info_request() -> None:
    request = stock_info_request(StockInfoQuery(code="600519", market="sh"))
    assert request.url() == f"{config.GUEST_HOST}{config.STOCK_GET_PATH}"
    params = request.params()
    assert params["secid"] == "1.600519"
    assert params["fields"] == config.STOCK_INFO_FIELDS
    assert params["fltt"] == "1"
    assert request.market == "sh"


def test_unknown_market_falls_back_to_sz() -> None:
    assert normalize_market("hk") == "sz"
    request = stock_info_request(StockInfoQuery(code="000001", market="hk"))
    assert request.secid == "0.000001"
    assert request.market == "sz"


# ---------------------------------------------------------------- stock_bid_ask_em


def test_bid_ask_book_levels() -> None:
    book = to_stock_bid_ask(_fx()["bid_ask"]["0.000001"], "sz")
    assert [b.price for b in book.bids] == pytest.approx([11.81, 11.80, 11.79, 11.78, 11.77])
    assert [b.volume for b in book.bids] == pytest.approx([4384, 3026, 1562, 1001, 1836])
    assert [a.price for a in book.asks] == pytest.approx([11.82, 11.83, 11.84, 11.85, 11.86])
    assert [a.volume for a in book.asks] == pytest.approx([1019, 717, 3560, 44706, 16687])
    # 买一 < 卖一，各自向外单调
    assert book.bids[0].price < book.asks[0].price


def test_bid_ask_quote_fields() -> None:
    book = to_stock_bid_ask(_fx()["bid_ask"]["0.000001"], "sz")
    assert (book.code, book.name, book.market) == ("000001", "平安银行", "sz")
    assert book.price == pytest.approx(11.81)
    assert book.avg_price == pytest.approx(11.75)
    assert book.open == pytest.approx(11.62)
    assert book.high == pytest.approx(11.85)
    assert book.low == pytest.approx(11.57)
    assert book.pre_close == pytest.approx(11.64)
    assert book.limit_up == pytest.approx(12.80)
    assert book.limit_down == pytest.approx(10.48)
    assert book.volume == pytest.approx(1640276)  # 手
    assert book.turnover == pytest.approx(1927307590.53)
    assert book.outer_volume == pytest.approx(938074)
    assert book.volume_ratio == pytest.approx(0.99)


def test_bid_ask_no_price_limit_is_none() -> None:
    # 北交所新股首日不设涨跌幅限制：上游涨跌停价、量比为 "-"
    book = to_stock_bid_ask(_fx()["bid_ask"]["0.920085"], "bj")
    assert book.limit_up is None
    assert book.limit_down is None
    assert book.volume_ratio is None
    assert book.price == pytest.approx(39.25)
    assert book.bids[0].price == pytest.approx(39.25)


def test_bid_ask_request_omits_fields() -> None:
    # 五档 f11–f40 只在默认字段集里：显式传 fields 一个都拿不到（实测）
    request = stock_bid_ask_request(StockBidAskQuery(code="000001", market="sz"))
    params = request.params()
    assert "fields" not in params
    assert params["secid"] == "0.000001"
    assert request.market == "sz"


def test_bid_ask_empty_book_levels() -> None:
    book = to_stock_bid_ask({"rc": 0, "data": {"f57": "x", "f58": "y", "f59": 2}})
    assert len(book.bids) == len(book.asks) == 5
    assert all(level.price is None and level.volume is None for level in book.bids)


# ---------------------------------------------------------------- 查无此券


def test_not_found_payload_detected() -> None:
    raw = _fx()["not_found"]
    assert raw["rc"] == 100
    assert is_security_not_found(raw)
    assert not is_security_not_found({"rc": 0, "data": {}})
    assert not is_security_not_found({"rc": 100, "data": {"f57": "x"}})  # 有数据就不是“查无”


def test_stock_get_validator_accepts_not_found_but_generic_does_not() -> None:
    text = json.dumps(_fx()["not_found"])
    assert _is_valid_stock_get(text) is True
    assert _is_valid_payload(text) is False  # 通用校验会把它当劫持页
    assert _is_valid_stock_get("<html>502</html>") is False
    assert _is_valid_stock_get('{"rc":102,"data":null}') is True


class _FakeClient:
    def __init__(self, text: str) -> None:
        self._text = text

    def get_text(self, url, params, headers, validator=None, read_timeout=None) -> str:
        assert validator is None or validator(self._text)
        return self._text


@pytest.mark.parametrize("fetch", ["fetch_stock_info", "fetch_stock_bid_ask"])
def test_fetch_raises_not_found(fetch: str) -> None:
    source = EastMoneySource(_FakeClient(json.dumps(_fx()["not_found"])))
    request = stock_info_request(StockInfoQuery(code="999999"))
    with pytest.raises(SecurityNotFoundError, match=r"secid=0\.999999"):
        getattr(source, fetch)(request)


def test_not_found_is_not_retryable_channel_error() -> None:
    assert not issubclass(SecurityNotFoundError, ChannelError)


def test_not_found_does_not_burn_proxies_through_real_transport() -> None:
    # 走真实 HttpClient + ProxyPool：rc=100 只发 1 次请求，不拉黑 IP、不换 IP 重试
    pool_session = MagicMock(spec=requests.Session)
    pool_session.get.return_value = MagicMock(text="1.1.1.1:8080\n2.2.2.2:8080")
    ps = ProxySettings(api="http://x", num=2, ttl_sec=30, mode="always", prefilter_sources=0)
    router = ProxyRouter(ProxyPool(ps, pool_session), ps)
    session = MagicMock(spec=requests.Session)
    session.get.return_value = MagicMock(status_code=200, text=json.dumps(_fx()["not_found"]))
    client = HttpClient(session, router, RetryPolicy(max_retries=3, backoff_sec=0.0), timeout_sec=5)

    with pytest.raises(SecurityNotFoundError):
        EastMoneySource(client).fetch_stock_info(stock_info_request(StockInfoQuery(code="999999")))
    assert session.get.call_count == 1
    assert router._pool.stats()["ip_failures"] == 0


def test_registry_exposes_requests() -> None:
    assert registry.stock_info_request is stock_info_request
    assert registry.stock_bid_ask_request is stock_bid_ask_request

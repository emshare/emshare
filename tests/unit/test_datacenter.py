"""数据中心报表底座的行为锁：协议校验、单页解析、查询条件、翻页器（不触网）。

固定报文 ``datacenter_billboard.json`` 是 2026-11-09 抓取的真实响应（龙虎榜详情）：
``detail_page`` 为 11-06 共 79 条中每页 4 条的第 1 页；``empty`` / ``query_error`` /
``param_error`` 分别是上游对“查无数据 / 列名写错 / 页码不是整数”的真实答复（9201 / 9501 / 200）。
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

from em.application import reports
from em.application.reports import fetch_report
from em.channels.eastmoney import config
from em.channels.eastmoney.datacenter import (
    Column,
    ReportSpec,
    codes_of,
    dash_date,
    date_span,
    day,
    equals,
    filter_columns,
    from_wan,
    from_yi,
    integer,
    is_answer,
    last_quarter_end,
    market_of,
    normalize_scope,
    on,
    pct_of_ratio,
    report_period,
    safe_value,
    scope_filter,
    text,
    to_report_chunk,
)
from em.channels.eastmoney.request import DatacenterRequest
from em.channels.eastmoney.source import EastMoneySource, _is_valid_datacenter
from em.core.errors import InvalidContentError, QueryRejectedError
from em.core.proxy import ProxyPool, ProxyRouter, ProxySettings
from em.core.resilience import RetryPolicy
from em.core.transport import HttpClient

FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "eastmoney" / "datacenter_billboard.json"
)
BUSY = {"success": False, "message": "服务器繁忙", "code": 9701, "result": None}


def _fx() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- 协议校验


@pytest.mark.parametrize("name", ["detail_page", "empty", "query_error", "param_error", "latest"])
def test_upstream_answers_pass_protocol_check(name: str) -> None:
    # 查无数据与查询写错都是正常答复：判失败会拉黑好 IP 并换 IP 重试到耗尽
    assert _is_valid_datacenter(json.dumps(_fx()[name]))


@pytest.mark.parametrize(
    "text_",
    [
        json.dumps(BUSY),  # 服务器繁忙：换 IP 重试
        '{"code": 1234, "success": false}',  # 未知 code
        '{"code": 0, "result": null}',  # 成功却没有 result
        "<html>502 Bad Gateway</html>",
        "",
    ],
)
def test_busy_unknown_and_hijacked_fail_protocol_check(text_: str) -> None:
    assert not _is_valid_datacenter(text_)


def test_is_answer_rejects_non_dict() -> None:
    assert not is_answer(None)
    assert not is_answer([1, 2])


# ---------------------------------------------------------------- 单页解析


def _row_spec() -> ReportSpec[dict]:
    def model(**kw: object) -> dict:
        return kw

    return ReportSpec(
        report="RPT_DAILYBILLBOARD_DETAILSNEW",
        model=model,
        columns=(Column("code", "SECURITY_CODE"), Column("day", "TRADE_DATE", day)),
    )


def test_chunk_carries_total_pages_rows_and_keys() -> None:
    chunk = to_report_chunk(_fx()["detail_page"], _row_spec().map_row)
    assert (chunk.total, chunk.pages) == (79, 20)
    assert len(chunk.items) == len(chunk.keys) == 4
    assert chunk.items[0] == {"code": "000525", "day": "2026-11-06"}
    assert len(set(chunk.keys)) == 4  # 整行去重键互不相同


@pytest.mark.parametrize("name", ["empty", "query_error"])
def test_chunk_of_null_result_is_empty(name: str) -> None:
    chunk = to_report_chunk(_fx()[name], _row_spec().map_row)
    assert (chunk.total, chunk.pages, chunk.items) == (0, 0, ())


def test_spec_requests_mapped_key_and_filter_columns() -> None:
    spec = ReportSpec(
        report="R",
        model=dict,
        columns=(Column("a", "A"), Column("pair", ("B", "C"), tuple)),
        key_columns=("ID",),
        sort=(("A", 1), ("ID", -1)),
    )
    request = spec.request("(D>='2026-01-01')(A=\"x\")")
    assert request.columns == ("A", "B", "C", "ID", "D")
    params = request.params()
    assert (params["sortColumns"], params["sortTypes"]) == ("A,ID", "1,-1")
    assert params["pageSize"] == str(config.DATACENTER_PAGE_SIZE)
    assert spec.map_row({"A": "1", "B": 2, "C": 3}) == {"a": "1", "pair": (2, 3)}


def test_filter_columns_parses_all_operators() -> None:
    flt = (
        "(TRADE_DATE>='2026-11-02')(TRADE_DATE<='2026-11-06')(SECURITY_CODE=\"000530\")"
        '(TRADE_MARKET_CODE in ("069001001001"))((GOODWILL_STATE="1")( | IMPAIRMENT_STATE="1"))'
        '(N_DATE=-30)(X<>"NULL")'
    )
    assert filter_columns(flt) == (
        "TRADE_DATE",
        "SECURITY_CODE",
        "TRADE_MARKET_CODE",
        "GOODWILL_STATE",
        "IMPAIRMENT_STATE",
        "N_DATE",
        "X",
    )


def test_latest_lookup_and_on_day() -> None:
    spec = _row_spec()
    request = spec.request('(TRADE_MARKET_CODE="069001017")', latest_of="TRADE_DATE")
    lookup = request.latest_lookup()
    params = lookup.params()
    assert (params["sortColumns"], params["sortTypes"], params["pageSize"]) == (
        "TRADE_DATE",
        "-1",
        "1",
    )
    assert params["columns"] == "TRADE_DATE"
    assert params["filter"] == request.filter
    assert lookup.mapper({"TRADE_DATE": "2026-11-09 00:00:00"}) == "2026-11-09"
    pinned = request.on_day("2026-11-06")
    assert pinned.filter == "(TRADE_MARKET_CODE=\"069001017\")(TRADE_DATE='2026-11-06')"
    assert pinned.latest_of == ""
    assert pinned.with_page(3).params()["pageNumber"] == "3"


# ---------------------------------------------------------------- 字段换算与查询条件


def test_converters() -> None:
    assert text(" - ") is None and text("") is None and text(None) is None
    assert day("2026-11-06 00:00:00") == "2026-11-06"
    assert market_of("000525.SZ") == "sz" and market_of("920717.BJ") == "bj"
    assert market_of("00700.HK") is None and market_of(None) is None
    assert pct_of_ratio(0.021511643931) == pytest.approx(2.1511643931)
    assert from_wan(861.82026) == pytest.approx(8618202.6)
    assert codes_of("600127.SH 600261.SH") == ("600127", "600261")
    assert codes_of(None) == ()
    assert integer("12") == 12 and integer(3.0) == 3 and integer("-") is None
    assert from_yi(1.5) == pytest.approx(150000000.0)
    assert on("TRADE_DATE", "2026-11-06") == "(TRADE_DATE='2026-11-06')"
    assert equals("SECURITY_CODE", "000530") == '(SECURITY_CODE="000530")'


def test_scope_filters_match_stock_list_scopes() -> None:
    from em.channels.eastmoney.ashare_stocks.stock_list import MARKET_SCOPE_FS

    assert set(config.DATACENTER_SCOPE_FILTERS) <= set(MARKET_SCOPE_FS)  # 取值与 stock_list_em 一致
    assert scope_filter("all") == "" and scope_filter("nope") == ""
    assert scope_filter("bj") == '(TRADE_MARKET_CODE="069001017")'
    assert normalize_scope("kc") == "kc" and normalize_scope("nope") == "all"
    assert all(
        filter_columns(f) == ("TRADE_MARKET_CODE",)
        for f in config.DATACENTER_SCOPE_FILTERS.values()
        if f
    )


@pytest.mark.parametrize("bad", ["2026-11-06", "261106", "20261131", "abcdefgh", ""])
def test_dash_date_rejects_bad_input(bad: str) -> None:
    # 上游对其他写法只回 9501 语法错误，本地先拦住给出可读的提示
    with pytest.raises(ValueError):
        dash_date(bad)


def test_date_span_rules() -> None:
    now = datetime(2026, 11, 9, 1, 0, tzinfo=timezone.utc)  # 北京时间 11-09 09:00
    assert date_span(None, None) is None
    assert date_span("20261102", "20261106") == ("2026-11-02", "2026-11-06")
    assert date_span("20261105", None, now) == ("2026-11-05", "2026-11-09")  # 取到今天
    assert date_span(None, "20261106") == ("2026-11-06", "2026-11-06")  # 只给 end：单日
    with pytest.raises(ValueError, match="晚于"):
        date_span("20261106", "20261101")


def test_report_period_rules() -> None:
    beijing = timezone(timedelta(hours=8))
    assert report_period("20260930") == "2026-09-30"
    assert report_period(None, datetime(2026, 11, 9, tzinfo=beijing)) == "2026-09-30"
    with pytest.raises(ValueError, match="季末"):
        report_period("20261106")
    # 季末当天还没出齐，取上一个季末
    assert last_quarter_end(datetime(2026, 9, 30).date()).isoformat() == "2026-06-30"
    assert last_quarter_end(datetime(2026, 1, 5).date()).isoformat() == "2025-12-31"


@pytest.mark.parametrize("bad", ['000001")(X="1', "a'b", "(x)", ""])
def test_safe_value_rejects_filter_injection(bad: str) -> None:
    with pytest.raises(ValueError):
        safe_value(bad, "code")


# ---------------------------------------------------------------- 翻页器


class _PagedClient:
    """按页号返回预设页的 HttpClient 桩：与真实传输层一样执行协议校验。"""

    def __init__(self, pages: dict[int, dict], latest: str | None = None, live: int = 0) -> None:
        self.pages = pages
        self.latest = latest
        self.live = live
        self.calls: list[dict] = []

    def get_text(self, url, params, headers, validator=None, read_timeout=None) -> str:
        self.calls.append(dict(params))
        if params["pageSize"] == "1" and self.latest is not None:
            body: dict = {
                "code": 0,
                "result": {"count": 1, "pages": 1, "data": [{"TRADE_DATE": self.latest}]},
            }
        else:
            body = self.pages[int(params["pageNumber"])]
        text_ = json.dumps(body)
        if validator is not None and not validator(text_):
            raise InvalidContentError(f"桩：未通过校验 {text_[:40]}")
        return text_

    def available_proxies(self, url: str) -> int:
        return self.live


def _page(codes: list[str], total: int, pages: int) -> dict:
    return {
        "code": 0,
        "result": {"count": total, "pages": pages, "data": [{"SECURITY_CODE": c} for c in codes]},
    }


def _request(**kw: object) -> DatacenterRequest[str]:
    return DatacenterRequest(
        report="R", columns=("SECURITY_CODE",), mapper=lambda row: row["SECURITY_CODE"], **kw
    )


def test_fetches_all_pages_in_order() -> None:
    client = _PagedClient(
        {1: _page(["a", "b"], 5, 3), 2: _page(["c", "d"], 5, 3), 3: _page(["e"], 5, 3)}
    )
    page = fetch_report(client, _request())  # type: ignore[arg-type]
    assert (page.total, page.items) == (5, ("a", "b", "c", "d", "e"))
    assert sorted(int(c["pageNumber"]) for c in client.calls) == [1, 2, 3]


def test_empty_result_is_empty_page() -> None:
    client = _PagedClient({1: _fx()["empty"]})
    page = fetch_report(client, _request())  # type: ignore[arg-type]
    assert (page.total, page.items) == (0, ())
    assert len(client.calls) == 1


def test_latest_day_lookup_then_filter() -> None:
    client = _PagedClient({1: _page(["a"], 1, 1)}, latest="2026-11-09 00:00:00")
    page = fetch_report(client, _request(filter='(X="1")', latest_of="TRADE_DATE"))  # type: ignore[arg-type]
    assert page.items == ("a",)
    lookup, data = client.calls
    assert lookup["pageSize"] == "1" and lookup["sortColumns"] == "TRADE_DATE"
    assert data["filter"] == "(X=\"1\")(TRADE_DATE='2026-11-09')"


def test_latest_day_on_empty_table() -> None:
    client = _PagedClient({1: _fx()["empty"]})
    page = fetch_report(client, _request(latest_of="TRADE_DATE"))  # type: ignore[arg-type]
    assert (page.total, page.items) == (0, ())
    assert len(client.calls) == 1  # 最新日都查不到，不再发数据请求


def test_distinct_drops_repeated_rows_only_when_enabled() -> None:
    pages = {1: _page(["a", "a"], 3, 2), 2: _page(["b"], 3, 2)}
    assert fetch_report(_PagedClient(pages), _request()).items == ("a", "a", "b")  # type: ignore[arg-type]
    assert fetch_report(_PagedClient(pages), _request(distinct=True)).items == ("a", "b")  # type: ignore[arg-type]


def test_refetches_round_once_when_counts_drift(caplog: pytest.LogCaptureFixture) -> None:
    # 首轮第 2 页报告的总数变了（翻页期间上游新增），整轮重取一次后一致
    client = _PagedClient({1: _page(["a", "b"], 3, 2), 2: _page(["c", "d"], 4, 2)})
    calls = {"n": 0}
    original = client.get_text

    def drifting(url, params, headers, validator=None, read_timeout=None) -> str:
        calls["n"] += 1
        if calls["n"] == 3:  # 第二轮起上游稳定
            client.pages = {1: _page(["a", "b"], 4, 2), 2: _page(["c", "d"], 4, 2)}
        return original(url, params, headers, validator, read_timeout)

    client.get_text = drifting  # type: ignore[method-assign]
    with caplog.at_level("INFO"):
        page = fetch_report(client, _request())  # type: ignore[arg-type]
    assert (page.total, page.items) == (4, ("a", "b", "c", "d"))
    assert calls["n"] == 4
    assert "整轮重取" in caplog.text


def test_persistent_drift_returns_last_round_with_warning(caplog: pytest.LogCaptureFixture) -> None:
    client = _PagedClient({1: _page(["a", "b"], 5, 2), 2: _page(["c"], 5, 2)})
    page = fetch_report(client, _request())  # type: ignore[arg-type]
    assert (page.total, len(page.items)) == (5, 3)
    assert "翻页结果不一致" in caplog.text


def test_query_error_raises_without_retry() -> None:
    client = _PagedClient({1: _fx()["query_error"]})
    with pytest.raises(QueryRejectedError, match="NO_SUCH_COL"):
        fetch_report(client, _request())  # type: ignore[arg-type]
    assert len(client.calls) == 1


def test_query_rejected_is_not_a_channel_error() -> None:
    from em.core.errors import ChannelError

    assert not issubclass(QueryRejectedError, ChannelError)


def test_page_failure_is_retried_once(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reports.time, "sleep", lambda s: None)
    client = _PagedClient({1: _page(["a"], 2, 2), 2: _page(["b"], 2, 2)})
    original = client.get_text
    failed = {"n": 0}

    def flaky(url, params, headers, validator=None, read_timeout=None) -> str:
        if params["pageNumber"] == "2" and failed["n"] == 0:
            failed["n"] += 1
            raise InvalidContentError("桩：传输层重试耗尽")
        return original(url, params, headers, validator, read_timeout)

    client.get_text = flaky  # type: ignore[method-assign]
    assert fetch_report(client, _request()).items == ("a", "b")  # type: ignore[arg-type]


def test_workers_follow_live_proxies() -> None:
    assert reports._effective_workers(5, 0, 10) == 5  # 直连态：保持给定并发
    assert reports._effective_workers(5, 1, 10) == 2  # 单出口：2 个
    assert reports._effective_workers(5, 9, 3) == 3  # 不超过待取页数
    assert reports._effective_workers(5, 1, 0) == 1


def test_read_budget_is_declared() -> None:
    timeouts: list[float | None] = []

    class _Client(_PagedClient):
        def get_text(self, url, params, headers, validator=None, read_timeout=None) -> str:
            timeouts.append(read_timeout)
            return super().get_text(url, params, headers, validator, read_timeout)

    EastMoneySource(_Client({1: _page(["a"], 1, 1)})).fetch_report_page(_request())  # type: ignore[arg-type]
    assert timeouts == [config.DATACENTER_READ_TIMEOUT_SEC]


# ---------------------------------------------------------------- 真实传输层


def _real_client(body: dict) -> tuple[HttpClient, MagicMock, ProxyRouter]:
    pool_session = MagicMock(spec=requests.Session)
    pool_session.get.return_value = MagicMock(text="1.1.1.1:8080\n2.2.2.2:8080")
    ps = ProxySettings(api="http://x", num=2, ttl_sec=30, mode="always", prefilter_sources=0)
    router = ProxyRouter(ProxyPool(ps, pool_session), ps)
    session = MagicMock(spec=requests.Session)
    session.get.return_value = MagicMock(status_code=200, text=json.dumps(body))
    client = HttpClient(session, router, RetryPolicy(max_retries=3, backoff_sec=0.0), timeout_sec=5)
    return client, session, router


@pytest.mark.parametrize("name", ["empty", "query_error", "param_error"])
def test_answers_do_not_burn_proxies_through_real_transport(name: str) -> None:
    # 9201 / 9501 / 200 只发 1 次请求，不拉黑 IP、不换 IP 重试
    client, session, router = _real_client(_fx()[name])
    source = EastMoneySource(client)
    if name == "empty":
        assert source.fetch_report_page(_request()).items == ()  # type: ignore[arg-type]
    else:
        with pytest.raises(QueryRejectedError):
            source.fetch_report_page(_request())  # type: ignore[arg-type]
    assert session.get.call_count == 1
    assert router._pool.stats()["ip_failures"] == 0


def test_busy_is_retried_through_real_transport() -> None:
    client, session, _ = _real_client(BUSY)
    with pytest.raises(InvalidContentError):
        EastMoneySource(client).fetch_report_page(_request())  # type: ignore[arg-type]
    assert session.get.call_count == 4  # 1 次 + 3 次换 IP 重试

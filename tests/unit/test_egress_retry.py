"""无法换出口时限制疑似限流；瞬时故障、代理轮换与分页终止的离线回归。"""

import socket
from http.client import RemoteDisconnected
from unittest.mock import MagicMock

import pytest
import requests
from urllib3.exceptions import ProtocolError

from em.application import market_data, reports
from em.application.pagination import PageRetryGuard
from em.channels.eastmoney.datacenter import ReportChunk
from em.channels.eastmoney.request import DatacenterRequest
from em.core.errors import (
    EgressRetryStopped,
    NetworkError,
    RemoteDisconnectError,
    UpstreamReadTimeout,
)
from em.core.settings import Settings
from em.core.transport import _classify
from em.domain.models import Quote, QuotePage

TARGET = "https://push2.eastmoney.com/test"


def disconnected():
    return requests.ConnectionError(ProtocolError("aborted", RemoteDisconnected("closed")))


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("offline test attempted network")

    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr("em.core.transport.sleep_backoff", lambda *args: 0.0)
    monkeypatch.setattr(market_data.time, "sleep", lambda *args: None)
    monkeypatch.setenv("EM_LEDGER_PATH", "none")


def make_client(monkeypatch, outcomes, **settings):
    session = MagicMock()
    session.get.side_effect = outcomes
    monkeypatch.setattr(market_data, "ExplicitProxySession", lambda: session)
    client = market_data._create_client(Settings(proxy_prefilter=False, **settings))
    return client, session


def ok():
    return MagicMock(status_code=200, text='{"rc":0}')


@pytest.mark.parametrize(
    "settings",
    [
        {"proxy_api": "", "proxy_mode": "auto"},
        {"proxy_api": "https://supplier.test", "proxy_mode": "never"},
        {"proxy_api": "https://supplier.test", "proxy_enabled": False},
    ],
)
def test_two_disconnects_stop_without_rotation_and_preserve_cause(monkeypatch, settings):
    client, session = make_client(monkeypatch, [disconnected(), disconnected(), ok()], **settings)
    try:
        with pytest.raises(EgressRetryStopped) as caught:
            client.get_text(TARGET, {}, {})
        assert not caught.value.retryable
        assert "疑似限流" in str(caught.value)
        assert isinstance(caught.value.__cause__, RemoteDisconnectError)
        assert client.timing_stats()["failed_attempts"] == 2
        assert session.get.call_count == 2
        # 不跨调用持久封禁；调用者下次主动请求可以恢复。
        assert client.get_text(TARGET, {}, {}) == '{"rc":0}'
    finally:
        client.close()


@pytest.mark.parametrize(
    "sequence",
    [
        [disconnected(), ok()],
        [disconnected(), requests.ReadTimeout("slow"), disconnected(), ok()],
        [requests.ConnectionError("dns failure"), requests.ConnectionError("dns failure"), ok()],
        [requests.exceptions.ProxyError("tunnel", RemoteDisconnected("closed"))] * 2 + [ok()],
        [requests.exceptions.SSLError("tls", RemoteDisconnected("closed"))] * 2 + [ok()],
    ],
)
def test_transient_or_unrelated_failures_keep_recovery(monkeypatch, sequence):
    client, session = make_client(monkeypatch, sequence, proxy_api="")
    try:
        client.get_text(TARGET, {}, {})
        assert session.get.call_count == len(sequence)
    finally:
        client.close()


@pytest.mark.parametrize(
    "host", ["datacenter-web.eastmoney.com", "push2.example.com", "push2.eastmoney.com.evil.test"]
)
def test_other_hosts_are_not_subject_to_push2_rule(monkeypatch, host):
    client, session = make_client(monkeypatch, [disconnected(), disconnected(), ok()], proxy_api="")
    try:
        client.get_text(f"https://{host}/test", {}, {})
        assert session.get.call_count == 3
    finally:
        client.close()


@pytest.mark.parametrize(
    "host",
    [
        "pushguest.eastmoney.com",
        "82.push2.eastmoney.com",
        "push2his.eastmoney.com",
        "63.push2his.eastmoney.com",
        "push2ex.eastmoney.com",
        "push2delay.eastmoney.com",
    ],
)
def test_push2_variants_stop(monkeypatch, host):
    client, session = make_client(monkeypatch, [disconnected(), disconnected()], proxy_api="")
    try:
        with pytest.raises(EgressRetryStopped):
            client.get_text(f"https://{host}/test", {}, {})
        assert session.get.call_count == 2
    finally:
        client.close()


def test_configured_retry_limit_is_not_increased(monkeypatch):
    client, session = make_client(monkeypatch, [disconnected()], proxy_api="", max_retries=0)
    try:
        with pytest.raises(RemoteDisconnectError):
            client.get_text(TARGET, {}, {})
        assert session.get.call_count == 1
    finally:
        client.close()


def test_dynamic_route_still_switches_and_replaces_bad_proxy(monkeypatch):
    supplier = MagicMock(text="192.0.2.1:80\n192.0.2.2:80")
    client, session = make_client(
        monkeypatch,
        [disconnected(), supplier, disconnected(), ok()],
        proxy_api="https://supplier.test",
        proxy_num=2,
    )
    try:
        client.get_text(TARGET, {}, {})
        business = [c.kwargs["proxies"] for c in session.get.call_args_list if c.args[0] == TARGET]
        assert business == [
            None,
            {"http": "http://192.0.2.1:80", "https": "http://192.0.2.1:80"},
            {"http": "http://192.0.2.2:80", "https": "http://192.0.2.2:80"},
        ]
    finally:
        client.close()


def test_classifier_handles_context_and_cycles():
    error = requests.ConnectionError("outer")
    error.__context__ = RemoteDisconnected("closed")
    error.__context__.__cause__ = error
    assert isinstance(_classify(error), RemoteDisconnectError)
    error.__context__ = requests.ReadTimeout("slow")
    error.__context__._em_network_phase = "response_headers"
    assert isinstance(_classify(error), UpstreamReadTimeout)


def test_first_snapshot_page_stops_after_two_http_attempts(monkeypatch):
    client, session = make_client(monkeypatch, [disconnected(), disconnected()], proxy_api="")
    monkeypatch.setattr(market_data, "_build_client", lambda *args, **kwargs: client)
    with pytest.raises(EgressRetryStopped):
        market_data.stock_list_all_em(workers=1, max_rounds=5)
    assert session.get.call_count == 2
    session.close.assert_called_once()


def test_later_snapshot_failure_skips_queued_pages_and_refill(monkeypatch):
    source = MagicMock()
    source.fetch_page.side_effect = [
        QuotePage(total=400, items=(Quote(code="000001", name="x"),)),
        EgressRetryStopped("疑似限流"),
    ]
    monkeypatch.setattr(market_data.registry, "EastMoneySource", lambda client: source)
    client = MagicMock()
    client.available_proxies.return_value = 0
    with pytest.raises(EgressRetryStopped):
        market_data._stock_list_all(None, 5, 1, client)
    assert [c.args[0].page for c in source.fetch_page.call_args_list] == [1, 2]


@pytest.mark.parametrize("fail_first", [True, False])
def test_reports_propagate_stop_without_page_or_round_retry(monkeypatch, fail_first):
    source = MagicMock()
    failure = EgressRetryStopped("疑似限流")
    source.fetch_report_page.side_effect = (
        [failure]
        if fail_first
        else [ReportChunk(total=4, pages=4, items=("first",), keys=("first",)), failure]
    )
    monkeypatch.setattr(reports.registry, "EastMoneySource", lambda client: source)
    monkeypatch.setattr(reports, "REPORT_FETCH_WORKERS", 1)
    client = MagicMock()
    client.available_proxies.return_value = 0
    request = DatacenterRequest(report="TEST", columns=("X",), mapper=lambda row: row)
    with pytest.raises(EgressRetryStopped):
        reports.fetch_report(client, request)
    assert source.fetch_report_page.call_count == (1 if fail_first else 2)


def test_report_transient_error_still_retries():
    source = MagicMock()
    chunk = ReportChunk(total=1, pages=1, items=("ok",), keys=("ok",))
    source.fetch_report_page.side_effect = [NetworkError("transient"), chunk]
    request = DatacenterRequest(report="TEST", columns=("X",), mapper=lambda row: row)
    assert reports._fetch_page(source, request, PageRetryGuard()) is chunk
    assert source.fetch_report_page.call_count == 2


def test_always_proxy_keeps_rotating_after_two_disconnects(monkeypatch):
    supplier = MagicMock(text="192.0.2.1:80\n192.0.2.2:80\n192.0.2.3:80")
    client, session = make_client(
        monkeypatch,
        [supplier, disconnected(), disconnected(), ok()],
        proxy_api="https://supplier.test",
        proxy_num=3,
        proxy_mode="always",
    )
    try:
        client.get_text(TARGET, {}, {})
        used = [
            c.kwargs["proxies"]["https"] for c in session.get.call_args_list if c.args[0] == TARGET
        ]
        assert used == ["http://192.0.2.1:80", "http://192.0.2.2:80", "http://192.0.2.3:80"]
    finally:
        client.close()


def test_connection_reset_has_same_bounded_retry(monkeypatch):
    errors = [requests.ConnectionError(ConnectionResetError("reset")) for _ in range(2)]
    client, session = make_client(monkeypatch, errors, proxy_api="")
    try:
        with pytest.raises(EgressRetryStopped):
            client.get_text(TARGET, {}, {})
        assert session.get.call_count == 2
    finally:
        client.close()


def test_page_guard_stops_new_work_but_allows_inflight_to_finish():
    import threading
    from concurrent.futures import ThreadPoolExecutor

    guard = PageRetryGuard()
    entered = threading.Event()
    release = threading.Event()

    def inflight():
        with guard.attempt():
            entered.set()
            assert release.wait(timeout=3)
        return "finished"

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(inflight)
        try:
            assert entered.wait(timeout=3)
            with pytest.raises(EgressRetryStopped), guard.attempt():
                raise EgressRetryStopped("stop")
            with pytest.raises(EgressRetryStopped), guard.attempt():
                pytest.fail("new page must not start")
        finally:
            release.set()
        assert future.result(timeout=3) == "finished"
    with PageRetryGuard().attempt():
        pass  # 新任务没有继承上次终止状态。

"""固定出口的配置、真实发送参数、无采购与认证脱敏（完全离线）。"""

import json
import socket
import traceback
from http.client import RemoteDisconnected
from unittest.mock import MagicMock
from urllib.parse import urlsplit

import pytest
import requests
from urllib3.exceptions import ProtocolError

from em.application import convenience, market_data, resolve
from em.core.errors import ConfigError, EgressRetryStopped
from em.core.fixed_proxy import FixedProxyRouter
from em.core.settings import Settings

URL = "http://alice:secret%40pass@proxy.test:8080"
TARGET = "https://pushguest.eastmoney.com/test"


@pytest.fixture(autouse=True)
def isolated(monkeypatch, clean_em_env):
    def deny(*args, **kwargs):
        raise AssertionError("fixed proxy must not purchase/probe/contact network")

    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(market_data, "_usage_for", deny)
    monkeypatch.setattr(market_data, "ProxyPool", deny)
    monkeypatch.setattr(market_data, "_make_prober", deny)
    monkeypatch.setattr("em.core.transport.sleep_backoff", lambda *args: 0.0)
    monkeypatch.setenv("EM_LEDGER_PATH", "none")
    monkeypatch.setenv("HTTPS_PROXY", "http://environment.test:80")
    resolve.reset_resolve_cache()
    yield
    resolve.reset_resolve_cache()
    if resolve._session.cache_info().currsize:
        resolve._session().close()
    resolve._session.cache_clear()


@pytest.fixture
def wire(monkeypatch):
    calls, outcomes = [], []

    def send(self, request, stream=False, timeout=None, verify=True, cert=None, proxies=None):
        calls.append((request, dict(proxies=proxies, verify=verify, timeout=timeout)))
        result = outcomes.pop(0) if outcomes else (200, '{"rc":0}', {})
        if isinstance(result, Exception):
            raise result
        status, text, headers = result
        response = requests.Response()
        response.request = request
        response.url = request.url
        response.status_code = status
        response._content = text.encode()
        response.headers.update(headers)
        return response

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", send)
    return calls, outcomes


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:7890",
        "http://localhost:7890",
        "https://proxy.test:443",
        "http://[::1]:8080",
        URL,
    ],
)
def test_valid_settings_and_env(monkeypatch, url):
    monkeypatch.setenv("EM_PROXY_URL", url)
    settings = Settings.from_env()
    assert settings.proxy_url == url
    assert settings.fixed_proxy == url
    assert url not in repr(settings)


@pytest.mark.parametrize(
    "url",
    [
        "127.0.0.1:80",
        "socks5://host:80",
        "http://host",
        "http://host:0",
        "http://host:99999",
        "http://alice:secret@host:bad",
        "http://host:80/path",
        "http://host:80?token=secret",
        "http://host:80#secret",
        "http://:secret@host:80",
        "http://[::1:80",
        "http://host :80",
    ],
)
def test_invalid_url_does_not_echo_input(url):
    with pytest.raises(ConfigError) as caught:
        Settings(proxy_url=url)
    assert "secret" not in str(caught.value)
    assert url not in str(caught.value)


@pytest.mark.parametrize("mode", ["auto", "always", "never"])
def test_conflicting_sources_fail_even_if_disabled(mode):
    with pytest.raises(ConfigError, match="不能同时配置"):
        Settings(proxy_url=URL, proxy_api="http://supplier.test", proxy_mode=mode)


def test_backup_source_also_conflicts(monkeypatch):
    monkeypatch.setenv("EM_PROXY_URL", URL)
    monkeypatch.setenv("EM_PROXY_API_BACKUP", "http://supplier.test")
    with pytest.raises(ConfigError, match="不能同时配置"):
        Settings.from_env()


@pytest.mark.parametrize(
    "option",
    [
        {"proxy_usage_db": "usage.sqlite3"},
        {"proxy_usage_max_new": 2},
        {"proxy_usage_balance_url": "https://supplier.test/balance"},
    ],
)
def test_dynamic_budget_cannot_be_attached_to_fixed_proxy(option):
    with pytest.raises(ConfigError, match="固定代理不能配置"):
        Settings(proxy_url=URL, **option)


@pytest.mark.parametrize(
    ("mode", "enabled", "expected"),
    [
        ("auto", True, URL),
        ("always", True, URL),
        ("never", True, None),
        ("auto", False, None),
        ("always", False, None),
    ],
)
@pytest.mark.parametrize("scheme", ["http", "https"])
def test_fixed_route_modes_do_not_purchase_or_probe(
    wire, mode, enabled, expected, scheme, monkeypatch
):
    calls, _ = wire
    monkeypatch.setenv("REQUESTS_CA_BUNDLE", "/company/ca.pem")
    client = market_data._create_client(
        Settings(
            proxy_url=URL,
            proxy_mode=mode,
            proxy_enabled=enabled,
            # 极短动态租期不应限制固定出口。
            proxy_ttl_sec=2,
            proxy_safety_margin_sec=1,
        )
    )
    try:
        client.get_text(TARGET.replace("https:", f"{scheme}:"), {}, {})
        client.evict_last_proxy(TARGET.replace("https:", f"{scheme}:"))
        client.get_text(TARGET.replace("https:", f"{scheme}:"), {}, {})
        assert client.available_proxies(TARGET) == int(expected is not None)
        assert client.proxy_stats()["route_kind"] == ("fixed" if expected else "direct")
        assert client.timing_stats()["proxy_requests"] == (2 if expected else 0)
        assert "secret" not in repr(client.proxy_stats())
    finally:
        client.close()
    assert len(calls) == 2
    for request, kwargs in calls:
        assert dict(kwargs["proxies"]) == (
            {"http": expected, "https": expected} if expected else {}
        )
        assert kwargs["verify"] == "/company/ca.pem"
        assert kwargs["timeout"][0] == 3  # 固定出口不套动态 IP 首次使用的 1.5s。
        assert "Proxy-Authorization" not in request.headers
        assert "alice" not in request.url


def test_fixed_redirect_keeps_proxy_and_certificate(wire):
    calls, outcomes = wire
    outcomes.append((302, "", {"Location": "https://other.test/final"}))
    client = market_data._create_client(Settings(proxy_url=URL))
    try:
        client.get_text(TARGET, {}, {})
    finally:
        client.close()
    assert len(calls) == 2
    assert all(kwargs["proxies"]["https"] == URL for _, kwargs in calls)


@pytest.mark.parametrize(
    "error",
    [
        requests.exceptions.ProxyError,
        requests.ReadTimeout,
        requests.ConnectTimeout,
    ],
)
def test_fixed_failures_stop_at_two_and_redact_logs_and_traceback(wire, caplog, error):
    calls, outcomes = wire
    outcomes.extend([error(f"failed {URL}") for _ in range(2)])
    client = market_data._create_client(Settings(proxy_url=URL))
    try:
        with pytest.raises(EgressRetryStopped) as caught:
            client.get_text(TARGET, {}, {})
        trace = "".join(traceback.format_exception(caught.type, caught.value, caught.tb))
        for secret in (URL, "alice", "secret%40pass"):
            assert secret not in caplog.text
            assert secret not in trace
        assert "采购" in str(caught.value)
        assert len(calls) == 2
    finally:
        client.close()


@pytest.mark.parametrize("status", [403, 429])
def test_fixed_limit_status_stops(wire, status):
    calls, outcomes = wire
    outcomes.extend([(status, "blocked", {})] * 2)
    client = market_data._create_client(Settings(proxy_url=URL))
    try:
        with pytest.raises(EgressRetryStopped):
            client.get_text(TARGET, {}, {})
        assert len(calls) == 2
    finally:
        client.close()


def test_fixed_transient_disconnect_recovers_without_changing_proxy(wire):
    calls, outcomes = wire
    outcomes.append(
        requests.ConnectionError(ProtocolError("aborted", RemoteDisconnected("closed")))
    )
    client = market_data._create_client(Settings(proxy_url=URL))
    try:
        assert client.get_text(TARGET, {}, {}) == '{"rc":0}'
        assert [kwargs["proxies"]["https"] for _, kwargs in calls] == [URL, URL]
    finally:
        client.close()


def test_fixed_failure_propagates_through_snapshot(wire):
    calls, outcomes = wire
    outcomes.extend([requests.exceptions.ProxyError(URL) for _ in range(2)])
    with pytest.raises(EgressRetryStopped):
        market_data.stock_list_all_em(settings=Settings(proxy_url=URL), workers=1)
    assert len(calls) == 2


def search_response():
    return (
        200,
        json.dumps(
            {
                "QuotationCodeTable": {
                    "Data": [
                        {"Name": "测试", "Code": "000001", "SecurityTypeName": "深A"},
                        {"Name": "测试", "Code": "BK0001", "Classify": "BK"},
                    ]
                }
            }
        ),
        {},
    )


def test_search_cache_separates_fixed_and_direct_and_accepts_env(wire, monkeypatch):
    calls, outcomes = wire
    monkeypatch.setenv("EM_PROXY_URL", URL)
    outcomes.extend([search_response(), search_response()])
    assert resolve.resolve_code("测试").code == "000001"
    assert resolve.resolve_board("测试").code == "BK0001"
    assert resolve.resolve_code("测试", settings=Settings(proxy_url=URL, proxy_mode="never"))
    assert len(calls) == 2
    assert calls[0][1]["proxies"]["https"] == URL
    assert not calls[1][1]["proxies"]
    assert all(urlsplit(request.url).hostname == "searchapi.eastmoney.com" for request, _ in calls)


def test_search_failure_redacts_credential(wire):
    _, outcomes = wire
    outcomes.append(requests.exceptions.ProxyError(f"bad auth {URL}"))
    with pytest.raises(requests.exceptions.ProxyError) as caught:
        resolve.resolve_code("测试", settings=Settings(proxy_url=URL))
    assert "secret" not in "".join(traceback.format_exception(caught.type, caught.value, caught.tb))


def test_convenience_passes_same_settings_to_search_and_data(monkeypatch):
    settings = Settings(proxy_url=URL)
    lookup = MagicMock(return_value=resolve.StockRef("000001", "测试", "sz"))
    fetch = MagicMock(return_value="series")
    monkeypatch.setattr(convenience, "resolve_code", lookup)
    monkeypatch.setattr(convenience, "stock_kline_em", fetch)
    assert convenience.kline_by_name("测试", settings=settings) == "series"
    lookup.assert_called_once_with("测试", settings=settings)
    assert fetch.call_args.kwargs["settings"] is settings


def test_fixed_router_has_no_ttl_or_usage_reservation():
    router = FixedProxyRouter(URL)
    assert router.remaining_lifetime(URL) == float("inf")
    assert not router.can_rotate
    with router.usage_attempt(URL) as outcome:
        assert outcome is not None


def test_proxy_auth_encoding_is_passed_to_proxy_adapter():
    import base64

    adapter = requests.adapters.HTTPAdapter()
    try:
        value = adapter.proxy_headers(URL)["Proxy-Authorization"]
        assert value == "Basic " + base64.b64encode(b"alice:secret@pass").decode()
    finally:
        adapter.close()


def test_fixed_retry_limit_zero_still_attempts_only_once(wire):
    calls, outcomes = wire
    outcomes.append(requests.exceptions.ProxyError(URL))
    client = market_data._create_client(Settings(proxy_url=URL, max_retries=0))
    try:
        from em.core.errors import NetworkError

        with pytest.raises(NetworkError):
            client.get_text(TARGET, {}, {})
        assert len(calls) == 1
    finally:
        client.close()

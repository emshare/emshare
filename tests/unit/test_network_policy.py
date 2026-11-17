"""拦截真实 Session 下的适配器发送：验证路由、重定向和 CA 最终参数。"""

import json
import socket
from urllib.parse import urlsplit

import pytest
import requests

from em.application import market_data, resolve
from em.core.session import ExplicitProxySession
from em.core.settings import Settings
from em.core.usage import ProxyUsage

TARGET = "https://push2.eastmoney.com/test-policy"
SUPPLIER = "https://supplier.test/get"
IP = "192.0.2.1:8080"
PROXIES = {"http": f"http://{IP}", "https": f"http://{IP}"}


@pytest.fixture
def wire(monkeypatch):
    calls = []
    replies = []
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.setenv(key, "http://127.0.0.1:18999")
    for key in ("NO_PROXY", "no_proxy", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
        monkeypatch.delenv(key, raising=False)

    def forbidden(*args, **kwargs):
        raise AssertionError("不应读取系统代理/netrc 或发出真实网络请求")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(requests.sessions, "get_environ_proxies", forbidden)
    monkeypatch.setattr(requests.sessions, "get_netrc_auth", forbidden)
    monkeypatch.setattr("em.core.transport.sleep_backoff", lambda *args: 0.0)

    def send(adapter, request, stream=False, timeout=None, verify=True, cert=None, proxies=None):
        calls.append(
            (
                request,
                dict(stream=stream, timeout=timeout, verify=verify, cert=cert, proxies=proxies),
            )
        )
        response = requests.Response()
        response.request = request
        response.url = request.url
        response.status_code = 200
        if replies:
            status, body, headers = replies.pop(0)
            response.status_code = status
            response._content = body.encode()
            response.headers.update(headers)
        elif urlsplit(request.url).hostname == "supplier.test":
            response._content = IP.encode()
        else:
            response._content = b'{"rc":0}'
        return response

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", send)
    return calls, replies


@pytest.mark.parametrize("mode", ["never", "auto"])
@pytest.mark.parametrize("scheme", ["http", "https"])
def test_direct_business_does_not_use_environment_or_purchase(wire, mode, scheme):
    calls, _ = wire
    client = market_data._create_client(Settings(proxy_mode=mode, proxy_api=SUPPLIER))
    try:
        client.get_text(TARGET.replace("https:", f"{scheme}:"), {}, {})
    finally:
        client.close()
    assert len(calls) == 1
    assert not calls[0][1]["proxies"]
    assert calls[0][1]["verify"] is True


def test_supplier_direct_prefilter_and_business_use_selected_proxy(wire, monkeypatch):
    calls, _ = wire
    monkeypatch.setenv("REQUESTS_CA_BUNDLE", "/custom/ca.pem")
    client = market_data._create_client(
        Settings(proxy_mode="always", proxy_api=SUPPLIER, proxy_prefilter=True)
    )
    try:
        client.get_text(TARGET, {}, {})
    finally:
        client.close()
    assert len(calls) == 3
    assert calls[0][0].url == SUPPLIER
    assert not calls[0][1]["proxies"]
    assert "/api/qt/clist/get" in calls[1][0].url
    assert calls[1][1]["proxies"] == PROXIES
    assert calls[2][0].url == TARGET
    assert calls[2][1]["proxies"] == PROXIES
    assert all(kwargs["verify"] == "/custom/ca.pem" for _, kwargs in calls)


def test_auto_switch_and_recovery_probe_respect_actual_route(wire):
    calls, replies = wire
    replies.append((403, "blocked", {}))
    client = market_data._create_client(
        Settings(
            proxy_mode="auto",
            proxy_api=SUPPLIER,
            proxy_prefilter=False,
            proxy_cooldown_sec=0,
            proxy_proxy_successes=1,
            max_retries=2,
        )
    )
    try:
        client.get_text(TARGET, {}, {})
        client.get_text(TARGET, {}, {})
    finally:
        client.close()
    assert [request.url for request, _ in calls] == [TARGET, SUPPLIER, TARGET, TARGET]
    assert [dict(kwargs["proxies"]) for _, kwargs in calls] == [{}, {}, PROXIES, {}]


def test_balance_is_direct_preserves_ca_and_disables_redirects(wire, tmp_path, monkeypatch):
    calls, replies = wire
    monkeypatch.setenv("CURL_CA_BUNDLE", "/custom/fallback.pem")
    replies.append(
        (
            200,
            json.dumps(
                {
                    "success": "true",
                    "data": [{"type": "次数套餐", "num": "10", "use": "1", "valid": "true"}],
                }
            ),
            {},
        )
    )
    manager = ProxyUsage(
        str(tmp_path / "usage.sqlite3"),
        ["https://api.xiequ.cn/VAD/GetIp.aspx?uid=test&vkey=test&type=2"],
        0,
        100,
        100,
        "https://op.xiequ.cn/ApiUser.aspx?act=suitdt&uid=test&ukey=test",
    )
    assert manager.refresh_balance(force=True)["available"] == 9
    replies.append((302, "", {"Location": "https://elsewhere.test/balance"}))
    manager.refresh_balance(force=True)
    assert len(calls) == 2
    assert all(not kwargs["proxies"] for _, kwargs in calls)
    assert all(kwargs["verify"] == "/custom/fallback.pem" for _, kwargs in calls)


def test_name_search_uses_same_direct_and_ca_policy(wire, monkeypatch):
    calls, replies = wire
    monkeypatch.setenv("REQUESTS_CA_BUNDLE", "/custom/ca.pem")
    replies.append((200, '{"QuotationCodeTable":{"Data":[]}}', {}))
    resolve._search.cache_clear()
    if resolve._session.cache_info().currsize:
        resolve._session().close()
    resolve._session.cache_clear()
    try:
        assert resolve.resolve_code("离线测试名称") is None
    finally:
        resolve._session().close()
        resolve._session.cache_clear()
        resolve._search.cache_clear()
    assert len(calls) == 1
    assert urlsplit(calls[0][0].url).hostname == "searchapi.eastmoney.com"
    assert not calls[0][1]["proxies"]
    assert calls[0][1]["verify"] == "/custom/ca.pem"


@pytest.mark.parametrize("proxies", [None, PROXIES])
def test_redirect_does_not_reintroduce_environment_proxy(wire, proxies, monkeypatch):
    calls, replies = wire
    monkeypatch.setenv("REQUESTS_CA_BUNDLE", "/custom/ca.pem")
    replies.append((302, "", {"Location": "https://other.test/final"}))
    with ExplicitProxySession() as session:
        session.get(TARGET, proxies=proxies)
    assert len(calls) == 2
    assert calls[1][0].url == "https://other.test/final"
    assert all(dict(kwargs["proxies"]) == (proxies or {}) for _, kwargs in calls)
    assert all(kwargs["verify"] == "/custom/ca.pem" for _, kwargs in calls)


@pytest.mark.parametrize(
    ("request_ca", "curl_ca", "verify", "expected"),
    [
        (None, None, None, True),
        ("/request.pem", "/curl.pem", None, "/request.pem"),
        ("/request.pem", "/curl.pem", True, "/request.pem"),
        (None, "/curl.pem", None, "/curl.pem"),
        ("", "/curl.pem", None, "/curl.pem"),
        ("/request.pem", "/curl.pem", "/explicit.pem", "/explicit.pem"),
        ("/request.pem", "/curl.pem", False, False),
    ],
)
def test_ca_precedence_reaches_adapter(wire, monkeypatch, request_ca, curl_ca, verify, expected):
    calls, _ = wire
    for name, value in (("REQUESTS_CA_BUNDLE", request_ca), ("CURL_CA_BUNDLE", curl_ca)):
        if value is not None:
            monkeypatch.setenv(name, value)
    with ExplicitProxySession() as session:
        session.get(TARGET, verify=verify)
    assert calls[0][1]["verify"] == expected


def test_ca_is_read_at_request_time_and_session_verify_is_preserved(wire, monkeypatch):
    calls, _ = wire
    with ExplicitProxySession() as session:
        session.verify = "/session.pem"
        session.get(TARGET)
        monkeypatch.setenv("REQUESTS_CA_BUNDLE", "/first.pem")
        session.get(TARGET)
        monkeypatch.setenv("REQUESTS_CA_BUNDLE", "/second.pem")
        session.get(TARGET)
        monkeypatch.delenv("REQUESTS_CA_BUNDLE")
        session.get(TARGET)
    assert [kwargs["verify"] for _, kwargs in calls] == [
        "/session.pem",
        "/first.pem",
        "/second.pem",
        "/session.pem",
    ]

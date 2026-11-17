"""真实 requests/urllib3 封装链的离线阶段回归；禁止真实网络连接。"""

import io
import socket
from http.client import HTTPConnection

import pytest
import requests
import urllib3.connection
import urllib3.util.connection

from em.core.errors import (
    ProxyConnectError,
    UpstreamReadTimeout,
)
from em.core.session import BoundedProxyAdapter, ExplicitProxySession, network_failure_phase
from em.core.transport import _classify


class FakeSocket:
    def __init__(self, timeout, phase):
        self.timeout = timeout
        self.phase = phase
        self.closed = False

    def settimeout(self, timeout):
        self.timeout = timeout

    def gettimeout(self):
        return self.timeout

    def sendall(self, data):
        if self.phase == "request_send":
            raise TimeoutError("simulated request send timeout")

    def makefile(self, *args, **kwargs):
        class Body(io.BytesIO):
            def readline(self, *args, **kwargs):
                if phase == "response_headers":
                    raise TimeoutError("simulated response headers timeout")
                return super().readline(*args, **kwargs)

            def read(self, *args, **kwargs):
                if phase == "response_body":
                    raise TimeoutError("simulated body timeout")
                return super().read(*args, **kwargs)

        phase = self.phase
        return Body(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok")

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("offline regression attempted network")

    monkeypatch.setattr(socket.socket, "connect", denied)


def simulated_network(monkeypatch, phase):
    sockets = []
    phases = iter(phase) if isinstance(phase, list) else None

    def create_connection(address, timeout, *args, **kwargs):
        current = next(phases) if phases is not None else phase() if callable(phase) else phase
        if current == "tcp":
            raise TimeoutError("simulated TCP timeout")
        sock = FakeSocket(timeout, current)
        sockets.append(sock)
        return sock

    def tunnel(connection):
        if connection.sock.phase == "proxy_connect":
            raise TimeoutError("simulated CONNECT timeout")

    def tls(**kwargs):
        if kwargs["sock"].phase == "tls":
            raise TimeoutError("simulated TLS timeout")
        return kwargs["sock"], True

    def proxy_tls(connection, hostname, sock):
        if sock.phase == "proxy_tls":
            raise TimeoutError("simulated proxy TLS timeout")
        return sock

    monkeypatch.setattr(urllib3.util.connection, "create_connection", create_connection)
    monkeypatch.setattr(HTTPConnection, "_tunnel", tunnel)
    monkeypatch.setattr(urllib3.connection, "_ssl_wrap_socket_and_match_hostname", tls)
    monkeypatch.setattr(urllib3.connection.HTTPSConnection, "_connect_tls_proxy", proxy_tls)
    return sockets


@pytest.mark.parametrize(
    ("phase", "expected"),
    [
        ("tcp", ProxyConnectError),
        ("proxy_connect", ProxyConnectError),
        ("tls", ProxyConnectError),
        ("proxy_tls", ProxyConnectError),
        ("request_send", ProxyConnectError),
        ("response_headers", UpstreamReadTimeout),
        ("response_body", UpstreamReadTimeout),
    ],
)
def test_real_exception_chain_classifies_failure_phase(monkeypatch, phase, expected):
    sockets = simulated_network(monkeypatch, phase)
    with ExplicitProxySession() as session:
        adapter = BoundedProxyAdapter()
        session.mount("https://", adapter)
        with pytest.raises(requests.RequestException) as caught:
            session.get(
                "https://target.invalid/data",
                proxies={
                    "https": ("https" if phase == "proxy_tls" else "http") + "://proxy.invalid:8080"
                },
                timeout=(1.5, 8.0),
            )
        assert isinstance(_classify(caught.value), expected)
        assert network_failure_phase(caught.value) == phase
        assert _classify(caught.value).network_phase == phase
    assert all(sock.closed for sock in sockets)
    assert adapter.proxy_manager == {}


@pytest.mark.parametrize(
    ("url", "phase"),
    [
        ("http://target.invalid/data", stage)
        for stage in ("tcp", "response_headers", "response_body")
    ]
    + [
        ("https://target.invalid/data", stage)
        for stage in ("tcp", "tls", "response_headers", "response_body")
    ],
)
def test_direct_connections_record_phases(monkeypatch, url, phase):
    sockets = simulated_network(monkeypatch, phase)
    with ExplicitProxySession() as session, pytest.raises(requests.RequestException) as caught:
        session.get(url, timeout=(1.5, 8))
    assert network_failure_phase(caught.value) == phase
    assert all(sock.closed for sock in sockets)

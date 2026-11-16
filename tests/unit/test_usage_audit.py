"""交付批次、首次预占与实际请求结果关联，不访问网络。"""

import json
import socket
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

import pytest
import requests

from em.application import market_data
from em.core.budget import request_budget
from em.core.errors import (
    InvalidContentError,
    NetworkError,
    ProxyQuotaExceededError,
)
from em.core.proxy import ProxyPool, ProxyRouter, ProxySettings
from em.core.resilience import RetryPolicy
from em.core.transport import HttpClient
from em.core.usage import ProxyUsage, usage_http_result, usage_http_started

API = "http://api.xiequ.cn/VAD/GetIp.aspx?uid=test&vkey=secret&type=2"


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("network is disabled")

    monkeypatch.setattr(socket.socket, "connect", deny)


def build(tmp_path, *, probe=False, manager=None):
    manager = manager or ProxyUsage(str(tmp_path / "usage.sqlite3"), [API], 0, 5, 5)
    session = MagicMock(spec=requests.Session)
    session.get.return_value = MagicMock(status_code=200, text='{"rc":0,"data":{}}')
    supplier = MagicMock(spec=requests.Session)
    supplier.get.return_value = MagicMock(text="192.0.2.1:80", status_code=200)
    settings = ProxySettings(api=API, mode="always")
    prober = market_data._make_prober(session, 3) if probe else None
    pool = ProxyPool(settings, supplier, prober=prober, usage=manager)
    client = HttpClient(
        session, ProxyRouter(pool, settings), RetryPolicy(max_retries=0), timeout_sec=3
    )
    return manager, client, pool, session


def test_probe_and_business_share_lease_but_have_separate_http_results(tmp_path):
    manager, client, pool, _session = build(tmp_path, probe=True)
    client.get_text("http://target.test", {}, {})
    audit = manager.client_audit(pool.client_id)
    assert audit["summary"] == dict(
        fetch_calls=1,
        returned=1,
        attempts=2,
        first_uses=1,
        pending=0,
        successful_http=2,
        accepted=2,
    )
    assert {entry["phase"] for entry in audit["attempts"]} == {"prefilter", "business"}
    assert {entry["lease_token"] for entry in audit["attempts"]} == {
        audit["attempts"][0]["lease_token"]
    }
    assert all(entry["batch_id"] == audit["batches"][0]["id"] for entry in audit["attempts"])
    assert all(entry["sent"] == 1 and entry["status_code"] == 200 for entry in audit["attempts"])
    assert all(entry["source"] == "paid" for entry in audit["attempts"])
    assert pool.stats()["usage_client"] == audit["summary"]
    assert pool.stats()["fetch_calls"] == audit["summary"]["fetch_calls"]


def test_idle_client_stats_are_not_the_active_client_stats(tmp_path):
    manager, active, pool, _session = build(tmp_path)
    _manager, unused, unused_pool, _unused_session = build(tmp_path, manager=manager)
    active.get_text("http://target.test", {}, {})
    assert active.proxy_stats()["fetch_calls"] == 1
    assert active.proxy_stats()["usage_client"]["attempts"] == 1
    assert unused.proxy_stats()["fetch_calls"] == 0
    assert unused.proxy_stats()["usage_client"]["attempts"] == 0
    assert pool.client_id != unused_pool.client_id
    assert active.proxy_stats()["usage"]["account"] == unused.proxy_stats()["usage"]["account"]


def test_http_200_with_invalid_payload_is_not_business_success(tmp_path):
    manager, client, pool, session = build(tmp_path)
    session.get.return_value.text = "bad"
    with pytest.raises(InvalidContentError):
        client.get_text("http://target.test", {}, {}, validator=lambda _: False)
    event = manager.client_audit(pool.client_id)["attempts"][0]
    assert event["sent"] == 1 and event["status_code"] == 200
    assert event["accepted"] == 0 and event["error_type"] == "InvalidContentError"
    assert event["first_use"] == 1


def test_raw_network_failure_is_recorded_without_sensitive_message(tmp_path):
    manager, client, pool, session = build(tmp_path)
    session.get.side_effect = requests.ReadTimeout("sensitive-vkey=do-not-store")
    with pytest.raises(NetworkError):
        client.get_text("http://target.test", {}, {})
    audit = manager.client_audit(pool.client_id)
    event = audit["attempts"][0]
    assert event["status_code"] is None and event["error_type"] == "ReadTimeout"
    assert event["sent"] == 1 and event["accepted"] == 0
    assert "sensitive" not in json.dumps(audit)
    assert b"do-not-store" not in manager.path.read_bytes()


def test_prefilter_caught_timeout_still_has_actual_error(tmp_path):
    manager, _client, pool, session = build(tmp_path, probe=True)
    session.get.side_effect = requests.ConnectTimeout("secret")
    proxy = pool.acquire()
    assert proxy is None
    events = manager.client_audit(pool.client_id)["attempts"]
    assert len(events) == 1
    assert events[0]["phase"] == "prefilter"
    assert events[0]["error_type"] == "ConnectTimeout"
    assert events[0]["sent"] == 1 and events[0]["accepted"] == 0


def test_reservation_and_pending_event_are_atomic(tmp_path):
    manager, _client, pool, _session = build(tmp_path)
    proxy = pool.acquire()
    lease = pool._usage_leases[proxy]
    with sqlite3.connect(manager.path) as connection:
        connection.execute("""CREATE TRIGGER audit_fail BEFORE INSERT ON usage_attempts
            BEGIN SELECT RAISE(ABORT,'failure'); END""")
    with pytest.raises(sqlite3.IntegrityError):
        manager.reserve(lease, "business", pool.client_id)
    assert manager.snapshot()["account"]["paid"]["reserved"] == 0
    assert manager.client_audit(pool.client_id)["attempts"] == []
    pool.release(proxy)


def test_pending_attempt_survives_new_manager_and_expired_lease(tmp_path, monkeypatch):
    manager, _client, pool, _session = build(tmp_path)
    proxy = pool.acquire()
    lease = pool._usage_leases[proxy]
    manager.reserve(lease, "business", pool.client_id)
    monkeypatch.setattr("em.core.usage.time.time", lambda: lease.expires_at + 1)
    reopened = ProxyUsage(str(manager.path), [API], 0, 5, 5)
    reopened.register(API, "192.0.2.2:80", lease.expires_at + 31)
    audit = reopened.client_audit(pool.client_id)
    assert audit["summary"]["pending"] == 1
    assert audit["attempts"][0]["first_use"] == 1
    assert audit["attempts"][0]["finished"] is None
    assert reopened.snapshot()["account"]["paid"]["reserved"] == 1


def test_concurrent_attempts_record_one_first_use(tmp_path):
    manager, _client, pool, _session = build(tmp_path)
    proxy = pool.acquire()
    lease = pool._usage_leases[proxy]

    def request(_):
        with manager.attempt(lease, "business", pool.client_id) as outcome:
            usage_http_started()
            usage_http_result(status_code=200)
            outcome.accepted = True

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(request, range(16)))
    audit = manager.client_audit(pool.client_id)
    assert audit["summary"]["attempts"] == 16
    assert audit["summary"]["first_uses"] == 1
    assert audit["summary"]["accepted"] == 16
    assert audit["summary"]["pending"] == 0
    pool.release(proxy)


def test_two_clients_have_distinct_delivery_batches_and_same_lease(tmp_path):
    manager, first, pool1, _session1 = build(tmp_path)
    _manager, second, pool2, _session2 = build(tmp_path, manager=manager)
    first.get_text("http://target.test", {}, {})
    second.get_text("http://target.test", {}, {})
    event1 = manager.client_audit(pool1.client_id)["attempts"][0]
    event2 = manager.client_audit(pool2.client_id)["attempts"][0]
    assert event1["lease_token"] == event2["lease_token"]
    assert event1["identity"] == event2["identity"]
    assert event1["batch_id"] != event2["batch_id"]
    assert [event1["first_use"], event2["first_use"]] == [1, 0]


def test_result_is_saved_after_outer_deadline_expired(tmp_path, monkeypatch):
    manager, client, pool, session = build(tmp_path)
    now = [10.0]
    monkeypatch.setattr("em.core.budget.time.monotonic", lambda: now[0])

    def get(*args, **kwargs):
        now[0] = 30.0
        raise requests.ReadTimeout("timeout")

    session.get.side_effect = get
    with pytest.raises(NetworkError), request_budget(20):
        client.get_text("http://target.test", {}, {})
    event = manager.client_audit(pool.client_id)["attempts"][0]
    assert event["state"] == "finished" and event["error_type"] == "ReadTimeout"


def test_missing_client_delivery_rejects_without_preoccupying(tmp_path):
    manager, _client, pool, _session = build(tmp_path)
    proxy = pool.acquire()
    lease = pool._usage_leases[proxy]
    with pytest.raises(ProxyQuotaExceededError):
        manager.reserve(lease, "business", "unrelated-client")
    assert manager.snapshot()["account"]["paid"]["reserved"] == 0
    pool.release(proxy)


def test_expiry_after_reserve_records_not_sent_without_refund(tmp_path, monkeypatch):
    manager, client, pool, session = build(tmp_path)
    now = [10.0]
    monkeypatch.setattr("em.core.budget.time.monotonic", lambda: now[0])
    original = manager.reserve

    def reserve(*args, **kwargs):
        identifier = original(*args, **kwargs)
        now[0] = 50
        return identifier

    monkeypatch.setattr(manager, "reserve", reserve)
    with pytest.raises(NetworkError):
        client.get_text("http://target.test", {}, {})
    event = manager.client_audit(pool.client_id)["attempts"][0]
    session.get.assert_not_called()
    assert event["first_use"] == 1 and event["sent"] == 0
    assert event["error_type"] == "ProxyUnavailableError"
    assert event["accepted"] == 0 and event["status_code"] is None
    assert manager.snapshot()["account"]["paid"]["reserved"] == 1


def test_previous_reservation_is_not_recreated_as_a_new_first_use(tmp_path):
    manager, client, pool, _session = build(tmp_path)
    proxy = pool.acquire()
    lease = pool._usage_leases[proxy]
    manager.reserve(lease, "business")
    pool.release(proxy)
    client.get_text("http://target.test", {}, {})
    audit = manager.client_audit(pool.client_id)
    assert audit["summary"]["attempts"] == 1
    assert audit["summary"]["first_uses"] == 0
    assert manager.snapshot()["account"]["paid"]["reserved"] == 1


def test_result_write_failure_preserves_pending_and_consumed_budget(tmp_path):
    manager, client, pool, session = build(tmp_path)
    with sqlite3.connect(manager.path) as connection:
        connection.execute("""CREATE TRIGGER reject_completion BEFORE UPDATE ON usage_attempts
            BEGIN SELECT RAISE(ABORT,'completion failed'); END""")
    with pytest.raises(sqlite3.IntegrityError):
        client.get_text("http://target.test", {}, {})
    assert session.get.call_count == 1
    assert manager.snapshot()["account"]["paid"]["reserved"] == 1
    audit = manager.client_audit(pool.client_id)
    assert audit["summary"]["pending"] == 1
    assert audit["attempts"][0]["accepted"] is None
    assert pool._in_flight == {}


def test_client_close_releases_session_even_if_router_cleanup_fails(tmp_path, monkeypatch):
    _manager, client, _pool, session = build(tmp_path)

    def fail():
        raise RuntimeError("cleanup failed")

    monkeypatch.setattr(client._router, "close", fail)
    with pytest.raises(RuntimeError):
        client.close()
    session.close.assert_called_once()
    assert client._closed

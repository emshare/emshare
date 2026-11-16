"""短效出口准入、重复交付、实际派发与请求预算。"""

import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

import pytest
import requests

from em.core.budget import request_budget
from em.core.errors import ProxyUnavailableError
from em.core.proxy import ProxyPool, ProxyRouter, ProxySettings
from em.core.resilience import RetryPolicy
from em.core.transport import HttpClient


@pytest.fixture
def clock(monkeypatch):
    now = [0.0]
    monkeypatch.setattr("em.core.proxy.time.monotonic", lambda: now[0])

    def pause(duration):
        now[0] += duration

    monkeypatch.setattr("em.core.budget.time.sleep", pause)
    return now


def make_client(monkeypatch, batches, retries=4):
    supplier = MagicMock(spec=requests.Session)
    supplier.get.side_effect = [MagicMock(text=batch) for batch in batches]
    settings = ProxySettings(api="http://supplier.test", mode="always", num=2)
    pool = ProxyPool(settings, supplier)
    monkeypatch.setattr(pool, "_maybe_renew", lambda: None)
    business = MagicMock(spec=requests.Session)
    business.get.return_value = MagicMock(status_code=200, text="ok")
    client = HttpClient(
        business,
        ProxyRouter(pool, settings),
        RetryPolicy(max_retries=retries),
        timeout_sec=3,
        connect_timeout_sec=3,
    )
    return client, pool, supplier, business


def test_late_dispatch_uses_young_ip_and_preserves_old_for_short_budget(clock, monkeypatch):
    client, pool, supplier, business = make_client(monkeypatch, ["192.0.2.1:80", "192.0.2.2:80"])
    client.get_text("http://target.test", {}, {})
    clock[0] = 25.756
    client.get_text("http://target.test", {}, {})
    assert business.get.call_args.kwargs["proxies"]["http"] == "http://192.0.2.2:80"
    assert pool.hold("192.0.2.1:80", min_lifetime=0.5)
    pool.release("192.0.2.1:80")
    assert pool._failed_at == {}
    assert pool._in_flight == {}
    assert supplier.get.call_count == 2


def test_soft_retry_rejects_closing_lease(clock, monkeypatch):
    client, pool, _supplier, business = make_client(monkeypatch, ["192.0.2.1:80", "192.0.2.2:80"])
    client.get_text("http://target.test", {}, {})
    clock[0] = 20.9
    attempts = []

    def send(*args, **kwargs):
        attempts.append(kwargs["proxies"]["http"])
        if len(attempts) == 1:
            clock[0] += 3
            raise requests.ReadTimeout("delay")
        return MagicMock(status_code=200, text="ok")

    business.get.side_effect = send
    client.get_text("http://target.test", {}, {})
    assert attempts == ["http://192.0.2.1:80", "http://192.0.2.2:80"]
    assert pool.stats()["lifetime_hold_rejected"] == 1
    assert pool._failed_at == {}
    assert pool._in_flight == {}


def test_duplicate_batch_bought_once_then_suppressed_without_losing_old(clock, monkeypatch):
    client, pool, supplier, business = make_client(monkeypatch, ["192.0.2.1:80", "192.0.2.1:80"])
    client.get_text("http://target.test", {}, {})
    clock[0] = 25.756
    with pytest.raises(ProxyUnavailableError):
        client.get_text("http://target.test", {}, {})
    assert supplier.get.call_count == 2
    assert pool._adopted_at["192.0.2.1:80"] == 0
    assert pool.stats()["lifetime_refill_suppressed"] > 0
    assert not pool._failed_at
    assert pool.hold("192.0.2.1:80", 0.1)
    pool.release("192.0.2.1:80")
    assert business.get.call_count == 1


def test_concurrent_missing_capacity_merges_purchase(clock, monkeypatch):
    client, pool, supplier, _business = make_client(monkeypatch, ["192.0.2.1:80"])
    client.get_text("http://target.test", {}, {})
    clock[0] = 25.756
    entered = threading.Event()
    finish = threading.Event()
    barrier = threading.Barrier(6)

    def fetch(*args, **kwargs):
        entered.set()
        assert finish.wait(2)
        return MagicMock(text="192.0.2.1:80")

    supplier.get.side_effect = fetch

    def acquire():
        barrier.wait(timeout=2)
        return pool.acquire(6)

    with ThreadPoolExecutor(max_workers=6) as executor:
        tasks = [executor.submit(acquire) for _ in range(6)]
        try:
            assert entered.wait(2)
        finally:
            finish.set()
        assert [task.result(timeout=2) for task in tasks] == [None] * 6
    assert supplier.get.call_count == 2
    assert pool._in_flight == {}
    assert pool.remaining_lifetime("192.0.2.1:80") == pytest.approx(1.244)


def test_large_hint_can_run_with_timeout_bounded_by_lease(clock, monkeypatch):
    client, pool, supplier, business = make_client(monkeypatch, ["192.0.2.1:80"])
    client.get_text("http://target.test", {}, {}, read_timeout=60)
    connect, read = business.get.call_args.kwargs["timeout"]
    assert connect == 1.5
    assert read == 25.5
    assert supplier.get.call_count == 1
    assert pool._in_flight == {}


def test_large_hint_uses_young_standby_not_unbounded_refill(clock, monkeypatch):
    client, _pool, supplier, business = make_client(monkeypatch, ["192.0.2.1:80", "192.0.2.2:80"])
    client.get_text("http://target.test", {}, {})
    clock[0] = 15
    client.get_text("http://target.test", {}, {}, read_timeout=60)
    assert business.get.call_args.kwargs["proxies"]["http"] == "http://192.0.2.2:80"
    assert supplier.get.call_count == 2


def test_short_outer_deadline_allows_old_proxy(clock, monkeypatch):
    client, _pool, supplier, business = make_client(monkeypatch, ["192.0.2.1:80"])
    client.get_text("http://target.test", {}, {})
    clock[0] = 25
    with request_budget(26):
        client.get_text("http://target.test", {}, {}, read_timeout=60)
    assert business.get.call_args.kwargs["timeout"] == (0.5, 0.5)
    assert supplier.get.call_count == 1


def test_dispatch_rechecks_after_scheduler_delay(clock, monkeypatch):
    client, pool, _supplier, business = make_client(monkeypatch, ["192.0.2.1:80"], retries=0)
    client.get_text("http://target.test", {}, {})
    original = client._attempt

    def delayed(*args, **kwargs):
        clock[0] = 27
        return original(*args, **kwargs)

    monkeypatch.setattr(client, "_attempt", delayed)
    with pytest.raises(ProxyUnavailableError):
        client.get_text("http://target.test", {}, {})
    assert business.get.call_count == 1
    assert pool._in_flight == {}
    assert not pool._failed_at
    assert client.timing_stats()["failed_attempts"] == 0


def test_renewal_preserves_outstanding_lease_metadata(clock, monkeypatch):
    _client, pool, _supplier, _business = make_client(monkeypatch, ["192.0.2.1:80", "192.0.2.2:80"])
    old = pool.acquire()
    clock[0] = 25
    pool._renew_worker()
    assert pool.remaining_lifetime(old) == 2
    assert pool._in_flight == {old: 1}
    assert pool.remaining_lifetime("192.0.2.2:80") == 27
    pool.release(old)
    assert pool._in_flight == {}
    assert not pool._renew_due()


def test_duplicate_cooldown_does_not_block_short_request(clock, monkeypatch):
    client, pool, supplier, _business = make_client(monkeypatch, ["192.0.2.1:80", "192.0.2.1:80"])
    client.get_text("http://target.test", {}, {})
    clock[0] = 25
    assert pool.acquire(6) is None
    assert pool.acquire(0.5) == "192.0.2.1:80"
    pool.release("192.0.2.1:80")
    assert supplier.get.call_count == 2


def test_short_lifetime_qualification_never_extends_same_lease(clock, monkeypatch):
    client, pool, _supplier, _business = make_client(monkeypatch, ["192.0.2.1:80", "192.0.2.1:80"])
    client.get_text("http://target.test", {}, {})
    clock[0] = 25
    assert pool.acquire(100) is None
    assert pool.remaining_lifetime("192.0.2.1:80") == 2


def test_short_ttl_admits_bounded_request(clock, monkeypatch):
    supplier = MagicMock(spec=requests.Session)
    supplier.get.return_value = MagicMock(text="192.0.2.1:80")
    settings = ProxySettings(
        api="http://supplier.test", mode="always", ttl_sec=2, safety_margin_sec=0
    )
    pool = ProxyPool(settings, supplier)
    business = MagicMock(spec=requests.Session)
    business.get.return_value = MagicMock(status_code=200, text="ok")
    client = HttpClient(business, ProxyRouter(pool, settings), RetryPolicy(max_retries=0))
    assert client.get_text("http://target.test", {}, {}, read_timeout=60) == "ok"
    assert sum(business.get.call_args.kwargs["timeout"]) <= 2


def test_unavailable_pool_never_sends_direct(clock, monkeypatch):
    client, _pool, _supplier, business = make_client(monkeypatch, [""])
    with pytest.raises(ProxyUnavailableError):
        client.get_text("http://target.test", {}, {}, read_timeout=60)
    business.get.assert_not_called()


def test_background_duplicate_is_suppressed_until_lease_expires(clock, monkeypatch):
    client, pool, supplier, _business = make_client(
        monkeypatch, ["192.0.2.1:80", "192.0.2.1:80", "192.0.2.2:80"]
    )
    client.get_text("http://target.test", {}, {})
    clock[0] = 25
    pool._renew_worker()
    clock[0] = 26
    pool._renew_worker()
    assert supplier.get.call_count == 2
    assert pool.remaining_lifetime("192.0.2.1:80") == 1
    clock[0] = 27.1
    assert pool.acquire(6) == "192.0.2.2:80"
    pool.release("192.0.2.2:80")
    assert supplier.get.call_count == 3
    assert pool._in_flight == {}


def test_pool_overlap_and_live_lease_metadata_are_bounded(clock, monkeypatch):
    client, pool, _supplier, _business = make_client(monkeypatch, ["192.0.2.1:80"])
    client.get_text("http://target.test", {}, {})
    oldest = pool.acquire()
    for number in range(2, 12):
        clock[0] = number
        pool._batch_started_at = number
        pool._adopt([f"192.0.2.{number}:80"])
    assert len(pool._standby) + 1 == pool._settings.num * 2
    assert pool.remaining_lifetime(oldest) == 16
    pool.release(oldest)
    assert oldest not in pool._adopted_at
    assert pool._in_flight == {}

"""代理审查问题的正确性回归：全部使用假网络与可控时钟。"""

import threading
from unittest.mock import MagicMock, patch

import pytest
import requests
from urllib3.exceptions import ReadTimeoutError

from em.application import market_data
from em.core.budget import request_budget
from em.core.errors import ConfigError, HttpStatusError, PageDeadlineExceeded, ProxyUnavailableError
from em.core.proxy import ProxyPool, ProxyRouter, ProxySettings
from em.core.resilience import RetryPolicy
from em.core.session import BoundedProxyAdapter
from em.core.settings import Settings
from em.core.transport import HttpClient, _classify
from em.domain.models import Quote, QuotePage


def fake_session(*batches):
    session = MagicMock(spec=requests.Session)
    session.get.side_effect = [MagicMock(text=batch, status_code=200) for batch in batches]
    return session


def test_background_renewal_does_not_lease_or_count_service(monkeypatch):
    now = [0.0]
    monkeypatch.setattr("em.core.proxy.time.monotonic", lambda: now[0])
    pool = ProxyPool(
        ProxySettings(api="http://source.test"), fake_session("1.1.1.1:80", "2.2.2.2:80")
    )
    pool.release(pool.acquire())
    now[0] = 25
    pool._renew_worker()
    assert pool._in_flight == {}
    assert pool.stats()["ips_served"] == 1
    assert pool.acquire() == "2.2.2.2:80"
    pool.release("2.2.2.2:80")
    assert pool._in_flight == {}


@pytest.mark.parametrize("mode", ["always", "auto"])
def test_exhausted_proxy_never_sends_direct(mode, monkeypatch):
    monkeypatch.setattr("em.core.proxy.time.sleep", lambda _: None)
    settings = ProxySettings(api="http://source.test", mode=mode)
    pool = ProxyPool(settings, fake_session(""))
    router = ProxyRouter(pool, settings)
    if mode == "auto":
        router.report_result("target.test", None, success=False, banned=True)
    session = fake_session("ok")
    client = HttpClient(session, router, RetryPolicy(max_retries=2))
    with pytest.raises(ProxyUnavailableError):
        client.get_text("http://target.test", {}, {})
    session.get.assert_not_called()
    assert pool._in_flight == {}


def test_three_dead_batches_do_not_revive_blacklisted_ip(monkeypatch):
    monkeypatch.setattr("em.core.proxy.time.sleep", lambda _: None)
    settings = ProxySettings(api="http://a.test,http://b.test", prefilter_sources=2)
    pool = ProxyPool(
        settings,
        fake_session("1.1.1.1:80", "2.2.2.2:80", "3.3.3.3:80"),
        prober=lambda _: False,
        fallback_prober=lambda _: False,
    )
    assert pool.acquire() is None
    assert pool.available() == 0
    assert pool.stats()["ips_adopted"] == 0


def test_screening_time_is_deducted_from_ttl(monkeypatch):
    now = [0.0]
    monkeypatch.setattr("em.core.proxy.time.monotonic", lambda: now[0])

    def probe(_):
        now[0] += 8
        return True

    pool = ProxyPool(
        ProxySettings(api="http://source.test"), fake_session("1.1.1.1:80"), prober=probe
    )
    proxy = pool.acquire()
    now[0] = 26
    assert pool._is_live(proxy)
    now[0] = 27
    assert not pool._is_live(proxy)


def test_batch_expired_during_screening_is_not_installed(monkeypatch):
    now = [0.0]
    monkeypatch.setattr("em.core.proxy.time.monotonic", lambda: now[0])

    def probe(_):
        now[0] = 31
        return True

    pool = ProxyPool(
        ProxySettings(api="http://source.test"), fake_session("1.1.1.1:80"), prober=probe
    )
    assert pool.acquire() is None
    assert pool.stats()["ips_adopted"] == 0


def test_late_proxy_result_does_not_change_recovered_direct_route():
    settings = ProxySettings(
        api="http://source.test", direct_fails=1, cooldown_sec=0, proxy_successes=1
    )
    pool = MagicMock()
    router = ProxyRouter(pool, settings)
    router.report_result("host", None, success=False, banned=True)
    router.report_result("host", "1.1.1.1:80", success=True)
    assert router.acquire("host") is None
    router.report_result("host", None, success=True)
    router.report_result("host", "2.2.2.2:80", success=False)
    assert router.host_state("host").mode == "direct"
    pool.report_failure.assert_called_once_with("2.2.2.2:80")


def test_old_direct_success_cannot_complete_new_probe():
    settings = ProxySettings(
        api="http://source.test", direct_fails=1, cooldown_sec=0, proxy_successes=1
    )
    router = ProxyRouter(MagicMock(), settings)
    issued = threading.Event()
    finish = threading.Event()

    def old_direct():
        router.acquire("host")
        issued.set()
        assert finish.wait(2)
        router.report_result("host", None, success=True)

    worker = threading.Thread(target=old_direct)
    worker.start()
    assert issued.wait(2)
    router.report_result("host", None, success=False, banned=True)
    router.report_result("host", "1.1.1.1:80", success=True)
    router.acquire("host")
    finish.set()
    worker.join(2)
    assert router.host_state("host").mode == "probe"
    assert router.host_state("host").probe_in_flight
    router.report_result("host", None, success=True)
    assert router.host_state("host").mode == "direct"


@pytest.mark.parametrize("status", [404, 500, 503])
def test_upstream_status_does_not_blacklist_exit(status):
    settings = ProxySettings(api="http://source.test", mode="always")
    pool = ProxyPool(settings, fake_session("1.1.1.1:80"))
    session = MagicMock(spec=requests.Session)
    session.get.return_value = MagicMock(status_code=status, text="error")
    client = HttpClient(session, ProxyRouter(pool, settings), RetryPolicy(max_retries=0))
    with pytest.raises(HttpStatusError):
        client.get_text("http://target.test", {}, {})
    assert pool.available() == 1
    assert pool.stats()["ip_failures"] == 0
    assert pool._in_flight == {}


def test_requests_body_timeout_uses_soft_failure_class():
    from em.core.errors import UpstreamReadTimeout

    raw = MagicMock()
    raw.stream.side_effect = ReadTimeoutError(None, "/body", "timeout")
    response = requests.Response()
    response.raw = raw
    # 已观察到响应体读取；未知阶段的 ReadTimeout 不再默认视为软失败。
    error = raw.stream.side_effect
    error._em_network_phase = "response_body"
    with pytest.raises(requests.ConnectionError) as caught:
        _ = response.content
    assert isinstance(_classify(caught.value), UpstreamReadTimeout)


def test_budget_stops_internal_retries(monkeypatch):
    now = [0.0]
    monkeypatch.setattr("em.core.budget.time.monotonic", lambda: now[0])

    def get(*args, **kwargs):
        now[0] += 4
        raise requests.ReadTimeout("timeout")

    def pause(delay):
        now[0] += delay

    monkeypatch.setattr("em.core.budget.time.sleep", pause)
    session = MagicMock(spec=requests.Session)
    session.get.side_effect = get
    settings = ProxySettings(api="", mode="never")
    client = HttpClient(
        session, ProxyRouter(ProxyPool(settings, session), settings), RetryPolicy(max_retries=10)
    )
    with pytest.raises(PageDeadlineExceeded), request_budget(10):
        client.get_text("http://target.test", {}, {})
    assert session.get.call_count == 3


def test_budget_bounds_refill_lock_wait():
    import time

    pool = ProxyPool(ProxySettings(api="http://source.test"), fake_session(""))
    pool._refill_lock.acquire()
    try:
        with pytest.raises(PageDeadlineExceeded), request_budget(time.monotonic() + 0.02):
            pool.acquire()
        pool._session.get.assert_not_called()
    finally:
        pool._refill_lock.release()


def test_adapter_bounds_inactive_managers_and_preserves_active():
    adapter = BoundedProxyAdapter(proxy_limit=2)
    pinned = "http://192.0.2.1:80"
    try:
        manager = adapter.proxy_manager_for(pinned)
        adapter._active[pinned] = 1
        for number in range(2, 102):
            adapter.proxy_manager_for(f"http://192.0.2.{number}:80")
        assert len(adapter.proxy_manager) == 2
        assert adapter.proxy_manager[pinned] is manager
    finally:
        adapter.close()
    assert adapter.proxy_manager == {}


def test_adapter_keeps_manager_until_response_body_is_consumed():
    adapter = BoundedProxyAdapter(proxy_limit=1)
    pinned = "http://192.0.2.1:80"
    reading = threading.Event()
    finish = threading.Event()
    errors = []

    class Response:
        @property
        def content(self):
            reading.set()
            assert finish.wait(2)
            return b"done"

    def send(*args, **kwargs):
        adapter.proxy_manager_for(pinned)
        return Response()

    request = requests.Request("GET", "http://target.test").prepare()

    def worker():
        try:
            adapter.send(request, proxies={"http": pinned})
        except Exception as error:
            errors.append(error)

    with patch.object(requests.adapters.HTTPAdapter, "send", side_effect=send):
        thread = threading.Thread(target=worker)
        thread.start()
        try:
            assert reading.wait(2)
            adapter.proxy_manager_for("http://192.0.2.2:80")
            assert pinned in adapter.proxy_manager
        finally:
            finish.set()
            thread.join(2)
            adapter.close()
    assert not errors
    assert not thread.is_alive()
    assert adapter._active == {}


def test_snapshot_records_ledger_only_after_cleanup(monkeypatch):
    client = fake_snapshot_client()
    source = MagicMock()
    source.fetch_page.return_value = QuotePage(total=0, items=())

    def record(*args):
        client.close.assert_called_once()

    monkeypatch.setattr(market_data, "_build_client", lambda *args, **kwargs: client)
    monkeypatch.setattr(market_data.registry, "EastMoneySource", lambda _: source)
    monkeypatch.setattr(market_data, "record_ledger", record)
    assert market_data.stock_list_all_em().total == 0


def test_close_waits_for_renewal_and_does_not_install_new_batch(monkeypatch):
    now = [0.0]
    monkeypatch.setattr("em.core.proxy.time.monotonic", lambda: now[0])
    entered = threading.Event()
    finish = threading.Event()
    session = fake_session("1.1.1.1:80")
    pool = ProxyPool(ProxySettings(api="http://source.test"), session)
    pool.release(pool.acquire())

    def fetch(*args, **kwargs):
        entered.set()
        assert finish.wait(2)
        return MagicMock(status_code=200, text="2.2.2.2:80")

    session.get.side_effect = fetch
    now[0] = 25
    pool._maybe_renew()
    assert entered.wait(2)
    closer = threading.Thread(target=pool.close)
    closer.start()
    try:
        for _ in range(2000):
            if pool._closed:
                break
            threading.Event().wait(0.001)
        assert pool._closed
    finally:
        finish.set()
    closer.join(2)
    assert not closer.is_alive()
    assert not pool._renewing
    assert pool.acquire() is None
    assert pool._in_flight == {}
    assert pool.stats()["ips_adopted"] == 1


def fake_snapshot_client():
    client = MagicMock()
    client.available_proxies.return_value = 0
    client.timing_stats.return_value = dict(
        direct_requests=0,
        direct_sec=0,
        proxy_requests=0,
        proxy_sec=0,
        proxy_wait_sec=0,
        backoff_sec=0,
        failed_attempts=0,
    )
    client.proxy_stats.return_value = {}
    return client


def test_empty_last_page_does_not_erase_expected_total(monkeypatch):
    first = QuotePage(
        total=200, items=tuple(Quote(code=str(number), name="x") for number in range(100))
    )
    source = MagicMock()
    source.fetch_page.side_effect = lambda request: first if request.page == 1 else QuotePage(0, ())
    client = fake_snapshot_client()
    monkeypatch.setattr(market_data, "_build_client", lambda *args, **kwargs: client)
    monkeypatch.setattr(market_data.registry, "EastMoneySource", lambda _: source)
    monkeypatch.setattr(market_data, "record_ledger", lambda *args: None)
    result = market_data.stock_list_all_em(max_rounds=1, workers=1)
    assert result.total == 200 and len(result.items) == 100
    assert source.fetch_page.call_count > 2
    client.close.assert_called_once()


def test_gap_fill_does_not_evict_correct_existing_page(monkeypatch):
    calls = {1: 0, 2: 0}

    def fetch(request):
        calls[request.page] += 1
        if request.page == 1:
            items = tuple(Quote(code=str(number), name="x") for number in range(100))
        else:
            items = () if calls[2] <= 3 else (Quote(code="100", name="x"),)
        return QuotePage(total=101, items=items)

    source = MagicMock()
    source.fetch_page.side_effect = fetch
    client = fake_snapshot_client()
    monkeypatch.setattr(market_data, "_build_client", lambda *args, **kwargs: client)
    monkeypatch.setattr(market_data.registry, "EastMoneySource", lambda _: source)
    monkeypatch.setattr(market_data, "record_ledger", lambda *args: None)
    result = market_data.stock_list_all_em(workers=1)
    assert len(result.items) == 101
    client.evict_last_proxy.assert_not_called()


def test_each_snapshot_has_isolated_accounting_and_closes_session(monkeypatch):
    payload = '{"rc":0,"data":{"total":1,"diff":[{"f12":"000001","f14":"x"}]}}'
    sessions = [fake_session(payload), fake_session(payload)]
    rows = []
    monkeypatch.setattr(
        market_data,
        "record_ledger",
        lambda pool, timing, *args: rows.append(timing["direct_requests"]),
    )
    with patch.object(market_data, "ExplicitProxySession", side_effect=sessions):
        market_data.stock_list_all_em(settings=Settings(proxy_mode="never"))
        market_data.stock_list_all_em(settings=Settings(proxy_mode="never"))
    assert rows == [1, 1]
    for session in sessions:
        session.close.assert_called_once()


@pytest.mark.parametrize(
    "options",
    [
        dict(request_timeout_sec=0),
        dict(proxy_timeout_sec=-1),
        dict(proxy_safety_margin_sec=-1),
        dict(backoff_sec=float("nan")),
    ],
)
def test_invalid_settings_rejected(options):
    with pytest.raises(ConfigError):
        Settings(**options)


def test_jitter_uses_random_sample(monkeypatch):
    monkeypatch.setattr("em.core.resilience.random.uniform", lambda low, high: high / 2)
    assert RetryPolicy(backoff_sec=0.2, jitter_sec=0.1).backoff_for(1) == pytest.approx(0.45)


def test_history_has_explicit_bounded_lower_bound(monkeypatch):
    monkeypatch.setattr(ProxyPool, "_HISTORY_LIMIT", 2)
    pool = ProxyPool(ProxySettings(api="http://source.test"), fake_session(""))
    for number in range(10):
        pool.report_success(f"192.0.2.{number}:80")
    assert pool.stats()["ips_productive"] == 2
    assert pool.stats()["history_truncated"] is True

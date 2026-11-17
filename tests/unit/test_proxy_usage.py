"""使用额度离线回归：提取不预占，网络尝试前预占且失败不退款。"""

import json
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from unittest.mock import MagicMock

import pytest
import requests

from em.application import market_data
from em.core.errors import ConfigError, NetworkError, ProxyQuotaExceededError, ProxyUnavailableError
from em.core.proxy import ProxyPool, ProxyRouter, ProxySettings
from em.core.resilience import RetryPolicy
from em.core.settings import Settings
from em.core.transport import HttpClient
from em.core.usage import ProxyUsage

FREE = "http://api.xiequ.cn/VAD/GetIp.aspx?uid=test&vkey=test-secret&type=0&num=3"
PAID = "http://api.xiequ.cn/VAD/GetIp.aspx?uid=test&vkey=test-secret&type=2&num=3"


@pytest.fixture(autouse=True)
def deny_real_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("offline test attempted network")

    monkeypatch.setattr(socket.socket, "connect", denied)


def usage(tmp_path, free=0, paid=5, run_limit=None):
    return ProxyUsage(str(tmp_path / "usage.sqlite3"), [FREE, PAID], free, paid, run_limit)


def register(manager, entry="192.0.2.1:80", source=PAID, duration=30):
    return manager.register(source, entry, time.time() + duration)


def client_for(manager, batches, *, prefilter=False, retries=0, sources=None):
    supplier = MagicMock(spec=requests.Session)
    supplier.get.side_effect = [MagicMock(text=batch) for batch in batches]
    settings = ProxySettings(
        api=sources or f"{FREE},{PAID}", mode="always", num=3, prefilter_sources=2
    )
    probe = MagicMock(return_value=True) if prefilter else None
    pool = ProxyPool(settings, supplier, prober=probe, usage=manager)
    business = MagicMock(spec=requests.Session)
    business.get.return_value = MagicMock(status_code=200, text="ok")
    client = HttpClient(
        business,
        ProxyRouter(pool, settings),
        RetryPolicy(max_retries=retries),
        timeout_sec=3,
        connect_timeout_sec=3,
    )
    return client, pool, supplier, business, probe


def test_extract_and_acquire_alone_do_not_consume(tmp_path):
    manager = usage(tmp_path)
    client, pool, supplier, business, _probe = client_for(manager, ["192.0.2.1:80\n192.0.2.2:80"])
    proxy = pool.acquire()
    pool.release(proxy)
    assert supplier.get.call_count == 1
    business.get.assert_not_called()
    assert manager.snapshot()["account"]["paid"]["reserved"] == 0
    assert pool.stats()["ips_returned"] == 2
    client.close()


def test_prefilter_and_business_share_first_use(tmp_path):
    manager = usage(tmp_path)
    client, pool, supplier, business, probe = client_for(
        manager, ["192.0.2.1:80\n192.0.2.2:80"], prefilter=True
    )
    assert client.get_text("http://target.test", {}, {}) == "ok"
    assert client.get_text("http://target.test", {}, {}) == "ok"
    snapshot = manager.snapshot()["account"]["paid"]
    assert snapshot["reserved"] == 2
    assert snapshot["prefilter_used"] == 2
    assert snapshot["business_used"] == 1
    assert snapshot["business_attempts"] == 2
    assert probe.call_count == 2
    assert business.get.call_count == 2
    assert supplier.get.call_args.args[0] == PAID
    assert pool._in_flight == {}


def test_free_zero_skips_source_and_probe(tmp_path):
    manager = usage(tmp_path)
    client, pool, supplier, business, probe = client_for(manager, ["192.0.2.1:80"], prefilter=True)
    client.get_text("http://target.test", {}, {})
    assert supplier.get.call_args.args[0] == PAID
    assert supplier.get.call_count == 1
    assert manager.snapshot()["account"]["free"]["reserved"] == 0
    assert manager.snapshot()["account"]["paid"]["reserved"] == 1
    assert probe.call_count == 1
    assert business.get.call_count == 1
    assert pool._failed_at == {}


def test_zero_everywhere_stops_without_network(tmp_path):
    manager = usage(tmp_path, paid=0)
    client, _pool, supplier, business, _probe = client_for(manager, [])
    with pytest.raises(ProxyQuotaExceededError):
        client.get_text("http://target.test", {}, {})
    supplier.get.assert_not_called()
    business.get.assert_not_called()


def test_same_identity_concurrent_reservation_is_one(tmp_path):
    manager = usage(tmp_path, paid=1)
    lease = register(manager)
    with ThreadPoolExecutor(max_workers=12) as executor:
        list(executor.map(lambda _: manager.reserve(lease, "business"), range(48)))
    account = manager.snapshot()["account"]["paid"]
    assert account["reserved"] == 1
    assert account["business_used"] == 1
    assert account["business_attempts"] == 48


def test_unique_concurrent_use_never_exceeds_account(tmp_path):
    manager = usage(tmp_path, paid=3)
    leases = [register(manager, f"192.0.2.{number}:80") for number in range(1, 25)]

    def reserve(lease):
        try:
            manager.reserve(lease, "prefilter")
            return True
        except ProxyQuotaExceededError:
            return False

    with ThreadPoolExecutor(max_workers=12) as executor:
        assert sum(executor.map(reserve, leases)) == 3
    account = manager.snapshot()["account"]["paid"]
    assert account["reserved"] == 3
    assert account["prefilter_attempts"] == 3


def test_prefilter_over_budget_is_not_marked_dead(tmp_path):
    manager = usage(tmp_path, paid=1)
    client, pool, _supplier, business, probe = client_for(
        manager, ["192.0.2.1:80\n192.0.2.2:80\n192.0.2.3:80"], prefilter=True
    )
    client.get_text("http://target.test", {}, {})
    assert probe.call_count == 1
    assert business.get.call_count == 1
    assert manager.snapshot()["account"]["paid"]["reserved"] == 1
    assert pool.stats()["prefilter_rejected"] == 0
    assert pool._failed_at == {}


def test_used_ip_still_allowed_when_remaining_zero(tmp_path):
    manager = usage(tmp_path, paid=1)
    client, _pool, supplier, business, _probe = client_for(manager, ["192.0.2.1:80"])
    for _ in range(4):
        client.get_text("http://target.test", {}, {})
    assert manager.snapshot()["account"]["paid"]["remaining"] == 0
    assert business.get.call_count == 4
    assert supplier.get.call_count == 1


def test_failed_connection_keeps_reservation(tmp_path):
    manager = usage(tmp_path, paid=1)
    client, pool, _supplier, business, _probe = client_for(manager, ["192.0.2.1:80"])
    business.get.side_effect = requests.ConnectionError("failed")
    with pytest.raises(NetworkError):
        client.get_text("http://target.test", {}, {})
    assert manager.snapshot()["account"]["paid"]["reserved"] == 1
    assert manager.snapshot()["account"]["paid"]["business_attempts"] == 1
    assert pool._in_flight == {}


def test_failed_probe_keeps_reservation_and_skips_followup_fetch(tmp_path):
    manager = usage(tmp_path, paid=1)
    client, _pool, supplier, business, probe = client_for(manager, ["192.0.2.1:80"], prefilter=True)
    probe.return_value = False
    with pytest.raises(ProxyQuotaExceededError):
        client.get_text("http://target.test", {}, {})
    assert manager.snapshot()["account"]["paid"]["reserved"] == 1
    business.get.assert_not_called()
    assert supplier.get.call_count == 1


def test_duplicate_delivery_same_lease_does_not_reset_or_recharge(tmp_path):
    manager = usage(tmp_path)
    initial = register(manager)
    manager.reserve(initial, "prefilter")
    duplicate = register(manager, "http://192.0.2.1:80", duration=60)
    assert duplicate == initial
    manager.reserve(duplicate, "business")
    assert manager.snapshot()["account"]["paid"]["reserved"] == 1


def test_new_lease_after_expiry_requires_new_reservation(tmp_path, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr("em.core.usage.time.time", lambda: now[0])
    manager = usage(tmp_path)
    initial = register(manager)
    manager.reserve(initial, "business")
    now[0] = 1031
    renewed = register(manager)
    assert renewed.token != initial.token
    manager.reserve(renewed, "business")
    assert manager.snapshot()["account"]["paid"]["reserved"] == 2
    with pytest.raises(ProxyUnavailableError):
        manager.reserve(initial, "business")


def test_sources_are_distinct_even_for_same_endpoint(tmp_path):
    manager = usage(tmp_path, free=2, paid=2)
    manager.reserve(register(manager, source=FREE), "business")
    manager.reserve(register(manager, source=PAID), "business")
    assert {kind: values["reserved"] for kind, values in manager.snapshot()["account"].items()} == {
        "free": 1,
        "paid": 1,
    }


def test_reopening_database_preserves_balance_and_live_lease(tmp_path):
    manager = usage(tmp_path)
    initial = register(manager)
    manager.reserve(initial, "business")
    reopened = usage(tmp_path)
    lease = register(reopened)
    assert lease == initial
    reopened.reserve(lease, "prefilter")
    assert reopened.snapshot()["account"]["paid"]["reserved"] == 1
    assert reopened.snapshot()["run"]["reserved"] == 0


def test_changed_initial_balance_rejected(tmp_path):
    usage(tmp_path, paid=5)
    with pytest.raises(ConfigError):
        usage(tmp_path, paid=6)


def test_process_limit_spans_sources(tmp_path):
    manager = usage(tmp_path, free=2, paid=2, run_limit=1)
    manager.reserve(register(manager, source=FREE), "business")
    with pytest.raises(ProxyQuotaExceededError):
        manager.reserve(register(manager, source=PAID), "business")
    assert manager.snapshot()["account"]["paid"]["reserved"] == 0


def test_unknown_proxy_denied_without_traffic(tmp_path):
    manager = usage(tmp_path)
    client, pool, _supplier, business, _probe = client_for(manager, [])
    pool._current = "192.0.2.1:80"
    pool._adopted_at[pool._current] = time.monotonic()
    with pytest.raises(ProxyQuotaExceededError):
        client._attempt("http://target.test", {}, {}, pool._current)
    business.get.assert_not_called()


def test_corrupt_database_fails_closed(tmp_path):
    path = tmp_path / "usage.sqlite3"
    path.write_bytes(b"broken")
    import sqlite3

    with pytest.raises(sqlite3.DatabaseError):
        usage(tmp_path)


def test_secrets_not_stored_in_database_or_snapshot(tmp_path):
    manager = usage(tmp_path)
    manager.reserve(register(manager, "http://username:password@192.0.2.1:80"), "business")
    raw = (tmp_path / "usage.sqlite3").read_bytes()
    snapshot = json.dumps(manager.snapshot()).encode()
    for secret in (
        b"test-secret",
        b"username",
        b"password",
        b"192.0.2.1",
        FREE.encode(),
        PAID.encode(),
    ):
        assert secret not in raw
        assert secret not in snapshot


def test_missing_source_mapping_fails_before_session_construction(tmp_path, monkeypatch):
    settings = Settings(
        proxy_api="http://unsupported.test?type=2",
        proxy_usage_db=str(tmp_path / "usage.sqlite3"),
        proxy_usage_free_limit=0,
        proxy_usage_paid_limit=5,
    )
    session = MagicMock()
    monkeypatch.setattr(market_data, "ExplicitProxySession", session)
    with pytest.raises(ConfigError):
        market_data._create_client(settings)
    session.assert_not_called()


def test_independent_clients_share_process_budget(tmp_path):
    settings = Settings(
        proxy_api=f"{FREE},{PAID}",
        proxy_usage_db=str(tmp_path / "usage.sqlite3"),
        proxy_usage_free_limit=0,
        proxy_usage_paid_limit=5,
        proxy_usage_max_new=1,
    )
    first = market_data._build_client(settings, isolated=True)
    second = market_data._build_client(settings, isolated=True)
    try:
        manager = first._router._pool._usage
        assert manager is second._router._pool._usage
        manager.reserve(register(manager), "prefilter")
        with pytest.raises(ProxyQuotaExceededError):
            manager.reserve(register(manager, "192.0.2.2:80"), "business")
    finally:
        first.close()
        second.close()


def test_changed_settings_do_not_create_another_process_allowance(tmp_path):
    settings = Settings(
        proxy_api=f"{FREE},{PAID}",
        proxy_usage_db=str(tmp_path / "usage.sqlite3"),
        proxy_usage_free_limit=0,
        proxy_usage_paid_limit=5,
        proxy_usage_max_new=1,
    )
    market_data._usage_for(settings)
    with pytest.raises(ConfigError):
        market_data._usage_for(replace(settings, proxy_usage_max_new=2))


@pytest.mark.parametrize(
    "options",
    [
        dict(proxy_usage_paid_limit=1),
        dict(proxy_usage_db="x"),
        dict(proxy_usage_free_limit=-1),
        dict(proxy_usage_max_new=-1),
    ],
)
def test_partial_or_negative_quota_settings_rejected(options):
    with pytest.raises(ConfigError):
        Settings(**options)


def test_quota_settings_load_from_environment(clean_em_env, monkeypatch, tmp_path):
    monkeypatch.setenv("EM_PROXY_USAGE_DB", str(tmp_path / "usage.sqlite3"))
    monkeypatch.setenv("EM_PROXY_USAGE_FREE_LIMIT", "0")
    monkeypatch.setenv("EM_PROXY_USAGE_PAID_LIMIT", "812")
    monkeypatch.setenv("EM_PROXY_USAGE_MAX_NEW", "20")
    settings = Settings.from_env()
    assert settings.proxy_usage_free_limit == 0
    assert settings.proxy_usage_paid_limit == 812
    assert settings.proxy_usage_max_new == 20


def test_two_processes_cannot_overspend_shared_account(tmp_path):
    manager = usage(tmp_path, paid=3)
    program = """
import sys,time
from em.core.usage import ProxyUsage
from em.core.errors import ProxyQuotaExceededError
api='http://api.xiequ.cn/VAD/GetIp.aspx?uid=test&vkey=test-secret&type=2&num=3'
manager=ProxyUsage(sys.argv[1],[api],0,3)
accepted=0
for number in range(10):
    lease=manager.register(api,f'192.0.{sys.argv[2]}.{number}:80',time.time()+30)
    try:
        manager.reserve(lease,'business')
        accepted+=1
    except ProxyQuotaExceededError:
        pass
print(accepted)
"""
    workers = [
        subprocess.Popen(
            [sys.executable, "-c", program, str(manager.path), str(number)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for number in (1, 2)
    ]
    accepted = 0
    for worker in workers:
        stdout, stderr = worker.communicate(timeout=20)
        assert worker.returncode == 0, stderr
        accepted += int(stdout)
    assert accepted == 3
    assert manager.snapshot()["account"]["paid"]["remaining"] == 0


def test_prefilter_exhausted_free_source_can_fail_over_to_paid(tmp_path):
    manager = usage(tmp_path, free=1, paid=1)
    client, pool, supplier, business, probe = client_for(
        manager, ["192.0.2.1:80", "192.0.2.2:80"], prefilter=True
    )
    probe.side_effect = lambda proxy: proxy == "192.0.2.2:80"
    assert client.get_text("http://target.test", {}, {}) == "ok"
    assert [call.args[0] for call in supplier.get.call_args_list] == [FREE, PAID]
    assert manager.snapshot()["account"]["free"]["reserved"] == 1
    assert manager.snapshot()["account"]["paid"]["reserved"] == 1
    assert business.get.call_count == 1
    assert pool._in_flight == {}


def test_quota_race_after_acquire_prevents_send_and_releases_lease(tmp_path, monkeypatch):
    manager = usage(tmp_path, paid=1)
    client, pool, _supplier, business, _probe = client_for(manager, ["192.0.2.1:80"])
    competing = register(manager, "192.0.2.2:80")
    original = client._attempt

    def race(*args, **kwargs):
        manager.reserve(competing, "business")
        return original(*args, **kwargs)

    monkeypatch.setattr(client, "_attempt", race)
    with pytest.raises(ProxyQuotaExceededError):
        client.get_text("http://target.test", {}, {})
    business.get.assert_not_called()
    assert pool._in_flight == {}
    assert pool._failed_at == {}


def test_unknown_or_duplicate_source_type_is_rejected(tmp_path):
    for source in (PAID + "&type=0", PAID.replace("type=2", "type=3")):
        with pytest.raises(ConfigError):
            ProxyUsage(str(tmp_path / "usage.sqlite3"), [source], 0, 2)


def test_body_validation_failure_keeps_used_reservation(tmp_path):
    from em.core.errors import InvalidContentError

    manager = usage(tmp_path)
    client, pool, _supplier, business, _probe = client_for(manager, ["192.0.2.1:80"])
    with pytest.raises(InvalidContentError):
        client.get_text("http://target.test", {}, {}, validator=lambda _: False)
    assert business.get.call_count == 1
    assert manager.snapshot()["account"]["paid"]["reserved"] == 1
    assert pool._in_flight == {}


def test_repeated_configuration_and_cache_reset_keep_same_run_allowance(tmp_path):
    settings = Settings(
        proxy_api=f"{FREE},{PAID}",
        proxy_usage_db=str(tmp_path / "usage.sqlite3"),
        proxy_usage_free_limit=0,
        proxy_usage_paid_limit=5,
        proxy_usage_max_new=1,
    )
    manager = market_data._usage_for(settings)
    manager.reserve(register(manager), "business")
    market_data._reset_client_cache()
    assert market_data._usage_for(settings) is manager
    with pytest.raises(ProxyQuotaExceededError):
        manager.reserve(register(manager, "192.0.2.2:80"), "business")


def test_ledger_snapshot_is_explicitly_account_cumulative(tmp_path):
    from em.application.ledger import build_row

    manager = usage(tmp_path)
    manager.reserve(register(manager), "prefilter")
    row = build_row({"usage": manager.snapshot()}, {}, pages=1, items=1, wall=1)
    assert row["usage_account_snapshot"]["account"]["paid"]["reserved"] == 1
    assert row["ips_returned"] == 0
    assert "not_provider_billing" in row["usage_account_snapshot"]["basis"]


def test_account_budget_survives_new_run_even_if_run_limit_resets(tmp_path):
    first = usage(tmp_path, paid=2, run_limit=1)
    first.reserve(register(first), "business")
    second = usage(tmp_path, paid=2, run_limit=1)
    second.reserve(register(second, "192.0.2.2:80"), "business")
    third = usage(tmp_path, paid=2, run_limit=1)
    with pytest.raises(ProxyQuotaExceededError):
        third.reserve(register(third, "192.0.2.3:80"), "business")
    assert third.snapshot()["account"]["paid"]["remaining"] == 0


def test_balance_refresh_parses_count_package_without_network_in_unit(tmp_path, monkeypatch):
    manager = usage(tmp_path)
    manager.balance_url = "https://balance.test"
    response = MagicMock(status_code=200)
    response.json.return_value = {
        "success": "true",
        "data": [
            {"type": "次数套餐", "num": "8000", "use": "7148", "valid": "true"},
            {"type": "流量套餐", "num": "1073741824", "use": "12778309"},
        ],
    }
    session = MagicMock()
    session.get.return_value = response
    session.__enter__.return_value = session
    monkeypatch.setattr("em.core.usage.ExplicitProxySession", lambda: session)
    result = manager.refresh_balance(force=True)
    assert result["available"] == 852
    assert result["total"] == 8000
    assert result["used"] == 7148
    assert manager.snapshot()["remote_balance"]["available"] == 852


def test_remote_balance_can_tighten_local_capacity(tmp_path, monkeypatch):
    manager = usage(tmp_path, paid=5)
    manager.balance_url = "https://balance.test"
    response = MagicMock(status_code=200)
    response.json.return_value = {
        "success": "true",
        "data": [{"type": "次数套餐", "num": "2", "use": "2", "valid": "true"}],
    }
    session = MagicMock()
    session.get.return_value = response
    session.__enter__.return_value = session
    monkeypatch.setattr("em.core.usage.ExplicitProxySession", lambda: session)
    assert not manager.can_start(PAID)


def test_cross_client_same_lease_uses_same_reservation(tmp_path):
    manager = usage(tmp_path)
    first, _pool1, _supplier1, _business1, _probe1 = client_for(
        manager, ["192.0.2.1:80"], prefilter=True
    )
    second, _pool2, _supplier2, _business2, _probe2 = client_for(manager, ["192.0.2.1:80"])
    first.get_text("http://target.test", {}, {})
    second.get_text("http://target.test", {}, {})
    assert manager.snapshot()["account"]["paid"]["reserved"] == 1
    assert manager.snapshot()["account"]["paid"]["prefilter_attempts"] == 1
    assert manager.snapshot()["account"]["paid"]["business_attempts"] == 2


def test_reservation_write_failure_prevents_business_request(tmp_path, monkeypatch):
    import sqlite3

    manager = usage(tmp_path)
    client, pool, _supplier, business, _probe = client_for(manager, ["192.0.2.1:80"])

    def fail(*args, **kwargs):
        raise sqlite3.OperationalError("simulated storage failure")

    monkeypatch.setattr(manager, "reserve", fail)
    with pytest.raises(sqlite3.OperationalError):
        client.get_text("http://target.test", {}, {})
    business.get.assert_not_called()
    assert pool._in_flight == {}
    assert manager.snapshot()["account"]["paid"]["reserved"] == 0


def test_transaction_rolls_back_account_when_run_update_fails(tmp_path):
    import sqlite3

    manager = usage(tmp_path)
    lease = register(manager)
    with sqlite3.connect(manager.path) as connection:
        connection.execute("""CREATE TRIGGER reject_run_update BEFORE UPDATE ON runs
            BEGIN SELECT RAISE(ABORT, 'simulated failure'); END""")
    with pytest.raises(sqlite3.IntegrityError):
        manager.reserve(lease, "business")
    snapshot = manager.snapshot()
    assert snapshot["account"]["paid"]["reserved"] == 0
    assert snapshot["run"]["reserved"] == 0

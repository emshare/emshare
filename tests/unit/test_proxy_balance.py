"""余额刷新只收紧持久化额度；并发预占、缓存、重启及失败均不重置。"""

import copy
import socket
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

import pytest
import requests

from em.core.budget import request_budget
from em.core.errors import ConfigError, PageDeadlineExceeded, ProxyQuotaExceededError
from em.core.usage import ProxyUsage

API = "https://api.xiequ.cn/VAD/GetIp.aspx?uid=test&vkey=private&type=2"
BALANCE = "https://op.xiequ.cn/ApiUser.aspx?act=suitdt&uid=test&ukey=private"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("offline test attempted network")

    monkeypatch.setattr(socket.socket, "connect", deny)


def make_usage(tmp_path, balance_url=BALANCE):
    return ProxyUsage(str(tmp_path / "usage.sqlite3"), [API], 0, 100, 100, balance_url)


def fake_provider(monkeypatch, total=10, used=9):
    response = MagicMock(status_code=200)
    response.json.return_value = {
        "success": "true",
        "data": [{"type": "次数套餐", "num": str(total), "use": str(used), "valid": "true"}],
    }
    session = MagicMock()
    session.__enter__.return_value = session
    session.get.return_value = response
    monkeypatch.setattr("em.core.usage.requests.Session", lambda: session)
    return session, response


def lease(manager, number):
    return manager.register(API, f"192.0.2.{number}:80", time.time() + 30)


def test_remote_one_allows_only_one_new_lease_between_queries(tmp_path, monkeypatch):
    session, _response = fake_provider(monkeypatch)
    manager = make_usage(tmp_path)
    first = lease(manager, 1)
    second = lease(manager, 2)
    manager.reserve(first, "business")
    with pytest.raises(ProxyQuotaExceededError):
        manager.reserve(second, "prefilter")
    manager.reserve(first, "business")
    assert manager.snapshot()["remote_guard_remaining"] == 0
    assert manager.snapshot()["account"]["paid"]["reserved"] == 1
    assert session.get.call_count == 1


def test_stale_repeated_query_never_replenishes_allowance(tmp_path, monkeypatch):
    _session, _response = fake_provider(monkeypatch)
    manager = make_usage(tmp_path)
    manager.reserve(lease(manager, 1), "business")
    assert manager.refresh_balance(force=True)["available"] == 1
    assert manager.snapshot()["remote_guard_remaining"] == 0
    with pytest.raises(ProxyQuotaExceededError):
        manager.reserve(lease(manager, 2), "business")


def test_remote_lower_cap_persists_across_restart_and_query_outage(tmp_path, monkeypatch):
    session, _response = fake_provider(monkeypatch, total=10, used=10)
    manager = make_usage(tmp_path)
    assert not manager.can_start(API)
    session.get.side_effect = requests.ConnectionError("secret-url")
    reopened = make_usage(tmp_path)
    assert not reopened.can_start(API)
    assert reopened.snapshot()["remote_balance"]["available"] == 0
    assert reopened.snapshot()["remote_guard_remaining"] == 0
    offline = make_usage(tmp_path, balance_url="")
    assert not offline.can_start(API)


def test_parallel_managers_share_one_remote_unit(tmp_path, monkeypatch):
    _session, _response = fake_provider(monkeypatch)
    managers = [make_usage(tmp_path) for _ in range(8)]
    leases = [lease(manager, number) for number, manager in enumerate(managers, 1)]
    barrier = threading.Barrier(8)

    def reserve(index):
        barrier.wait(timeout=3)
        try:
            managers[index].reserve(leases[index], "business")
            return True
        except ProxyQuotaExceededError:
            return False

    with ThreadPoolExecutor(max_workers=8) as executor:
        assert sum(executor.map(reserve, range(8))) == 1
    assert managers[0].snapshot()["account"]["paid"]["reserved"] == 1


def test_reservations_during_initial_query_are_subtracted(tmp_path, monkeypatch):
    session, response = fake_provider(monkeypatch)
    manager = make_usage(tmp_path)
    competing = make_usage(tmp_path, balance_url="")
    competing_lease = lease(competing, 1)

    def get(*args, **kwargs):
        competing.reserve(competing_lease, "business")
        return response

    session.get.side_effect = get
    assert manager.refresh_balance(force=True)["available"] == 1
    assert manager.snapshot()["remote_guard_remaining"] == 0
    with pytest.raises(ProxyQuotaExceededError):
        manager.reserve(lease(manager, 2), "business")


def test_confirmed_provider_deduction_does_not_double_charge_local(tmp_path, monkeypatch):
    _session, response = fake_provider(monkeypatch, total=10, used=8)
    manager = make_usage(tmp_path)
    manager.reserve(lease(manager, 1), "business")
    response.json.return_value["data"][0]["use"] = "9"
    manager.refresh_balance(force=True)
    assert manager.snapshot()["remote_guard_remaining"] == 1
    manager.reserve(lease(manager, 2), "business")
    assert manager.snapshot()["remote_guard_remaining"] == 0


def test_newly_reported_external_consumption_tightens_persistent_cap(tmp_path, monkeypatch):
    _session, response = fake_provider(monkeypatch, total=10, used=5)
    manager = make_usage(tmp_path)
    manager.reserve(lease(manager, 1), "business")
    response.json.return_value["data"][0]["use"] = "9"
    manager.refresh_balance(force=True)
    assert manager.snapshot()["remote_guard_remaining"] == 1
    manager.reserve(lease(manager, 2), "business")
    with pytest.raises(ProxyQuotaExceededError):
        manager.reserve(lease(manager, 3), "business")


@pytest.mark.parametrize(
    "bad_response",
    [
        {"success": "false", "data": []},
        {"success": "true", "data": {}},
        {"success": "true", "data": ["bad"]},
        {
            "success": "true",
            "data": [{"type": "流量套餐", "num": "1000", "use": "0", "valid": "true"}],
        },
        {
            "success": "true",
            "data": [{"type": "次数套餐", "num": "10", "use": "0", "valid": "false"}],
        },
        {
            "success": "true",
            "data": [{"type": "次数套餐", "num": True, "use": "0", "valid": "true"}],
        },
        {
            "success": "true",
            "data": [{"type": "次数套餐", "num": "10", "use": "-1", "valid": "true"}],
        },
        {
            "success": "true",
            "data": [{"type": "次数套餐", "num": "10", "use": "11", "valid": "true"}],
        },
        {
            "success": "true",
            "data": [{"type": "次数套餐", "num": "10", "use": "1.5", "valid": "true"}],
        },
    ],
)
def test_invalid_balance_response_retains_previous_limit(tmp_path, monkeypatch, bad_response):
    _session, response = fake_provider(monkeypatch, total=10, used=10)
    manager = make_usage(tmp_path)
    before = manager.refresh_balance(force=True)
    response.json.return_value = bad_response
    assert manager.refresh_balance(force=True) == before
    assert manager.snapshot()["remote_guard_remaining"] == 0


def test_multiple_count_packages_are_not_silently_selected(tmp_path, monkeypatch):
    _session, response = fake_provider(monkeypatch)
    response.json.return_value["data"].append(copy.deepcopy(response.json.return_value["data"][0]))
    manager = make_usage(tmp_path)
    assert manager.refresh_balance(force=True) is None
    assert manager.snapshot()["remote_guard_remaining"] is None


def test_first_query_failure_falls_back_to_unchanged_local_limit(tmp_path, monkeypatch):
    session, _response = fake_provider(monkeypatch)
    session.get.side_effect = requests.ConnectionError("url-with-secret")
    manager = make_usage(tmp_path)
    assert manager.can_start(API)
    assert manager.snapshot()["account"]["paid"]["remaining"] == 100
    assert manager.snapshot()["remote_balance"] is None


def test_non_200_and_redirect_are_not_valid_snapshots(tmp_path, monkeypatch):
    session, response = fake_provider(monkeypatch)
    response.status_code = 302
    manager = make_usage(tmp_path)
    assert manager.refresh_balance(force=True) is None
    assert session.get.call_args.kwargs["allow_redirects"] is False
    assert session.trust_env is False


def test_balance_cache_returns_copy_and_avoids_extra_queries(tmp_path, monkeypatch):
    session, _response = fake_provider(monkeypatch)
    manager = make_usage(tmp_path)
    result = manager.refresh_balance(force=True)
    result["available"] = 999999
    assert manager.refresh_balance()["available"] == 1
    assert session.get.call_count == 1


def test_refresh_single_flight_rechecks_time_under_lock(tmp_path, monkeypatch):
    session, _response = fake_provider(monkeypatch)
    manager = make_usage(tmp_path)
    with ThreadPoolExecutor(max_workers=8) as executor:
        assert all(executor.map(lambda _: manager.refresh_balance()["available"] == 1, range(16)))
    assert session.get.call_count == 1


def test_deadline_bounds_wait_for_balance_lock(tmp_path, monkeypatch):
    session, _response = fake_provider(monkeypatch)
    manager = make_usage(tmp_path)
    manager._balance_lock.acquire()
    try:
        with pytest.raises(PageDeadlineExceeded), request_budget(time.monotonic() + 0.02):
            manager.refresh_balance()
    finally:
        manager._balance_lock.release()
    session.get.assert_not_called()


@pytest.mark.parametrize(
    "url",
    [
        BALANCE.replace("uid=test", "uid=someone-else"),
        BALANCE.replace("https:", "http:"),
        BALANCE.replace("op.xiequ.cn", "example.test"),
        BALANCE.replace("act=suitdt", "act=other"),
        BALANCE + "&uid=other",
        BALANCE + "#fragment",
    ],
)
def test_invalid_balance_endpoint_rejected_before_database_or_network(tmp_path, url):
    with pytest.raises(ConfigError):
        make_usage(tmp_path, balance_url=url)
    assert not (tmp_path / "usage.sqlite3").exists()


def test_remote_limit_write_failure_is_not_treated_as_network_fallback(tmp_path, monkeypatch):
    _session, _response = fake_provider(monkeypatch)
    manager = make_usage(tmp_path)
    with sqlite3.connect(manager.path) as connection:
        connection.execute("""CREATE TRIGGER reject_remote BEFORE INSERT ON remote_limits
            BEGIN SELECT RAISE(ABORT,'storage failed'); END""")
    with pytest.raises(sqlite3.IntegrityError):
        manager.refresh_balance(force=True)
    assert manager.snapshot()["account"]["paid"]["reserved"] == 0

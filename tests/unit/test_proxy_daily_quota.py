"""免费额度按北京时间分日，收费余额及进程累计不随午夜重置。"""

import copy
import socket
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
import requests

from em.core.errors import ConfigError, ProxyQuotaExceededError
from em.core.settings import Settings
from em.core.usage import ProxyUsage

FREE = "http://api.xiequ.cn/VAD/GetIp.aspx?uid=test&vkey=secret&type=0"
PAID = FREE.replace("type=0", "type=2")
BALANCE = "https://op.xiequ.cn/ApiUser.aspx?act=suitdt&uid=test&ukey=secret"
BEIJING = timezone(timedelta(hours=8))


@pytest.fixture
def clock(monkeypatch):
    now = [datetime(2026, 11, 17, 23, 59, 55, tzinfo=BEIJING).timestamp()]
    monkeypatch.setattr("em.core.usage.time.time", lambda: now[0])

    def deny(*args, **kwargs):
        raise AssertionError("network forbidden")

    monkeypatch.setattr(socket.socket, "connect", deny)
    return now


def provider(monkeypatch, *, total=1000, used=0, paid_used=9):
    response = MagicMock(status_code=200)
    response.json.return_value = {
        "success": "true",
        "data": [
            {
                "type": "免费套餐",
                "num": str(total),
                "use": str(used),
                "valid": "true",
                "enddate": "2026/11/18 0:00:00",
            },
            {"type": "次数套餐", "num": "10", "use": str(paid_used), "valid": "true"},
            {"type": "流量套餐", "num": "9999999", "use": "0", "valid": "true"},
        ],
    }
    session = MagicMock()
    session.__enter__.return_value = session
    session.get.return_value = response
    monkeypatch.setattr("em.core.usage.ExplicitProxySession", lambda: session)
    return session, response


def manager(tmp_path, run_limit=10, daily=1000):
    return ProxyUsage(
        str(tmp_path / "usage.db"), [FREE, PAID], 0, 50, run_limit, BALANCE, free_daily_limit=daily
    )


def lease(usage, clock, number=1, api=FREE):
    return usage.register(api, f"192.0.2.{number}:80", clock[0] + 30)


def test_free_does_not_consume_paid_remote_allowance(clock, tmp_path, monkeypatch):
    provider(monkeypatch, paid_used=10)
    usage = manager(tmp_path)
    assert usage.can_start(FREE)
    assert not usage.can_start(PAID)
    usage.reserve(lease(usage, clock), "prefilter")
    snapshot = usage.snapshot()
    assert snapshot["free_daily"]["remaining"] == 999
    assert snapshot["account"]["free"]["reserved"] == 1
    assert snapshot["account"]["paid"]["reserved"] == 0
    assert snapshot["remote_guard_remaining"] == 0


def test_paid_use_does_not_consume_free_allowance(clock, tmp_path, monkeypatch):
    provider(monkeypatch)
    usage = manager(tmp_path)
    usage.reserve(lease(usage, clock, api=PAID), "business")
    assert usage.snapshot()["free_daily"]["remaining"] == 1000
    assert usage.snapshot()["remote_guard_remaining"] == 0


def test_midnight_requires_new_valid_package_and_reuses_no_old_allowance(
    clock, tmp_path, monkeypatch
):
    session, response = provider(monkeypatch, used=999)
    usage = manager(tmp_path)
    old = lease(usage, clock)
    usage.reserve(old, "prefilter")
    assert usage.snapshot()["free_daily"]["remaining"] == 0
    clock[0] += 6
    assert not usage.can_start(FREE)
    assert session.get.call_count == 2
    assert not usage.can_use(old)
    response.json.return_value["data"][0].update(use="0", enddate="2026/11/19 0:00:00")
    usage.refresh_balance(force=True)
    usage.reserve(old, "business")
    snapshot = usage.snapshot()
    assert snapshot["free_daily"]["day"] == "2026-11-18"
    assert snapshot["free_daily"]["remaining"] == 999
    assert snapshot["free_daily"]["reserved_today"] == 1
    assert snapshot["account"]["free"]["reserved"] == 2
    assert snapshot["run"]["reserved"] == 2
    with sqlite3.connect(usage.path) as connection:
        assert connection.execute(
            "SELECT day,reserved FROM free_daily_limits ORDER BY day"
        ).fetchall() == [("2026-11-17", 1), ("2026-11-18", 1)]


def test_midnight_never_resets_run_limit(clock, tmp_path, monkeypatch):
    _session, response = provider(monkeypatch)
    usage = manager(tmp_path, run_limit=1)
    old = lease(usage, clock)
    usage.reserve(old, "business")
    clock[0] += 6
    response.json.return_value["data"][0]["enddate"] = "2026/11/19 0:00:00"
    with pytest.raises(ProxyQuotaExceededError):
        usage.reserve(old, "business")
    assert usage.snapshot()["free_daily"]["remaining"] == 1000
    assert usage.snapshot()["run"]["reserved"] == 1


def test_pause_stays_zero_after_free_refresh(clock, tmp_path, monkeypatch):
    provider(monkeypatch)
    usage = manager(tmp_path, run_limit=0)
    assert not usage.can_start(FREE)
    assert usage.snapshot()["free_daily"]["remaining"] == 1000
    with pytest.raises(ProxyQuotaExceededError):
        usage.reserve(lease(usage, clock), "business")


def test_repeated_stale_balance_does_not_restore_used_free_unit(clock, tmp_path, monkeypatch):
    provider(monkeypatch, used=999)
    usage = manager(tmp_path)
    usage.reserve(lease(usage, clock), "business")
    usage.refresh_balance(force=True)
    assert not usage.can_start(FREE)
    assert usage.snapshot()["free_daily"]["remaining"] == 0


def test_provider_catches_up_without_double_subtraction(clock, tmp_path, monkeypatch):
    _session, response = provider(monkeypatch, used=998)
    usage = manager(tmp_path)
    usage.reserve(lease(usage, clock), "business")
    response.json.return_value["data"][0]["use"] = "999"
    usage.refresh_balance(force=True)
    assert usage.snapshot()["free_daily"]["remaining"] == 1


def test_same_day_restart_preserves_free_uses(clock, tmp_path, monkeypatch):
    provider(monkeypatch, used=999)
    first = manager(tmp_path)
    first.reserve(lease(first, clock), "business")
    reopened = manager(tmp_path)
    assert not reopened.can_start(FREE)
    assert reopened.snapshot()["free_daily"]["remaining"] == 0


def test_refresh_failure_crossing_midnight_does_not_grant_free(clock, tmp_path, monkeypatch):
    session, _response = provider(monkeypatch)
    usage = manager(tmp_path)
    assert usage.can_start(FREE)
    clock[0] += 6
    session.get.side_effect = requests.ConnectionError("secret")
    assert not usage.can_start(FREE)
    assert usage.snapshot()["free_daily"]["remaining"] == 0


@pytest.mark.parametrize(
    "mutation",
    ["missing", "duplicate", "invalid", "expired", "wrong_expiry", "malformed", "overspent"],
)
def test_bad_free_package_blocks_free_without_poisoning_paid(
    clock, tmp_path, monkeypatch, mutation
):
    _session, response = provider(monkeypatch)
    package = response.json.return_value["data"][0]
    if mutation == "missing":
        response.json.return_value["data"].pop(0)
    elif mutation == "duplicate":
        response.json.return_value["data"].append(copy.deepcopy(package))
    elif mutation == "invalid":
        package["valid"] = "false"
    elif mutation == "expired":
        package["enddate"] = "2026/11/17 0:00:00"
    elif mutation == "wrong_expiry":
        package["enddate"] = "2026/11/19 0:00:00"
    elif mutation == "malformed":
        package["use"] = True
    else:
        package["use"] = "1001"
    usage = manager(tmp_path)
    assert not usage.can_start(FREE)
    assert usage.can_start(PAID)


def test_explicit_invalid_refresh_revokes_prior_free_capacity(clock, tmp_path, monkeypatch):
    _session, response = provider(monkeypatch)
    usage = manager(tmp_path)
    assert usage.can_start(FREE)
    response.json.return_value["data"][0]["valid"] = "false"
    usage.refresh_balance(force=True)
    assert not usage.can_start(FREE)


def test_query_crossing_midnight_cannot_assign_yesterdays_balance(clock, tmp_path, monkeypatch):
    session, response = provider(monkeypatch)
    usage = manager(tmp_path)

    def query(*args, **kwargs):
        clock[0] += 6
        return response

    session.get.side_effect = query
    usage.refresh_balance(force=True)
    assert usage.snapshot()["free_daily"]["remaining"] == 0


def test_free_daily_parallel_last_unit_is_atomic(clock, tmp_path, monkeypatch):
    provider(monkeypatch, used=999)
    managers = [manager(tmp_path) for _ in range(8)]
    leases = [lease(value, clock, number) for number, value in enumerate(managers, 1)]

    def reserve(index):
        try:
            managers[index].reserve(leases[index], "business")
            return True
        except ProxyQuotaExceededError:
            return False

    with ThreadPoolExecutor(max_workers=8) as executor:
        assert sum(executor.map(reserve, range(8))) == 1
    assert managers[0].snapshot()["free_daily"]["remaining"] == 0


def test_legacy_remote_limit_migration_preserves_paid_remaining(clock, tmp_path, monkeypatch):
    provider(monkeypatch)
    path = tmp_path / "usage.db"
    with sqlite3.connect(path) as connection:
        connection.execute("""CREATE TABLE remote_limits(account_id TEXT PRIMARY KEY,ceiling INTEGER,
                           total INTEGER,used INTEGER,queried REAL,checked REAL)""")
    usage = manager(tmp_path)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE accounts SET reserved=3 WHERE kind='free'")
        connection.execute("UPDATE accounts SET reserved=2 WHERE kind='paid'")
        connection.execute(
            "INSERT INTO remote_limits VALUES (?,?,?,?,?,?,'account')",
            (usage.account_id, 10, 10, 5, clock[0], clock[0]),
        )
    reopened = manager(tmp_path)
    assert reopened.snapshot()["remote_guard_remaining"] == 5
    again = manager(tmp_path)
    assert again.snapshot()["remote_guard_remaining"] == 5
    assert again.snapshot()["account"]["paid"]["reserved"] == 2


def test_same_lease_repeated_today_only_reserves_once(clock, tmp_path, monkeypatch):
    provider(monkeypatch)
    usage = manager(tmp_path)
    value = lease(usage, clock)
    usage.reserve(value, "prefilter")
    usage.reserve(value, "business")
    assert usage.snapshot()["free_daily"]["reserved_today"] == 1
    assert usage.snapshot()["run"]["reserved"] == 1


def test_disable_daily_mode_keeps_static_free_zero(clock, tmp_path, monkeypatch):
    provider(monkeypatch)
    usage = manager(tmp_path, daily=0)
    assert not usage.can_start(FREE)
    assert usage.snapshot()["free_daily"]["enabled"] is False


def test_daily_mode_requires_balance_and_valid_nonnegative_limit():
    with pytest.raises(ConfigError):
        Settings(proxy_usage_free_daily_limit=1000)
    with pytest.raises(ConfigError):
        Settings(proxy_usage_free_daily_limit=-1)


def test_free_package_still_works_if_paid_package_is_absent(clock, tmp_path, monkeypatch):
    _session, response = provider(monkeypatch)
    response.json.return_value["data"].pop(1)
    usage = manager(tmp_path)
    assert usage.can_start(FREE)
    assert usage.snapshot()["free_daily"]["remaining"] == 1000
    assert usage.snapshot()["remote_balance"] is None


def test_settings_load_daily_limit_without_resetting_process_pause(clean_em_env, monkeypatch):
    monkeypatch.setenv("EM_PROXY_USAGE_DB", "/tmp/example.db")
    monkeypatch.setenv("EM_PROXY_USAGE_FREE_LIMIT", "0")
    monkeypatch.setenv("EM_PROXY_USAGE_PAID_LIMIT", "812")
    monkeypatch.setenv("EM_PROXY_USAGE_MAX_NEW", "0")
    monkeypatch.setenv("EM_PROXY_BALANCE_URL", BALANCE)
    monkeypatch.setenv("EM_PROXY_USAGE_FREE_DAILY_LIMIT", "1000")
    settings = Settings.from_env()
    assert settings.proxy_usage_free_daily_limit == 1000
    assert settings.proxy_usage_max_new == 0
    assert settings.proxy_usage_free_limit == 0


def test_local_daily_cap_and_provider_used_are_both_enforced(clock, tmp_path, monkeypatch):
    provider(monkeypatch, used=999)
    usage = manager(tmp_path, daily=100)
    assert not usage.can_start(FREE)


def test_clock_rollback_does_not_recreate_previously_consumed_day(clock, tmp_path, monkeypatch):
    _session, response = provider(monkeypatch, used=999)
    usage = manager(tmp_path)
    yesterday = clock[0]
    usage.reserve(lease(usage, clock), "business")
    clock[0] += 6
    response.json.return_value["data"][0].update(use="0", enddate="2026/11/19 0:00:00")
    assert usage.can_start(FREE)
    clock[0] = yesterday
    response.json.return_value["data"][0].update(use="999", enddate="2026/11/18 0:00:00")
    assert not usage.can_start(FREE)


def test_daily_reserved_increments_rollback_if_attempt_audit_fails(clock, tmp_path, monkeypatch):
    provider(monkeypatch)
    usage = manager(tmp_path)
    value = lease(usage, clock)
    with sqlite3.connect(usage.path) as connection:
        connection.execute("""CREATE TRIGGER fail_daily_attempt BEFORE INSERT ON usage_attempts
            BEGIN SELECT RAISE(ABORT,'audit failed'); END""")
    with pytest.raises(sqlite3.IntegrityError):
        usage.reserve(value, "business")
    state = usage.snapshot()
    assert state["free_daily"]["reserved_today"] == 0
    assert state["account"]["free"]["reserved"] == 0
    assert state["run"]["reserved"] == 0

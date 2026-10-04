"""ProxyPool 行为锁：TTL 复用、失败后优先用 standby、过期才回源（不触网）。"""

from unittest.mock import MagicMock

import pytest
import requests

from em.core.errors import ConfigError
from em.core.proxy import ProxyPool, ProxySettings


def _settings(num: int = 1, ttl_sec: int = 30, safety_margin_sec: int = 3) -> ProxySettings:
    return ProxySettings(
        api="http://example/getip",
        enabled=True,
        num=num,
        ttl_sec=ttl_sec,
        safety_margin_sec=safety_margin_sec,
        timeout_sec=8,
    )


def _session_returning(ips: list[str]) -> requests.Session:
    session = MagicMock(spec=requests.Session)
    session.get.return_value = MagicMock(text="\n".join(ips))
    return session


def test_disabled_returns_none() -> None:
    settings = ProxySettings(api="x", enabled=False)
    pool = ProxyPool(settings, MagicMock(spec=requests.Session))
    assert pool.acquire() is None


def test_first_acquire_refills_and_returns_current() -> None:
    session = _session_returning(["1.1.1.1:8080"])
    pool = ProxyPool(_settings(), session)
    assert pool.acquire() == "1.1.1.1:8080"


def test_reuses_current_within_ttl() -> None:
    session = _session_returning(["1.1.1.1:8080"])
    pool = ProxyPool(_settings(ttl_sec=30), session)
    pool.acquire()
    # TTL 内再次 acquire 不应再调代理 API
    assert pool.acquire() == "1.1.1.1:8080"
    assert session.get.call_count == 1


def test_failure_then_standby_used_without_refill() -> None:
    # num=3 一次拉 3 个，current 失败后应优先用 standby，不再调代理 API
    session = _session_returning(["1.1.1.1:8080", "2.2.2.2:8080", "3.3.3.3:8080"])
    pool = ProxyPool(_settings(num=3, ttl_sec=30), session)
    assert pool.acquire() == "1.1.1.1:8080"
    assert session.get.call_count == 1

    pool.report_failure("1.1.1.1:8080")
    # 失效后应立即拿到 standby 中的 2.2.2.2，且不触发回源
    assert pool.acquire() == "2.2.2.2:8080"
    assert session.get.call_count == 1

    pool.report_failure("2.2.2.2:8080")
    assert pool.acquire() == "3.3.3.3:8080"
    assert session.get.call_count == 1


def test_standby_exhausted_then_refill() -> None:
    session = _session_returning(["1.1.1.1:8080", "2.2.2.2:8080"])
    pool = ProxyPool(_settings(num=2, ttl_sec=30), session)
    pool.acquire()
    pool.report_failure("1.1.1.1:8080")
    pool.acquire()  # 用掉 standby 2.2.2.2
    pool.report_failure("2.2.2.2:8080")
    # standby 耗尽，应回源；让下一次拉取返回新 IP
    session.get.return_value = MagicMock(text="4.4.4.4:8080")
    assert pool.acquire() == "4.4.4.4:8080"
    assert session.get.call_count == 2


def test_ttl_expired_skips_standby_and_refills() -> None:
    # TTL 过期时 standby 同批也已过期，应跳过 standby 直接回源
    session = _session_returning(["1.1.1.1:8080", "2.2.2.2:8080"])
    pool = ProxyPool(_settings(num=2, ttl_sec=1, safety_margin_sec=0), session)
    pool.acquire()
    # 等待 TTL 过期
    import time

    time.sleep(1.1)
    session.get.return_value = MagicMock(text="3.3.3.3:8080")
    assert pool.acquire() == "3.3.3.3:8080"


def test_report_failure_removes_proxy_from_standby() -> None:
    session = _session_returning(["1.1.1.1:8080", "2.2.2.2:8080", "3.3.3.3:8080"])
    pool = ProxyPool(_settings(num=3), session)
    pool.acquire()
    # 直接淘汰 standby 中的 2.2.2.2
    pool.report_failure("2.2.2.2:8080")
    pool.report_failure("1.1.1.1:8080")
    # 应跳过已淘汰的 2.2.2.2，直接给 3.3.3.3
    assert pool.acquire() == "3.3.3.3:8080"


def test_fetch_failure_degrades_to_none() -> None:
    session = MagicMock(spec=requests.Session)
    session.get.side_effect = requests.RequestException("boom")
    pool = ProxyPool(_settings(), session)
    assert pool.acquire() is None


def test_unexpected_format_warns_and_degrades(caplog) -> None:
    # 代理源返回错误文本（余额不足/频率过快）应 warning，不能静默退化直连
    session = MagicMock(spec=requests.Session)
    session.get.return_value = MagicMock(text="频率过快，请稍后再试")
    pool = ProxyPool(_settings(), session)
    caplog.set_level("WARNING", logger="em.core.proxy")
    assert pool.acquire() is None
    assert any("非预期格式" in r.message for r in caplog.records)


def test_invalid_settings_raise() -> None:
    with pytest.raises(ConfigError):
        ProxySettings(api="x", num=0)
    with pytest.raises(ConfigError):
        ProxySettings(api="x", ttl_sec=3, safety_margin_sec=3)


def _session_sequence(ips: list[str]) -> requests.Session:
    """代理 API 按序返回给定 IP，超出后重复最后一个。"""
    session = MagicMock(spec=requests.Session)
    responses = [MagicMock(text=ip) for ip in ips]
    session.get.side_effect = responses + [responses[-1]] * 10
    return session


def test_failed_ip_not_immediately_reused() -> None:
    # API 交替返回 A,B,A,B...；失败 A 后下次应拿到 B 而非 A
    session = _session_sequence(["1.1.1.1:8080", "2.2.2.2:8080", "1.1.1.1:8080", "2.2.2.2:8080"])
    pool = ProxyPool(_settings(), session)
    assert pool.acquire() == "1.1.1.1:8080"
    pool.report_failure("1.1.1.1:8080")
    # refill 应跳过黑名单中的 1.1.1.1，拿到 2.2.2.2
    assert pool.acquire() == "2.2.2.2:8080"


def test_blacklist_exhausted_falls_back_to_hard_use() -> None:
    # IP 池只有 1 个 IP，失败后 3 次重拉都拿到它 → 硬用（避免拿不到代理）
    session = _session_sequence(["1.1.1.1:8080"])
    pool = ProxyPool(_settings(), session)
    assert pool.acquire() == "1.1.1.1:8080"
    pool.report_failure("1.1.1.1:8080")
    assert pool.acquire() == "1.1.1.1:8080"


def test_blacklist_purged_after_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    # 失败记录在 TTL 后清除，IP 可重新使用

    fake_now = [0.0]
    monkeypatch.setattr("em.core.proxy.time.monotonic", lambda: fake_now[0])

    session = _session_sequence(["1.1.1.1:8080", "2.2.2.2:8080", "1.1.1.1:8080"])
    pool = ProxyPool(_settings(ttl_sec=30), session)
    assert pool.acquire() == "1.1.1.1:8080"
    pool.report_failure("1.1.1.1:8080")
    # TTL 内：跳过 1.1.1.1
    fake_now[0] = 10.0
    assert pool.acquire() == "2.2.2.2:8080"
    pool.report_failure("2.2.2.2:8080")
    # 超过 TTL：1.1.1.1 出黑名单，可重新拿到
    fake_now[0] = 35.0
    assert pool.acquire() == "1.1.1.1:8080"

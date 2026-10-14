"""ProxyPool 行为锁：TTL 复用、失败后优先用 standby、过期才回源、预筛与耗时（不触网）。"""

import time
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


def test_least_in_flight_first_distribution() -> None:
    # 分发按"在飞最少"选择：多 worker 并发不挤同一 IP，在飞计数被均匀压平
    from collections import Counter

    session = _session_returning(["1.1.1.1:8080", "2.2.2.2:8080", "3.3.3.3:8080"])
    pool = ProxyPool(_settings(num=3), session)
    got = [pool.acquire() for _ in range(6)]
    # 3 IP 均摊 6 次取用（各 2 次），任何时刻在飞差 <=1
    assert set(Counter(got).values()) == {2}
    pool.release("1.1.1.1:8080")
    pool.release("2.2.2.2:8080")
    # 1.1/2.2 在飞 1、3.3 在飞 2 → 优先在飞最小者（并列保序取 1.1）
    assert pool.acquire() == "1.1.1.1:8080"
    # release 多余调用安全；report_failure 释放其在飞占用并淘汰
    pool.release("3.3.3.3:8080")
    pool.release("3.3.3.3:8080")  # 归零清除，多余调用安全
    pool.report_failure("1.1.1.1:8080")
    assert pool.acquire() == "3.3.3.3:8080"  # 1.1 已淘汰；3.3 在飞 0 优先于 2.2
    assert session.get.call_count == 1  # 全程未回源


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


def test_empty_refill_negative_cached_within_cooldown(monkeypatch) -> None:
    # 回源空返回后，负缓存窗口内排队线程不得连环打代理 API
    import em.core.proxy as proxymod

    monkeypatch.setattr(proxymod, "_EMPTY_REFILL_COOLDOWN_SEC", 10)
    session = MagicMock(spec=requests.Session)
    session.get.side_effect = requests.RequestException("IP资源不足")
    pool = ProxyPool(_settings(), session)
    assert pool.acquire() is None
    assert pool.acquire() is None
    assert session.get.call_count == 1  # 第二次被负缓存拦截，未再请求代理源


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


# --- 回源预筛 ---


def test_prefilter_rejects_dead_ips_before_pool() -> None:
    # prober 判死的 IP 记黑名单不进池，只有存活的被采纳
    session = _session_sequence(["1.1.1.1:8080", "2.2.2.2:8080", "3.3.3.3:8080", "9.9.9.9:8080"])
    verdicts = {"1.1.1.1:8080": False, "2.2.2.2:8080": True, "3.3.3.3:8080": True}
    pool = ProxyPool(_settings(num=3), session, prober=lambda ip: verdicts.get(ip, True))
    assert pool.acquire() == "2.2.2.2:8080"  # 1.1.1.1 被筛死，2.2.2.2 为首个存活
    assert "1.1.1.1:8080" in pool._failed_at  # noqa: SLF001
    assert pool.stats()["prefilter_rejected"] == 1


def test_prefilter_all_dead_degrades_then_recovers(monkeypatch: pytest.MonkeyPatch) -> None:
    # 整批筛死 → 暂停预筛一个窗口：窗口内 refill 跳过探测直接进池（业务自然淘汰），
    # 窗口过后自动恢复探测——极差时段不空转，好时段保持拦截
    fake_now = [0.0]
    monkeypatch.setattr("em.core.proxy.time.monotonic", lambda: fake_now[0])
    session = _session_sequence(
        ["1.1.1.1:8080", "2.2.2.2:8080", "3.3.3.3:8080", "4.4.4.4:8080"]
    )
    calls: list[str] = []

    def prober(ip: str) -> bool:
        calls.append(ip)
        return False  # 全部判死

    pool = ProxyPool(_settings(num=1, ttl_sec=60), session, prober=prober)
    assert pool.acquire() == "2.2.2.2:8080"  # 首批预筛全死 → 暂停 → 第 2 批直接进池
    assert calls == ["1.1.1.1:8080"]  # 暂停期不再探测
    assert pool.stats()["prefilter_rejected"] == 1

    fake_now[0] = 11.0  # 窗口（10s）过期
    pool.report_failure("2.2.2.2:8080")  # 淘汰在池 IP，强制下次 refill
    # 恢复探测：3.3.3.3 筛死再次触发暂停 → 第 2 批 4.4.4.4 直接进池
    assert pool.acquire() == "4.4.4.4:8080"
    assert calls == ["1.1.1.1:8080", "3.3.3.3:8080"]


def test_prefilter_alive_resets_pause() -> None:
    # 批内有存活 → 不触发降级窗口，后续 refill 继续正常预筛
    session = MagicMock(spec=requests.Session)
    session.get.side_effect = [
        MagicMock(text="1.1.1.1:8080\n1.1.1.2:8080"),
        MagicMock(text="2.2.2.2:8080\n2.2.2.3:8080"),
    ]
    seen: list[str] = []

    def prober(ip: str) -> bool:
        seen.append(ip)
        return ip != "1.1.1.1:8080"  # 第 1 批一死一活，之后全活

    pool = ProxyPool(_settings(num=2), session, prober=prober)
    assert pool.acquire() == "1.1.1.2:8080"
    pool.report_failure("1.1.1.2:8080")
    assert pool.acquire() == "2.2.2.2:8080"  # 第 2 批仍正常预筛（未降级）
    assert seen == [
        "1.1.1.1:8080",
        "1.1.1.2:8080",
        "2.2.2.2:8080",
        "2.2.2.3:8080",
    ]


def test_prefilter_none_keeps_legacy_behavior() -> None:
    # 未注入 prober：完全不预筛，行为与旧版一致
    session = _session_sequence(["1.1.1.1:8080", "2.2.2.2:8080"])
    pool = ProxyPool(_settings(num=1), session, prober=None)
    assert pool.acquire() == "1.1.1.1:8080"
    pool.report_failure("1.1.1.1:8080")
    assert pool.acquire() == "2.2.2.2:8080"
    assert pool.stats()["prefilter_rejected"] == 0


def test_prefilter_marks_dead_for_refill_skip() -> None:
    # 预筛判死的 IP 进入黑名单：后续回源命中同一 IP 时直接跳过（不再重复预筛）
    session = _session_sequence(["1.1.1.1:8080", "1.1.1.1:8080", "2.2.2.2:8080"])
    pool = ProxyPool(_settings(num=1), session, prober=lambda ip: ip != "1.1.1.1:8080")
    assert pool.acquire() == "2.2.2.2:8080"  # 第 1 批筛死 → 第 2 批同 IP 被黑名单跳过
    assert session.get.call_count == 3
    assert pool.stats()["prefilter_rejected"] == 1


def test_prefilter_and_refill_time_accumulated() -> None:
    # 代理段耗时计算：回源与预筛的墙钟耗时分别累计，供端到端归因
    session = _session_sequence(["1.1.1.1:8080"])
    pool = ProxyPool(_settings(num=1), session, prober=lambda _ip: time.sleep(0.02) or True)
    assert pool.acquire() == "1.1.1.1:8080"
    stats = pool.stats()
    assert stats["refill_sec"] > 0.0
    assert stats["prefilter_sec"] >= 0.02


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

"""ProxyPool 行为锁：TTL 复用、失败后优先用 standby、过期才回源、预筛与耗时（不触网）。"""

import time
from unittest.mock import MagicMock

import pytest
import requests

from em.core.errors import ConfigError
from em.core.proxy import ProxyPool, ProxySettings, fetch_proxies, proxy_url


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
    # release 多余调用安全；report_failure 只淘汰，在飞计数留给 release 归零
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


def test_proxy_url_normalizes_entries() -> None:
    # 裸 ip:port 补 http://；显式 scheme 与认证原样保留
    assert proxy_url("1.1.1.1:8080") == "http://1.1.1.1:8080"
    assert proxy_url("https://1.1.1.1:8443") == "https://1.1.1.1:8443"
    assert proxy_url("u:p@1.1.1.1:8080") == "http://u:p@1.1.1.1:8080"


def test_fetch_proxies_accepts_auth_and_rejects_socks() -> None:
    # 支持显式 scheme 与 user:pass@ 认证；socks 需要 PySocks，本项目不引新依赖；
    # 重复行原样保留（计费按交付行数对账），去重发生在截断前
    session = MagicMock(spec=requests.Session)
    session.get.return_value = MagicMock(
        text="1.1.1.1:8080\n1.1.1.1:8080\nuser:pw@2.2.2.2:8080\nhttps://3.3.3.3:8443\n"
        "socks5://4.4.4.4:1080\n垃圾"
    )
    assert fetch_proxies(_settings(num=9), session) == [
        "1.1.1.1:8080",
        "1.1.1.1:8080",
        "user:pw@2.2.2.2:8080",
        "https://3.3.3.3:8443",
    ]


def test_invalid_settings_raise() -> None:
    with pytest.raises(ConfigError):
        ProxySettings(api="x", num=0)
    with pytest.raises(ConfigError):
        ProxySettings(api="x", ttl_sec=3, safety_margin_sec=3)
    with pytest.raises(ConfigError):
        ProxySettings(api="x", prefilter_sources=-1)
    with pytest.raises(ConfigError):
        ProxySettings(api="x", degraded_mode="bogus")  # type: ignore[arg-type]


# --- 整批全死后的处置：adopt（暂停） vs lenient（降级快筛）---


def test_lenient_mode_probes_with_fallback_after_all_dead() -> None:
    # 整批全死 → 不暂停，改用快筛继续过滤：hang IP 不必交给业务侧用两次超时鉴死
    session = _session_sequence(["1.1.1.1:8080\n1.1.1.2:8080", "2.2.2.2:8080\n2.2.2.3:8080"])
    settings = ProxySettings(api="http://p/get", num=2, ttl_sec=60, degraded_mode="lenient")
    strict: list[str] = []
    fast: list[str] = []
    pool = ProxyPool(
        settings,
        session,
        prober=lambda ip: strict.append(ip) or False,
        fallback_prober=lambda ip: fast.append(ip) or True,
    )
    assert pool.acquire() == "2.2.2.2:8080"
    assert strict == ["1.1.1.1:8080", "1.1.1.2:8080"]  # 首批用正常探测
    assert fast == ["2.2.2.2:8080", "2.2.2.3:8080"]  # 全死后改用快筛，而非直接放行
    stats = pool.stats()
    assert stats["prefilter_rejected"] == 2
    assert stats["prefilter_lenient_rejected"] == 0


def test_adopt_mode_skips_probe_in_degraded_window() -> None:
    # 默认 adopt：整批全死后直接放行下一批，一次探测都不做（保持旧行为，便于 A/B）
    session = _session_sequence(["1.1.1.1:8080\n1.1.1.2:8080", "2.2.2.2:8080\n2.2.2.3:8080"])
    # 显式指定 adopt：这是回退路径，默认值已是 lenient
    settings = ProxySettings(api="http://p/get", num=2, ttl_sec=60, degraded_mode="adopt")
    strict: list[str] = []
    fast: list[str] = []
    pool = ProxyPool(
        settings,
        session,
        prober=lambda ip: strict.append(ip) or False,
        fallback_prober=lambda ip: fast.append(ip) or True,
    )
    assert pool.acquire() == "2.2.2.2:8080"
    assert strict == ["1.1.1.1:8080", "1.1.1.2:8080"]
    assert fast == []  # adopt 模式不启用快筛
    # 未验证就放行的 IP 数与触发次数都必须可量化（评估降级策略的暴露面与触发率）
    assert pool.stats()["degraded_adopted"] == 2
    assert pool.stats()["degraded_events"] == 1


# --- 预筛范围：收费备用源不预筛（淘汰等于浪费配额）---


def test_prefilter_skipped_for_backup_source() -> None:
    # 主源空返回 → 备用源交付；备用源不参与预筛，判死回调一次都不该被调用
    session = MagicMock(spec=requests.Session)
    session.get.side_effect = [
        MagicMock(text="IP资源不足"),
        MagicMock(text="5.5.5.5:8080\n6.6.6.6:8080"),
    ]
    settings = ProxySettings(
        api="http://p/get,http://b/get", num=2, ttl_sec=60, prefilter_sources=1
    )
    calls: list[str] = []
    pool = ProxyPool(settings, session, prober=lambda ip: calls.append(ip) or False)
    assert pool.acquire() == "5.5.5.5:8080"
    assert calls == []  # 收费源直接进池
    assert pool.stats()["prefilter_rejected"] == 0
    assert [v["rejected"] for v in pool.stats()["source_stats"].values()] == [0, 0]


def test_prefilter_applies_to_primary_by_default() -> None:
    # 主源仍按老口径预筛：默认值不改变单源/主源行为
    session = MagicMock(spec=requests.Session)
    session.get.return_value = MagicMock(text="1.1.1.1:8080\n2.2.2.2:8080")
    settings = ProxySettings(api="http://p/get,http://b/get", num=2, ttl_sec=60)
    calls: list[str] = []
    pool = ProxyPool(settings, session, prober=lambda ip: calls.append(ip) or ip == "2.2.2.2:8080")
    assert pool.acquire() == "2.2.2.2:8080"
    assert calls == ["1.1.1.1:8080", "2.2.2.2:8080"]
    assert pool.stats()["prefilter_rejected"] == 1


def test_prefilter_sources_zero_disables_prefilter() -> None:
    # N=0：完全关闭预筛（死 IP 交给业务请求自然淘汰），连主源也不探测
    session = _session_returning(["1.1.1.1:8080"])
    settings = ProxySettings(api="http://p/get", num=1, ttl_sec=30, prefilter_sources=0)
    calls: list[str] = []
    pool = ProxyPool(settings, session, prober=lambda ip: calls.append(ip) or False)
    assert pool.acquire() == "1.1.1.1:8080"
    assert calls == []


# --- 连败熔断：全死窗口不再持续买 IP ---


def test_consecutive_dead_batches_trip_breaker() -> None:
    # 连续 2 批全死即熔断：不再回源，直接返回 None（全死窗口里继续买是纯支出）
    session = _session_sequence(["1.1.1.1:8080", "2.2.2.2:8080", "3.3.3.3:8080"])
    settings = ProxySettings(api="http://p/get", num=1, ttl_sec=60, degraded_mode="lenient")
    pool = ProxyPool(settings, session, prober=lambda ip: False, fallback_prober=lambda ip: False)
    assert pool.acquire() is None
    assert session.get.call_count == 2  # 阈值 2：第三批不再买
    assert pool.stats()["source_breaker_trips"] == 1


def test_breaker_fails_over_to_backup_source() -> None:
    # 主源熔断后应立刻改用备用源，而不是整体停摆
    session = MagicMock(spec=requests.Session)
    session.get.side_effect = [
        MagicMock(text="1.1.1.1:8080\n1.1.1.2:8080"),
        MagicMock(text="2.2.2.2:8080\n2.2.2.3:8080"),
        MagicMock(text="9.9.9.9:8080\n9.9.9.8:8080"),
    ]
    settings = ProxySettings(
        api="http://p/get,http://b/get",
        num=2,
        ttl_sec=60,
        prefilter_sources=1,
        degraded_mode="lenient",
    )
    pool = ProxyPool(settings, session, prober=lambda ip: False, fallback_prober=lambda ip: False)
    assert pool.acquire() == "9.9.9.9:8080"
    stats = pool.stats()
    assert stats["source_breaker_trips"] == 1
    assert stats["fetch_calls"] == 3
    assert stats["ips_adopted"] == 2  # 备用源不预筛，直接进池


def test_breaker_recovers_after_cooldown(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_now = [0.0]
    monkeypatch.setattr("em.core.proxy.time.monotonic", lambda: fake_now[0])
    session = _session_sequence(["1.1.1.1:8080", "2.2.2.2:8080", "3.3.3.3:8080"])
    settings = ProxySettings(api="http://p/get", num=1, ttl_sec=60, degraded_mode="lenient")
    alive = {"3.3.3.3:8080": True}
    pool = ProxyPool(
        settings,
        session,
        prober=lambda ip: alive.get(ip, False),
        fallback_prober=lambda ip: False,
    )
    assert pool.acquire() is None  # 两批全死 → 熔断
    assert session.get.call_count == 2
    fake_now[0] = 61.0  # 冷却到期：允许再次回源
    assert pool.acquire() == "3.3.3.3:8080"
    assert session.get.call_count == 3


def test_live_batch_resets_dead_streak() -> None:
    # 死一批 → 活一批 → 再连续死两批：连败被成功打断过，因此只在第二次连死时熔断
    session = _session_sequence(
        ["1.1.1.1:8080", "2.2.2.2:8080", "3.3.3.3:8080", "4.4.4.4:8080"]
    )
    settings = ProxySettings(api="http://p/get", num=1, ttl_sec=60, degraded_mode="lenient")
    alive = {"2.2.2.2:8080": True}
    # 第 2 批落在降级窗口内，走快筛；快筛同样认得 2.2.2.2
    pool = ProxyPool(
        settings,
        session,
        prober=lambda ip: alive.get(ip, False),
        fallback_prober=lambda ip: alive.get(ip, False),
    )
    assert pool.acquire() == "2.2.2.2:8080"  # 第 2 批命中 → 连败清零
    assert pool.stats()["source_breaker_trips"] == 0

    pool.report_failure("2.2.2.2:8080")  # 强制下一轮回源
    assert pool.acquire() is None  # 第 3、4 批连死 → 才熔断
    assert session.get.call_count == 4
    assert pool.stats()["source_breaker_trips"] == 1


def test_refill_backs_off_between_rounds(monkeypatch: pytest.MonkeyPatch) -> None:
    # 整批不可用后不能零间隔连打代理 API：每轮之间短退避，最后一轮失败后不再等
    from em.core.proxy import _REFILL_ROUND_BACKOFF_SEC

    slept: list[float] = []
    monkeypatch.setattr("em.core.proxy.time.sleep", slept.append)
    session = _session_sequence(["1.1.1.1:8080", "2.2.2.2:8080", "3.3.3.3:8080"])
    settings = ProxySettings(api="http://p/get", num=1, ttl_sec=60, degraded_mode="lenient")
    pool = ProxyPool(settings, session, prober=lambda ip: False, fallback_prober=lambda ip: False)
    assert pool.acquire() is None
    # 两轮失败各退避一次，第三轮直接返回（熔断后不再回源）
    assert slept == [_REFILL_ROUND_BACKOFF_SEC] * 2


# --- 续期：硬到期前 3s 后台换血，旧 IP 继续服务 ---


def test_renew_due_enters_window_before_hard_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    # TTL=10、余量=2 → 硬到期 8s；提前量 3s → 5s 起进入续期窗口，但对外仍发旧 IP
    fake_now = [0.0]
    monkeypatch.setattr("em.core.proxy.time.monotonic", lambda: fake_now[0])
    session = _session_sequence(["1.1.1.1:8080", "2.2.2.2:8080"])
    pool = ProxyPool(_settings(ttl_sec=10, safety_margin_sec=2), session)
    assert pool.acquire() == "1.1.1.1:8080"
    assert pool._renew_due() is False
    fake_now[0] = 4.9
    assert pool._renew_due() is False
    fake_now[0] = 5.0
    assert pool._renew_due() is True
    assert pool._is_live("1.1.1.1:8080") is True  # 还没硬到期，仍在服务
    assert pool._take_live() == "1.1.1.1:8080"


def test_renew_worker_replaces_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_now = [0.0]
    monkeypatch.setattr("em.core.proxy.time.monotonic", lambda: fake_now[0])
    session = _session_sequence(["1.1.1.1:8080", "2.2.2.2:8080"])
    pool = ProxyPool(_settings(ttl_sec=10, safety_margin_sec=2), session)
    assert pool.acquire() == "1.1.1.1:8080"
    fake_now[0] = 6.0
    pool._renewing = True
    pool._renew_worker()
    assert pool._renewing is False
    assert pool._current == "2.2.2.2:8080"
    assert session.get.call_count == 2


def test_renewal_failure_keeps_old_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    # 续期失败（回源空/异常）不丢旧 IP：它已被业务证明可用，撑到硬到期比没 IP 强
    fake_now = [0.0]
    monkeypatch.setattr("em.core.proxy.time.monotonic", lambda: fake_now[0])
    session = MagicMock(spec=requests.Session)
    session.get.return_value = MagicMock(text="1.1.1.1:8080")
    pool = ProxyPool(_settings(ttl_sec=10, safety_margin_sec=2), session)
    assert pool.acquire() == "1.1.1.1:8080"
    session.get.side_effect = requests.RequestException("boom")
    fake_now[0] = 6.0
    pool._renewing = True
    pool._renew_worker()
    assert pool._current == "1.1.1.1:8080"
    assert pool._take_live() == "1.1.1.1:8080"


def test_acquire_returns_old_ip_without_waiting_for_renewal(monkeypatch) -> None:
    # 续期在后台线程：业务线程拿旧 IP 立即返回，不陪回源等 0.2s
    real_monotonic = time.monotonic
    fake_now = [0.0]
    monkeypatch.setattr("em.core.proxy.time.monotonic", lambda: fake_now[0])
    calls: list[str] = []

    def slow_get(url, **_kw):
        calls.append(url)
        if len(calls) == 1:
            return MagicMock(text="1.1.1.1:8080")
        time.sleep(0.2)  # 续期回源慢
        return MagicMock(text="2.2.2.2:8080")

    session = MagicMock(spec=requests.Session)
    session.get.side_effect = slow_get
    pool = ProxyPool(_settings(ttl_sec=10, safety_margin_sec=2), session)
    assert pool.acquire() == "1.1.1.1:8080"

    fake_now[0] = 6.0
    t0 = real_monotonic()
    assert pool.acquire() == "1.1.1.1:8080"
    assert real_monotonic() - t0 < 0.1

    deadline = real_monotonic() + 3
    while pool._renewing and real_monotonic() < deadline:
        time.sleep(0.01)
    assert pool._current == "2.2.2.2:8080"


def test_renew_disabled_when_ttl_too_short(monkeypatch: pytest.MonkeyPatch) -> None:
    # TTL 5 / 余量 3 → 提前量算下来 <=0：不做后台续期，否则每次采纳即触发，变成连环回源
    fake_now = [0.0]
    monkeypatch.setattr("em.core.proxy.time.monotonic", lambda: fake_now[0])
    session = _session_sequence(["1.1.1.1:8080"])
    pool = ProxyPool(_settings(ttl_sec=5, safety_margin_sec=3), session)
    assert pool.acquire() == "1.1.1.1:8080"
    fake_now[0] = 4.0
    assert pool._renew_due() is False


def test_available_counts_only_live_ips(monkeypatch: pytest.MonkeyPatch) -> None:
    # 并发收敛依据：只数未到硬到期的 IP，过期/淘汰后立刻归零
    fake_now = [0.0]
    monkeypatch.setattr("em.core.proxy.time.monotonic", lambda: fake_now[0])
    session = _session_returning(["1.1.1.1:8080", "2.2.2.2:8080", "3.3.3.3:8080"])
    pool = ProxyPool(_settings(num=3, ttl_sec=10, safety_margin_sec=2), session)
    assert pool.available() == 0
    pool.acquire()
    assert pool.available() == 3
    fake_now[0] = 8.0  # 硬到期
    assert pool.available() == 0
    assert pool.hold("1.1.1.1:8080") is False


def _session_sequence(ips: list[str]) -> requests.Session:
    """代理 API 按序返回给定 IP，超出后重复最后一个。"""
    session = MagicMock(spec=requests.Session)
    responses = [MagicMock(text=ip) for ip in ips]
    session.get.side_effect = responses + [responses[-1]] * 10
    return session


def test_single_source_ignores_failover_window(monkeypatch: pytest.MonkeyPatch) -> None:
    # 单源配置：主源慢/空时不能进入"降级备用源"窗口——窗口内 urls 为空，
    # 整段时间一个 IP 都拿不到（真网复现过 second acquire None in 0.000s）
    fake_now = [0.0]
    monkeypatch.setattr("em.core.proxy.time.monotonic", lambda: fake_now[0])
    urls: list[str] = []

    def get(url, **_kw):
        urls.append(url)
        fake_now[0] += 4.0  # 超过 _PRIMARY_SLOW_SEC，会触发降级窗口
        return MagicMock(text="1.1.1.1:8080" if len(urls) == 1 else "2.2.2.2:8080")

    session = MagicMock(spec=requests.Session)
    session.get.side_effect = get
    pool = ProxyPool(_settings(ttl_sec=10, safety_margin_sec=2), session)
    assert pool.acquire() == "1.1.1.1:8080"
    fake_now[0] += 9.0  # 旧 IP 硬到期（10 - 2）
    assert pool.acquire() == "2.2.2.2:8080"  # 即便过慢也不能被窗口挡成 None
    assert len(urls) == 2


def test_failure_does_not_clear_other_in_flight_counts() -> None:
    # 同一 IP 被多个 worker 持有时，一个失败只该减自己那一份（由 finally 的 release
    # 归还）；若在 report_failure 里整条清空，该 IP 复采后会被当空闲，新请求全压上去
    session = _session_returning(["1.1.1.1:8080"])
    pool = ProxyPool(_settings(), session)
    first = pool.acquire()
    second = pool.acquire()
    assert first == second == "1.1.1.1:8080"
    assert pool._in_flight["1.1.1.1:8080"] == 2
    pool.report_failure("1.1.1.1:8080")
    assert pool._in_flight["1.1.1.1:8080"] == 2  # 另一个仍在飞，计数不能丢
    pool.release("1.1.1.1:8080")
    assert pool._in_flight["1.1.1.1:8080"] == 1
    pool.release("1.1.1.1:8080")
    assert pool._in_flight == {}


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
    assert "1.1.1.1:8080" in pool._failed_at
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
    # 预筛判死的 IP 进入黑名单：后续回源命中同一 IP 时直接跳过（不再重复预筛）；
    # 连续两批都拿不到新 IP 即熔断，不再无限回源
    session = _session_sequence(["1.1.1.1:8080", "1.1.1.1:8080", "2.2.2.2:8080"])
    pool = ProxyPool(_settings(num=1), session, prober=lambda ip: ip != "1.1.1.1:8080")
    assert pool.acquire() is None
    assert session.get.call_count == 2  # 第二批已在黑名单，不再探测/不再买第三批
    assert pool.stats()["prefilter_rejected"] == 1
    assert pool.stats()["source_breaker_trips"] == 1


def test_prefilter_and_refill_time_accumulated() -> None:
    # 代理段耗时计算：回源与预筛的墙钟耗时分别累计，供端到端归因
    session = _session_sequence(["1.1.1.1:8080"])
    pool = ProxyPool(_settings(num=1), session, prober=lambda _ip: time.sleep(0.02) or True)
    assert pool.acquire() == "1.1.1.1:8080"
    stats = pool.stats()
    assert stats["refill_sec"] > 0.0
    assert stats["prefilter_sec"] >= 0.02


# --- 多源冗余（主源免费/备用收费） ---


def _multi_source_pool(session: requests.Session, ttl_sec: int = 60) -> tuple[ProxyPool, str, str]:
    primary, backup = "http://p/get", "http://b/get"
    settings = ProxySettings(api=f"{primary},{backup}", num=1, ttl_sec=ttl_sec)
    return ProxyPool(settings, session), primary, backup


def _urls(session: MagicMock) -> list[str]:
    return [c.args[0] for c in session.get.call_args_list]


def test_multi_source_fallback_on_empty_primary() -> None:
    # 主源空返回（限频文案）→ 同一次 refill 立即试备用源，并设置降级窗口
    session = MagicMock(spec=requests.Session)
    session.get.side_effect = [
        MagicMock(text="IP资源不足"),
        MagicMock(text="5.5.5.5:8080"),
    ]
    pool, primary, backup = _multi_source_pool(session)
    assert pool.acquire() == "5.5.5.5:8080"
    assert _urls(session) == [primary, backup]


def test_multi_source_failover_window_skips_primary(monkeypatch: pytest.MonkeyPatch) -> None:
    # 降级窗口内 refill 直接用备用源，不再先撞一次慢/挂的主源
    fake_now = [0.0]
    monkeypatch.setattr("em.core.proxy.time.monotonic", lambda: fake_now[0])
    session = MagicMock(spec=requests.Session)
    session.get.side_effect = [
        MagicMock(text="fail"),
        MagicMock(text="5.5.5.5:8080"),
        MagicMock(text="6.6.6.6:8080"),
    ]
    pool, primary, backup = _multi_source_pool(session)
    assert pool.acquire() == "5.5.5.5:8080"
    pool.report_failure("5.5.5.5:8080")
    assert pool.acquire() == "6.6.6.6:8080"  # 窗口内：跳过主源
    assert _urls(session) == [primary, backup, backup]


def test_multi_source_failover_recovers_after_window(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_now = [0.0]
    monkeypatch.setattr("em.core.proxy.time.monotonic", lambda: fake_now[0])
    session = MagicMock(spec=requests.Session)
    session.get.side_effect = [
        MagicMock(text="fail"),
        MagicMock(text="5.5.5.5:8080"),
        MagicMock(text="6.6.6.6:8080"),
    ]
    pool, primary, backup = _multi_source_pool(session)
    assert pool.acquire() == "5.5.5.5:8080"
    pool.report_failure("5.5.5.5:8080")
    assert pool.acquire() == "6.6.6.6:8080"

    fake_now[0] = 61.0  # 窗口过期：恢复主源试探
    session.get.side_effect = [MagicMock(text="7.7.7.7:8080")]
    pool.report_failure("6.6.6.6:8080")
    assert pool.acquire() == "7.7.7.7:8080"
    assert _urls(session)[-1] == primary


def test_multi_source_fallback_on_slow_primary(monkeypatch: pytest.MonkeyPatch) -> None:
    # 主源回源超 3s（疑似限流降速，上次实测均 5.6s）→ 采纳 IP 同时设降级窗口
    fake_now = [0.0]
    monkeypatch.setattr("em.core.proxy.time.monotonic", lambda: fake_now[0])
    primary, backup = "http://p/get", "http://b/get"
    session = MagicMock(spec=requests.Session)

    def slow_get(url, **_):
        if url == primary:
            fake_now[0] += 4.0
            return MagicMock(text="5.5.5.5:8080")
        fake_now[0] += 0.1
        return MagicMock(text="6.6.6.6:8080")

    session.get.side_effect = slow_get
    pool, _, _ = _multi_source_pool(session)
    assert pool.acquire() == "5.5.5.5:8080"  # 慢但有 IP：采纳并降级
    pool.report_failure("5.5.5.5:8080")
    assert pool.acquire() == "6.6.6.6:8080"  # 窗口内用备用
    assert _urls(session)[-1] == backup


def test_blacklist_exhausted_degrades_instead_of_hard_use() -> None:
    # 只有一个 IP 且已判死：不再硬用（硬用会形成"每请求 N 次 API"的循环），
    # 连败熔断后返回 None，由上层退化直连或等冷却结束再试
    session = _session_sequence(["1.1.1.1:8080"])
    pool = ProxyPool(_settings(), session)
    assert pool.acquire() == "1.1.1.1:8080"
    pool.report_failure("1.1.1.1:8080")
    assert pool.acquire() is None
    assert pool.stats()["source_breaker_trips"] == 1
    assert session.get.call_count == 3  # 两次空批后停止回源


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


# --- 采购账本（对应后台"消耗 IP 数"）---


def test_ledger_purchase_funnel() -> None:
    # 厂商按返回条数计费：交付量、去重、预筛淘汰、进池、服役、有产出必须逐段对得上，
    # 否则只能靠后台面板反推消耗（本用例锁住五段漏斗的口径）
    session = _session_returning(["1.1.1.1:8080", "2.2.2.2:8080", "3.3.3.3:8080"])
    pool = ProxyPool(_settings(num=3), session, prober=lambda ip: ip != "1.1.1.1:8080")
    proxy = pool.acquire()
    assert proxy == "2.2.2.2:8080"
    pool.report_success(proxy)
    stats = pool.stats()
    assert stats["fetch_calls"] == 1
    assert stats["ips_returned"] == 3  # 计费口径
    assert stats["ips_unique"] == 3
    assert stats["prefilter_rejected"] == 1
    assert stats["ips_adopted"] == 2
    assert stats["ips_served"] == 1
    assert stats["ips_productive"] == 1
    # 预筛范围要随快照暴露：报表靠它区分"淘汰率是测出来的"还是"根本没筛"
    assert len(stats["prefiltered"]) == 1
    assert str(stats["prefiltered"][0]).startswith("src0:")


def test_ledger_counts_truncated_and_duplicate_delivery() -> None:
    # 厂商返回超过 num 的行：交付量按全量记，进池按 num 截断——差额就是被丢弃的已付费 IP
    session = _session_returning(["1.1.1.1:8080", "1.1.1.1:8080", "2.2.2.2:8080", "3.3.3.3:8080"])
    pool = ProxyPool(_settings(num=2), session)
    assert pool.acquire() == "1.1.1.1:8080"
    stats = pool.stats()
    assert stats["ips_returned"] == 4  # 计费按交付行数
    assert stats["ips_unique"] == 3  # 重复返回同样计费，只有去重后才知道真实利用率
    assert stats["ips_adopted"] == 2  # 重复项不占 num 名额：进池的是两个不同 IP
    assert pool._current != pool._standby[0]


def test_source_stats_split_by_source() -> None:
    # 分源账本是"主备顺序该按谁在前"的唯一客观依据：主源空返回也要记一次 calls
    session = MagicMock(spec=requests.Session)
    session.get.side_effect = [MagicMock(text="IP资源不足"), MagicMock(text="5.5.5.5:8080")]
    pool, _, _ = _multi_source_pool(session)
    assert pool.acquire() == "5.5.5.5:8080"
    stats = pool.stats()["source_stats"]
    assert [v["calls"] for v in stats.values()] == [1, 1]
    assert [v["returned"] for v in stats.values()] == [0, 1]
    assert [v["adopted"] for v in stats.values()] == [0, 1]


# --- 失败分级：硬失败立即淘汰，软失败（读超时）两次才淘汰 ---


def test_soft_failure_keeps_ip_until_second_strike() -> None:
    session = _session_returning(["1.1.1.1:8080"])
    pool = ProxyPool(_settings(), session)
    assert pool.acquire() == "1.1.1.1:8080"
    pool.report_failure("1.1.1.1:8080", hard=False)  # 读超时：先记一笔
    assert pool.stats()["soft_failures"] == 1
    assert pool.stats()["ip_failures"] == 0
    assert pool.acquire() == "1.1.1.1:8080"  # 仍可复用，未回源
    assert session.get.call_count == 1
    pool.report_failure("1.1.1.1:8080", hard=False)  # 连续第二次才淘汰
    assert pool.stats()["ip_failures"] == 1
    assert "1.1.1.1:8080" in pool._failed_at


def test_hard_failure_evicts_immediately() -> None:
    session = _session_sequence(["1.1.1.1:8080", "2.2.2.2:8080"])
    pool = ProxyPool(_settings(), session)
    assert pool.acquire() == "1.1.1.1:8080"
    pool.report_failure("1.1.1.1:8080")  # 连接失败：默认硬失败
    assert pool.stats()["ip_failures"] == 1
    assert pool.stats()["soft_failures"] == 0
    assert pool.acquire() == "2.2.2.2:8080"


def test_success_clears_soft_strikes() -> None:
    # 抖动恢复后计数必须清零，否则两次不连续的超时会累积成淘汰
    session = _session_returning(["1.1.1.1:8080"])
    pool = ProxyPool(_settings(), session)
    proxy = pool.acquire()
    pool.report_failure(proxy, hard=False)
    pool.report_success(proxy)
    pool.report_failure(proxy, hard=False)
    assert pool.stats()["ip_failures"] == 0
    assert pool.stats()["ips_productive"] == 1


def test_hold_reuses_ip_and_keeps_in_flight_paired() -> None:
    # 同 IP 重试：hold 加一次在飞占用，release 必须能一一配对，不出现负计数
    session = _session_returning(["1.1.1.1:8080"])
    pool = ProxyPool(_settings(), session)
    proxy = pool.acquire()
    assert pool.hold(proxy) is True
    assert pool._in_flight[proxy] == 2
    pool.release(proxy)
    pool.release(proxy)
    assert pool._in_flight == {}
    pool.report_failure(proxy)  # 淘汰后不可续用
    assert pool.hold(proxy) is False

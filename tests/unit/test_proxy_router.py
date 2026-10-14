"""ProxyRouter 状态机行为锁：auto 模式直连↔代理↔探测、always/never、per-host 独立。"""

from unittest.mock import MagicMock

from em.core.proxy import ProxyRouter, ProxySettings


def _settings(
    mode: str = "auto",
    enabled: bool = True,
    direct_fails: int = 3,
    proxy_successes: int = 5,
    cooldown_sec: int = 300,
) -> ProxySettings:
    return ProxySettings(
        api="http://x",
        enabled=enabled,
        mode=mode,  # type: ignore[arg-type]
        direct_fails=direct_fails,
        proxy_successes=proxy_successes,
        cooldown_sec=cooldown_sec,
    )


def _mock_pool(acquire_returns: str | None = "1.1.1.1:8080"):
    pool = MagicMock()
    pool.enabled = True
    pool.acquire.return_value = acquire_returns
    return pool


# --- never / always ---


def test_mode_never_always_direct():
    router = ProxyRouter(_mock_pool(), _settings(mode="never"))
    assert router.acquire("push2.eastmoney.com") is None
    router.report_result("push2.eastmoney.com", None, success=False, banned=True)
    # never 模式不改变任何状态
    assert router.host_state("push2.eastmoney.com") is None


def test_mode_always_uses_pool():
    pool = _mock_pool("2.2.2.2:8080")
    router = ProxyRouter(pool, _settings(mode="always"))
    assert router.acquire("push2.eastmoney.com") == "2.2.2.2:8080"
    assert pool.acquire.call_count == 1


def test_mode_always_reports_failure_to_pool():
    pool = _mock_pool("2.2.2.2:8080")
    router = ProxyRouter(pool, _settings(mode="always"))
    router.report_result("h", "2.2.2.2:8080", success=False)
    pool.report_failure.assert_called_once_with("2.2.2.2:8080")


def test_enabled_false_forces_never():
    pool = _mock_pool("2.2.2.2:8080")
    router = ProxyRouter(pool, _settings(enabled=False, mode="always"))
    assert router.acquire("h") is None


# --- auto: 直连 → 代理 ---


def test_auto_starts_direct():
    router = ProxyRouter(_mock_pool(), _settings())
    assert router.acquire("h") is None
    assert router.host_state("h").mode == "direct"


def test_auto_direct_fails_threshold_switches_to_proxy():
    pool = _mock_pool("9.9.9.9:8080")
    router = ProxyRouter(pool, _settings(direct_fails=3))
    for _ in range(2):
        router.report_result("h", None, success=False)
    assert router.host_state("h").mode == "direct"  # 还没到阈值
    router.report_result("h", None, success=False)
    assert router.host_state("h").mode == "proxy"
    assert router.acquire("h") == "9.9.9.9:8080"


def test_auto_banned_immediately_switches():
    pool = _mock_pool("9.9.9.9:8080")
    router = ProxyRouter(pool, _settings(direct_fails=3))
    router.report_result("h", None, success=False, banned=True)
    assert router.host_state("h").mode == "proxy"


def test_auto_direct_success_resets_fails():
    pool = _mock_pool()
    router = ProxyRouter(pool, _settings(direct_fails=3))
    router.report_result("h", None, success=False)
    router.report_result("h", None, success=False)
    router.report_result("h", None, success=True)  # 成功重置
    router.report_result("h", None, success=False)
    assert router.host_state("h").mode == "direct"  # 只累计 1 次，未到 3


# --- auto: 代理 → 探测 → 直连 ---


def test_auto_proxy_success_then_probe_after_cooldown(monkeypatch):
    fake_now = [0.0]
    monkeypatch.setattr("em.core.proxy.time.monotonic", lambda: fake_now[0])
    pool = _mock_pool("9.9.9.9:8080")
    router = ProxyRouter(pool, _settings(proxy_successes=2, cooldown_sec=10))
    # 先切到代理
    router.report_result("h", None, success=False, banned=True)
    assert router.host_state("h").mode == "proxy"
    # 代理成功 2 次但冷却未过
    fake_now[0] = 5.0
    router.report_result("h", "9.9.9.9:8080", success=True)
    router.report_result("h", "9.9.9.9:8080", success=True)
    assert router.host_state("h").mode == "proxy"  # 冷却未过
    # 冷却过后再成功一次触发探测
    fake_now[0] = 20.0
    router.report_result("h", "9.9.9.9:8080", success=True)
    assert router.host_state("h").mode == "probe"
    assert router.acquire("h") is None  # 探测走直连


def test_auto_probe_success_returns_to_direct():
    pool = _mock_pool()
    router = ProxyRouter(pool, _settings())
    router.report_result("h", None, success=False, banned=True)
    assert router.host_state("h").mode == "proxy"
    # 强行切到 probe
    router.host_state("h").mode = "probe"
    router.report_result("h", None, success=True)
    assert router.host_state("h").mode == "direct"


def test_auto_probe_only_one_direct_request_in_flight():
    # probe 态：首个请求放行直连探测，其余并发请求继续走代理，不做并发探测
    from em.core.proxy import HostState

    pool = _mock_pool("9.9.9.9:8080")
    router = ProxyRouter(pool, _settings())
    router._hosts["h"] = HostState("h", mode="probe")
    assert router.acquire("h") is None  # 唯一探测请求走直连
    assert router.acquire("h") == "9.9.9.9:8080"  # 探测在途，其余走代理
    assert router.acquire("h") == "9.9.9.9:8080"
    # 探测成功回归直连，单飞标志复位
    router.report_result("h", None, success=True)
    assert router.host_state("h").mode == "direct"
    assert router.host_state("h").probe_in_flight is False


def test_auto_probe_failure_back_to_proxy():
    pool = _mock_pool()
    router = ProxyRouter(pool, _settings())
    router.report_result("h", None, success=False, banned=True)
    router.host_state("h").mode = "probe"
    router.report_result("h", None, success=False)
    assert router.host_state("h").mode == "proxy"


def test_auto_probe_proxy_result_does_not_masquerade(monkeypatch):
    # probe 态下在途代理请求成功不得冒充探测结果把 host 切回直连，
    # 是否回直连只由直连探测请求的结果决定
    fake_now = [0.0]
    monkeypatch.setattr("em.core.proxy.time.monotonic", lambda: fake_now[0])
    pool = _mock_pool("9.9.9.9:8080")
    router = ProxyRouter(pool, _settings(proxy_successes=1, cooldown_sec=10))
    router.report_result("h", None, success=False, banned=True)
    fake_now[0] = 20.0
    router.report_result("h", "9.9.9.9:8080", success=True)  # 触发进入 probe
    assert router.host_state("h").mode == "probe"
    router.acquire("h")  # 放行唯一直连探测，probe_in_flight=True
    router.report_result("h", "9.9.9.9:8080", success=True)  # 在途代理请求归来
    assert router.host_state("h").mode == "probe"  # 不被代理结果带偏
    assert router.host_state("h").probe_in_flight is True
    router.report_result("h", None, success=True)  # 真正的探测结果归来
    assert router.host_state("h").mode == "direct"


def test_report_proxy_failure_only_evicts_ip():
    # 仅淘汰 IP，不改路由状态机（应用层发现坏 IP 场景）
    pool = _mock_pool()
    router = ProxyRouter(pool, _settings())
    router.report_proxy_failure("1.1.1.1:8080")
    pool.report_failure.assert_called_once_with("1.1.1.1:8080")
    assert router.host_state("h") is None  # 状态机未动
    router.report_proxy_failure(None)  # 直连时无事发生
    assert pool.report_failure.call_count == 1


def test_release_forwards_to_pool():
    pool = _mock_pool()
    router = ProxyRouter(pool, _settings())
    router.release("1.1.1.1:8080")
    pool.release.assert_called_once_with("1.1.1.1:8080")
    router.release(None)  # 直连无代理可还
    assert pool.release.call_count == 1


def test_auto_proxy_failure_reports_to_pool_and_resets_successes():
    pool = _mock_pool()
    router = ProxyRouter(pool, _settings(proxy_successes=2))
    router.report_result("h", None, success=False, banned=True)
    state = router.host_state("h")
    # 代理成功 1 次
    router.report_result("h", "1.1.1.1:8080", success=True)
    assert state.proxy_successes == 1
    # 代理失败：重置 + 通知 pool
    router.report_result("h", "1.1.1.1:8080", success=False)
    assert state.proxy_successes == 0
    pool.report_failure.assert_called_once_with("1.1.1.1:8080")


# --- per-host 独立 ---


def test_per_host_independent():
    pool = _mock_pool("9.9.9.9:8080")
    router = ProxyRouter(pool, _settings(direct_fails=1))
    # host A 被封切代理
    router.report_result("a.host", None, success=False, banned=True)
    assert router.host_state("a.host").mode == "proxy"
    # host B 仍直连
    assert router.acquire("b.host") is None
    assert router.host_state("b.host").mode == "direct"
    assert router.acquire("a.host") == "9.9.9.9:8080"

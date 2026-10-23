"""全量拉取页级兜底的行为锁：传输全失败时兜底重试之间有短退避，末次失败不再退避。"""

from unittest.mock import MagicMock

import pytest
import requests

from em.application.market_data import (
    _CLIST_PAGE_SIZE_MAX,
    _CLIST_SNAPSHOT_SORT,
    _PAGE_RETRY_BACKOFF_SEC,
    _build_client,
    _ledger_line,
    _make_prober,
    _reset_client_cache,
    stock_list_all_em,
)
from em.core.errors import NetworkError, PageDeadlineExceeded
from em.core.proxy import ProxyPool, ProxyRouter, ProxySettings
from em.core.resilience import RetryPolicy
from em.core.settings import Settings
from em.core.transport import HttpClient


def test_page_retry_backoff_between_attempts(monkeypatch):
    # 首页 3 次兜底尝试全失败：退避 2 次（末次失败直接返回，不多等 0.5s），最终抛最后异常
    session = MagicMock(spec=requests.Session)
    session.get.side_effect = requests.ConnectionError("boom")
    ps = ProxySettings(api="http://x", num=1, ttl_sec=30, mode="always")
    router = ProxyRouter(ProxyPool(ps, session), ps)
    client = HttpClient(
        session, router, RetryPolicy(max_retries=0, backoff_sec=0.0), timeout_sec=2
    )
    monkeypatch.setattr("em.application.market_data._build_client", lambda s: client)
    slept: list[float] = []
    monkeypatch.setattr("em.application.market_data.time.sleep", slept.append)

    with pytest.raises(NetworkError):
        stock_list_all_em(max_rounds=1)

    assert slept == [_PAGE_RETRY_BACKOFF_SEC] * 2


# --- 单页预算：超预算的页交给补漏，不把整轮钉住 ---


def test_page_deadline_stops_retrying(monkeypatch) -> None:
    import em.application.market_data as md

    fake_now = [0.0]
    monkeypatch.setattr(md, "_PAGE_DEADLINE_SEC", 5.0)
    monkeypatch.setattr(md.time, "monotonic", lambda: fake_now[0])
    monkeypatch.setattr(md.time, "sleep", lambda _s: None)  # 页级退避不真睡
    pages: list[int] = []

    class _FakeSource:
        name = "eastmoney"

        def __init__(self, client) -> None:
            pass

        def fetch_page(self, request, flow_field: str = "f62"):
            pages.append(request.page)
            fake_now[0] += 6.0  # 每次取数耗 6s（模拟连续换 IP 重试）
            raise NetworkError("boom")

    class _FakeClient:
        def timing_stats(self) -> dict[str, float]:
            return {}

        def proxy_stats(self) -> dict[str, object]:
            return {}

        def available_proxies(self, url: str) -> int:
            return 0

        def evict_last_proxy(self, url: str) -> None:
            raise AssertionError("本用例不应触发淘汰")

    monkeypatch.setattr(md, "_build_client", lambda s: _FakeClient())
    monkeypatch.setattr(md.registry, "EastMoneySource", _FakeSource)

    with pytest.raises(PageDeadlineExceeded):
        stock_list_all_em()

    # 首页预算 = 2 x 5s：t=0 首试、t=6 第二试、t=12 已超 10s → 第三次不再发
    assert len(pages) == 2


# --- 预筛预热复用：探测必须走业务 Session ---


def test_prober_uses_business_session() -> None:
    # 探测与业务请求同 Session/同 host/同出口，业务请求可复用探测已建好的连接；
    # 单独开探测 Session 会把这次握手白付一遍（实测代理页均 0.87s 里握手占大头）
    session = MagicMock(spec=requests.Session)
    session.get.return_value = MagicMock(status_code=200, text='{"rc":0,"data":{}}')
    probe = _make_prober(session, 2.5)
    assert probe("1.1.1.1:8080") is True
    _, kwargs = session.get.call_args
    assert kwargs["proxies"] == {
        "http": "http://1.1.1.1:8080",
        "https": "http://1.1.1.1:8080",
    }
    assert session.get.call_count == 1


def test_prober_returns_false_on_request_error() -> None:
    session = MagicMock(spec=requests.Session)
    session.get.side_effect = requests.RequestException("boom")
    assert _make_prober(session, 2.5)("1.1.1.1:8080") is False


def test_probe_request_matches_business_page_shape() -> None:
    # 探测口径必须等于业务页：用 pz=1 的极小请求会放过"小请求能过、整页超时"的坏出口，
    # 也会漏掉 fs/fields/ut 的漂移；因此探测请求必须由业务构建器派生
    from em.application import registry as app_registry
    from em.domain.queries import MarketQuery

    session = MagicMock(spec=requests.Session)
    session.get.return_value = MagicMock(status_code=200, text='{"rc":0,"data":{}}')
    assert _make_prober(session, 2.5)("1.1.1.1:8080") is True

    args, kwargs = session.get.call_args
    business = app_registry.stock_list_request(
        MarketQuery(sort=_CLIST_SNAPSHOT_SORT, page=1, size=_CLIST_PAGE_SIZE_MAX)
    )
    assert args[0] == business.url()
    assert kwargs["params"] == business.params()
    assert kwargs["timeout"] == (1.0, 2.5)  # 读取需覆盖整页耗时，连接仍快速判死


def test_build_client_wires_prober_to_business_session() -> None:
    # 装配层必须把 prober 绑到 client 自己的 Session 上，否则预热复用静默失效
    _reset_client_cache()
    try:
        settings = Settings(proxy_api="http://x", proxy_prefilter=True)
        client = _build_client(settings)
        prober = client._router._pool._prober
        assert prober is not None
        client._session.get = MagicMock(return_value=MagicMock(status_code=200, text='"rc"'))
        assert prober("1.1.1.1:8080") is True
        client._session.get.assert_called_once()
    finally:
        _reset_client_cache()


# --- 采购账本日志行 ---


def test_ledger_line_reports_purchase_funnel() -> None:
    # 与后台"消耗 IP 数"对账的口径：采购 = 回源次数 × 每次交付，而不是进池数
    pool = {
        "fetch_calls": 3,
        "ips_returned": 15,
        "ips_unique": 14,
        "prefilter_rejected": 9,
        "ips_adopted": 6,
        "ips_served": 6,
        "ips_productive": 5,
        "soft_failures": 2,
    }
    line = _ledger_line(pool, pages=56)
    assert "采购 15（3 次回源）" in line
    assert "去重 14" in line
    assert "预筛淘汰 9（60%）" in line
    assert "进池 6" in line
    assert "有产出 5" in line
    assert "单有效 IP 11.2 页" in line
    assert "软失败 2" in line


def test_ledger_line_handles_empty_pool() -> None:
    # 全程直连（代理未启用）时不能除零，账本行仍要可读
    line = _ledger_line({}, pages=0)
    assert "采购 0" in line
    assert "单有效 IP 0.0 页" in line


def test_page_retry_backoff_exceeds_empty_refill_cooldown() -> None:
    # 页级重试必须落在代理池的"空返回负缓存"之后，否则重试时池子必然还是空的，
    # 白白烧掉一次页级尝试（两个常量分属两层，这里锁住它们的相对关系）
    from em.core.proxy import _EMPTY_REFILL_COOLDOWN_SEC

    assert _PAGE_RETRY_BACKOFF_SEC > _EMPTY_REFILL_COOLDOWN_SEC


def test_effective_workers_caps_by_live_proxies() -> None:
    # 每个出口 2 个并发预算：不按 1:1 收敛（实测 1:1 只会砍半吞吐、降不下失败率）
    from em.application.market_data import _effective_workers

    assert _effective_workers(5, 0) == 5  # 直连态/池空：保持调用方并发
    assert _effective_workers(5, -1) == 5
    assert _effective_workers(5, 1) == 2  # 单出口：只放 2 个 worker
    assert _effective_workers(5, 2) == 4  # 2 出口：4 个 worker，不砍到 2
    assert _effective_workers(5, 3) == 5  # 预算已覆盖，不再收紧
    assert _effective_workers(5, 9) == 5
    assert _effective_workers(1, 3) == 1


def test_build_client_caps_probe_read_timeout(monkeypatch) -> None:
    # 探测读取预算取业务读超时（上限 3s）：探测比业务宽松会放行"必然超时"的出口
    import em.application.market_data as md

    captured: list[float] = []

    def _fake_make_prober(session, read_timeout):
        captured.append(read_timeout)
        return lambda ip: True

    monkeypatch.setattr(md, "_make_prober", _fake_make_prober)
    _reset_client_cache()
    try:
        _build_client(Settings(proxy_api="http://x", proxy_prefilter=True, request_timeout_sec=10))
        _build_client(Settings(proxy_api="http://x", proxy_prefilter=True, request_timeout_sec=2))
    finally:
        _reset_client_cache()
    # 每次装配造两个探测：正常（≤3s，跟随业务读超时）+ 降级快筛（≤1.5s）
    assert captured == [3.0, 1.5, 2.0, 1.5]


def test_ledger_line_uses_page_count_not_record_count(monkeypatch, caplog) -> None:
    # "单有效 IP 页数"的分子必须是页数：误传记录数会把 5 条/页放大成 5 页，
    # 指标虚高 5 倍，等于账本失效
    from em.domain.models import Quote, QuotePage

    class _FakeSource:
        name = "eastmoney"

        def __init__(self, client) -> None:
            pass

        def fetch_page(self, request, flow_field: str = "f62") -> QuotePage:
            return QuotePage(
                total=5,
                items=tuple(Quote(code=f"00000{i}", name="x") for i in range(5)),
            )

    class _FakeClient:
        def timing_stats(self) -> dict[str, float]:
            return {
                "direct_requests": 0,
                "direct_sec": 0.0,
                "proxy_requests": 1,
                "proxy_sec": 0.1,
                "proxy_wait_sec": 0.0,
                "backoff_sec": 0.0,
                "failed_attempts": 0,
            }

        def proxy_stats(self) -> dict[str, object]:
            return {
                "fetch_calls": 1,
                "ips_returned": 5,
                "prefilter_rejected": 4,
                "ips_adopted": 1,
                "ips_served": 1,
                "ips_productive": 1,
                "soft_failures": 0,
                "refill_sec": 0.1,
                "prefilter_sec": 0.2,
                "source_stats": {},
            }

        def evict_last_proxy(self, url: str) -> None:
            raise AssertionError("本用例不应触发淘汰")

        def available_proxies(self, url: str) -> int:
            return 0  # 直连态：不收敛并发

    monkeypatch.setattr("em.application.market_data._build_client", lambda s: _FakeClient())
    monkeypatch.setattr("em.application.market_data.registry.EastMoneySource", _FakeSource)
    caplog.set_level("INFO", logger="em.application.market_data")

    page = stock_list_all_em()
    assert len(page.items) == 5
    assert any("单有效 IP 1.0 页" in r.message for r in caplog.records)

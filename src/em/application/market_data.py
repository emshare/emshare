"""应用层服务：装配传输/代理/来源，暴露面向用户的 ``*_em`` 公共面（``df_*_em`` 为 DataFrame 版）。"""

from __future__ import annotations

import atexit
import functools
import logging
import threading
import time
import weakref
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING, Any

import requests

from em.application import hints, registry
from em.application.dataframe import (
    to_balance_sheet_dataframe,
    to_billboard_branch_active_dataframe,
    to_billboard_branch_rank_dataframe,
    to_billboard_branch_stats_dataframe,
    to_billboard_branch_trades_dataframe,
    to_billboard_detail_dataframe,
    to_billboard_institution_dataframe,
    to_billboard_institution_stats_dataframe,
    to_billboard_stock_dataframe,
    to_billboard_stock_dates_dataframe,
    to_billboard_stock_stats_dataframe,
    to_block_trade_branch_active_dataframe,
    to_block_trade_branch_rank_dataframe,
    to_block_trade_detail_dataframe,
    to_block_trade_market_daily_dataframe,
    to_block_trade_stock_daily_dataframe,
    to_block_trade_stock_stats_dataframe,
    to_board_changes_dataframe,
    to_board_fund_flow_dataframe,
    to_board_list_dataframe,
    to_cash_flow_statement_dataframe,
    to_dataframe,
    to_earnings_express_dataframe,
    to_earnings_forecast_dataframe,
    to_earnings_report_dataframe,
    to_earnings_schedule_dataframe,
    to_fund_flow_dataframe,
    to_fund_list_dataframe,
    to_hk_stock_list_dataframe,
    to_income_statement_dataframe,
    to_index_list_dataframe,
    to_kline_dataframe,
    to_limit_pool_dataframe,
    to_stock_bid_ask_dataframe,
    to_stock_changes_dataframe,
    to_stock_info_dataframe,
    to_trend_dataframe,
)
from em.application.ledger import record as record_ledger
from em.application.pagination import PageRetryGuard
from em.application.reports import fetch_report
from em.channels.eastmoney import config as em_config
from em.channels.eastmoney.network import disconnect_may_be_limited
from em.core import budget as budget_module
from em.core.errors import (
    EgressRetryStopped,
    PageDeadlineExceeded,
)
from em.core.fixed_proxy import FixedProxyRouter
from em.core.proxy import ProxyPool, ProxyRouter, ProxySettings, proxy_url
from em.core.resilience import RetryPolicy
from em.core.session import BoundedProxyAdapter, ExplicitProxySession, network_failure_phase
from em.core.settings import Settings
from em.core.transport import HttpClient
from em.domain.models import (
    BalanceSheet,
    BillboardBranchActive,
    BillboardBranchRank,
    BillboardBranchStats,
    BillboardBranchTrade,
    BillboardEntry,
    BillboardInstitutionStats,
    BillboardInstitutionTrade,
    BillboardSeat,
    BillboardStockDate,
    BillboardStockStats,
    BlockTrade,
    BlockTradeBranchActive,
    BlockTradeBranchRank,
    BlockTradeMarketDaily,
    BlockTradeStockDaily,
    BlockTradeStockStats,
    BoardChangesPage,
    BoardFundFlowSeries,
    BoardListPage,
    CashFlowStatement,
    EarningsExpress,
    EarningsForecast,
    EarningsReport,
    EarningsSchedule,
    FundFlowSeries,
    FundListPage,
    HkStockListPage,
    IncomeStatement,
    IndexListPage,
    KlineSeries,
    LimitPoolPage,
    Quote,
    QuotePage,
    ReportPage,
    StockBidAsk,
    StockChangesPage,
    StockInfo,
    TrendSeries,
)
from em.domain.queries import (
    BalanceSheetQuery,
    BillboardBranchActiveQuery,
    BillboardBranchRankQuery,
    BillboardBranchStatsQuery,
    BillboardBranchTradesQuery,
    BillboardDetailQuery,
    BillboardInstitutionQuery,
    BillboardInstitutionStatsQuery,
    BillboardStockDatesQuery,
    BillboardStockQuery,
    BillboardStockStatsQuery,
    BlockTradeBranchActiveQuery,
    BlockTradeBranchRankQuery,
    BlockTradeDetailQuery,
    BlockTradeMarketDailyQuery,
    BlockTradeStockDailyQuery,
    BlockTradeStockStatsQuery,
    BoardChangesQuery,
    BoardFundFlowQuery,
    BoardKlineQuery,
    BoardListQuery,
    BoardQuery,
    CashFlowStatementQuery,
    EarningsExpressQuery,
    EarningsForecastQuery,
    EarningsReportQuery,
    EarningsScheduleQuery,
    FundFlowQuery,
    FundListQuery,
    HkStockListQuery,
    IncomeStatementQuery,
    IndexListQuery,
    KlineQuery,
    LimitPoolQuery,
    MarketQuery,
    StockBidAskQuery,
    StockChangesQuery,
    StockInfoQuery,
    TrendQuery,
)

if TYPE_CHECKING:
    import pandas as pd

log = logging.getLogger(__name__)

# 东财游客 clist 单页条数硬上限（pz 超出 100 会被静默截断为 100，不会返回报错）
_CLIST_PAGE_SIZE_MAX = 100
# 全量快照固定按代码排序：f3 等行情字段盘中实时跳动，并发翻页时窗口漂移会导致
# 跨页大面积重复（实测 56 页放大到 346 次请求）；代码序几乎不变，1:1 无重复。
_CLIST_SNAPSHOT_SORT = "f12"
# 全量翻页默认并发度（有界并发，过高易触发代理源限频与东财封禁）
_DEFAULT_FETCH_WORKERS = 5
# 每个可用出口允许的并发数：实测 2 个出口跑 5 并发与跑 2 并发失败率相当（10 vs 12 次），
# 但并发砍半会让墙钟翻倍；按每出口 2 个预算收敛，只有单出口时才真正收紧
_WORKERS_PER_PROXY = 2
# 页级兜底重试的短退避：整批 IP 全死/代理源限流后立即重发大概率撞同一批。
# 必须长于代理池的空返回负缓存（_EMPTY_REFILL_COOLDOWN_SEC=1s）：否则重试正好落在
# 负缓存窗口内，池子必然还是空的，白白烧掉一次页级尝试
_PAGE_RETRY_BACKOFF_SEC = 1.1
# 单页时间预算：正常页 0.3~1.5s，含 2~3 次换 IP 重试约 5s；
# 15s 是"确实不对劲"的界线（5 次重试各 1.5s 连接超时 ≈ 8.5s，再留余量）。
# 超预算的页标记失败交给定向补漏，而不是让它把整轮钉住（最坏曾达 ~42s/页）
_PAGE_DEADLINE_SEC = 15.0
# 回源预筛探测请求与业务请求同源：复用业务的请求构建器与页大小（pz=100）。
# 旧实现用 pz=1 的极小请求，会出现"探测 1.4s 通过、真页 pz=100 超时"的口径漂移——
# 探测成本花在错的判据上；同一构建器还保证 host/fs/fields/ut 不会各自漂移。
_PROXY_PROBE_QUERY = MarketQuery(sort=_CLIST_SNAPSHOT_SORT, page=1, size=_CLIST_PAGE_SIZE_MAX)
# (连接, 读取)：死 IP 仍卡连接，1.0s 快速判死；读取取业务读超时（上限 3s），
# 保证"探测放行的 IP，业务也能在同样预算内完成"——探测比业务宽松会放过必然超时的出口
_PROXY_PROBE_CONNECT_TIMEOUT_SEC = 1.0
_PROXY_PROBE_MAX_SEC = 3.0
# 降级快筛的读预算：实测整页均值 0.79~1.25s，1.5s 仍能卡住"连上但不响应"的 hang，
# 又给正常慢页留了余量；整批全死后用它继续过滤，而不是把未验证 IP 直接放给业务
_PROXY_PROBE_LENIENT_SEC = 1.5


def _make_prober(session: ExplicitProxySession, read_timeout: float) -> Callable[[str], bool]:
    """构造回源预筛回调：用业务 Session 探测，把已建立的连接预热给业务请求。

    ``requests`` 的 ``HTTPAdapter`` 按 (代理, 目标 host) 缓存连接池，探测与业务请求
    同 Session、同 host、同出口时，业务请求可直接复用探测已完成的 TCP/TLS 握手——
    实测代理页均 0.87s 里握手占大头，省掉一次就是每个 IP 一次的净收益。
    单独开一个探测 Session 会把这笔握手白付一遍，故此处不这么写。
    """

    # 探测请求由业务构建器派生一次：口径与真实分页请求完全一致，不会随渠道参数漂移
    request = registry.stock_list_request(_PROXY_PROBE_QUERY)
    url, params = request.url(), request.params()

    timeout = (_PROXY_PROBE_CONNECT_TIMEOUT_SEC, read_timeout)

    def probe(ip: str) -> bool:
        proxies = {"http": proxy_url(ip), "https": proxy_url(ip)}
        try:
            timeout_values = budget_module.timeouts(*timeout)
            resp = session.get(
                url,
                params=params,
                headers=em_config.HEADERS,
                proxies=proxies,
                timeout=timeout_values,
            )
        except requests.RequestException as exc:
            log.debug("预筛判死 stage=%s: %s", network_failure_phase(exc), type(exc).__name__)
            return False
        return resp.status_code == 200 and '"rc"' in resp.text

    return probe


def _create_client(settings: Settings, probe_all: bool = False) -> HttpClient:
    """``probe_all``：预筛整批全探，忽略 ``proxy_prefilter_target``。

    代理按"发出过请求的 IP"计费，顺序请求只需探到够用的活 IP；并发任务会把整批
    出口都用上，分波探测省不下计费、只会拖慢冷启动，因此整批并发探测。
    """
    session = ExplicitProxySession()
    # 代理 IP 是多 origin 的连接目标：放大连接池避免并发放大时反复建连
    adapter = BoundedProxyAdapter(pool_connections=20, pool_maxsize=20)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    router: ProxyRouter | FixedProxyRouter
    if settings.proxy_url:
        router = FixedProxyRouter(settings.fixed_proxy)
    else:
        ps = ProxySettings(
            api=settings.proxy_api,
            enabled=settings.proxy_enabled,
            num=settings.proxy_num,
            ttl_sec=settings.proxy_ttl_sec,
            safety_margin_sec=settings.proxy_safety_margin_sec,
            timeout_sec=settings.proxy_timeout_sec,
            mode=settings.proxy_mode,
            direct_fails=settings.proxy_direct_fails,
            proxy_successes=settings.proxy_proxy_successes,
            cooldown_sec=settings.proxy_cooldown_sec,
            prefilter_sources=settings.proxy_prefilter_sources,
            degraded_mode=settings.proxy_degraded_mode,
        )
        probe_read = min(float(settings.request_timeout_sec), _PROXY_PROBE_MAX_SEC)
        prober = _make_prober(session, probe_read) if settings.proxy_prefilter else None
        # 降级快筛只在 lenient 模式下由池子选用；adopt 模式仍走"暂停预筛"的老行为
        fallback = (
            _make_prober(session, min(probe_read, _PROXY_PROBE_LENIENT_SEC))
            if settings.proxy_prefilter
            else None
        )
        pool = ProxyPool(
            ps,
            session,
            prober=prober,
            fallback_prober=fallback,
            prefilter_target=(
                None
                if probe_all or settings.proxy_prefilter_target == 0
                else settings.proxy_prefilter_target
            ),
        )
        router = ProxyRouter(pool, ps)
    policy = RetryPolicy(
        max_retries=settings.max_retries,
        backoff_sec=settings.backoff_sec,
        backoff_cap_sec=settings.backoff_cap_sec,
        jitter_sec=settings.backoff_jitter_sec,
    )
    client = HttpClient(
        session,
        router,
        policy,
        timeout_sec=settings.request_timeout_sec,
        connect_timeout_sec=settings.request_connect_timeout_sec,
        dynamic_timeout=settings.request_dynamic_timeout,
        # 重试耗尽时：若是出口类失败且代理用不上，把"该配什么"挂到异常上，库调用也能看到
        exhausted_hint=lambda host, exc: hints.egress_hint(exc, settings, host),
        disconnect_may_be_limited=disconnect_may_be_limited,
    )
    with _client_lock:
        _clients.add(client)
    return client


_cached_client = functools.lru_cache(maxsize=8)(_create_client)
_client_lock = threading.RLock()
_clients: weakref.WeakSet[HttpClient] = weakref.WeakSet()


def _build_client(
    settings: Settings, *, isolated: bool = False, probe_all: bool = False
) -> HttpClient:
    with _client_lock:
        if isolated:
            return _create_client(settings, probe_all)
        return _cached_client(settings)


def _reset_client_cache() -> None:
    """清空 client 缓存（测试用）。"""
    with _client_lock:
        for client in list(_clients):
            client.close()
        _clients.clear()
        _cached_client.cache_clear()


atexit.register(_reset_client_cache)


def board_constituent_em(
    query: BoardQuery | None = None, settings: Settings | None = None
) -> QuotePage:
    """抓取板块成分股（含资金流），返回领域模型 ``QuotePage``。"""
    query = query or BoardQuery()
    client = _build_client(settings or Settings.from_env())
    source = registry.EastMoneySource(client)
    request = registry.board_constituent_request(query)
    return source.fetch_page(request, registry.flow_field(query))


def stock_list_em(query: MarketQuery | None = None, settings: Settings | None = None) -> QuotePage:
    """抓取沪深京 A 股列表（``query.scope`` 可限定市场 / 板块），返回领域模型 ``QuotePage``。"""
    query = query or MarketQuery()
    client = _build_client(settings or Settings.from_env())
    source = registry.EastMoneySource(client)
    return source.fetch_page(registry.stock_list_request(query))


def _suspicious_pages(page_codes: dict[int, set[str]], total_pages: int) -> set[int]:
    """根据各页最近码集合定位需补漏的页号。

    东财多后端节点的分页快照不一致表现为"替换型漂移"：某页 100 条中混入邻页的码，
    相邻页码集合出现交集（真码被挤出）。检测两种信号：
    1. 相邻页（pn, pn+1）码集合有重叠 → 两页都重抓；
    2. 非末页返回不足 100 条（短页）→ 该页重抓。
    纯集合运算，不依赖排序规则，也无需知道全集。
    """
    sus: set[int] = set()
    for pn in range(1, total_pages):
        a, b = page_codes.get(pn), page_codes.get(pn + 1)
        if a and b and (a & b):
            sus.update((pn, pn + 1))
    for pn, codes in page_codes.items():
        if pn < total_pages and len(codes) < _CLIST_PAGE_SIZE_MAX:
            sus.add(pn)
    return sus


def _effective_workers(workers: int, live_proxies: int) -> int:
    """并发度按可用出口数收敛：每个出口给 ``_WORKERS_PER_PROXY`` 个并发预算。

    不按 1:1 收敛：实测 2 个出口配 2 个 worker 与配 5 个 worker 失败率几乎一样
    （12 vs 10 次），但墙钟从 22s 涨到 51s——出口数少时的瓶颈是并发不足，不是 IP 被打死。
    ``live_proxies <= 0`` 表示拿不到代理（直连态或池空），保持调用方给定的并发。
    """
    if live_proxies <= 0:
        return workers
    return max(1, min(workers, live_proxies * _WORKERS_PER_PROXY))


def _ledger_line(pool: dict[str, Any], pages: int) -> str:
    """输出交付、预筛与业务利用率。"""
    calls = int(pool.get("fetch_calls", 0) or 0)
    returned = int(pool.get("ips_returned", 0) or 0)
    unique = int(pool.get("ips_unique", 0) or 0)
    rejected = int(pool.get("prefilter_rejected", 0) or 0)
    adopted = int(pool.get("ips_adopted", 0) or 0)
    served = int(pool.get("ips_served", 0) or 0)
    productive = int(pool.get("ips_productive", 0) or 0)
    soft = int(pool.get("soft_failures", 0) or 0)
    degraded = int(pool.get("degraded_adopted", 0) or 0)
    rejected_pct = 100.0 * rejected / returned if returned else 0.0
    pages_per_ip = pages / productive if productive else 0.0
    return (
        f"代理账本：提取 {returned}（{calls} 次回源）｜去重 {unique}｜"
        f"预筛淘汰 {rejected}（{rejected_pct:.0f}%）｜进池 {adopted}｜服役 {served}｜"
        f"有产出 {productive}｜单有效 IP {pages_per_ip:.1f} 页｜软失败 {soft}｜"
        f"降级放行 {degraded}"
    )


def stock_list_all_em(
    query: MarketQuery | None = None,
    settings: Settings | None = None,
    max_rounds: int = 5,
    workers: int = _DEFAULT_FETCH_WORKERS,
) -> QuotePage:
    """以独立客户端取全市场快照，任务完成后释放代理与连接资源。"""
    if workers < 1:
        raise ValueError("workers 必须 >= 1")
    started = time.monotonic()
    # 并发翻页会用上整批出口：预筛整批并发探测，不分波
    client = _build_client(settings or Settings.from_env(), isolated=True, probe_all=True)
    try:
        result = _stock_list_all(query, max_rounds, workers, client)
    finally:
        client.close()
    _record_snapshot(client, result, started)
    return result


def _stock_list_all(
    query: MarketQuery | None, max_rounds: int, workers: int, client: HttpClient
) -> QuotePage:
    """有界并发翻页拉取沪深京 A 股全市场快照（游客 clist 单页上限 100，约 56 页）。

    固定按代码（f12）稳定排序翻页——``query.sort`` 在此忽略：f3 等行情排序盘中实时
    漂移会使并发分页跨页重复（实测 6x 请求放大）；需要特定行情顺序请取完后在本地排序。
    ``query.scope`` 生效（默认 ``all`` 即全市场），每一页都按同一范围请求。
    先抓首页拿 ``total`` 推算总页数，再用 ``workers`` 个线程并发抓余下各页，按 ``code``
    去重。补漏为**定向重抓**：东财后端节点不一致表现为"邻页码集合重叠（替换型漂移）"，
    首轮即可定位问题页，只重抓可疑页（实测缺 3 码仅涉 3 页）；若可疑页清零仍缺码，
    再做至多一次全量兜底轮。单页超过 ``_PAGE_DEADLINE_SEC`` 即标记失败交给补漏，
    避免个别页把整轮钉住（最坏曾达 ~42s/页）。
    """
    if workers < 1:
        raise ValueError("workers 必须 >= 1")
    query = query or MarketQuery()
    source = registry.EastMoneySource(client)
    seen: dict[str, Quote] = {}
    page_codes: dict[int, set[str]] = {}  # 每页最近一次返回的码集合，用于邻页重叠定位
    lock = threading.Lock()
    total = 0
    retry_guard = PageRetryGuard()

    def fetch_one(
        page_no: int, total_pages: int, dup_retries: int, budget: float | None = None
    ) -> Exception | None:
        """抓单页并入 ``seen``/``page_codes``；返回 None 成功，否则最后一次异常。

        总尝试 = 3 次（传输失败/空页兜底）+ ``dup_retries`` 次（零新增旧快照换 IP）。
        ``budget`` 为单页时间预算，缺省用 ``_PAGE_DEADLINE_SEC``；首页传两倍——
        它是串行冷启动，要先等回源与预筛产出 IP，且失败会中断整个调用。
        """
        nonlocal total
        budget = _PAGE_DEADLINE_SEC if budget is None else budget
        request = registry.stock_list_request(
            MarketQuery(
                sort=_CLIST_SNAPSHOT_SORT,
                page=page_no,
                size=_CLIST_PAGE_SIZE_MAX,
                scope=query.scope,
            )
        )
        last_exc: Exception | None = None
        dup_used = 0
        attempts = 3 + dup_retries
        deadline = time.monotonic() + budget
        for attempt in range(attempts):
            # 首轮必须放行（冷启动页要拿 total）；此后超预算即止损，交给定向补漏
            if attempt and time.monotonic() > deadline:
                last_exc = PageDeadlineExceeded(f"第{page_no}页超过单页预算 {budget:.0f}s")
                log.info("第%d页超预算（>%.0fs），标记失败交给补漏", page_no, budget)
                break
            try:
                with retry_guard.attempt(), budget_module.request_budget(deadline):
                    page = source.fetch_page(request)
            except PageDeadlineExceeded as exc:
                return exc
            except EgressRetryStopped:
                raise
            except Exception as exc:  # 传输层已换 IP 重试 10 次，此处兜底整页重试
                last_exc = exc
                if attempt < attempts - 1:  # 还有后继尝试才退避，末次失败直接返回
                    time.sleep(_PAGE_RETRY_BACKOFF_SEC)
                continue
            is_last = page_no == total_pages
            with lock:
                has_new = any(q.code not in seen for q in page.items)
            if not page.items and (not is_last or total > (page_no - 1) * _CLIST_PAGE_SIZE_MAX):
                last_exc = ValueError(f"第{page_no}页空返回")
                continue
            # 非末页“满页零新增”= 代理节点旧快照：淘汰该出口 IP 强制下轮换新，
            # 否则大概率还从同一节点拿到同一份旧快照，重试只是空耗
            if not is_last and page_no not in page_codes and not has_new and dup_used < dup_retries:
                dup_used += 1
                client.evict_last_proxy(request.url())
                last_exc = ValueError(f"第{page_no}页返回重复快照")
                continue
            with lock:
                if page_no == 1 and 1 not in page_codes:
                    total = page.total
                elif page.total != total:
                    last_exc = ValueError(f"第{page_no}页 total={page.total} 与首页 {total} 不一致")
                    continue
                codes = set()
                for quote in page.items:
                    seen.setdefault(quote.code, quote)
                    codes.add(quote.code)
                page_codes[page_no] = codes  # 以最新快照覆盖，供下一轮定位
            return None
        return last_exc

    def run_targets(page_nos: list[int] | range, dup_retries: int) -> set[int]:
        """并发抓取指定页，返回失败页号集合。"""
        failed: set[int] = set()
        if not page_nos:
            return failed
        # 并发收敛按 host 判断：auto 模式下直连态不该被池里别的 host 的 IP 数压住
        list_url = registry.stock_list_request(MarketQuery(page=1, size=1)).url()
        size = min(_effective_workers(workers, client.available_proxies(list_url)), len(page_nos))
        if size < min(workers, len(page_nos)):
            log.info("并发按可用出口收敛：%d -> %d", workers, size)
        with ThreadPoolExecutor(max_workers=size) as pool:
            futures = {pool.submit(fetch_one, pn, total_pages, dup_retries): pn for pn in page_nos}
            for future in as_completed(futures):
                if future.result() is not None:
                    failed.add(futures[future])
        return failed

    def suspicious_pages(total_pages: int) -> set[int]:
        return _suspicious_pages(page_codes, total_pages)

    # 首轮：首页确定 total/总页数，其余并发全抓。首页给两倍预算：它串行冷启动、
    # 要先等回源+预筛产出 IP，失败还会中断整个调用
    err = fetch_one(1, 1, dup_retries=0, budget=_PAGE_DEADLINE_SEC * 2)
    if err is not None:
        raise err
    total_pages = -(-total // _CLIST_PAGE_SIZE_MAX)
    failed = run_targets(list(range(2, total_pages + 1)), dup_retries=2)

    safety_net_used = False
    force_full = False
    for round_no in range(1, max_rounds + 1):
        if len(seen) >= total and not failed:
            break
        before = len(seen)
        sus = suspicious_pages(total_pages)
        if force_full or (not sus and not failed and len(seen) < total):
            # 全量兜底安全网：无可疑页可定向但仍缺码（如整码消失型），整场重抓一次
            if safety_net_used:
                break
            safety_net_used = True
            force_full = False
            mode = "全量兜底"
            log.info("定向补漏无可疑页但仍缺 %d 码，执行全量兜底轮", total - len(seen))
            targets: list[int] | range = range(1, total_pages + 1)
        else:
            mode = "定向"
            targets = sorted(sus | failed)
        if not targets:
            break
        failed = run_targets(targets, dup_retries=1)
        added = len(seen) - before
        log.info(
            "补漏第%d轮：重抓 %d 页（%s），新增 %d，累计 %d/%d，失败页 %d",
            round_no,
            len(targets),
            mode,
            added,
            len(seen),
            total,
            len(failed),
        )
        # 定向轮零新增且无失败：重抓同批不会有结果，下轮直接全量兜底或收敛
        force_full = mode == "定向" and added == 0 and not failed and len(seen) < total

    if len(seen) < total:
        log.warning("全量拉取不完整：唯一 %d < total %d（代理资源不足）", len(seen), total)
    return QuotePage(total=total, items=tuple(sorted(seen.values(), key=lambda quote: quote.code)))


def _record_snapshot(client: HttpClient, result: QuotePage, started: float) -> None:
    total_pages = -(-result.total // _CLIST_PAGE_SIZE_MAX)
    # 端到端耗时分解：请求分桶 + 代理获取（回源/预筛）+ 重试退避，每一秒可归因
    ts = client.timing_stats()
    pool = client.proxy_stats()
    log.info(
        "请求耗时统计：直连 %d 次 %.2fs（均 %.3fs）｜代理 %d 次 %.2fs（均 %.3fs）｜"
        "代理获取等待 %.2fs（回源 %.2fs + 预筛 %.2fs）｜重试退避 %.2fs｜失败尝试 %d",
        ts["direct_requests"],
        ts["direct_sec"],
        ts["direct_sec"] / max(ts["direct_requests"], 1),
        ts["proxy_requests"],
        ts["proxy_sec"],
        ts["proxy_sec"] / max(ts["proxy_requests"], 1),
        ts["proxy_wait_sec"],
        pool.get("refill_sec", 0.0),
        pool.get("prefilter_sec", 0.0),
        ts["backoff_sec"],
        ts["failed_attempts"],
    )
    log.info("%s", _ledger_line(pool, total_pages))
    for name, stat in sorted((pool.get("source_stats") or {}).items()):
        if stat.get("calls"):
            log.info(
                "  源 %s：回源 %d 次，交付 %d，预筛淘汰 %d，进池 %d",
                name,
                stat.get("calls", 0),
                stat.get("returned", 0),
                stat.get("rejected", 0),
                stat.get("adopted", 0),
            )
    # 旁路记账：追加一行 JSONL，供跨天按源比较（写失败只告警，不影响本次结果）
    record_ledger(pool, ts, total_pages, len(result.items), time.monotonic() - started)


def df_board_constituent_em(
    query: BoardQuery | None = None,
    settings: Settings | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``board_constituent_em`` 的 DataFrame 版（akshare 风格中文列名）。"""
    return to_dataframe(board_constituent_em(query, settings), columns)


def df_stock_list_em(
    query: MarketQuery | None = None,
    settings: Settings | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``stock_list_em`` 的 DataFrame 版（akshare 风格中文列名）。"""
    return to_dataframe(stock_list_em(query, settings), columns)


def df_stock_list_all_em(
    settings: Settings | None = None,
    max_rounds: int = 5,
    workers: int = _DEFAULT_FETCH_WORKERS,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``stock_list_all_em`` 的 DataFrame 版（akshare 风格中文列名）。"""
    return to_dataframe(
        stock_list_all_em(settings=settings, max_rounds=max_rounds, workers=workers), columns
    )


def stock_kline_em(
    query: KlineQuery | None = None, settings: Settings | None = None
) -> KlineSeries:
    """抓取个股 / 指数历史 K 线，返回领域模型 ``KlineSeries``。"""
    query = query or KlineQuery()
    client = _build_client(settings or Settings.from_env())
    source = registry.EastMoneySource(client)
    return source.fetch_kline(registry.kline_request(query))


def df_stock_kline_em(
    query: KlineQuery | None = None,
    settings: Settings | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``stock_kline_em`` 的 DataFrame 版（akshare 风格中文列名）。"""
    return to_kline_dataframe(stock_kline_em(query, settings), columns)


def stock_trends_em(
    query: TrendQuery | None = None, settings: Settings | None = None
) -> TrendSeries:
    """抓取个股 / 指数分时行情，返回领域模型 ``TrendSeries``。"""
    query = query or TrendQuery()
    client = _build_client(settings or Settings.from_env())
    source = registry.EastMoneySource(client)
    return source.fetch_trends(registry.trends_request(query))


def df_stock_trends_em(
    query: TrendQuery | None = None,
    settings: Settings | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``stock_trends_em`` 的 DataFrame 版（中文列名）。"""
    return to_trend_dataframe(stock_trends_em(query, settings), columns)


def stock_fund_flow_em(
    query: FundFlowQuery | None = None, settings: Settings | None = None
) -> FundFlowSeries:
    """抓取个股历史资金流，返回领域模型 ``FundFlowSeries``。"""
    query = query or FundFlowQuery()
    client = _build_client(settings or Settings.from_env())
    source = registry.EastMoneySource(client)
    return source.fetch_fund_flow(registry.fund_flow_request(query))


def df_stock_fund_flow_em(
    query: FundFlowQuery | None = None,
    settings: Settings | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``stock_fund_flow_em`` 的 DataFrame 版（akshare 风格中文列名）。"""
    return to_fund_flow_dataframe(stock_fund_flow_em(query, settings), columns)


def board_fund_flow_em(
    query: BoardFundFlowQuery | None = None, settings: Settings | None = None
) -> BoardFundFlowSeries:
    """抓取板块（行业 / 概念 / 地域）历史资金流，返回领域模型 ``BoardFundFlowSeries``。"""
    query = query or BoardFundFlowQuery()
    client = _build_client(settings or Settings.from_env())
    source = registry.EastMoneySource(client)
    return source.fetch_board_fund_flow(registry.board_fund_flow_request(query))


def df_board_fund_flow_em(
    query: BoardFundFlowQuery | None = None,
    settings: Settings | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``board_fund_flow_em`` 的 DataFrame 版（akshare 风格中文列名）。"""
    return to_board_fund_flow_dataframe(board_fund_flow_em(query, settings), columns)


def board_kline_em(
    query: BoardKlineQuery | None = None, settings: Settings | None = None
) -> KlineSeries:
    """抓取板块（行业 / 概念 / 地域）历史 K 线，返回领域模型 ``KlineSeries``。"""
    query = query or BoardKlineQuery()
    client = _build_client(settings or Settings.from_env())
    source = registry.EastMoneySource(client)
    return source.fetch_kline(registry.board_kline_request(query))


def df_board_kline_em(
    query: BoardKlineQuery | None = None,
    settings: Settings | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``board_kline_em`` 的 DataFrame 版（akshare 风格中文列名）。"""
    return to_kline_dataframe(board_kline_em(query, settings), columns)


def board_industry_list_em(
    query: BoardListQuery | None = None, settings: Settings | None = None
) -> BoardListPage:
    """抓取板块列表（行业 / 概念 / 地域），返回领域模型 ``BoardListPage``。"""
    query = query or BoardListQuery()
    client = _build_client(settings or Settings.from_env())
    source = registry.EastMoneySource(client)
    return source.fetch_board_list(registry.board_industry_list_request(query))


def df_board_industry_list_em(
    query: BoardListQuery | None = None,
    settings: Settings | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``board_industry_list_em`` 的 DataFrame 版（akshare 风格中文列名）。"""
    return to_board_list_dataframe(board_industry_list_em(query, settings), columns)


def index_list_em(
    query: IndexListQuery | None = None, settings: Settings | None = None
) -> IndexListPage:
    """抓取指数列表（沪深重要指数 / 上证 / 深证 / 中证系列），返回领域模型 ``IndexListPage``。"""
    query = query or IndexListQuery()
    client = _build_client(settings or Settings.from_env())
    source = registry.EastMoneySource(client)
    return source.fetch_index_list(registry.index_list_request(query))


def df_index_list_em(
    query: IndexListQuery | None = None,
    settings: Settings | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``index_list_em`` 的 DataFrame 版（akshare 风格中文列名）。"""
    return to_index_list_dataframe(index_list_em(query, settings), columns)


def hk_stock_list_em(
    query: HkStockListQuery | None = None, settings: Settings | None = None
) -> HkStockListPage:
    """抓取港股列表（主板 / 创业板），返回领域模型 ``HkStockListPage``。"""
    query = query or HkStockListQuery()
    client = _build_client(settings or Settings.from_env())
    source = registry.EastMoneySource(client)
    return source.fetch_hk_stock_list(registry.hk_stock_list_request(query))


def df_hk_stock_list_em(
    query: HkStockListQuery | None = None,
    settings: Settings | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``hk_stock_list_em`` 的 DataFrame 版（akshare 风格中文列名）。"""
    return to_hk_stock_list_dataframe(hk_stock_list_em(query, settings), columns)


def fund_list_em(
    query: FundListQuery | None = None, settings: Settings | None = None
) -> FundListPage:
    """抓取场内基金列表（ETF / LOF），返回领域模型 ``FundListPage``。"""
    query = query or FundListQuery()
    client = _build_client(settings or Settings.from_env())
    source = registry.EastMoneySource(client)
    return source.fetch_fund_list(registry.fund_list_request(query))


def df_fund_list_em(
    query: FundListQuery | None = None,
    settings: Settings | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``fund_list_em`` 的 DataFrame 版（akshare 风格中文列名）。"""
    return to_fund_list_dataframe(fund_list_em(query, settings), columns)


def stock_limit_pool_em(
    query: LimitPoolQuery | None = None, settings: Settings | None = None
) -> LimitPoolPage:
    """抓取某个交易日的涨跌停股池（涨停 / 昨日涨停 / 强势 / 次新 / 炸板 / 跌停），返回 ``LimitPoolPage``。"""
    query = query or LimitPoolQuery()
    client = _build_client(settings or Settings.from_env())
    source = registry.EastMoneySource(client)
    return source.fetch_limit_pool(registry.stock_limit_pool_request(query))


def df_stock_limit_pool_em(
    query: LimitPoolQuery | None = None,
    settings: Settings | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``stock_limit_pool_em`` 的 DataFrame 版（只含该股池适用的列，akshare 风格中文列名）。"""
    return to_limit_pool_dataframe(stock_limit_pool_em(query, settings), columns)


def stock_info_em(
    query: StockInfoQuery | None = None, settings: Settings | None = None
) -> StockInfo:
    """抓取个股基本信息（行业 / 上市时间 / 股本 / 市值），返回 ``StockInfo``；查无此券抛 ``SecurityNotFoundError``。"""
    query = query or StockInfoQuery()
    client = _build_client(settings or Settings.from_env())
    source = registry.EastMoneySource(client)
    return source.fetch_stock_info(registry.stock_info_request(query))


def df_stock_info_em(
    query: StockInfoQuery | None = None, settings: Settings | None = None
) -> pd.DataFrame:
    """``stock_info_em`` 的 DataFrame 版（akshare 风格 ``item`` / ``value`` 纵表）。"""
    return to_stock_info_dataframe(stock_info_em(query, settings))


def stock_bid_ask_em(
    query: StockBidAskQuery | None = None, settings: Settings | None = None
) -> StockBidAsk:
    """抓取个股五档盘口与当日行情快照，返回 ``StockBidAsk``；查无此券抛 ``SecurityNotFoundError``。"""
    query = query or StockBidAskQuery()
    client = _build_client(settings or Settings.from_env())
    source = registry.EastMoneySource(client)
    return source.fetch_stock_bid_ask(registry.stock_bid_ask_request(query))


def df_stock_bid_ask_em(
    query: StockBidAskQuery | None = None, settings: Settings | None = None
) -> pd.DataFrame:
    """``stock_bid_ask_em`` 的 DataFrame 版（akshare 风格 ``item`` / ``value`` 纵表）。"""
    return to_stock_bid_ask_dataframe(stock_bid_ask_em(query, settings))


def stock_changes_em(
    query: StockChangesQuery | None = None, settings: Settings | None = None
) -> StockChangesPage:
    """抓取最近一个交易日某一类盘口异动（大笔买入 / 火箭发射 / 封涨停板等 22 种）的全部记录。"""
    query = query or StockChangesQuery()
    client = _build_client(settings or Settings.from_env())
    source = registry.EastMoneySource(client)
    return source.fetch_stock_changes(registry.stock_changes_request(query))


def df_stock_changes_em(
    query: StockChangesQuery | None = None,
    settings: Settings | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``stock_changes_em`` 的 DataFrame 版（akshare 风格中文列名，数量 / 金额只在大笔买卖等四类有）。"""
    return to_stock_changes_dataframe(stock_changes_em(query, settings), columns)


def board_changes_em(
    query: BoardChangesQuery | None = None, settings: Settings | None = None
) -> BoardChangesPage:
    """抓取最近一个交易日全部有异动的板块（异动次数 / 最频繁个股 / 各类异动次数），返回 ``BoardChangesPage``。"""
    query = query or BoardChangesQuery()
    client = _build_client(settings or Settings.from_env())
    source = registry.EastMoneySource(client)
    return source.fetch_board_changes(registry.board_changes_request(query))


def df_board_changes_em(
    query: BoardChangesQuery | None = None,
    settings: Settings | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``board_changes_em`` 的 DataFrame 版（akshare 风格中文列名，主力净流入单位元）。"""
    return to_board_changes_dataframe(board_changes_em(query, settings), columns)


def billboard_detail_em(
    query: BillboardDetailQuery | None = None, settings: Settings | None = None
) -> ReportPage[BillboardEntry]:
    """抓取龙虎榜详情（按上榜日期区间，日期留空取最近一个有龙虎榜的交易日），自动翻完全部页。"""
    query = query or BillboardDetailQuery()
    client = _build_client(settings or Settings.from_env())
    return fetch_report(client, registry.billboard_detail_request(query))


def df_billboard_detail_em(
    query: BillboardDetailQuery | None = None,
    settings: Settings | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``billboard_detail_em`` 的 DataFrame 版（akshare 风格中文列名）。"""
    return to_billboard_detail_dataframe(billboard_detail_em(query, settings), columns)


def billboard_stock_stats_em(
    query: BillboardStockStatsQuery | None = None, settings: Settings | None = None
) -> ReportPage[BillboardStockStats]:
    """抓取个股上榜统计（统计周期内各股的上榜次数与龙虎榜、机构买卖合计），自动翻完全部页。"""
    query = query or BillboardStockStatsQuery()
    request = registry.billboard_stock_stats_request(query)
    return fetch_report(_build_client(settings or Settings.from_env()), request)


def df_billboard_stock_stats_em(
    query: BillboardStockStatsQuery | None = None,
    settings: Settings | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``billboard_stock_stats_em`` 的 DataFrame 版（akshare 风格中文列名）。"""
    return to_billboard_stock_stats_dataframe(billboard_stock_stats_em(query, settings), columns)


def billboard_institution_em(
    query: BillboardInstitutionQuery | None = None, settings: Settings | None = None
) -> ReportPage[BillboardInstitutionTrade]:
    """抓取机构买卖每日统计（按上榜日期区间，日期留空取最近一个有机构席位上榜的交易日），自动翻完全部页。"""
    query = query or BillboardInstitutionQuery()
    request = registry.billboard_institution_request(query)
    return fetch_report(_build_client(settings or Settings.from_env()), request)


def df_billboard_institution_em(
    query: BillboardInstitutionQuery | None = None,
    settings: Settings | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``billboard_institution_em`` 的 DataFrame 版（akshare 风格中文列名）。"""
    return to_billboard_institution_dataframe(billboard_institution_em(query, settings), columns)


def billboard_institution_stats_em(
    query: BillboardInstitutionStatsQuery | None = None, settings: Settings | None = None
) -> ReportPage[BillboardInstitutionStats]:
    """抓取机构席位追踪（统计周期内各股上榜时机构席位的买卖合计），自动翻完全部页。"""
    query = query or BillboardInstitutionStatsQuery()
    request = registry.billboard_institution_stats_request(query)
    return fetch_report(_build_client(settings or Settings.from_env()), request)


def df_billboard_institution_stats_em(
    query: BillboardInstitutionStatsQuery | None = None,
    settings: Settings | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``billboard_institution_stats_em`` 的 DataFrame 版（akshare 风格中文列名）。"""
    return to_billboard_institution_stats_dataframe(
        billboard_institution_stats_em(query, settings), columns
    )


def billboard_branch_active_em(
    query: BillboardBranchActiveQuery | None = None, settings: Settings | None = None
) -> ReportPage[BillboardBranchActive]:
    """抓取每日活跃营业部（按上榜日期区间，日期留空取最近一个有龙虎榜的交易日），自动翻完全部页。"""
    query = query or BillboardBranchActiveQuery()
    request = registry.billboard_branch_active_request(query)
    return fetch_report(_build_client(settings or Settings.from_env()), request)


def df_billboard_branch_active_em(
    query: BillboardBranchActiveQuery | None = None,
    settings: Settings | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``billboard_branch_active_em`` 的 DataFrame 版（akshare 风格中文列名）。"""
    return to_billboard_branch_active_dataframe(
        billboard_branch_active_em(query, settings), columns
    )


def billboard_branch_rank_em(
    query: BillboardBranchRankQuery | None = None, settings: Settings | None = None
) -> ReportPage[BillboardBranchRank]:
    """抓取营业部排行（统计周期内各营业部买入上榜后 1 / 2 / 3 / 5 / 10 天的平均涨幅与上涨概率），自动翻完全部页。"""
    query = query or BillboardBranchRankQuery()
    request = registry.billboard_branch_rank_request(query)
    return fetch_report(_build_client(settings or Settings.from_env()), request)


def df_billboard_branch_rank_em(
    query: BillboardBranchRankQuery | None = None,
    settings: Settings | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``billboard_branch_rank_em`` 的 DataFrame 版（akshare 风格中文列名）。"""
    return to_billboard_branch_rank_dataframe(billboard_branch_rank_em(query, settings), columns)


def billboard_branch_stats_em(
    query: BillboardBranchStatsQuery | None = None, settings: Settings | None = None
) -> ReportPage[BillboardBranchStats]:
    """抓取营业部统计（统计周期内各营业部的上榜次数与买卖合计），自动翻完全部页。"""
    query = query or BillboardBranchStatsQuery()
    request = registry.billboard_branch_stats_request(query)
    return fetch_report(_build_client(settings or Settings.from_env()), request)


def df_billboard_branch_stats_em(
    query: BillboardBranchStatsQuery | None = None,
    settings: Settings | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``billboard_branch_stats_em`` 的 DataFrame 版（akshare 风格中文列名）。"""
    return to_billboard_branch_stats_dataframe(billboard_branch_stats_em(query, settings), columns)


def billboard_branch_trades_em(
    query: BillboardBranchTradesQuery, settings: Settings | None = None
) -> ReportPage[BillboardBranchTrade]:
    """抓取营业部详情（一家营业部的上榜买卖记录，日期留空取全部历史），自动翻完全部页。"""
    request = registry.billboard_branch_trades_request(query)
    return fetch_report(_build_client(settings or Settings.from_env()), request)


def df_billboard_branch_trades_em(
    query: BillboardBranchTradesQuery,
    settings: Settings | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``billboard_branch_trades_em`` 的 DataFrame 版（akshare 风格中文列名）。"""
    return to_billboard_branch_trades_dataframe(
        billboard_branch_trades_em(query, settings), columns
    )


def billboard_stock_dates_em(
    query: BillboardStockDatesQuery, settings: Settings | None = None
) -> ReportPage[BillboardStockDate]:
    """抓取一只股票历次上榜的日期（倒序），自动翻完全部页。"""
    request = registry.billboard_stock_dates_request(query)
    return fetch_report(_build_client(settings or Settings.from_env()), request)


def df_billboard_stock_dates_em(
    query: BillboardStockDatesQuery,
    settings: Settings | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``billboard_stock_dates_em`` 的 DataFrame 版（akshare 风格中文列名）。"""
    return to_billboard_stock_dates_dataframe(billboard_stock_dates_em(query, settings), columns)


def billboard_stock_em(
    query: BillboardStockQuery, settings: Settings | None = None
) -> ReportPage[BillboardSeat]:
    """抓取个股龙虎榜详情（一只股票某个上榜日的买入或卖出席位，日期留空取该股最近一个上榜日）。"""
    request = registry.billboard_stock_request(query)
    return fetch_report(_build_client(settings or Settings.from_env()), request)


def df_billboard_stock_em(
    query: BillboardStockQuery,
    settings: Settings | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``billboard_stock_em`` 的 DataFrame 版（akshare 风格中文列名）。"""
    return to_billboard_stock_dataframe(billboard_stock_em(query, settings), columns)


def block_trade_market_daily_em(
    query: BlockTradeMarketDailyQuery | None = None, settings: Settings | None = None
) -> ReportPage[BlockTradeMarketDaily]:
    """抓取大宗交易市场统计（一个交易日一行，日期留空取 2000-08-29 起的全部历史），自动翻完全部页。"""
    query = query or BlockTradeMarketDailyQuery()
    request = registry.block_trade_market_daily_request(query)
    return fetch_report(_build_client(settings or Settings.from_env()), request)


def df_block_trade_market_daily_em(
    query: BlockTradeMarketDailyQuery | None = None,
    settings: Settings | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``block_trade_market_daily_em`` 的 DataFrame 版（akshare 风格中文列名）。"""
    return to_block_trade_market_daily_dataframe(
        block_trade_market_daily_em(query, settings), columns
    )


def block_trade_detail_em(
    query: BlockTradeDetailQuery | None = None, settings: Settings | None = None
) -> ReportPage[BlockTrade]:
    """抓取大宗交易每日明细（按证券类型和交易日期区间，日期留空取最近一个交易日），自动翻完全部页。"""
    query = query or BlockTradeDetailQuery()
    request = registry.block_trade_detail_request(query)
    return fetch_report(_build_client(settings or Settings.from_env()), request)


def df_block_trade_detail_em(
    query: BlockTradeDetailQuery | None = None,
    settings: Settings | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``block_trade_detail_em`` 的 DataFrame 版（akshare 风格中文列名）。"""
    return to_block_trade_detail_dataframe(block_trade_detail_em(query, settings), columns)


def block_trade_stock_daily_em(
    query: BlockTradeStockDailyQuery | None = None, settings: Settings | None = None
) -> ReportPage[BlockTradeStockDaily]:
    """抓取大宗交易每日统计（各 A 股当天的大宗交易汇总，日期留空取最近一个交易日），自动翻完全部页。"""
    query = query or BlockTradeStockDailyQuery()
    request = registry.block_trade_stock_daily_request(query)
    return fetch_report(_build_client(settings or Settings.from_env()), request)


def df_block_trade_stock_daily_em(
    query: BlockTradeStockDailyQuery | None = None,
    settings: Settings | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``block_trade_stock_daily_em`` 的 DataFrame 版（akshare 风格中文列名）。"""
    return to_block_trade_stock_daily_dataframe(
        block_trade_stock_daily_em(query, settings), columns
    )


def block_trade_stock_stats_em(
    query: BlockTradeStockStatsQuery | None = None, settings: Settings | None = None
) -> ReportPage[BlockTradeStockStats]:
    """抓取大宗交易活跃 A 股统计（统计周期内各股的成交笔数、总成交额与之后的平均涨跌幅），自动翻完全部页。"""
    query = query or BlockTradeStockStatsQuery()
    request = registry.block_trade_stock_stats_request(query)
    return fetch_report(_build_client(settings or Settings.from_env()), request)


def df_block_trade_stock_stats_em(
    query: BlockTradeStockStatsQuery | None = None,
    settings: Settings | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``block_trade_stock_stats_em`` 的 DataFrame 版（akshare 风格中文列名）。"""
    return to_block_trade_stock_stats_dataframe(
        block_trade_stock_stats_em(query, settings), columns
    )


def block_trade_branch_active_em(
    query: BlockTradeBranchActiveQuery | None = None, settings: Settings | None = None
) -> ReportPage[BlockTradeBranchActive]:
    """抓取大宗交易活跃营业部统计（最近 N 个交易日各营业部的买卖笔数、金额与买入的股票），自动翻完全部页。"""
    query = query or BlockTradeBranchActiveQuery()
    request = registry.block_trade_branch_active_request(query)
    return fetch_report(_build_client(settings or Settings.from_env()), request)


def df_block_trade_branch_active_em(
    query: BlockTradeBranchActiveQuery | None = None,
    settings: Settings | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``block_trade_branch_active_em`` 的 DataFrame 版（akshare 风格中文列名）。"""
    return to_block_trade_branch_active_dataframe(
        block_trade_branch_active_em(query, settings), columns
    )


def block_trade_branch_rank_em(
    query: BlockTradeBranchRankQuery | None = None, settings: Settings | None = None
) -> ReportPage[BlockTradeBranchRank]:
    """抓取大宗交易营业部排行（最近 N 个交易日各营业部买入后 1 / 5 / 10 / 20 日的平均涨幅与上涨概率），自动翻完全部页。"""
    query = query or BlockTradeBranchRankQuery()
    request = registry.block_trade_branch_rank_request(query)
    return fetch_report(_build_client(settings or Settings.from_env()), request)


def df_block_trade_branch_rank_em(
    query: BlockTradeBranchRankQuery | None = None,
    settings: Settings | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``block_trade_branch_rank_em`` 的 DataFrame 版（akshare 风格中文列名）。"""
    return to_block_trade_branch_rank_dataframe(
        block_trade_branch_rank_em(query, settings), columns
    )


def earnings_report_em(
    query: EarningsReportQuery | None = None, settings: Settings | None = None
) -> ReportPage[EarningsReport]:
    """抓取业绩报告（按报告期，留空取最近的季末；``scope`` 筛市场范围），自动翻完全部页。"""
    query = query or EarningsReportQuery()
    request = registry.earnings_report_request(query)
    return fetch_report(_build_client(settings or Settings.from_env()), request)


def df_earnings_report_em(
    query: EarningsReportQuery | None = None,
    settings: Settings | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``earnings_report_em`` 的 DataFrame 版（中文列名）。"""
    return to_earnings_report_dataframe(earnings_report_em(query, settings), columns)


def earnings_express_em(
    query: EarningsExpressQuery | None = None, settings: Settings | None = None
) -> ReportPage[EarningsExpress]:
    """抓取业绩快报（按报告期，留空取最近的季末；``scope`` 筛市场范围），自动翻完全部页。"""
    query = query or EarningsExpressQuery()
    request = registry.earnings_express_request(query)
    return fetch_report(_build_client(settings or Settings.from_env()), request)


def df_earnings_express_em(
    query: EarningsExpressQuery | None = None,
    settings: Settings | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``earnings_express_em`` 的 DataFrame 版（中文列名）。"""
    return to_earnings_express_dataframe(earnings_express_em(query, settings), columns)


def earnings_forecast_em(
    query: EarningsForecastQuery | None = None, settings: Settings | None = None
) -> ReportPage[EarningsForecast]:
    """抓取业绩预告（按报告期，留空取最近的季末；``scope`` 筛市场范围），自动翻完全部页。"""
    query = query or EarningsForecastQuery()
    request = registry.earnings_forecast_request(query)
    return fetch_report(_build_client(settings or Settings.from_env()), request)


def df_earnings_forecast_em(
    query: EarningsForecastQuery | None = None,
    settings: Settings | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``earnings_forecast_em`` 的 DataFrame 版（中文列名）。"""
    return to_earnings_forecast_dataframe(earnings_forecast_em(query, settings), columns)


def earnings_schedule_em(
    query: EarningsScheduleQuery | None = None, settings: Settings | None = None
) -> ReportPage[EarningsSchedule]:
    """抓取预约披露时间（按报告期，留空取最近的季末；``scope`` 筛市场范围），自动翻完全部页。"""
    query = query or EarningsScheduleQuery()
    request = registry.earnings_schedule_request(query)
    return fetch_report(_build_client(settings or Settings.from_env()), request)


def df_earnings_schedule_em(
    query: EarningsScheduleQuery | None = None,
    settings: Settings | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``earnings_schedule_em`` 的 DataFrame 版（中文列名）。"""
    return to_earnings_schedule_dataframe(earnings_schedule_em(query, settings), columns)


def balance_sheet_em(
    query: BalanceSheetQuery | None = None, settings: Settings | None = None
) -> ReportPage[BalanceSheet]:
    """抓取资产负债表（按报告期，留空取最近的季末；``scope`` 筛市场范围），自动翻完全部页。"""
    query = query or BalanceSheetQuery()
    request = registry.balance_sheet_request(query)
    return fetch_report(_build_client(settings or Settings.from_env()), request)


def df_balance_sheet_em(
    query: BalanceSheetQuery | None = None,
    settings: Settings | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``balance_sheet_em`` 的 DataFrame 版（中文列名）。"""
    return to_balance_sheet_dataframe(balance_sheet_em(query, settings), columns)


def income_statement_em(
    query: IncomeStatementQuery | None = None, settings: Settings | None = None
) -> ReportPage[IncomeStatement]:
    """抓取利润表（按报告期，留空取最近的季末；``scope`` 筛市场范围），自动翻完全部页。"""
    query = query or IncomeStatementQuery()
    request = registry.income_statement_request(query)
    return fetch_report(_build_client(settings or Settings.from_env()), request)


def df_income_statement_em(
    query: IncomeStatementQuery | None = None,
    settings: Settings | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``income_statement_em`` 的 DataFrame 版（中文列名）。"""
    return to_income_statement_dataframe(income_statement_em(query, settings), columns)


def cash_flow_statement_em(
    query: CashFlowStatementQuery | None = None, settings: Settings | None = None
) -> ReportPage[CashFlowStatement]:
    """抓取现金流量表（按报告期，留空取最近的季末；``scope`` 筛市场范围），自动翻完全部页。"""
    query = query or CashFlowStatementQuery()
    request = registry.cash_flow_statement_request(query)
    return fetch_report(_build_client(settings or Settings.from_env()), request)


def df_cash_flow_statement_em(
    query: CashFlowStatementQuery | None = None,
    settings: Settings | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``cash_flow_statement_em`` 的 DataFrame 版（中文列名）。"""
    return to_cash_flow_statement_dataframe(cash_flow_statement_em(query, settings), columns)

"""应用层服务：装配传输/代理/来源，暴露面向用户的 ``*_em`` 公共面（``df_*_em`` 为 DataFrame 版）。"""

from __future__ import annotations

import functools
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

import requests

from em.application import registry
from em.application.dataframe import (
    to_board_fund_flow_dataframe,
    to_board_list_dataframe,
    to_dataframe,
    to_fund_flow_dataframe,
    to_kline_dataframe,
    to_trend_dataframe,
)
from em.channels.eastmoney import config as em_config
from em.core.proxy import ProxyPool, ProxyRouter, ProxySettings
from em.core.resilience import RetryPolicy
from em.core.settings import Settings
from em.core.transport import HttpClient
from em.domain.models import (
    BoardFundFlowSeries,
    BoardListPage,
    FundFlowSeries,
    KlineSeries,
    Quote,
    QuotePage,
    TrendSeries,
)
from em.domain.queries import (
    BoardFundFlowQuery,
    BoardListQuery,
    BoardQuery,
    FundFlowQuery,
    KlineQuery,
    MarketQuery,
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
# 页级兜底重试的短退避：整批 IP 全死/代理源限流后立即重发大概率撞同一批，
# 短等一个换血窗口（代理池回源 ~0.2s、负缓存 1s 量级），0.5s 折中
_PAGE_RETRY_BACKOFF_SEC = 0.5
# 回源预筛探测地址：极小 clist 请求（pz=1），1.5s 内拿不到有效 JSONP 视为死 IP
_PROXY_PROBE_URL = (
    "https://pushguest.eastmoney.com/api/qt/clist/get"
    "?pn=1&pz=1&po=1&np=1&fltt=2&invt=2&fid=f12&fs=m:0+t:6&fields=f12"
)
_PROXY_PROBE_TIMEOUT = (1.0, 1.5)  # (连接, 读取)：死 IP 多卡连接或短读超时
_probe_session = requests.Session()  # 预筛探测复用连接（低频、多代理出口）


def _probe_proxy(ip: str) -> bool:
    """预筛探测：该代理 IP 能否在 1.5s 内拿到东财有效 JSONP。线程安全。"""
    proxies = {"http": f"http://{ip}", "https": f"http://{ip}"}
    try:
        resp = _probe_session.get(
            _PROXY_PROBE_URL, headers=em_config.HEADERS,
            proxies=proxies, timeout=_PROXY_PROBE_TIMEOUT,
        )
    except requests.RequestException:
        return False
    return resp.status_code == 200 and '"rc"' in resp.text


@functools.lru_cache(maxsize=8)
def _build_client(settings: Settings) -> HttpClient:
    session = requests.Session()
    # 代理 IP 是多 origin 的连接目标：放大连接池避免并发放大时反复建连
    adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
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
    )
    pool = ProxyPool(
        ps, session, prober=_probe_proxy if settings.proxy_prefilter else None
    )
    router = ProxyRouter(pool, ps)
    policy = RetryPolicy(
        max_retries=settings.max_retries,
        backoff_sec=settings.backoff_sec,
        backoff_cap_sec=settings.backoff_cap_sec,
        jitter_sec=settings.backoff_jitter_sec,
    )
    return HttpClient(
        session,
        router,
        policy,
        timeout_sec=settings.request_timeout_sec,
        connect_timeout_sec=settings.request_connect_timeout_sec,
        dynamic_timeout=settings.request_dynamic_timeout,
    )


def _reset_client_cache() -> None:
    """清空 client 缓存（测试用）。"""
    _build_client.cache_clear()


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
    """抓取沪深京 A 股全市场列表，返回领域模型 ``QuotePage``。"""
    query = query or MarketQuery()
    client = _build_client(settings or Settings.from_env())
    source = registry.EastMoneySource(client)
    return source.fetch_page(registry.stock_list_request(query))


def _suspicious_pages(
    page_codes: dict[int, set[str]], total_pages: int
) -> set[int]:
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


def stock_list_all_em(
    query: MarketQuery | None = None,
    settings: Settings | None = None,
    max_rounds: int = 5,
    workers: int = _DEFAULT_FETCH_WORKERS,
) -> QuotePage:
    """有界并发翻页拉取沪深京 A 股全市场快照（游客 clist 单页上限 100，约 56 页）。

    固定按代码（f12）稳定排序翻页——``query.sort`` 在此忽略：f3 等行情排序盘中实时
    漂移会使并发分页跨页重复（实测 6x 请求放大）；需要特定行情顺序请取完后在本地排序。
    先抓首页拿 ``total`` 推算总页数，再用 ``workers`` 个线程并发抓余下各页，按 ``code``
    去重。补漏为**定向重抓**：东财后端节点不一致表现为"邻页码集合重叠（替换型漂移）"，
    首轮即可定位问题页，只重抓可疑页（实测缺 3 码仅涉 3 页）；若可疑页清零仍缺码，
    再做至多一次全量兜底轮。
    """
    if workers < 1:
        raise ValueError("workers 必须 >= 1")
    query = query or MarketQuery()
    client = _build_client(settings or Settings.from_env())
    source = registry.EastMoneySource(client)
    seen: dict[str, Quote] = {}
    page_codes: dict[int, set[str]] = {}  # 每页最近一次返回的码集合，用于邻页重叠定位
    lock = threading.Lock()
    total = 0

    def fetch_one(page_no: int, total_pages: int, dup_retries: int) -> Exception | None:
        """抓单页并入 ``seen``/``page_codes``；返回 None 成功，否则最后一次异常。

        总尝试 = 3 次（传输失败/空页兜底）+ ``dup_retries`` 次（零新增旧快照换 IP）。
        """
        nonlocal total
        request = registry.stock_list_request(
            MarketQuery(sort=_CLIST_SNAPSHOT_SORT, page=page_no, size=_CLIST_PAGE_SIZE_MAX)
        )
        last_exc: Exception | None = None
        dup_used = 0
        attempts = 3 + dup_retries
        for attempt in range(attempts):
            try:
                page = source.fetch_page(request)
            except Exception as exc:  # 传输层已换 IP 重试 10 次，此处兜底整页重试
                last_exc = exc
                if attempt < attempts - 1:  # 还有后继尝试才退避，末次失败直接返回
                    time.sleep(_PAGE_RETRY_BACKOFF_SEC)
                continue
            is_last = page_no == total_pages
            with lock:
                has_new = any(q.code not in seen for q in page.items)
            if not page.items and not is_last:
                last_exc = ValueError(f"第{page_no}页空返回")
                continue
            # 非末页“满页零新增”= 代理节点旧快照：淘汰该出口 IP 强制下轮换新，
            # 否则大概率还从同一节点拿到同一份旧快照，重试只是空耗
            if not is_last and not has_new and dup_used < dup_retries:
                dup_used += 1
                client.evict_last_proxy(request.url())
                last_exc = ValueError(f"第{page_no}页返回重复快照")
                continue
            with lock:
                total = page.total
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
        with ThreadPoolExecutor(max_workers=min(workers, len(page_nos))) as pool:
            futures = {
                pool.submit(fetch_one, pn, total_pages, dup_retries): pn for pn in page_nos
            }
            for future in as_completed(futures):
                if future.result() is not None:
                    failed.add(futures[future])
        return failed

    def suspicious_pages(total_pages: int) -> set[int]:
        return _suspicious_pages(page_codes, total_pages)

    # 首轮：首页确定 total/总页数，其余并发全抓
    err = fetch_one(1, 1, dup_retries=0)
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
            round_no, len(targets), mode, added, len(seen), total, len(failed),
        )
        # 定向轮零新增且无失败：重抓同批不会有结果，下轮直接全量兜底或收敛
        force_full = mode == "定向" and added == 0 and not failed and len(seen) < total

    if len(seen) < total:
        log.warning("全量拉取不完整：唯一 %d < total %d（代理资源不足）", len(seen), total)
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
    # 按代码排序输出：并发抓取的 dict 插入序是页完成序，对调用方不稳定
    return QuotePage(total=total, items=tuple(sorted(seen.values(), key=lambda q: q.code)))


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
    return to_dataframe(stock_list_all_em(settings=settings, max_rounds=max_rounds, workers=workers), columns)


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

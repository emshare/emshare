"""数据中心报表的翻页：取首页定总页数，并发取其余页，校验条数，必要时整轮重取一次。

各报表接口只拼请求（``registry.*_request``），翻页、去重、“未给日期取最近一天”都在这里统一处理。
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar

from em.application import registry
from em.application.pagination import PageRetryGuard
from em.channels.eastmoney.datacenter import ReportChunk
from em.channels.eastmoney.request import DatacenterRequest
from em.core.errors import ChannelError
from em.core.transport import HttpClient
from em.domain.models import ReportPage

T = TypeVar("T")

log = logging.getLogger(__name__)

# 并发度：实测 10 并发 × 40 页全部 code=0、墙钟 1.4s；与全市场翻页一样取 5，并按可用出口收敛
REPORT_FETCH_WORKERS = 5
# 每个可用出口允许的并发数（同 market_data._WORKERS_PER_PROXY）
_WORKERS_PER_PROXY = 2
# 单页在传输层重试耗尽后，页级再兜底重取的次数与间隔（间隔长于代理池空返回负缓存 1s）
_PAGE_ATTEMPTS = 2
_PAGE_RETRY_BACKOFF_SEC = 1.1
# 条数对不上（翻页期间上游增删）时整轮重取的次数
_ROUND_ATTEMPTS = 2


def fetch_report(client: HttpClient, request: DatacenterRequest[T]) -> ReportPage[T]:
    """取完一张报表的全部页，返回 ``ReportPage``（``items`` 保持上游排序）。

    - ``request.latest_of`` 非空（查询没给日期）：先查该日期列的最新值，再过滤到那一天；表为空时返回空页。
    - 查无数据（9201）返回 ``total=0`` 的空页；查询写错抛 ``QueryRejectedError``，不重试。
    - 各页报告的总数不一致、或取到的条数与总数不等，说明翻页期间上游有增删，整轮重取一次，
      仍不一致记 warning 并返回最后一轮的结果。
    - ``request.distinct`` 为 True 时按上游原始整行去重（只对已知会重复返回同一行的报表打开）。
    """
    source = registry.EastMoneySource(client)
    if request.latest_of:
        latest = source.fetch_report_page(request.latest_lookup())
        day = latest.items[0] if latest.items else None
        if day is None:
            return ReportPage(total=0, items=())
        request = request.on_day(day)

    for attempt in range(1, _ROUND_ATTEMPTS + 1):
        chunks = _fetch_round(client, source, request)
        totals = {c.total for c in chunks if c.pages}
        rows = sum(len(c.items) for c in chunks)
        total = chunks[0].total
        if len(totals) <= 1 and rows == total:
            break
        if attempt < _ROUND_ATTEMPTS:
            log.info(
                "报表 %s 翻页期间条数变动（各页总数 %s，取到 %d），整轮重取",
                request.report,
                sorted(totals),
                rows,
            )
        else:
            log.warning(
                "报表 %s 翻页结果不一致：上游总数 %d，取到 %d（翻页期间上游持续增删）",
                request.report,
                total,
                rows,
            )
    return _merge(chunks, request.distinct)


def _fetch_round(
    client: HttpClient,
    source: registry.EastMoneySource,
    request: DatacenterRequest[T],
) -> list[ReportChunk[T]]:
    """取一轮：首页定总页数，其余页并发取；返回按页号排列的各页。"""
    retry_guard = PageRetryGuard()
    first = _fetch_page(source, request, retry_guard)
    if first.pages <= 1:
        return [first]
    workers = _effective_workers(
        REPORT_FETCH_WORKERS, client.available_proxies(request.url()), first.pages - 1
    )
    pages = range(2, first.pages + 1)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        rest = list(
            pool.map(lambda page: _fetch_page(source, request.with_page(page), retry_guard), pages)
        )
    return [first, *rest]


def _fetch_page(
    source: registry.EastMoneySource, request: DatacenterRequest[T], retry_guard: PageRetryGuard
) -> ReportChunk[T]:
    """取单页：传输层已换 IP 重试，耗尽后页级再兜底一次；查询写错等非渠道异常直接上抛。"""
    for attempt in range(1, _PAGE_ATTEMPTS + 1):
        try:
            with retry_guard.attempt():
                return source.fetch_report_page(request)
        except ChannelError as exc:
            if not exc.retryable or attempt == _PAGE_ATTEMPTS:
                raise
            log.info(
                "报表 %s 第 %d 页失败，%.1fs 后重取",
                request.report,
                request.page,
                _PAGE_RETRY_BACKOFF_SEC,
            )
            time.sleep(_PAGE_RETRY_BACKOFF_SEC)
    raise AssertionError("unreachable")  # pragma: no cover


def _effective_workers(workers: int, live_proxies: int, pages: int) -> int:
    """并发度按可用出口收敛（每出口 2 个），且不超过待取页数；拿不到代理（直连态）时保持给定并发。"""
    if live_proxies > 0:
        workers = min(workers, live_proxies * _WORKERS_PER_PROXY)
    return max(1, min(workers, pages))


def _merge(chunks: list[ReportChunk[T]], distinct: bool) -> ReportPage[T]:
    items: list[T] = []
    seen: set[str] = set()
    for chunk in chunks:
        for item, key in zip(chunk.items, chunk.keys, strict=True):
            if distinct:
                if key in seen:
                    continue
                seen.add(key)
            items.append(item)
    return ReportPage(total=chunks[0].total, items=tuple(items))

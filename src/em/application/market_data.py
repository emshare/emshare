"""应用层服务：装配传输/代理/来源，暴露面向用户的 ``*_em`` 公共面（``df_*_em`` 为 DataFrame 版）。"""

from __future__ import annotations

import functools
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
from em.core.proxy import ProxyPool, ProxyRouter, ProxySettings
from em.core.resilience import RetryPolicy
from em.core.settings import Settings
from em.core.transport import HttpClient
from em.domain.models import (
    BoardFundFlowSeries,
    BoardListPage,
    FundFlowSeries,
    KlineSeries,
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


@functools.lru_cache(maxsize=8)
def _build_client(settings: Settings) -> HttpClient:
    session = requests.Session()
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
    pool = ProxyPool(ps, session)
    router = ProxyRouter(pool, ps)
    policy = RetryPolicy(
        max_retries=settings.max_retries,
        backoff_sec=settings.backoff_sec,
        backoff_cap_sec=settings.backoff_cap_sec,
    )
    return HttpClient(session, router, policy, timeout_sec=settings.request_timeout_sec)


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

"""应用层服务：装配传输/代理/来源，暴露面向用户的 ``fetch_*`` 公共面。"""

from __future__ import annotations

from typing import TYPE_CHECKING

import requests

from em.application import registry
from em.application.dataframe import (
    to_board_fund_flow_dataframe,
    to_dataframe,
    to_fund_flow_dataframe,
    to_kline_dataframe,
    to_trend_dataframe,
)
from em.core.proxy import ProxyPool, ProxySettings
from em.core.resilience import RetryPolicy
from em.core.settings import Settings
from em.core.transport import HttpClient
from em.domain.models import (
    BoardFundFlowSeries,
    FundFlowSeries,
    KlineSeries,
    QuotePage,
    TrendSeries,
)
from em.domain.queries import (
    BoardFundFlowQuery,
    BoardQuery,
    FundFlowQuery,
    KlineQuery,
    MarketQuery,
    TrendQuery,
)

if TYPE_CHECKING:
    import pandas as pd


def _build_client(settings: Settings) -> HttpClient:
    session = requests.Session()
    pool = ProxyPool(
        ProxySettings(
            api=settings.proxy_api,
            enabled=settings.proxy_enabled,
            num=settings.proxy_num,
            ttl_sec=settings.proxy_ttl_sec,
            safety_margin_sec=settings.proxy_safety_margin_sec,
            timeout_sec=settings.proxy_timeout_sec,
        ),
        session,
    )
    policy = RetryPolicy(max_retries=settings.max_retries, backoff_sec=settings.backoff_sec)
    return HttpClient(session, pool, policy, timeout_sec=settings.request_timeout_sec)


def fetch_board(query: BoardQuery | None = None, settings: Settings | None = None) -> QuotePage:
    """抓取板块成分股（含资金流），返回领域模型 ``QuotePage``。"""
    query = query or BoardQuery()
    client = _build_client(settings or Settings.from_env())
    source = registry.EastMoneySource(client)
    request = registry.board_constituent_request(query)
    return source.fetch_page(request, registry.flow_field(query))


def fetch_market(query: MarketQuery | None = None, settings: Settings | None = None) -> QuotePage:
    """抓取沪深京 A 股全市场列表，返回领域模型 ``QuotePage``。"""
    query = query or MarketQuery()
    client = _build_client(settings or Settings.from_env())
    source = registry.EastMoneySource(client)
    return source.fetch_page(registry.stock_list_request(query))


def fetch_board_df(
    query: BoardQuery | None = None,
    settings: Settings | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``fetch_board`` 的 DataFrame 版（akshare 风格中文列名）。"""
    return to_dataframe(fetch_board(query, settings), columns)


def fetch_market_df(
    query: MarketQuery | None = None,
    settings: Settings | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``fetch_market`` 的 DataFrame 版（akshare 风格中文列名）。"""
    return to_dataframe(fetch_market(query, settings), columns)


def fetch_kline(query: KlineQuery | None = None, settings: Settings | None = None) -> KlineSeries:
    """抓取个股 / 指数历史 K 线，返回领域模型 ``KlineSeries``。"""
    query = query or KlineQuery()
    client = _build_client(settings or Settings.from_env())
    source = registry.EastMoneySource(client)
    return source.fetch_kline(registry.kline_request(query))


def fetch_kline_df(
    query: KlineQuery | None = None,
    settings: Settings | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``fetch_kline`` 的 DataFrame 版（akshare 风格中文列名）。"""
    return to_kline_dataframe(fetch_kline(query, settings), columns)


def fetch_trends(query: TrendQuery | None = None, settings: Settings | None = None) -> TrendSeries:
    """抓取个股 / 指数分时行情，返回领域模型 ``TrendSeries``。"""
    query = query or TrendQuery()
    client = _build_client(settings or Settings.from_env())
    source = registry.EastMoneySource(client)
    return source.fetch_trends(registry.trends_request(query))


def fetch_trends_df(
    query: TrendQuery | None = None,
    settings: Settings | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``fetch_trends`` 的 DataFrame 版（中文列名）。"""
    return to_trend_dataframe(fetch_trends(query, settings), columns)


def fetch_fund_flow(
    query: FundFlowQuery | None = None, settings: Settings | None = None
) -> FundFlowSeries:
    """抓取个股历史资金流，返回领域模型 ``FundFlowSeries``。"""
    query = query or FundFlowQuery()
    client = _build_client(settings or Settings.from_env())
    source = registry.EastMoneySource(client)
    return source.fetch_fund_flow(registry.fund_flow_request(query))


def fetch_fund_flow_df(
    query: FundFlowQuery | None = None,
    settings: Settings | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``fetch_fund_flow`` 的 DataFrame 版（akshare 风格中文列名）。"""
    return to_fund_flow_dataframe(fetch_fund_flow(query, settings), columns)


def fetch_board_fund_flow(
    query: BoardFundFlowQuery | None = None, settings: Settings | None = None
) -> BoardFundFlowSeries:
    """抓取板块（行业 / 概念 / 地域）历史资金流，返回领域模型 ``BoardFundFlowSeries``。"""
    query = query or BoardFundFlowQuery()
    client = _build_client(settings or Settings.from_env())
    source = registry.EastMoneySource(client)
    return source.fetch_board_fund_flow(registry.board_fund_flow_request(query))


def fetch_board_fund_flow_df(
    query: BoardFundFlowQuery | None = None,
    settings: Settings | None = None,
    columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``fetch_board_fund_flow`` 的 DataFrame 版（akshare 风格中文列名）。"""
    return to_board_fund_flow_dataframe(fetch_board_fund_flow(query, settings), columns)

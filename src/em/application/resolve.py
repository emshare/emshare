"""应用层服务：基于东财搜索接口的中文名→代码解析（单请求，轻量缓存）。

``searchapi.eastmoney.com/api/suggest/get`` 直连稳定（实测 30/30 零失败，avg 40ms）。
出口策略：
- 未配置动态代理源（或代理关闭 / ``never``）：直连；显式固定代理启用时使用该出口。
- 配置了动态代理源：与业务取数共用同一客户端与路由——``auto`` 下先直连，
  出口被封（403/429）或直连失败即切代理，稳定后自动探测回直连；``always`` 全程代理。
结果按关键词和出口配置缓存。

返回约定：查不到返回 ``None``（不臆测，让调用方决定）；网络故障抛异常（直连 / 固定出口为
``requests`` 异常，动态路由为 ``em.core.errors.ChannelError``）——以此区分"名字查不到"与"接口坏了"。
"""

from __future__ import annotations

import functools
import json
from dataclasses import dataclass

import requests

from em.core.session import ExplicitProxySession
from em.core.settings import Settings

_SEARCH_URL = "https://searchapi.eastmoney.com/api/suggest/get"
_SEARCH_TOKEN = "D2BF3E7AC4E7A1A2"
_SEARCH_TYPE_ALL = "14"
_SEARCH_COUNT = "20"
_SEARCH_TIMEOUT_SEC = 10
_SEARCH_HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.eastmoney.com/"}
_A_STOCK_MARKETS = {"深A": "sz", "沪A": "sh", "京A": "bj"}


@dataclass(frozen=True)
class StockRef:
    """证券引用（``resolve_code`` 的返回）：A 股代码 + 市场。"""

    code: str
    name: str
    market: str  # sz 深市 / sh 沪市 / bj 北交所


@dataclass(frozen=True)
class BoardRef:
    """板块引用（``resolve_board`` 的返回）：板块代码 + 名称。"""

    code: str
    name: str


@functools.lru_cache(maxsize=1)
def _session() -> ExplicitProxySession:
    """复用单例 Session（连接池）。"""
    s = ExplicitProxySession()
    s.headers.update(_SEARCH_HEADERS)
    return s


@functools.lru_cache(maxsize=512)
def _search(keyword: str, proxy: str | None = None) -> tuple[dict[str, object], ...]:
    """调用搜索接口，返回原始数据元组（按 keyword 与固定出口缓存）。

    网络故障抛 ``requests`` 异常；查不到返回空元组。
    """
    params = {
        "input": keyword,
        "type": _SEARCH_TYPE_ALL,
        "count": _SEARCH_COUNT,
        "token": _SEARCH_TOKEN,
    }
    proxies = {"http": proxy, "https": proxy} if proxy else None
    try:
        resp = _session().get(
            _SEARCH_URL, params=params, timeout=_SEARCH_TIMEOUT_SEC, proxies=proxies
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        if proxy:
            raise type(exc)("名称搜索固定代理请求失败，请检查代理服务与认证") from None
        raise
    return _rows(resp.json())


def _rows(payload: object) -> tuple[dict[str, object], ...]:
    table = payload.get("QuotationCodeTable") if isinstance(payload, dict) else None
    data = table.get("Data") if isinstance(table, dict) else None
    return tuple(data or ())


def _is_json_object(text: str) -> bool:
    """协议校验：搜索接口恒返回 JSON 对象；封禁页 / 代理劫持页不是，按出口失败换 IP。"""
    try:
        return isinstance(json.loads(text), dict)
    except ValueError:
        return False


def _dynamic(settings: Settings) -> bool:
    """是否有动态代理可切：配了代理源、总开关打开且不是 never（与固定出口互斥）。"""
    return (
        not settings.proxy_url
        and bool(settings.proxy_api.strip())
        and settings.proxy_enabled
        and settings.proxy_mode != "never"
    )


@functools.lru_cache(maxsize=512)
def _search_routed(keyword: str, settings: Settings) -> tuple[dict[str, object], ...]:
    """经业务客户端的代理路由搜索：直连被封时自动切代理（重试、换 IP、回退探测同业务取数）。"""
    from em.application.market_data import _build_client

    text = _build_client(settings).get_text(
        _SEARCH_URL,
        {
            "input": keyword,
            "type": _SEARCH_TYPE_ALL,
            "count": _SEARCH_COUNT,
            "token": _SEARCH_TOKEN,
        },
        _SEARCH_HEADERS,
        validator=_is_json_object,
    )
    return _rows(json.loads(text))


def _lookup(name: str, settings: Settings | None) -> tuple[dict[str, object], ...]:
    settings = settings or Settings.from_env()
    if _dynamic(settings):
        return _search_routed(name, settings)
    return _search(name, settings.fixed_proxy)


def resolve_code(name: str, *, settings: Settings | None = None) -> StockRef | None:
    """中文名 → A 股证券引用（精确名匹配）。

    按 ``SecurityTypeName in {深A, 沪A, 京A}`` 过滤 A 股（含北交所，
    其 ``Classify=NEEQ`` 但 ``SecurityTypeName=京A``），再精确名匹配。
    查不到返回 ``None``；网络故障抛异常。
    """
    for d in _lookup(name, settings):
        sec_type = d.get("SecurityTypeName", "")
        if sec_type in _A_STOCK_MARKETS and d.get("Name") == name:
            return StockRef(
                code=str(d["Code"]), name=str(d["Name"]), market=_A_STOCK_MARKETS[sec_type]
            )
    return None


def resolve_board(name: str, *, settings: Settings | None = None) -> BoardRef | None:
    """中文名 → 板块引用（精确名匹配，``Classify=BK``）。

    查不到返回 ``None``；网络故障抛异常。
    """
    for d in _lookup(name, settings):
        if d.get("Classify") == "BK" and d.get("Name") == name:
            return BoardRef(code=str(d["Code"]), name=str(d["Name"]))
    return None


def reset_resolve_cache() -> None:
    """清空 resolve 缓存（测试用）。"""
    _search.cache_clear()
    _search_routed.cache_clear()

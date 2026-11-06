"""应用层服务：基于东财搜索接口的中文名→代码解析（单请求，轻量缓存）。

``searchapi.eastmoney.com/api/suggest/get`` 直连稳定（实测 30/30 零失败，avg 40ms），
无需走代理链路、无需预热、无需按日缓存。仅 ``lru_cache`` 防同会话重复请求。

返回约定：查不到返回 ``None``（不臆测，让调用方决定）；网络故障抛 ``requests`` 异常
（上层可重试或上抛）——以此区分"名字查不到"与"接口坏了"。
"""

from __future__ import annotations

import functools
from dataclasses import dataclass

import requests

_SEARCH_URL = "https://searchapi.eastmoney.com/api/suggest/get"
_SEARCH_TOKEN = "D2BF3E7AC4E7A1A2"
_SEARCH_TYPE_ALL = "14"
_SEARCH_COUNT = "20"
_SEARCH_TIMEOUT_SEC = 10
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
def _session() -> requests.Session:
    """复用单例 Session（连接池）。"""
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0", "Referer": "https://www.eastmoney.com/"})
    return s


@functools.lru_cache(maxsize=512)
def _search(keyword: str) -> tuple[dict[str, object], ...]:
    """调用搜索接口，返回原始数据元组（按 keyword 缓存）。

    网络故障抛 ``requests`` 异常；查不到返回空元组。
    """
    params = {
        "input": keyword,
        "type": _SEARCH_TYPE_ALL,
        "count": _SEARCH_COUNT,
        "token": _SEARCH_TOKEN,
    }
    resp = _session().get(_SEARCH_URL, params=params, timeout=_SEARCH_TIMEOUT_SEC)
    resp.raise_for_status()
    data = resp.json().get("QuotationCodeTable", {}).get("Data", []) or []
    return tuple(data)


def resolve_code(name: str) -> StockRef | None:
    """中文名 → A 股证券引用（精确名匹配）。

    按 ``SecurityTypeName in {深A, 沪A, 京A}`` 过滤 A 股（含北交所，
    其 ``Classify=NEEQ`` 但 ``SecurityTypeName=京A``），再精确名匹配。
    查不到返回 ``None``；网络故障抛异常。
    """
    for d in _search(name):
        sec_type = d.get("SecurityTypeName", "")
        if sec_type in _A_STOCK_MARKETS and d.get("Name") == name:
            return StockRef(code=str(d["Code"]), name=str(d["Name"]), market=_A_STOCK_MARKETS[sec_type])
    return None


def resolve_board(name: str) -> BoardRef | None:
    """中文名 → 板块引用（精确名匹配，``Classify=BK``）。

    查不到返回 ``None``；网络故障抛异常。
    """
    for d in _search(name):
        if d.get("Classify") == "BK" and d.get("Name") == name:
            return BoardRef(code=str(d["Code"]), name=str(d["Name"]))
    return None


def reset_resolve_cache() -> None:
    """清空 resolve 缓存（测试用）。"""
    _search.cache_clear()

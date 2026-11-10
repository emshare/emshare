"""请求构建：把查询句柄翻译为东财 clist 的渠道参数（渠道键空间只在此出现）。"""

import functools
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from typing import Any, Generic, TypeVar

from em.channels.eastmoney import config

T = TypeVar("T")


@dataclass(frozen=True)
class ClistRequest:
    """clist 接口请求句柄：host/fs/fields/fid/分页。"""

    host: str
    fs: str
    fields: str
    fid: str = "f3"
    page: int = 1
    page_size: int = 20

    def url(self) -> str:
        return f"{self.host}{config.CLIST_PATH}"

    def params(self) -> dict[str, Any]:
        return {
            "np": "1",
            "fltt": "1",
            "invt": "2",
            "fs": self.fs,
            "fields": self.fields,
            "fid": self.fid,
            "pn": str(self.page),
            "pz": str(self.page_size),
            "po": "1",
            "dect": "1",
            "ut": config.UT,
            "wbp2u": "|0|0|0|web",
        }


@dataclass(frozen=True)
class KlineRequest:
    """kline 接口请求句柄：host/secid/klt/fqt/期间。

    ``period`` 与 ``adjust`` 为规范化后的领域值，仅用于回填 ``KlineSeries`` 元数据。
    """

    host: str
    secid: str
    klt: int
    fqt: int
    beg: str = "0"
    end: str = "20500101"
    period: str = "day"
    adjust: str = "qfq"
    rtntype: str = "6"

    def url(self) -> str:
        return f"{self.host}{config.KLINE_PATH}"

    def params(self) -> dict[str, Any]:
        return {
            "fields1": config.KLINE_FIELDS1,
            "fields2": config.KLINE_FIELDS2,
            "ut": config.UT,
            "klt": str(self.klt),
            "fqt": str(self.fqt),
            "secid": self.secid,
            "beg": self.beg,
            "end": self.end,
            "rtntype": self.rtntype,
        }


@dataclass(frozen=True)
class TrendsRequest:
    """trends2 接口请求句柄：host/secid/ndays。"""

    host: str
    secid: str
    ndays: int = 1
    iscr: int = 0
    iscca: int = 0

    def url(self) -> str:
        return f"{self.host}{config.TRENDS_PATH}"

    def params(self) -> dict[str, Any]:
        return {
            "fields1": config.TRENDS_FIELDS1,
            "fields2": config.TRENDS_FIELDS2,
            "ut": config.UT,
            "secid": self.secid,
            "ndays": str(self.ndays),
            "iscr": str(self.iscr),
            "iscca": str(self.iscca),
        }


@dataclass(frozen=True)
class FundFlowRequest:
    """fflow/daykline 接口请求句柄：host/secid/lmt/klt。

    ``market`` 为规范化后的领域值，仅用于回填 ``FundFlowSeries`` 元数据。
    """

    host: str
    secid: str
    market: str = "sz"
    lmt: int = 0
    klt: int = 101

    def url(self) -> str:
        return f"{self.host}{config.FFLOW_PATH}"

    def params(self) -> dict[str, Any]:
        return {
            "lmt": str(self.lmt),
            "klt": str(self.klt),
            "fields1": config.FFLOW_FIELDS1,
            "fields2": config.FFLOW_FIELDS2,
            "ut": config.FFLOW_UT,
            "secid": self.secid,
        }


@dataclass(frozen=True)
class LimitPoolRequest:
    """push2ex 涨跌停股池请求句柄：host/path/sort/date，一次取整池。

    ``pool_type`` 与 ``date`` 为规范化后的领域值，用于回填 ``LimitPoolPage``。
    """

    host: str
    path: str
    sort: str
    date: str  # YYYYMMDD
    pool_type: str = "limit_up"
    page_size: int = config.LIMIT_POOL_PAGE_SIZE

    def url(self) -> str:
        return f"{self.host}{self.path}"

    def params(self) -> dict[str, Any]:
        return {
            "ut": config.PUSH2EX_UT,
            "dpt": "wz.ztzt",
            "Pageindex": "0",
            "pagesize": str(self.page_size),
            "sort": self.sort,
            "date": self.date,
        }


@dataclass(frozen=True)
class StockGetRequest:
    """push2 ``stock/get`` 单只证券请求句柄：host/secid/fields。

    ``fields`` 为 None 时不传该参数，上游返回默认字段集——五档盘口只在默认字段集里，
    显式列出 f11–f40 反而一个都拿不到（实测）。``market`` 为规范化后的领域值，仅用于回填模型。
    """

    host: str
    secid: str
    fields: str | None = None
    market: str | None = None

    def url(self) -> str:
        return f"{self.host}{config.STOCK_GET_PATH}"

    def params(self) -> dict[str, Any]:
        params: dict[str, Any] = {"fltt": "1", "invt": "2", "secid": self.secid}
        if self.fields is not None:
            params["fields"] = self.fields
        return params


def _changes_params(page_size: int) -> dict[str, Any]:
    """盘口异动 / 板块异动的公共参数：从第 0 页取，``page_size`` 足够大即一次取全量。"""
    return {
        "ut": config.PUSH2EX_UT,
        "dpt": "wzchanges",
        "pageindex": "0",
        "pagesize": str(page_size),
    }


@dataclass(frozen=True)
class StockChangesRequest:
    """push2ex 盘口异动请求句柄：host/上游 type，一次取最近交易日该类异动的全部记录。

    ``change_type`` 为规范化后的领域值，用于回填 ``StockChangesPage``；``type_code`` 是它的上游代码。
    """

    host: str
    type_code: int
    change_type: str
    page_size: int = config.CHANGES_PAGE_SIZE

    def url(self) -> str:
        return f"{self.host}{config.STOCK_CHANGES_PATH}"

    def params(self) -> dict[str, Any]:
        return {"type": str(self.type_code), **_changes_params(self.page_size)}


@dataclass(frozen=True)
class BoardChangesRequest:
    """push2ex 板块异动请求句柄：一次取最近交易日全部有异动的板块。"""

    host: str
    page_size: int = config.CHANGES_PAGE_SIZE

    def url(self) -> str:
        return f"{self.host}{config.BOARD_CHANGES_PATH}"

    def params(self) -> dict[str, Any]:
        return _changes_params(self.page_size)


@dataclass(frozen=True)
class DatacenterRequest(Generic[T]):
    """数据中心报表的单页请求句柄：报表名 / 列 / 过滤 / 排序 / 页码，``mapper`` 把一行映射为领域模型。

    ``columns`` 只列要用到的列（单页体积可降一个数量级），并包含 ``filter`` 用到的列：上游对
    拼错的过滤字段静默忽略、返回整张表，而拼错的返回列会报 9501，借此把上游改名暴露出来。
    ``latest_of`` 非空表示查询没给日期：先取该日期列的最新值（``latest_lookup``），
    再用 ``on_day`` 过滤到那一天。``distinct`` 为 True 时整行去重（只对已知会重复返回同一行的报表打开）。
    """

    report: str
    columns: tuple[str, ...]
    mapper: Callable[[dict[str, Any]], T]
    filter: str = ""
    sort_columns: tuple[str, ...] = ()
    sort_types: tuple[int, ...] = ()
    latest_of: str = ""
    distinct: bool = False
    page: int = 1
    page_size: int = config.DATACENTER_PAGE_SIZE
    host: str = config.DATACENTER_HOST

    def url(self) -> str:
        return f"{self.host}{config.DATACENTER_PATH}"

    def params(self) -> dict[str, Any]:
        params: dict[str, Any] = {
            "reportName": self.report,
            "columns": ",".join(self.columns),
            "pageNumber": str(self.page),
            "pageSize": str(self.page_size),
            "source": "WEB",
            "client": "WEB",
        }
        if self.sort_columns:
            params["sortColumns"] = ",".join(self.sort_columns)
            params["sortTypes"] = ",".join(str(t) for t in self.sort_types)
        if self.filter:
            params["filter"] = self.filter
        return params

    def with_page(self, page: int) -> "DatacenterRequest[T]":
        return replace(self, page=page)

    def latest_lookup(self) -> "DatacenterRequest[str | None]":
        """取 ``latest_of`` 列的最新值：只请求该列，按它倒序取 1 行，过滤条件同本请求。"""
        return DatacenterRequest(
            report=self.report,
            columns=(self.latest_of,),
            mapper=functools.partial(_day_of, self.latest_of),
            filter=self.filter,
            sort_columns=(self.latest_of,),
            sort_types=(-1,),
            page_size=1,
            host=self.host,
        )

    def on_day(self, day: str) -> "DatacenterRequest[T]":
        """把 ``latest_of`` 列过滤到 ``day``（``YYYY-MM-DD``），得到可以直接翻页的请求。"""
        return replace(
            self,
            filter=f"{self.filter}({self.latest_of}='{day}')",
            columns=unique_columns(self.columns, (self.latest_of,)),
            latest_of="",
        )


def unique_columns(*groups: Iterable[str]) -> tuple[str, ...]:
    """合并几组列名，去重并保持首次出现的顺序。"""
    return tuple(dict.fromkeys(c for group in groups for c in group))


def _day_of(column: str, row: dict[str, Any]) -> str | None:
    """``2026-11-06 00:00:00`` → ``2026-11-06``。"""
    value = row.get(column)
    return str(value)[:10] if value else None

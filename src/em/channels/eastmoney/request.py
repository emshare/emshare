"""请求构建：把查询句柄翻译为东财 clist 的渠道参数（渠道键空间只在此出现）。"""

from dataclasses import dataclass
from typing import Any

from em.channels.eastmoney import config


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

"""数据中心（datacenter-web）报表的公共部分：按列声明的行映射、单位换算、过滤条件、单页解析。

每个报表接口只声明“领域字段 ← 上游列 + 换算”（``Column``），本模块据此生成要请求的列与行映射，
几十张报表不再各写一遍解析代码。
"""

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Generic, TypeVar

from em.channels.eastmoney import config
from em.channels.eastmoney.request import DatacenterRequest, unique_columns
from em.domain.units import YUAN_PER_WAN, YUAN_PER_YI, as_float

T = TypeVar("T")

# ---------------------------------------------------------------- 字段换算


def text(value: Any) -> str | None:
    """文本：None、空串、``-`` 映射为 None。"""
    if value is None:
        return None
    s = str(value).strip()
    return s if s and s != "-" else None


def required_text(value: Any) -> str:
    """必填文本（代码 / 名称）：缺失时为空串，与其他模型的 code / name 一致。"""
    return text(value) or ""


def number(value: Any) -> float | None:
    return as_float(value)


def integer(value: Any) -> int | None:
    f = as_float(value)
    return int(f) if f is not None else None


def day(value: Any) -> str | None:
    """``2026-11-06 00:00:00`` → ``2026-11-06``。"""
    s = text(value)
    return s[:10] if s else None


def pct_of_ratio(value: Any) -> float | None:
    """比例 → %（``0.0215`` → ``2.15``）：数据中心有的列给比例、有的给 %，统一成本工程的 % 口径。"""
    f = as_float(value)
    return None if f is None else round(f * 100, 10)


def from_wan(value: Any) -> float | None:
    """万元 / 万股 → 元 / 股。"""
    f = as_float(value)
    return None if f is None else round(f * YUAN_PER_WAN, 4)


def from_yi(value: Any) -> float | None:
    """亿元 → 元。"""
    f = as_float(value)
    return None if f is None else round(f * YUAN_PER_YI, 4)


def market_of(value: Any) -> str | None:
    """``SECUCODE`` 后缀 → 领域市场：``000525.SZ`` → ``sz``，可连同代码传给 ``stock_kline_em``。"""
    s = text(value)
    if not s or "." not in s:
        return None
    suffix = s.rsplit(".", 1)[1].lower()
    return suffix if suffix in ("sh", "sz", "bj") else None


def codes_of(value: Any) -> tuple[str, ...]:
    """空格分隔的 ``SECUCODE`` 列表 → 代码元组：``600127.SH 600261.SH`` → ``("600127", "600261")``。"""
    s = text(value)
    return tuple(token.split(".", 1)[0] for token in s.split()) if s else ()


# ---------------------------------------------------------------- 列声明


@dataclass(frozen=True)
class Column:
    """一列映射：领域字段 ← 上游列经 ``convert`` 换算；``source`` 为元组时把几列的值一起交给 ``convert``。"""

    field: str
    source: str | tuple[str, ...]
    convert: Callable[[Any], Any] = text

    def sources(self) -> tuple[str, ...]:
        return self.source if isinstance(self.source, tuple) else (self.source,)


# 过滤条件里的列名：(COL>='x') / (COL="x") / (COL in (...)) / ( | COL="x")
_FILTER_COLUMN_RE = re.compile(r"\(\s*\|?\s*([A-Z][A-Z0-9_]*)\s*(?:>=|<=|<>|!=|=|>|<|\s+in\b)")


def filter_columns(filter: str) -> tuple[str, ...]:
    """过滤条件引用的列。这些列要一并请求：上游对拼错的过滤字段静默忽略（返回整张表），
    对拼错的返回列则报 9501，借此把上游改名暴露出来。"""
    return unique_columns(_FILTER_COLUMN_RE.findall(filter))


@dataclass(frozen=True)
class ReportSpec(Generic[T]):
    """一张数据中心报表：报表名、模型、列映射、默认排序。各接口据此拼请求，解析由 ``map_row`` 完成。

    ``key_columns`` 是不映射、但用来区分行的列（如龙虎榜的 ``TRADE_ID``），一并请求，
    保证整行去重时不会把两条真实记录当成一条。``distinct`` 只对已知会重复返回同一行的报表打开。
    """

    report: str
    model: Callable[..., T]
    columns: tuple[Column, ...]
    sort: tuple[tuple[str, int], ...] = ()  # (列, 1 升序 / -1 降序)
    key_columns: tuple[str, ...] = ()
    distinct: bool = False

    def map_row(self, row: dict[str, Any]) -> T:
        values: dict[str, Any] = {}
        for column in self.columns:
            if isinstance(column.source, tuple):
                values[column.field] = column.convert(tuple(row.get(s) for s in column.source))
            else:
                values[column.field] = column.convert(row.get(column.source))
        return self.model(**values)

    def request(self, filter: str = "", latest_of: str = "") -> DatacenterRequest[T]:
        """拼单页请求；``latest_of`` 非空表示查询没给日期，取该列最新的一天（见 ``DatacenterRequest``）。"""
        return DatacenterRequest(
            report=self.report,
            columns=unique_columns(
                *(c.sources() for c in self.columns),
                self.key_columns,
                filter_columns(filter),
                (latest_of,) if latest_of else (),
            ),
            mapper=self.map_row,
            filter=filter,
            sort_columns=tuple(c for c, _ in self.sort),
            sort_types=tuple(t for _, t in self.sort),
            latest_of=latest_of,
            distinct=self.distinct,
        )


# ---------------------------------------------------------------- 查询条件

_YMD_RE = re.compile(r"^\d{8}$")
_SAFE_VALUE_RE = re.compile(r"^[^\"'()]+$")
_BEIJING = timezone(timedelta(hours=8))
_QUARTER_ENDS = ("0331", "0630", "0930", "1231")


def dash_date(value: str, name: str = "date") -> str:
    """``YYYYMMDD`` → ``YYYY-MM-DD``。格式不对在本地报错：上游对其他写法只回 9501 语法错误。"""
    if not _YMD_RE.match(value or ""):
        raise ValueError(f"{name} 必须是 YYYYMMDD 格式，收到 {value!r}")
    try:
        datetime.strptime(value, "%Y%m%d")
    except ValueError:
        raise ValueError(f"{name} 不是有效日期，收到 {value!r}") from None
    return f"{value[:4]}-{value[4:6]}-{value[6:]}"


def date_span(
    start: str | None, end: str | None, now: datetime | None = None
) -> tuple[str, str] | None:
    """日期区间 ``YYYYMMDD`` → ``(YYYY-MM-DD, YYYY-MM-DD)``。

    都留空返回 None（调用方改取最近一个有数据的交易日）；只给 ``start`` 时取到北京时间今天；
    只给 ``end`` 时只取那一天。
    """
    if not start and not end:
        return None
    if start:
        first = dash_date(start, "start_date")
        if end:
            last = dash_date(end, "end_date")
        else:
            last = (now or datetime.now(_BEIJING)).astimezone(_BEIJING).date().isoformat()
    else:
        first = last = dash_date(end or "", "end_date")
    if first > last:
        raise ValueError(f"start_date {first} 晚于 end_date {last}")
    return first, last


def report_period(value: str | None, now: datetime | None = None) -> str:
    """报告期 ``YYYYMMDD``（季末）→ ``YYYY-MM-DD``；留空取北京时间今天之前最近的季末。"""
    if not value:
        today = (now or datetime.now(_BEIJING)).astimezone(_BEIJING).date()
        return last_quarter_end(today).isoformat()
    dashed = dash_date(value, "report_date")
    if value[4:] not in _QUARTER_ENDS:
        raise ValueError(f"report_date 必须是季末（0331 / 0630 / 0930 / 1231），收到 {value!r}")
    return dashed


def last_quarter_end(today: date) -> date:
    """今天之前（不含今天）最近的季末：季度最后一天当天数据还没出齐。"""
    for month, mday in ((12, 31), (9, 30), (6, 30), (3, 31)):
        candidate = date(today.year, month, mday)
        if candidate < today:
            return candidate
    return date(today.year - 1, 12, 31)


def safe_value(value: str, name: str) -> str:
    """拼进过滤条件的取值（代码 / 名称）：不得含引号或括号，否则会改写过滤语法。"""
    if not value or not _SAFE_VALUE_RE.match(value):
        raise ValueError(f"{name} 不合法：{value!r}")
    return value


def between(column: str, first: str, last: str) -> str:
    return f"({column}>='{first}')({column}<='{last}')"


def on(column: str, dashed: str) -> str:
    return f"({column}='{dashed}')"


def equals(column: str, value: str) -> str:
    return f'({column}="{value}")'


def scope_filter(scope: str) -> str:
    """市场范围 → 过滤条件；未知回退 all（不过滤）。"""
    return config.DATACENTER_SCOPE_FILTERS.get(scope, "")


def normalize_scope(scope: str) -> str:
    return scope if scope in config.DATACENTER_SCOPE_FILTERS else "all"


# ---------------------------------------------------------------- 单页解析


def _code(data: dict[str, Any]) -> int | None:
    """返回码：一般是整数，参数类型错误时上游给字符串 ``"200"``（实测），统一成整数。"""
    value = data.get("code")
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value)
    return None


def is_answer(data: Any) -> bool:
    """协议校验：code 0（有数据）/ 9201（查无数据）/ 9501、200（查询写错）都是上游的正常答复。

    9701 服务器繁忙、未知 code、HTML 劫持页、非 JSON 一律判失败，由传输层换 IP 重试。
    """
    if not isinstance(data, dict):
        return False
    code = _code(data)
    if code == config.DATACENTER_OK:
        return isinstance(data.get("result"), dict)
    return code == config.DATACENTER_EMPTY or code in config.DATACENTER_QUERY_ERRORS


def is_query_error(data: dict[str, Any]) -> bool:
    return _code(data) in config.DATACENTER_QUERY_ERRORS


@dataclass(frozen=True)
class ReportChunk(Generic[T]):
    """一页的映射结果：上游总条数 / 总页数，本页各行及其整行去重键（上游原始行的规范化 JSON）。"""

    total: int
    pages: int
    items: tuple[T, ...]
    keys: tuple[str, ...]


def to_report_chunk(data: dict[str, Any], mapper: Callable[[dict[str, Any]], T]) -> ReportChunk[T]:
    """把单页响应映射为 ``ReportChunk``；9201 查无数据时 ``result`` 为 null，映射为空页。"""
    result = data.get("result")
    if not isinstance(result, dict):
        return ReportChunk(total=0, pages=0, items=(), keys=())
    rows = [row for row in (result.get("data") or []) if isinstance(row, dict)]
    return ReportChunk(
        total=int(result.get("count") or 0),
        pages=int(result.get("pages") or 0),
        items=tuple(mapper(row) for row in rows),
        keys=tuple(
            json.dumps(row, sort_keys=True, ensure_ascii=False, default=str) for row in rows
        ),
    )

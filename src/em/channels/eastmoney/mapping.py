"""报文映射：响应解析（JSON/JSONP）+ ``f*`` 字段 -> 领域模型（单位换算在此消化）。"""

import json
import re
from typing import Any

from em.domain.models import (
    BoardFundFlow,
    BoardFundFlowSeries,
    FundFlow,
    FundFlowSeries,
    Kline,
    KlineSeries,
    Quote,
    QuotePage,
    Trend,
    TrendSeries,
)
from em.domain.units import as_float, scaled

_JSONP_RE = re.compile(r"\((\{.*\})\)\s*;?\s*$", re.S)


def _as_dict(value: Any) -> dict[str, Any] | None:
    """仅接受 JSON 对象；数组 / 标量等非对象结构一律返回 None。"""
    return value if isinstance(value, dict) else None


def parse_jsonp(text: str) -> dict[str, Any] | None:
    """解析响应：兼容纯 JSON 与 JSONP 包裹；失败返回 None。

    不传 ``cb`` 时东财返回纯 JSON，传了则是 ``cb(...)`` 包裹，此处两者都接。
    仅接受 JSON 对象，非对象结构视为解析失败。
    """
    text = (text or "").strip()
    if not text:
        return None
    try:
        return _as_dict(json.loads(text))
    except json.JSONDecodeError:
        pass
    match = _JSONP_RE.search(text)
    if not match:
        return None
    try:
        return _as_dict(json.loads(match.group(1)))
    except json.JSONDecodeError:
        return None


def is_ok(data: dict[str, Any] | None) -> bool:
    """接口响应是否成功（rc == 0）。"""
    return data is not None and data.get("rc") == 0


def to_quote_page(data: dict[str, Any], flow_field: str = "f62") -> QuotePage:
    """把 clist 响应映射为 ``QuotePage``；``flow_field`` 指定主力净流入字段。"""
    block = data.get("data") or {}
    items = tuple(_to_quote(it, flow_field) for it in (block.get("diff") or []))
    return QuotePage(total=int(block.get("total") or 0), items=items)


def _to_quote(item: dict[str, Any], flow_field: str) -> Quote:
    return Quote(
        code=str(item.get("f12", "")),
        name=str(item.get("f14", "")),
        price=scaled(item.get("f2")),
        change_pct=scaled(item.get("f3")),
        change=scaled(item.get("f4")),
        main_net_inflow=as_float(item.get(flow_field)),
        turnover=as_float(item.get("f6")),
        turnover_rate=scaled(item.get("f8")),
    )


def to_kline_series(data: dict[str, Any], period: str = "day", adjust: str = "qfq") -> KlineSeries:
    """把 kline 响应映射为 ``KlineSeries``。

    ``klines`` 每项为逗号分隔字符串，字段依次为
    ``日期,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率``；
    价格不做 100 倍还原（与 ``fltt=1`` 的 clist 不同）。分钟级周期（5m/15m/30m/60m）
    时首字段为 ``YYYY-MM-DD HH:MM`` 时间戳，字段顺序与日级一致。
    """
    block = data.get("data") or {}
    items = tuple(_to_kline(line) for line in (block.get("klines") or []))
    return KlineSeries(
        code=str(block.get("code", "")),
        name=str(block.get("name", "")),
        period=period,
        adjust=adjust,
        items=items,
    )


def _to_kline(line: Any) -> Kline:
    parts: list[str | None] = list(str(line).split(","))
    parts += [None] * (11 - len(parts))
    return Kline(
        date=str(parts[0] or ""),
        open=as_float(parts[1]),
        close=as_float(parts[2]),
        high=as_float(parts[3]),
        low=as_float(parts[4]),
        volume=as_float(parts[5]),
        amount=as_float(parts[6]),
        amplitude=as_float(parts[7]),
        change_pct=as_float(parts[8]),
        change=as_float(parts[9]),
        turnover_rate=as_float(parts[10]),
    )


def to_trend_series(data: dict[str, Any], ndays: int = 1) -> TrendSeries:
    """把 trends2 响应映射为 ``TrendSeries``。

    ``trends`` 每项为逗号分隔字符串，字段依次为
    ``时间,最新价,均价,最高,最低,成交量,成交额,均价2``；价格不做 100 倍还原。
    """
    block = data.get("data") or {}
    items = tuple(_to_trend(line) for line in (block.get("trends") or []))
    return TrendSeries(
        code=str(block.get("code", "")),
        name=str(block.get("name", "")),
        pre_close=as_float(block.get("preClose")),
        pre_price=as_float(block.get("prePrice")),
        ndays=ndays,
        items=items,
    )


def _to_trend(line: Any) -> Trend:
    parts: list[str | None] = list(str(line).split(","))
    parts += [None] * (8 - len(parts))
    return Trend(
        time=str(parts[0] or ""),
        price=as_float(parts[1]),
        avg_price=as_float(parts[2]),
        high=as_float(parts[3]),
        low=as_float(parts[4]),
        volume=as_float(parts[5]),
        amount=as_float(parts[6]),
        avg_price2=as_float(parts[7]),
    )


def to_fund_flow_series(data: dict[str, Any], market: str = "sz") -> FundFlowSeries:
    """把 fflow/daykline 响应映射为 ``FundFlowSeries``。

    ``klines`` 每项为逗号分隔字符串，字段依次为
    ``日期,主力净额,小单净额,中单净额,大单净额,超大单净额,主力占比,小单占比,中单占比,大单占比,超大单占比,收盘价,涨跌幅``
    （上游 f51–f63；f64/f65 语义未确认，直接忽略）；金额不做 100 倍还原。
    """
    block = data.get("data") or {}
    items = tuple(_to_fund_flow(line) for line in (block.get("klines") or []))
    return FundFlowSeries(
        code=str(block.get("code", "")),
        name=str(block.get("name", "")),
        market=market,
        items=items,
    )


def _to_fund_flow(line: Any) -> FundFlow:
    parts: list[str | None] = list(str(line).split(","))
    parts += [None] * (13 - len(parts))
    return FundFlow(
        date=str(parts[0] or ""),
        main_net_inflow=as_float(parts[1]),
        small_net_inflow=as_float(parts[2]),
        medium_net_inflow=as_float(parts[3]),
        large_net_inflow=as_float(parts[4]),
        xlarge_net_inflow=as_float(parts[5]),
        main_net_pct=as_float(parts[6]),
        small_net_pct=as_float(parts[7]),
        medium_net_pct=as_float(parts[8]),
        large_net_pct=as_float(parts[9]),
        xlarge_net_pct=as_float(parts[10]),
        close=as_float(parts[11]),
        change_pct=as_float(parts[12]),
    )


def to_board_fund_flow_series(data: dict[str, Any]) -> BoardFundFlowSeries:
    """把板块 fflow/daykline 响应映射为 ``BoardFundFlowSeries``。

    字段同 ``to_fund_flow_series`` 的前 11 个（``f51``–``f61``），忽略
    ``f62``/``f63``（板块口径不含收盘价 / 涨跌幅）；金额不做 100 倍还原。
    """
    block = data.get("data") or {}
    items = tuple(_to_board_fund_flow(line) for line in (block.get("klines") or []))
    return BoardFundFlowSeries(
        code=str(block.get("code", "")),
        name=str(block.get("name", "")),
        items=items,
    )


def _to_board_fund_flow(line: Any) -> BoardFundFlow:
    parts: list[str | None] = list(str(line).split(","))
    parts += [None] * (11 - len(parts))
    return BoardFundFlow(
        date=str(parts[0] or ""),
        main_net_inflow=as_float(parts[1]),
        small_net_inflow=as_float(parts[2]),
        medium_net_inflow=as_float(parts[3]),
        large_net_inflow=as_float(parts[4]),
        xlarge_net_inflow=as_float(parts[5]),
        main_net_pct=as_float(parts[6]),
        small_net_pct=as_float(parts[7]),
        medium_net_pct=as_float(parts[8]),
        large_net_pct=as_float(parts[9]),
        xlarge_net_pct=as_float(parts[10]),
    )

"""报文映射：响应解析（JSON/JSONP）+ ``f*`` 字段 -> 领域模型（单位换算在此消化）。"""

import json
import re
from typing import Any

from em.channels.eastmoney import config
from em.domain.models import (
    Board,
    BoardFundFlow,
    BoardFundFlowSeries,
    BoardListPage,
    FundFlow,
    FundFlowSeries,
    FundListPage,
    FundQuote,
    HkQuote,
    HkStockListPage,
    IndexListPage,
    IndexQuote,
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


def to_board_list_page(data: dict[str, Any]) -> BoardListPage:
    """把 clist 板块列表响应映射为 ``BoardListPage``。

    ``fltt=1`` 时价格 / 涨跌幅 / 换手率放大 100 倍，用 ``scaled`` 还原；
    成交额（f20）与上涨 / 下跌家数（f104 / f105）为原始整数，不还原。
    """
    block = data.get("data") or {}
    items = tuple(_to_board(it) for it in (block.get("diff") or []))
    return BoardListPage(total=int(block.get("total") or 0), items=items)


def _to_int(value: Any) -> int | None:
    """安全转 int；None 或不可转换返回 None。"""
    f = as_float(value)
    return int(f) if f is not None else None


def _to_board(item: dict[str, Any]) -> Board:
    return Board(
        code=str(item.get("f12", "")),
        name=str(item.get("f14", "")),
        price=scaled(item.get("f2")),
        change_pct=scaled(item.get("f3")),
        change=scaled(item.get("f4")),
        turnover=as_float(item.get("f20")),
        turnover_rate=scaled(item.get("f8")),
        up_count=_to_int(item.get("f104")),
        down_count=_to_int(item.get("f105")),
        leader_code=str(item.get("f140") or "") or None,
        leader_name=str(item.get("f128") or "") or None,
        leader_change_pct=scaled(item.get("f136")),
        laggard_code=str(item.get("f208") or "") or None,
        laggard_name=str(item.get("f207") or "") or None,
        laggard_change_pct=scaled(item.get("f222")),
    )


def to_index_list_page(data: dict[str, Any]) -> IndexListPage:
    """把 clist 指数列表响应映射为 ``IndexListPage``。

    ``fltt=1`` 时点位 / 涨跌幅 / 振幅 / 量比放大 100 倍，用 ``scaled`` 还原；
    成交量（f5）与成交额（f6）为原值。停牌或未开盘的指数上游返回 ``"-"``，映射为 ``None``。
    """
    block = data.get("data") or {}
    items = tuple(_to_index(it) for it in (block.get("diff") or []))
    return IndexListPage(total=int(block.get("total") or 0), items=items)


def _index_market(prefix: Any, code: str) -> str | None:
    """f13（secid 市场前缀）-> 领域市场；北证指数也挂在 0 前缀下，按 899 代码段区分。"""
    key = _to_int(prefix)
    market = config.INDEX_MARKETS.get(key) if key is not None else None
    if market == "sz" and code.startswith(config.BJ_INDEX_CODE_PREFIX):
        return "bj"
    return market


def _to_index(item: dict[str, Any]) -> IndexQuote:
    code = str(item.get("f12", ""))
    return IndexQuote(
        code=code,
        name=str(item.get("f14", "")),
        market=_index_market(item.get("f13"), code),
        price=scaled(item.get("f2")),
        change_pct=scaled(item.get("f3")),
        change=scaled(item.get("f4")),
        volume=as_float(item.get("f5")),
        turnover=as_float(item.get("f6")),
        amplitude=scaled(item.get("f7")),
        high=scaled(item.get("f15")),
        low=scaled(item.get("f16")),
        open=scaled(item.get("f17")),
        pre_close=scaled(item.get("f18")),
        volume_ratio=scaled(item.get("f10")),
    )


def _price_factor(item: dict[str, Any]) -> float:
    """价格放大倍数：``fltt=1`` 时价格按 ``10 ** f1`` 放大（A 股 f1=2，港股 f1=3）。"""
    decimals = _to_int(item.get("f1"))
    return 10.0 ** (config.DEFAULT_PRICE_DECIMALS if decimals is None else decimals)


def to_hk_stock_list_page(data: dict[str, Any]) -> HkStockListPage:
    """把 clist 港股列表响应映射为 ``HkStockListPage``。

    港股价格有 3 位小数（f1=3），价格类字段按 ``10 ** f1`` 还原，不能套用 A 股的 100 倍；
    涨跌幅仍放大 100 倍。成交量（f5，单位股）与成交额（f6，港元）为原值。
    停牌或无成交的股票上游返回 ``"-"``，映射为 ``None``。
    """
    block = data.get("data") or {}
    items = tuple(_to_hk_quote(it) for it in (block.get("diff") or []))
    return HkStockListPage(total=int(block.get("total") or 0), items=items)


def _to_hk_quote(item: dict[str, Any]) -> HkQuote:
    factor = _price_factor(item)
    return HkQuote(
        code=str(item.get("f12", "")),
        name=str(item.get("f14", "")),
        price=scaled(item.get("f2"), factor),
        change_pct=scaled(item.get("f3")),
        change=scaled(item.get("f4"), factor),
        open=scaled(item.get("f17"), factor),
        high=scaled(item.get("f15"), factor),
        low=scaled(item.get("f16"), factor),
        pre_close=scaled(item.get("f18"), factor),
        volume=as_float(item.get("f5")),
        turnover=as_float(item.get("f6")),
    )


def to_fund_list_page(data: dict[str, Any]) -> FundListPage:
    """把 clist 场内基金列表响应映射为 ``FundListPage``。

    基金价格有 3 位小数（f1=3），价格类字段按 ``10 ** f1`` 还原；涨跌幅 / 换手率 / 折价率
    放大 100 倍；IOPV（f441）在 ``fltt=1`` 下也是原值，不还原。成交量（手）、成交额与市值为原值。
    停牌基金上游返回 ``"-"``，映射为 ``None``。
    """
    block = data.get("data") or {}
    items = tuple(_to_fund_quote(it) for it in (block.get("diff") or []))
    return FundListPage(total=int(block.get("total") or 0), items=items)


def _to_fund_quote(item: dict[str, Any]) -> FundQuote:
    factor = _price_factor(item)
    key = _to_int(item.get("f13"))
    return FundQuote(
        code=str(item.get("f12", "")),
        name=str(item.get("f14", "")),
        market=config.FUND_MARKETS.get(key) if key is not None else None,
        price=scaled(item.get("f2"), factor),
        iopv=as_float(item.get("f441")),
        discount_rate=scaled(item.get("f402")),
        change_pct=scaled(item.get("f3")),
        change=scaled(item.get("f4"), factor),
        volume=as_float(item.get("f5")),
        turnover=as_float(item.get("f6")),
        open=scaled(item.get("f17"), factor),
        high=scaled(item.get("f15"), factor),
        low=scaled(item.get("f16"), factor),
        pre_close=scaled(item.get("f18"), factor),
        turnover_rate=scaled(item.get("f8")),
        float_market_cap=as_float(item.get("f21")),
        total_market_cap=as_float(item.get("f20")),
    )

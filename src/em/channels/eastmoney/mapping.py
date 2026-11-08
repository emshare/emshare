"""报文映射：响应解析（JSON/JSONP）+ ``f*`` 字段 -> 领域模型（单位换算在此消化）。"""

import json
import re
from typing import Any

from em.channels.eastmoney import config
from em.domain.models import (
    Board,
    BoardChange,
    BoardChangesPage,
    BoardFundFlow,
    BoardFundFlowSeries,
    BoardListPage,
    ChangeTypeCount,
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
    LimitPoolPage,
    LimitPoolStock,
    OrderLevel,
    Quote,
    QuotePage,
    StockBidAsk,
    StockChange,
    StockChangesPage,
    StockInfo,
    Trend,
    TrendSeries,
)
from em.domain.units import YUAN_PER_WAN, as_float, scaled

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


def _price_factor(item: dict[str, Any], decimals_key: str = "f1") -> float:
    """价格放大倍数：``fltt=1`` 时价格按 ``10 ** 小数位`` 放大（A 股 2 位，港股 / 基金 3 位）。

    小数位字段：clist 是 ``f1``，stock/get 是 ``f59``。
    """
    decimals = _to_int(item.get(decimals_key))
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


def _pool_price(value: Any) -> float | None:
    """股池价格固定放大 1000 倍；北交所新股首日无涨停价时上游给哨兵值，映射为 None。"""
    if _to_int(value) == config.NO_LIMIT_PRICE_SENTINEL:
        return None
    return scaled(value, config.PUSH2EX_PRICE_FACTOR)


def _hms(value: Any) -> str | None:
    """把 ``92500`` / ``143051`` 这类整数时间转成 ``09:25:00`` / ``14:30:51``。"""
    n = _to_int(value)
    if n is None or n < 0:
        return None
    s = f"{n:06d}"
    return f"{s[:2]}:{s[2:4]}:{s[4:]}"


def _ymd(value: Any) -> str | None:
    """把 ``20261106`` 这类整数日期转成 ``2026-11-06``。"""
    n = _to_int(value)
    if n is None or n <= 0:
        return None
    s = f"{n:08d}"
    return f"{s[:4]}-{s[4:6]}-{s[6:]}"


def _push2ex_market(prefix: Any, code: str) -> str | None:
    """push2ex 个股 ``m`` -> 领域市场；北交所也挂在 0 前缀下，按代码段识别为 bj。"""
    key = _to_int(prefix)
    market = config.PUSH2EX_MARKETS.get(key) if key is not None else None
    if market == "sz" and code.startswith(config.BJ_STOCK_CODE_PREFIXES):
        return "bj"
    return market


def _flag(value: Any) -> bool | None:
    n = _to_int(value)
    return None if n is None else n == 1


def to_limit_pool_page(data: dict[str, Any], pool_type: str, date: str) -> LimitPoolPage:
    """把 push2ex 股池响应映射为 ``LimitPoolPage``。

    ``date`` 是请求的 ``YYYYMMDD``。上游 ``qdate`` 恒为最近交易日，与请求日期无关：
    请求今天或未来时数据属于 ``qdate``，请求过去的日期时数据属于该日期（非交易日为空池）。
    所以数据实际日期取两者中较早的那个。
    """
    block = data.get("data") or {}
    items = tuple(_to_pool_stock(it) for it in (block.get("pool") or []))
    requested = _to_int(date)
    latest = _to_int(block.get("qdate"))
    actual = min(requested, latest) if requested is not None and latest is not None else requested
    return LimitPoolPage(
        pool_type=pool_type,
        date=_ymd(actual) or "",
        total=int(block.get("tc") or 0),
        items=items,
    )


def _to_pool_stock(item: dict[str, Any]) -> LimitPoolStock:
    code = str(item.get("c", ""))
    raw_stat = item.get("zttj")
    stat: dict[str, Any] = raw_stat if isinstance(raw_stat, dict) else {}
    reason = _to_int(item.get("cc"))
    return LimitPoolStock(
        code=code,
        name=str(item.get("n", "")),
        market=_push2ex_market(item.get("m"), code),
        price=_pool_price(item.get("p")),
        change_pct=as_float(item.get("zdp")),
        turnover=as_float(item.get("amount")),
        float_market_cap=as_float(item.get("ltsz")),
        total_market_cap=as_float(item.get("tshare")),
        turnover_rate=as_float(item.get("hs")),
        industry=str(item["hybk"]) if item.get("hybk") else None,
        stat_days=_to_int(stat.get("days")),
        stat_limit_ups=_to_int(stat.get("ct")),
        limit_up_price=_pool_price(item.get("ztp")),
        seal_fund=as_float(item.get("fund")),
        first_seal_time=_hms(item.get("fbt")),
        last_seal_time=_hms(item.get("lbt")),
        broken_count=_to_int(item.get("zbc")),
        limit_up_streak=_to_int(item.get("lbc")),
        prev_seal_time=_hms(item.get("yfbt")),
        prev_limit_up_streak=_to_int(item.get("ylbc")),
        amplitude=as_float(item.get("zf")),
        speed=as_float(item.get("zs")),
        volume_ratio=as_float(item.get("lb")),
        new_high=_flag(item.get("nh")),
        reason=config.STRONG_POOL_REASONS.get(reason) if reason is not None else None,
        open_days=_to_int(item.get("ods")),
        open_date=_ymd(item.get("od")),
        listing_date=_ymd(item.get("ipod")),
        pe=as_float(item.get("pe")),
        board_turnover=as_float(item.get("fba")),
        limit_down_streak=_to_int(item.get("days")),
        open_count=_to_int(item.get("oc")),
    )


def is_security_not_found(data: dict[str, Any] | None) -> bool:
    """stock/get 查无此券：rc 为 100 / 102 且 data 为 null（实测）。"""
    return (
        isinstance(data, dict)
        and data.get("rc") in config.STOCK_NOT_FOUND_RCS
        and data.get("data") is None
    )


def to_stock_info(data: dict[str, Any], market: str | None = None) -> StockInfo:
    """把 stock/get（显式字段集）映射为 ``StockInfo``。

    最新价按 ``10 ** f59`` 还原；股本（股）与市值（元）为原值；上市日期 ``20010827`` → ``2001-08-27``。
    """
    item = data.get("data") or {}
    factor = _price_factor(item, "f59")
    return StockInfo(
        code=str(item.get("f57", "")),
        name=str(item.get("f58", "")),
        market=market,
        industry=str(item["f127"]) if item.get("f127") not in (None, "", "-") else None,
        listing_date=_ymd(item.get("f189")),
        price=scaled(item.get("f43"), factor),
        total_shares=as_float(item.get("f84")),
        float_shares=as_float(item.get("f85")),
        total_market_cap=as_float(item.get("f116")),
        float_market_cap=as_float(item.get("f117")),
    )


# 五档字段：(价格, 数量)。买一 f19/f20 … 买五 f11/f12；卖一 f39/f40 … 卖五 f31/f32
_BID_FIELDS = (("f19", "f20"), ("f17", "f18"), ("f15", "f16"), ("f13", "f14"), ("f11", "f12"))
_ASK_FIELDS = (("f39", "f40"), ("f37", "f38"), ("f35", "f36"), ("f33", "f34"), ("f31", "f32"))


def _levels(
    item: dict[str, Any], fields: tuple[tuple[str, str], ...], factor: float
) -> tuple[OrderLevel, ...]:
    return tuple(
        OrderLevel(price=scaled(item.get(p), factor), volume=as_float(item.get(v)))
        for p, v in fields
    )


def to_stock_bid_ask(data: dict[str, Any], market: str | None = None) -> StockBidAsk:
    """把 stock/get（默认字段集）映射为 ``StockBidAsk``。

    价格类字段（含五档价格）按 ``10 ** f59`` 还原；量比放大 100 倍；成交量、外盘、五档挂单量
    单位为手（原值，akshare 乘 100 换成股），成交额为原值。无涨跌幅限制时涨跌停价为 ``"-"`` → None。
    """
    item = data.get("data") or {}
    factor = _price_factor(item, "f59")
    return StockBidAsk(
        code=str(item.get("f57", "")),
        name=str(item.get("f58", "")),
        market=market,
        price=scaled(item.get("f43"), factor),
        avg_price=scaled(item.get("f71"), factor),
        open=scaled(item.get("f46"), factor),
        high=scaled(item.get("f44"), factor),
        low=scaled(item.get("f45"), factor),
        pre_close=scaled(item.get("f60"), factor),
        limit_up=scaled(item.get("f51"), factor),
        limit_down=scaled(item.get("f52"), factor),
        volume=as_float(item.get("f47")),
        turnover=as_float(item.get("f48")),
        outer_volume=as_float(item.get("f49")),
        volume_ratio=scaled(item.get("f50")),
        bids=_levels(item, _BID_FIELDS, factor),
        asks=_levels(item, _ASK_FIELDS, factor),
    )


# 上游 type -> 英文异动类型；8217–8222 等未公开类型不在表内，映射为 None
_CHANGE_TYPE_BY_CODE = {code: name for name, code in config.CHANGE_TYPE_CODES.items()}
# 相关信息 i 逗号分隔后，价格与涨跌幅（比例）的位置（实测，见 stock_changes_em 文档）：
# 封涨停 / 封跌停板为“封板价,?,价格,涨跌幅”，打开涨停 / 跌停板为“价格,涨跌幅”，其余为“x,价格,涨跌幅”
_CHANGE_PRICE_PCT_INDEX = {
    "limit_up_sealed": (2, 3),
    "limit_down_sealed": (2, 3),
    "limit_up_opened": (0, 1),
    "limit_down_opened": (0, 1),
}
_DEFAULT_PRICE_PCT_INDEX = (1, 2)
# 大笔买入 / 卖出、有大买盘 / 卖盘的相关信息为“股数,价格,涨跌幅,金额”
_TRADE_CHANGE_TYPES = frozenset({"big_buy", "big_sell", "big_bid", "big_ask"})


def _ratio_pct(value: Any) -> float | None:
    """上游涨跌幅是比例（``0.100198``），转成 %；保留 4 位即原值精度，避免乘法尾差。"""
    f = as_float(value)
    return None if f is None else round(f * 100, 4)


def _change_type(value: Any) -> str | None:
    """上游 type 代码 -> 英文异动类型；未公开类型或缺失为 None。"""
    code = _to_int(value)
    return _CHANGE_TYPE_BY_CODE.get(code) if code is not None else None


def _info_part(parts: list[str], index: int) -> str | None:
    return parts[index] if index < len(parts) else None


def to_stock_changes_page(data: dict[str, Any], change_type: str) -> StockChangesPage:
    """把 push2ex getAllStockChanges 响应映射为 ``StockChangesPage``（当天无记录时 data 为 null）。"""
    block = data.get("data") or {}
    items = tuple(_to_stock_change(it) for it in (block.get("allstock") or []))
    return StockChangesPage(change_type=change_type, total=int(block.get("tc") or 0), items=items)


def _to_stock_change(item: dict[str, Any]) -> StockChange:
    code = str(item.get("c", ""))
    change_type = _change_type(item.get("t"))
    info = str(item["i"]) if item.get("i") is not None else None
    parts = info.split(",") if info else []
    price_at, pct_at = (
        _CHANGE_PRICE_PCT_INDEX.get(change_type, _DEFAULT_PRICE_PCT_INDEX)
        if change_type
        else _DEFAULT_PRICE_PCT_INDEX
    )
    trade = change_type in _TRADE_CHANGE_TYPES
    return StockChange(
        time=_hms(item.get("tm")) or "",
        code=code,
        name=str(item.get("n", "")),
        market=_push2ex_market(item.get("m"), code),
        change_type=change_type,
        price=as_float(_info_part(parts, price_at)),
        change_pct=_ratio_pct(_info_part(parts, pct_at)),
        volume=as_float(_info_part(parts, 0)) if trade else None,
        amount=as_float(_info_part(parts, 3)) if trade else None,
        info=info,
    )


def to_board_changes_page(data: dict[str, Any]) -> BoardChangesPage:
    """把 push2ex getAllBKChanges 响应映射为 ``BoardChangesPage``。

    ``dt``（``20261106150000``）拆成数据日期与时间；主力净流入 ``zjl`` 单位万元，换算成元。
    """
    block = data.get("data") or {}
    stamp = _to_int(block.get("dt"))
    digits = f"{stamp:014d}" if stamp is not None and stamp > 0 else ""
    items = tuple(_to_board_change(it) for it in (block.get("allbk") or []))
    return BoardChangesPage(
        date=_ymd(digits[:8]) or "",
        time=_hms(digits[8:]) or "",
        total=int(block.get("tc") or 0),
        items=items,
    )


def _to_board_change(item: dict[str, Any]) -> BoardChange:
    raw_top = item.get("ms")
    top: dict[str, Any] = raw_top if isinstance(raw_top, dict) else {}
    top_code = str(top["c"]) if top.get("c") else None
    inflow_wan = as_float(item.get("zjl"))
    return BoardChange(
        code=str(item.get("c", "")),
        name=str(item.get("n", "")),
        change_pct=as_float(item.get("u")),
        main_net_inflow=None if inflow_wan is None else round(inflow_wan * YUAN_PER_WAN, 2),
        change_count=_to_int(item.get("ct")),
        top_stock_code=top_code,
        top_stock_name=str(top["n"]) if top.get("n") else None,
        top_stock_market=_push2ex_market(top.get("m"), top_code) if top_code else None,
        top_stock_change_type=_change_type(top.get("t")),
        type_counts=_type_counts(item.get("ydl")),
    )


def _type_counts(raw: Any) -> tuple[ChangeTypeCount, ...]:
    """板块各类异动次数：只保留 22 种已知类型（东财页面同样不展示未公开类型），顺序同上游。"""
    counts: list[ChangeTypeCount] = []
    for entry in raw if isinstance(raw, list) else []:
        if not isinstance(entry, dict):
            continue
        change_type = _change_type(entry.get("t"))
        count = _to_int(entry.get("ct"))
        if change_type is not None and count is not None:
            counts.append(ChangeTypeCount(change_type=change_type, count=count))
    return tuple(counts)

"""接口检索层：提供接口发现与元数据查询能力，对齐 akshare ``search`` / ``interface_info`` / ``list_categories``。

核心函数返回纯 Python 结构（``list[dict]`` / ``dict``），不依赖 pandas；
``search_df`` / ``list_categories_df`` 为 DataFrame 包装（需 ``pip install pandas``）。
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

from em.core.errors import InterfaceNotFoundError

if TYPE_CHECKING:
    import pandas as pd

# ------------------------------------------------------------------ 元数据

_QUOTE_FIELDS = (
    ("code", "str", "—", "证券代码"),
    ("name", "str", "—", "证券简称"),
    ("price", "float | None", "元", "最新价"),
    ("change_pct", "float | None", "%", "涨跌幅"),
    ("change", "float | None", "元", "涨跌额"),
    ("main_net_inflow", "float | None", "元", "主力净流入（按 period 周期）"),
    ("turnover", "float | None", "元", "成交额"),
    ("turnover_rate", "float | None", "%", "换手率"),
)

_KLINE_FIELDS = (
    ("date", "str", "—", "交易日期"),
    ("open", "float | None", "元", "开盘价"),
    ("close", "float | None", "元", "收盘价"),
    ("high", "float | None", "元", "最高价"),
    ("low", "float | None", "元", "最低价"),
    ("volume", "float | None", "手", "成交量"),
    ("amount", "float | None", "元", "成交额"),
    ("amplitude", "float | None", "%", "振幅"),
    ("change_pct", "float | None", "%", "涨跌幅"),
    ("change", "float | None", "元", "涨跌额"),
    ("turnover_rate", "float | None", "%", "换手率"),
)

# 板块 K 线与个股共用 Kline 模型，但板块是指数：价格类字段的单位是点而不是元
_BOARD_KLINE_POINT_FIELDS = frozenset({"open", "close", "high", "low", "change"})
_BOARD_KLINE_FIELDS = tuple(
    (name, typ, "点" if name in _BOARD_KLINE_POINT_FIELDS else unit, desc)
    for name, typ, unit, desc in _KLINE_FIELDS
)

_TREND_FIELDS = (
    ("time", "str", "—", "时间 YYYY-MM-DD HH:MM"),
    ("price", "float | None", "元", "最新价"),
    ("avg_price", "float | None", "元", "均价"),
    ("high", "float | None", "元", "该分钟最高"),
    ("low", "float | None", "元", "该分钟最低"),
    ("volume", "float | None", "手", "成交量"),
    ("amount", "float | None", "元", "成交额"),
    ("avg_price2", "float | None", "元", "均价（3 位精度，f58）"),
)

_FUND_FLOW_FIELDS = (
    ("date", "str", "—", "交易日期 YYYY-MM-DD"),
    ("close", "float | None", "元", "收盘价（f62）"),
    ("change_pct", "float | None", "%", "涨跌幅（f63）"),
    ("main_net_inflow", "float | None", "元", "主力净流入-净额（f52 = 大单 + 超大单）"),
    ("main_net_pct", "float | None", "%", "主力净流入-净占比（f57）"),
    ("xlarge_net_inflow", "float | None", "元", "超大单净流入-净额（f56）"),
    ("xlarge_net_pct", "float | None", "%", "超大单净流入-净占比（f61）"),
    ("large_net_inflow", "float | None", "元", "大单净流入-净额（f55）"),
    ("large_net_pct", "float | None", "%", "大单净流入-净占比（f60）"),
    ("medium_net_inflow", "float | None", "元", "中单净流入-净额（f54）"),
    ("medium_net_pct", "float | None", "%", "中单净流入-净占比（f59）"),
    ("small_net_inflow", "float | None", "元", "小单净流入-净额（f53）"),
    ("small_net_pct", "float | None", "%", "小单净流入-净占比（f58）"),
)

# 板块历史资金流字段（对齐 akshare stock_sector_fund_flow_hist，不含收盘价 / 涨跌幅）
_BOARD_FUND_FLOW_FIELDS = (
    ("date", "str", "—", "交易日期 YYYY-MM-DD"),
    ("main_net_inflow", "float | None", "元", "主力净流入-净额（f52 = 大单 + 超大单）"),
    ("main_net_pct", "float | None", "%", "主力净流入-净占比（f57）"),
    ("xlarge_net_inflow", "float | None", "元", "超大单净流入-净额（f56）"),
    ("xlarge_net_pct", "float | None", "%", "超大单净流入-净占比（f61）"),
    ("large_net_inflow", "float | None", "元", "大单净流入-净额（f55）"),
    ("large_net_pct", "float | None", "%", "大单净流入-净占比（f60）"),
    ("medium_net_inflow", "float | None", "元", "中单净流入-净额（f54）"),
    ("medium_net_pct", "float | None", "%", "中单净流入-净占比（f59）"),
    ("small_net_inflow", "float | None", "元", "小单净流入-净额（f53）"),
    ("small_net_pct", "float | None", "%", "小单净流入-净占比（f58）"),
)

# 板块列表字段（对齐 akshare stock_board_industry_name_em，含上涨/下跌家数与领涨/领跌股）
_BOARD_LIST_FIELDS = (
    ("code", "str", "—", "板块代码"),
    ("name", "str", "—", "板块名称"),
    ("price", "float | None", "元", "板块指数最新点位"),
    ("change_pct", "float | None", "%", "涨跌幅"),
    ("change", "float | None", "元", "涨跌额"),
    ("turnover", "float | None", "元", "成交额"),
    ("turnover_rate", "float | None", "%", "换手率"),
    ("up_count", "int | None", "—", "上涨家数"),
    ("down_count", "int | None", "—", "下跌家数"),
    ("leader_code", "str | None", "—", "领涨股代码"),
    ("leader_name", "str | None", "—", "领涨股名称"),
    ("leader_change_pct", "float | None", "%", "领涨股涨跌幅"),
    ("laggard_code", "str | None", "—", "领跌股代码"),
    ("laggard_name", "str | None", "—", "领跌股名称"),
    ("laggard_change_pct", "float | None", "%", "领跌股涨跌幅"),
)

_INDEX_LIST_FIELDS = (
    ("code", "str", "—", "指数代码"),
    ("name", "str", "—", "指数名称"),
    ("market", "str | None", "—", "市场：sh / sz / bj / csi，与 code 一起才能唯一定位指数"),
    ("price", "float | None", "点", "最新点位"),
    ("change_pct", "float | None", "%", "涨跌幅"),
    ("change", "float | None", "点", "涨跌额"),
    ("volume", "float | None", "手", "成交量"),
    ("turnover", "float | None", "元", "成交额"),
    ("amplitude", "float | None", "%", "振幅"),
    ("high", "float | None", "点", "最高"),
    ("low", "float | None", "点", "最低"),
    ("open", "float | None", "点", "今开"),
    ("pre_close", "float | None", "点", "昨收"),
    ("volume_ratio", "float | None", "—", "量比"),
)

_HK_STOCK_LIST_FIELDS = (
    ("code", "str", "—", "港股代码（5 位）"),
    ("name", "str", "—", "证券简称"),
    ("price", "float | None", "港元", "最新价"),
    ("change_pct", "float | None", "%", "涨跌幅"),
    ("change", "float | None", "港元", "涨跌额"),
    ("open", "float | None", "港元", "今开"),
    ("high", "float | None", "港元", "最高"),
    ("low", "float | None", "港元", "最低"),
    ("pre_close", "float | None", "港元", "昨收"),
    ("volume", "float | None", "股", "成交量（单位股，不是手）"),
    ("turnover", "float | None", "港元", "成交额"),
)

_LIMIT_POOL_FIELDS = (
    ("code", "str", "—", "股票代码"),
    ("name", "str", "—", "股票简称"),
    ("market", "str | None", "—", "市场：sh / sz / bj，可连同 code 传给 stock_kline_em"),
    ("price", "float | None", "元", "最新价"),
    ("change_pct", "float | None", "%", "涨跌幅"),
    ("turnover", "float | None", "元", "成交额"),
    ("float_market_cap", "float | None", "元", "流通市值"),
    ("total_market_cap", "float | None", "元", "总市值"),
    ("turnover_rate", "float | None", "%", "换手率"),
    ("industry", "str | None", "—", "所属行业"),
    ("stat_days", "int | None", "天", "涨停统计：统计天数"),
    ("stat_limit_ups", "int | None", "次", "涨停统计：涨停次数"),
    ("limit_up_price", "float | None", "元", "涨停价（昨日涨停/强势/次新/炸板）"),
    ("seal_fund", "float | None", "元", "封板资金（涨停）/ 封单资金（跌停）"),
    ("first_seal_time", "str | None", "—", "首次封板时间 HH:MM:SS（涨停/炸板）"),
    ("last_seal_time", "str | None", "—", "最后封板时间 HH:MM:SS（涨停/跌停）"),
    ("broken_count", "int | None", "次", "炸板次数（涨停/炸板）"),
    ("limit_up_streak", "int | None", "板", "连板数（涨停）"),
    ("prev_seal_time", "str | None", "—", "昨日封板时间（昨日涨停）"),
    ("prev_limit_up_streak", "int | None", "板", "昨日连板数（昨日涨停）"),
    ("amplitude", "float | None", "%", "振幅（昨日涨停/炸板）"),
    ("speed", "float | None", "%", "涨速（昨日涨停/强势/炸板）"),
    ("volume_ratio", "float | None", "—", "量比（强势）"),
    ("new_high", "bool | None", "—", "是否 60 日新高（强势/次新）"),
    ("reason", "str | None", "—", "入选理由（强势）"),
    ("open_days", "int | None", "天", "开板几日（次新）"),
    ("open_date", "str | None", "—", "开板日期 YYYY-MM-DD（次新）"),
    ("listing_date", "str | None", "—", "上市日期 YYYY-MM-DD（次新）"),
    ("pe", "float | None", "—", "动态市盈率（跌停）"),
    ("board_turnover", "float | None", "元", "板上成交额（跌停）"),
    ("limit_down_streak", "int | None", "天", "连续跌停（跌停）"),
    ("open_count", "int | None", "次", "开板次数（跌停）"),
)

_STOCK_INFO_FIELDS = (
    ("code", "str", "—", "股票代码"),
    ("name", "str", "—", "股票简称"),
    ("market", "str | None", "—", "市场：sh / sz / bj"),
    ("industry", "str | None", "—", "所属行业"),
    ("listing_date", "str | None", "—", "上市日期 YYYY-MM-DD"),
    ("price", "float | None", "元", "最新价"),
    ("total_shares", "float | None", "股", "总股本"),
    ("float_shares", "float | None", "股", "流通股"),
    ("total_market_cap", "float | None", "元", "总市值"),
    ("float_market_cap", "float | None", "元", "流通市值"),
)

_STOCK_BID_ASK_FIELDS = (
    ("code", "str", "—", "股票代码"),
    ("name", "str", "—", "股票简称"),
    ("market", "str | None", "—", "市场：sh / sz / bj"),
    ("price", "float | None", "元", "最新价"),
    ("avg_price", "float | None", "元", "均价"),
    ("open", "float | None", "元", "今开"),
    ("high", "float | None", "元", "最高"),
    ("low", "float | None", "元", "最低"),
    ("pre_close", "float | None", "元", "昨收"),
    ("limit_up", "float | None", "元", "涨停价（无涨跌幅限制时为 None）"),
    ("limit_down", "float | None", "元", "跌停价"),
    ("volume", "float | None", "手", "成交量（总手）"),
    ("turnover", "float | None", "元", "成交额"),
    ("outer_volume", "float | None", "手", "外盘"),
    ("volume_ratio", "float | None", "—", "量比"),
    ("bids", "tuple[OrderLevel, ...]", "元 / 手", "买一 ~ 买五（price / volume）"),
    ("asks", "tuple[OrderLevel, ...]", "元 / 手", "卖一 ~ 卖五（price / volume）"),
)

_STOCK_CHANGES_FIELDS = (
    ("time", "str", "—", "异动时间 HH:MM:SS（上游不给日期，属于最近一个交易日）"),
    ("code", "str", "—", "股票代码"),
    ("name", "str", "—", "股票简称"),
    ("market", "str | None", "—", "市场：sh / sz / bj，可连同 code 传给 stock_kline_em"),
    ("change_type", "str | None", "—", "异动类型（英文，如 big_buy）"),
    ("price", "float | None", "元", "异动时的价格（大笔买卖为成交价）"),
    ("change_pct", "float | None", "%", "异动时的涨跌幅"),
    ("volume", "float | None", "股", "成交量 / 挂单量（仅大笔买入卖出、有大买盘卖盘）"),
    ("amount", "float | None", "元", "成交额 / 挂单金额（仅大笔买入卖出、有大买盘卖盘）"),
    ("info", "str | None", "—", "上游原始相关信息（逗号分隔，各类型格式不同）"),
)

_BOARD_CHANGES_FIELDS = (
    ("code", "str", "—", "板块代码，可传给 board_kline_em 等板块接口"),
    ("name", "str", "—", "板块名称"),
    ("change_pct", "float | None", "%", "板块涨跌幅"),
    ("main_net_inflow", "float | None", "元", "主力净流入（上游单位万元，已换算）"),
    ("change_count", "int | None", "次", "板块异动总次数（含未公开类型）"),
    ("top_stock_code", "str | None", "—", "异动最频繁个股：代码"),
    ("top_stock_name", "str | None", "—", "异动最频繁个股：名称"),
    ("top_stock_market", "str | None", "—", "异动最频繁个股：sh / sz / bj"),
    (
        "top_stock_change_type",
        "str | None",
        "—",
        "异动最频繁个股：所属异动类型（未公开类型为 None）",
    ),
    (
        "type_counts",
        "tuple[ChangeTypeCount, ...]",
        "次",
        "各类异动次数（change_type / count），只含 22 种已知类型",
    ),
)

_FUND_LIST_FIELDS = (
    ("code", "str", "—", "基金代码"),
    ("name", "str", "—", "基金简称"),
    ("market", "str | None", "—", "市场：sh / sz，可连同 code 传给 stock_kline_em"),
    ("price", "float | None", "元", "最新价"),
    ("iopv", "float | None", "元", "IOPV 实时估值（仅 ETF 有）"),
    ("discount_rate", "float | None", "%", "基金折价率，负值表示溢价"),
    ("change_pct", "float | None", "%", "涨跌幅"),
    ("change", "float | None", "元", "涨跌额"),
    ("volume", "float | None", "手", "成交量"),
    ("turnover", "float | None", "元", "成交额"),
    ("open", "float | None", "元", "开盘价"),
    ("high", "float | None", "元", "最高价"),
    ("low", "float | None", "元", "最低价"),
    ("pre_close", "float | None", "元", "昨收"),
    ("turnover_rate", "float | None", "%", "换手率"),
    ("float_market_cap", "float | None", "元", "流通市值"),
    ("total_market_cap", "float | None", "元", "总市值"),
)


_BILLBOARD_DETAIL_FIELDS = (
    ("code", "str", "—", "股票代码"),
    ("name", "str", "—", "股票简称"),
    ("market", "str | None", "—", "市场：sh / sz / bj，可连同 code 传给 stock_kline_em"),
    ("trade_date", "str | None", "—", "上榜日 YYYY-MM-DD"),
    ("reason", "str | None", "—", "上榜原因（同股同日多个原因时为多条记录）"),
    ("interpretation", "str | None", "—", "解读，如“2家机构卖出，成功率18.37%”"),
    ("close", "float | None", "元", "收盘价"),
    ("change_pct", "float | None", "%", "涨跌幅"),
    ("net_buy", "float | None", "元", "龙虎榜净买额"),
    ("buy", "float | None", "元", "龙虎榜买入额"),
    ("sell", "float | None", "元", "龙虎榜卖出额"),
    ("billboard_turnover", "float | None", "元", "龙虎榜成交额"),
    ("turnover", "float | None", "元", "市场总成交额"),
    ("net_buy_ratio", "float | None", "%", "净买额占总成交比"),
    ("billboard_turnover_ratio", "float | None", "%", "龙虎榜成交额占总成交比"),
    ("turnover_rate", "float | None", "%", "换手率"),
    ("float_market_cap", "float | None", "元", "流通市值"),
    ("change_after_1d", "float | None", "%", "上榜后 1 日涨跌幅（未到期为 None）"),
    ("change_after_2d", "float | None", "%", "上榜后 2 日涨跌幅"),
    ("change_after_5d", "float | None", "%", "上榜后 5 日涨跌幅"),
    ("change_after_10d", "float | None", "%", "上榜后 10 日涨跌幅"),
)


@dataclass(frozen=True)
class Param:
    name: str
    type: str
    required: bool
    default: str
    desc: str


@dataclass(frozen=True)
class Field:
    name: str
    type: str
    unit: str
    desc: str


@dataclass(frozen=True)
class Interface:
    name: str
    category: str
    desc: str
    documented: bool
    inputs: tuple[Param, ...]
    outputs: tuple[Field, ...]
    example: str
    dataframe_variant: str | None = None


# 数据中心报表接口的公共参数说明
_DATE_RANGE_PARAMS = (
    Param(
        "start_date",
        "str | None",
        False,
        "None",
        "起始日期 YYYYMMDD；起止都留空取最近一个有数据的交易日，只给起始取到今天",
    ),
    Param("end_date", "str | None", False, "None", "结束日期 YYYYMMDD；只给结束日期时只取那一天"),
)


_INTERFACES: tuple[Interface, ...] = (
    Interface(
        name="board_constituent_em",
        category="board",
        desc="板块成分股（含主力净流入，可按当日/5日/10日资金流排序）",
        documented=True,
        inputs=(
            Param("board", "str", False, '"BK0438"', "板块代码（如 BK0438 白酒）"),
            Param("period", "str", False, '"10d"', "资金流周期：day/5d/10d，未知值回退 10d"),
            Param("page", "int", False, "1", "页码，从 1 起"),
            Param("size", "int", False, "8", "每页条数，上游上限 50"),
        ),
        outputs=tuple(Field(*f) for f in _QUOTE_FIELDS),
        example=(
            "from em import board_constituent_em\n"
            "from em.domain.queries import BoardQuery\n"
            "\n"
            'page = board_constituent_em(BoardQuery(board="BK0438", period="10d", size=3))\n'
            "print(page.total)\n"
            "for q in page.items:\n"
            "    print(q.code, q.name, q.price, q.main_net_inflow)"
        ),
        dataframe_variant="df_board_constituent_em",
    ),
    Interface(
        name="stock_list_em",
        category="market",
        desc="沪深京 A 股全市场列表（游客接口，不含资金流，可按沪/深/北/科创/创业/新股/ST 筛选）",
        documented=True,
        inputs=(
            Param("sort", "str", False, '"f3"', "排序字段（上游 f* 字段名）"),
            Param("page", "int", False, "1", "页码，从 1 起"),
            Param("size", "int", False, "20", "每页条数，上游上限 50"),
            Param(
                "scope",
                "str",
                False,
                '"all"',
                "范围：all 全部 / sh 沪市 / sz 深市 / bj 北交所 / kc 科创板 / cy 创业板 / "
                "new 新股 / st 风险警示，未知回退 all",
            ),
        ),
        outputs=tuple(Field(*f) for f in _QUOTE_FIELDS),
        example=(
            "from em import stock_list_em\n"
            "from em.domain.queries import MarketQuery\n"
            "\n"
            'page = stock_list_em(MarketQuery(sort="f3", size=3))\n'
            "print(page.total)\n"
            "for q in page.items:\n"
            "    print(q.code, q.name, q.price, q.change_pct)"
        ),
        dataframe_variant="df_stock_list_em",
    ),
    Interface(
        name="stock_kline_em",
        category="kline",
        desc="个股/指数/基金/港股历史 K 线（日/周/月，前/后/不复权）",
        documented=True,
        inputs=(
            Param("code", "str", False, '"000001"', "证券代码，如 000001"),
            Param(
                "market",
                "str",
                False,
                '"sz"',
                "市场：sz 深市 / sh 沪市 / bj 北交所 / csi 中证指数 / hk 港股"
                "（hk 时价格单位港元、成交量单位股），未知回退 sz",
            ),
            Param(
                "period",
                "str",
                False,
                '"day"',
                "周期：day 日K / week 周K / month 月K，未知回退 day",
            ),
            Param(
                "adjust",
                "str",
                False,
                '"qfq"',
                "复权：qfq 前复权 / hfq 后复权 / none 不复权，未知回退 qfq",
            ),
            Param("beg", "str", False, '"0"', "起始日期 YYYYMMDD，0 表示不限"),
            Param("end", "str", False, '"20500101"', "结束日期 YYYYMMDD"),
        ),
        outputs=tuple(Field(*f) for f in _KLINE_FIELDS),
        example=(
            "from em import stock_kline_em\n"
            "from em.domain.queries import KlineQuery\n"
            "\n"
            'series = stock_kline_em(KlineQuery(code="000001", market="sz", period="day"))\n'
            "print(series.code, series.name, len(series.items))\n"
            "for k in series.items[-3:]:\n"
            "    print(k.date, k.open, k.close, k.change_pct)"
        ),
        dataframe_variant="df_stock_kline_em",
    ),
    Interface(
        name="stock_trends_em",
        category="trends",
        desc="个股/指数分时行情（trends2，ndays 日分时）",
        documented=True,
        inputs=(
            Param("code", "str", False, '"000001"', "证券代码，如 000001"),
            Param("market", "str", False, '"sz"', "市场：sz 深市 / sh 沪市 / bj 北交所"),
            Param("ndays", "int", False, "1", "分时天数：1 当日 / 5 五日"),
            Param("iscr", "int", False, "0", "是否含前收盘"),
            Param("iscca", "int", False, "0", "是否含成交额累计"),
        ),
        outputs=tuple(Field(*f) for f in _TREND_FIELDS),
        example=(
            "from em import stock_trends_em\n"
            "from em.domain.queries import TrendQuery\n"
            "\n"
            'series = stock_trends_em(TrendQuery(code="000001", market="sz", ndays=1))\n'
            "print(series.code, series.name, series.pre_close, len(series.items))\n"
            "for t in series.items[:3]:\n"
            "    print(t.time, t.price, t.avg_price)"
        ),
        dataframe_variant="df_stock_trends_em",
    ),
    Interface(
        name="stock_fund_flow_em",
        category="fund_flow",
        desc="个股历史资金流（日线，主力/超大单/大单/中单/小单净流入）",
        documented=True,
        inputs=(
            Param("code", "str", False, '"000001"', "证券代码，如 000001"),
            Param("market", "str", False, '"sz"', "市场：sz 深市 / sh 沪市 / bj 北交所"),
        ),
        outputs=tuple(Field(*f) for f in _FUND_FLOW_FIELDS),
        example=(
            "from em import stock_fund_flow_em\n"
            "from em.domain.queries import FundFlowQuery\n"
            "\n"
            'series = stock_fund_flow_em(FundFlowQuery(code="000001", market="sz"))\n'
            "print(series.code, series.name, len(series.items))\n"
            "for f in series.items[-3:]:\n"
            "    print(f.date, f.main_net_inflow, f.main_net_pct)"
        ),
        dataframe_variant="df_stock_fund_flow_em",
    ),
    Interface(
        name="board_fund_flow_em",
        category="fund_flow",
        desc="板块历史资金流（行业/概念/地域，日线，主力/超大单/大单/中单/小单净流入，不含收盘价/涨跌幅）",
        documented=True,
        inputs=(Param("board", "str", False, '"BK0438"', "板块代码（如 BK0438 食品饮料）"),),
        outputs=tuple(Field(*f) for f in _BOARD_FUND_FLOW_FIELDS),
        example=(
            "from em import board_fund_flow_em\n"
            "from em.domain.queries import BoardFundFlowQuery\n"
            "\n"
            'series = board_fund_flow_em(BoardFundFlowQuery(board="BK0438"))\n'
            "print(series.code, series.name, len(series.items))\n"
            "for f in series.items[-3:]:\n"
            "    print(f.date, f.main_net_inflow, f.main_net_pct)"
        ),
        dataframe_variant="df_board_fund_flow_em",
    ),
    Interface(
        name="board_kline_em",
        category="kline",
        desc="板块历史 K 线（行业/概念/地域，日/周/月/分钟，板块指数点位）",
        documented=True,
        inputs=(
            Param("board", "str", False, '"BK0438"', "板块代码（如 BK0438 食品饮料）"),
            Param(
                "period",
                "str",
                False,
                '"day"',
                "周期：day 日K / week 周K / month 月K / 5m / 15m / 30m / 60m，未知回退 day",
            ),
            Param("beg", "str", False, '"0"', "起始日期 YYYYMMDD，0 表示不限"),
            Param("end", "str", False, '"20500101"', "结束日期 YYYYMMDD"),
        ),
        outputs=tuple(Field(*f) for f in _BOARD_KLINE_FIELDS),
        example=(
            "from em import board_kline_em\n"
            "from em.domain.queries import BoardKlineQuery\n"
            "\n"
            'series = board_kline_em(BoardKlineQuery(board="BK0438", period="day"))\n'
            "print(series.code, series.name, len(series.items))\n"
            "for k in series.items[-3:]:\n"
            "    print(k.date, k.open, k.close, k.change_pct)"
        ),
        dataframe_variant="df_board_kline_em",
    ),
    Interface(
        name="board_industry_list_em",
        category="board",
        desc="板块列表（行业/概念/地域，行业支持一/二/三级，含上涨下跌家数与领涨领跌股）",
        documented=True,
        inputs=(
            Param(
                "board_type",
                "str",
                False,
                '"industry"',
                "板块类型：industry 行业 / concept 概念 / region 地域，未知回退 industry",
            ),
            Param(
                "level",
                "str",
                False,
                '"1"',
                "行业分级：1 一级 / 2 二级 / 3 三级 / all 全级别，仅 industry 有效，未知回退 1",
            ),
            Param("sort", "str", False, '"f3"', "排序字段（上游 f* 字段名）"),
            Param("page", "int", False, "1", "页码，从 1 起"),
            Param("size", "int", False, "20", "每页条数，上游上限 100"),
        ),
        outputs=tuple(Field(*f) for f in _BOARD_LIST_FIELDS),
        example=(
            "from em import board_industry_list_em\n"
            "from em.domain.queries import BoardListQuery\n"
            "\n"
            'page = board_industry_list_em(BoardListQuery(board_type="industry", level="1", size=5))\n'
            "print(page.total)\n"
            "for b in page.items:\n"
            "    print(b.code, b.name, b.change_pct, b.up_count, b.down_count)"
        ),
        dataframe_variant="df_board_industry_list_em",
    ),
    Interface(
        name="index_list_em",
        category="index",
        desc="指数列表（沪深重要指数/上证系列/深证系列/中证系列，含点位、成交量与量比）",
        documented=True,
        inputs=(
            Param(
                "series",
                "str",
                False,
                '"main"',
                "指数系列：main 沪深重要指数 / sh 上证系列 / sz 深证系列 / csi 中证系列，"
                "未知回退 main",
            ),
            Param("sort", "str", False, '"f3"', "排序字段（上游 f* 字段名）"),
            Param("page", "int", False, "1", "页码，从 1 起"),
            Param("size", "int", False, "20", "每页条数，上游上限 100"),
        ),
        outputs=tuple(Field(*f) for f in _INDEX_LIST_FIELDS),
        example=(
            "from em import index_list_em\n"
            "from em.domain.queries import IndexListQuery\n"
            "\n"
            'page = index_list_em(IndexListQuery(series="main", size=5))\n'
            "print(page.total)\n"
            "for i in page.items:\n"
            "    print(i.code, i.market, i.name, i.price, i.change_pct)"
        ),
        dataframe_variant="df_index_list_em",
    ),
    Interface(
        name="hk_stock_list_em",
        category="hk",
        desc="港股列表（主板/创业板，价格与成交额单位为港元，不含 ETF 与债券）",
        documented=True,
        inputs=(
            Param(
                "scope",
                "str",
                False,
                '"all"',
                "范围：all 主板 + 创业板 / main 主板 / gem 创业板，未知回退 all",
            ),
            Param("sort", "str", False, '"f3"', "排序字段（上游 f* 字段名）"),
            Param("page", "int", False, "1", "页码，从 1 起"),
            Param("size", "int", False, "20", "每页条数，上游上限 100"),
        ),
        outputs=tuple(Field(*f) for f in _HK_STOCK_LIST_FIELDS),
        example=(
            "from em import hk_stock_list_em\n"
            "from em.domain.queries import HkStockListQuery\n"
            "\n"
            'page = hk_stock_list_em(HkStockListQuery(scope="main", sort="f6", size=5))\n'
            "print(page.total)\n"
            "for q in page.items:\n"
            "    print(q.code, q.name, q.price, q.change_pct)"
        ),
        dataframe_variant="df_hk_stock_list_em",
    ),
    Interface(
        name="fund_list_em",
        category="fund",
        desc="场内基金列表（ETF/LOF，含 IOPV 实时估值、折价率与市值）",
        documented=True,
        inputs=(
            Param(
                "fund_type",
                "str",
                False,
                '"etf"',
                "基金类型：etf / lof / all（ETF + LOF），未知回退 etf",
            ),
            Param("sort", "str", False, '"f3"', "排序字段（上游 f* 字段名）"),
            Param("page", "int", False, "1", "页码，从 1 起"),
            Param("size", "int", False, "20", "每页条数，上游上限 100"),
        ),
        outputs=tuple(Field(*f) for f in _FUND_LIST_FIELDS),
        example=(
            "from em import fund_list_em\n"
            "from em.domain.queries import FundListQuery\n"
            "\n"
            'page = fund_list_em(FundListQuery(fund_type="etf", sort="f6", size=5))\n'
            "print(page.total)\n"
            "for q in page.items:\n"
            "    print(q.code, q.market, q.name, q.price, q.iopv, q.discount_rate)"
        ),
        dataframe_variant="df_fund_list_em",
    ),
    Interface(
        name="stock_limit_pool_em",
        category="pool",
        desc="涨跌停股池（涨停/昨日涨停/强势/次新/炸板/跌停，按交易日取整池，含封板资金与连板数）",
        documented=True,
        inputs=(
            Param(
                "pool_type",
                "str",
                False,
                '"limit_up"',
                "股池：limit_up 涨停 / prev_limit_up 昨日涨停 / strong 强势 / sub_new 次新 / "
                "broken 炸板 / limit_down 跌停，未知回退 limit_up",
            ),
            Param(
                "date",
                "str | None",
                False,
                "None",
                "交易日 YYYYMMDD，留空取最近交易日；上游只保留约 15 个交易日",
            ),
        ),
        outputs=tuple(Field(*f) for f in _LIMIT_POOL_FIELDS),
        example=(
            "from em import stock_limit_pool_em\n"
            "from em.domain.queries import LimitPoolQuery\n"
            "\n"
            'page = stock_limit_pool_em(LimitPoolQuery(pool_type="limit_up"))\n'
            "print(page.date, page.total)\n"
            "for s in page.items[:5]:\n"
            "    print(s.code, s.name, s.limit_up_streak, s.first_seal_time, s.seal_fund)"
        ),
        dataframe_variant="df_stock_limit_pool_em",
    ),
    Interface(
        name="stock_info_em",
        category="stock",
        desc="个股基本信息（行业/上市时间/总股本/流通股/总市值/流通市值/最新价）",
        documented=True,
        inputs=(
            Param("code", "str", False, '"000001"', "股票代码，如 000001"),
            Param(
                "market", "str", False, '"sz"', "市场：sz 深市 / sh 沪市 / bj 北交所，未知回退 sz"
            ),
        ),
        outputs=tuple(Field(*f) for f in _STOCK_INFO_FIELDS),
        example=(
            "from em import stock_info_em\n"
            "from em.domain.queries import StockInfoQuery\n"
            "\n"
            'info = stock_info_em(StockInfoQuery(code="600519", market="sh"))\n'
            "print(info.name, info.industry, info.listing_date, info.total_market_cap)"
        ),
        dataframe_variant="df_stock_info_em",
    ),
    Interface(
        name="stock_bid_ask_em",
        category="stock",
        desc="个股五档盘口与行情快照（买卖五档、均价、涨跌停价、外盘、量比）",
        documented=True,
        inputs=(
            Param("code", "str", False, '"000001"', "股票代码，如 000001"),
            Param(
                "market", "str", False, '"sz"', "市场：sz 深市 / sh 沪市 / bj 北交所，未知回退 sz"
            ),
        ),
        outputs=tuple(Field(*f) for f in _STOCK_BID_ASK_FIELDS),
        example=(
            "from em import stock_bid_ask_em\n"
            "from em.domain.queries import StockBidAskQuery\n"
            "\n"
            'book = stock_bid_ask_em(StockBidAskQuery(code="000001", market="sz"))\n'
            "print(book.price, book.avg_price)\n"
            "for i, (b, a) in enumerate(zip(book.bids, book.asks), start=1):\n"
            '    print(f"买{i} {b.price} {b.volume}  卖{i} {a.price} {a.volume}")'
        ),
        dataframe_variant="df_stock_bid_ask_em",
    ),
    Interface(
        name="stock_changes_em",
        category="changes",
        # 描述里不写“封涨停板”等含“涨停”的类型：否则检索“涨停”会与涨跌停股池同分并按名字排到前面
        desc="盘口异动（大笔买入/大笔卖出、火箭发射、高台跳水等 22 种，最近交易日按类型取全量）",
        documented=True,
        inputs=(
            Param(
                "change_type",
                "str",
                False,
                '"big_buy"',
                "异动类型，22 种：rocket_launch 火箭发射 / quick_rebound 快速反弹 / big_buy 大笔买入 / "
                "limit_up_sealed 封涨停板 / limit_down_opened 打开跌停板 / big_bid 有大买盘 / "
                "auction_up 竞价上涨 / open_above_ma5 高开5日线 / gap_up 向上缺口 / "
                "new_high_60d 60日新高 / big_rise_60d 60日大幅上涨 / accelerated_drop 加速下跌 / "
                "high_dive 高台跳水 / big_sell 大笔卖出 / limit_down_sealed 封跌停板 / "
                "limit_up_opened 打开涨停板 / big_ask 有大卖盘 / auction_down 竞价下跌 / "
                "open_below_ma5 低开5日线 / gap_down 向下缺口 / new_low_60d 60日新低 / "
                "big_drop_60d 60日大幅下跌，未知回退 big_buy",
            ),
        ),
        outputs=tuple(Field(*f) for f in _STOCK_CHANGES_FIELDS),
        example=(
            "from em import stock_changes_em\n"
            "from em.domain.queries import StockChangesQuery\n"
            "\n"
            'page = stock_changes_em(StockChangesQuery(change_type="big_buy"))\n'
            "print(page.total)\n"
            "for c in page.items[:5]:\n"
            "    print(c.time, c.code, c.name, c.price, c.volume, c.amount)"
        ),
        dataframe_variant="df_stock_changes_em",
    ),
    Interface(
        name="board_changes_em",
        category="changes",
        desc="板块异动（当日有异动的板块：异动总次数、异动最频繁个股、各类异动次数、主力净流入）",
        documented=True,
        inputs=(),
        outputs=tuple(Field(*f) for f in _BOARD_CHANGES_FIELDS),
        example=(
            "from em import board_changes_em\n"
            "\n"
            "page = board_changes_em()\n"
            "print(page.date, page.time, page.total)\n"
            "for b in page.items[:5]:\n"
            "    print(b.code, b.name, b.change_count, b.top_stock_name, b.type_counts[:3])"
        ),
        dataframe_variant="df_board_changes_em",
    ),
    Interface(
        name="billboard_detail_em",
        category="billboard",
        desc="龙虎榜详情（按上榜日期区间取全部上榜记录：上榜原因、净买额、成交占比、上榜后涨跌幅）",
        documented=True,
        inputs=_DATE_RANGE_PARAMS,
        outputs=tuple(Field(*f) for f in _BILLBOARD_DETAIL_FIELDS),
        example=(
            "from em import billboard_detail_em\n"
            "from em.domain.queries import BillboardDetailQuery\n"
            "\n"
            'page = billboard_detail_em(BillboardDetailQuery("20261102", "20261106"))\n'
            "print(page.total)\n"
            "for e in page.items[:5]:\n"
            "    print(e.trade_date, e.code, e.name, e.net_buy, e.reason)"
        ),
        dataframe_variant="df_billboard_detail_em",
    ),
)


# ------------------------------------------------------------------ 打分检索

_TOKEN_SPLIT_RE = re.compile(r"[\s,，、;；/|]+")
_WHITESPACE_RE = re.compile(r"\s+")

WEIGHT_NAME_EXACT = 100.0
WEIGHT_NAME = 10.0
WEIGHT_DESC = 5.0
WEIGHT_CATEGORY = 3.0
WEIGHT_OUTPUT = 2.0
BONUS_ALL_TOKENS = 1.5
PENALTY_UNDOCUMENTED = 0.5

SEARCH_KEYS = ("接口名", "类目", "描述", "有无文档", "匹配分")


def _tokenize(query: str) -> list[str]:
    return [t for t in _TOKEN_SPLIT_RE.split(query.strip()) if t]


def _normalize(text: str) -> str:
    return _WHITESPACE_RE.sub("", text)


def _bigrams(query: str) -> list[str]:
    compact = re.sub(r"\s+", "", query)
    return [compact[i : i + 2] for i in range(len(compact) - 1)]


def _score(tokens: list[str], itf: Interface) -> float:
    if not tokens:
        return 0.0
    if len(tokens) == 1 and tokens[0] == itf.name:
        return WEIGHT_NAME_EXACT
    columns = "\x00".join(f.name for f in itf.outputs)
    norm_name = _normalize(itf.name)
    norm_desc = _normalize(itf.desc)
    norm_cat = _normalize(itf.category)
    norm_cols = _normalize(columns)
    total = 0.0
    hit = 0
    for token in tokens:
        nt = _normalize(token)
        sub = 0.0
        if nt in norm_name:
            sub += WEIGHT_NAME
        if nt in norm_desc:
            sub += WEIGHT_DESC
        if nt in norm_cat:
            sub += WEIGHT_CATEGORY
        if nt in norm_cols:
            sub += WEIGHT_OUTPUT
        if sub:
            hit += 1
        total += sub
    if total and hit == len(tokens):
        total *= BONUS_ALL_TOKENS
    if not itf.documented:
        total *= PENALTY_UNDOCUMENTED
    return total


def _rank(query: str, records: list[Interface]) -> list[tuple[Interface, float]]:
    tokens = _tokenize(query)
    fallback = _bigrams(query)
    stripped = query.strip()
    scored: list[tuple[Interface, float, bool]] = []
    for itf in records:
        s = _score(tokens, itf)
        if fallback:
            s = max(s, _score(fallback, itf))
        if s > 0:
            is_exact = (len(tokens) == 1 and tokens[0] == itf.name) or itf.name == stripped
            scored.append((itf, s, is_exact))
    scored.sort(key=lambda item: (not item[2], -item[1], item[0].name))
    return [(itf, s) for itf, s, _ in scored]


# ------------------------------------------------------------------ 公共面


def search(
    query: str,
    limit: int = 20,
    category: str | None = None,
    documented_only: bool = False,
) -> list[dict[str, Any]]:
    """按关键词检索 em 接口，返回 ``接口名/类目/描述/有无文档/匹配分`` 列表。"""
    if limit < 0:
        raise ValueError(f"limit 不能为负数，收到 {limit}")
    if not query.strip():
        return []
    records = list(_INTERFACES)
    if category:
        records = [itf for itf in records if itf.category == category]
    if documented_only:
        records = [itf for itf in records if itf.documented]
    ranked = _rank(query, records)
    return [
        {
            "接口名": itf.name,
            "类目": itf.category,
            "描述": itf.desc,
            "有无文档": itf.documented,
            "匹配分": round(score, 2),
        }
        for itf, score in ranked[:limit]
    ]


def interface_info(name: str) -> dict[str, Any]:
    """返回单个接口的完整元数据；未知时抛 ``InterfaceNotFoundError`` 并给最接近候选。"""
    for itf in _INTERFACES:
        if itf.name == name:
            return asdict(itf)
    candidates = [itf.name for itf, _ in _rank(name, list(_INTERFACES))[:3]]
    hint = "、".join(candidates) if candidates else "无"
    raise InterfaceNotFoundError(f"未知接口 {name}，最接近的候选: {hint}")


def list_categories() -> list[dict[str, Any]]:
    """列出全部类目及其接口数量。"""
    counter: dict[str, int] = {}
    for itf in _INTERFACES:
        counter[itf.category] = counter.get(itf.category, 0) + 1
    return [{"类目": k, "接口数": v} for k, v in sorted(counter.items())]


# ------------------------------------------------------------------ DataFrame 包装


def _to_df(rows: list[dict[str, Any]], columns: list[str]) -> pd.DataFrame:
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - 环境依赖
        raise ImportError("pandas 未安装：pip install pandas") from exc
    return pd.DataFrame(rows, columns=columns)  # type: ignore[no-any-return]


def search_df(
    query: str,
    limit: int = 20,
    category: str | None = None,
    documented_only: bool = False,
) -> pd.DataFrame:
    """``search`` 的 DataFrame 版。"""
    return _to_df(search(query, limit, category, documented_only), list(SEARCH_KEYS))


def list_categories_df() -> pd.DataFrame:
    """``list_categories`` 的 DataFrame 版。"""
    return _to_df(list_categories(), ["类目", "接口数"])


_INPUT_COL_MAP = {
    "name": "名称",
    "type": "类型",
    "required": "必填",
    "default": "默认值",
    "desc": "描述",
}
_OUTPUT_COL_MAP = {"name": "名称", "type": "类型", "unit": "单位", "desc": "描述"}


def interface_info_df(name: str) -> dict[str, pd.DataFrame]:
    """``interface_info`` 的 DataFrame 版：返回 ``{"inputs": 参数表, "outputs": 字段表}``。"""
    info = interface_info(name)
    inputs = [{_INPUT_COL_MAP[k]: v for k, v in row.items()} for row in info["inputs"]]
    outputs = [{_OUTPUT_COL_MAP[k]: v for k, v in row.items()} for row in info["outputs"]]
    return {
        "inputs": _to_df(inputs, list(_INPUT_COL_MAP.values())),
        "outputs": _to_df(outputs, list(_OUTPUT_COL_MAP.values())),
    }

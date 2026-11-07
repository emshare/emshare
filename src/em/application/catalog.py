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
        desc="个股/指数历史 K 线（日/周/月，前/后/不复权）",
        documented=True,
        inputs=(
            Param("code", "str", False, '"000001"', "证券代码，如 000001"),
            Param("market", "str", False, '"sz"', "市场：sz 深市 / sh 沪市 / bj 北交所"),
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

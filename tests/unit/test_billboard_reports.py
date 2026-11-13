"""龙虎榜其余 9 张报表的映射、请求构建、端到端取数与 DataFrame 行为锁（不触网）。

固定报文 ``datacenter_billboard_reports.json`` 是 2026-11-11 抓取的真实响应（每页 2 条的第 1 页，
个别为专门挑出的边界样本）：

- ``institution_two_reasons``：688836 宇树科技 10-26 因两个原因上榜的两条机构统计；
- ``branch_active_same_code``：营业部代码、上榜日、金额都相同，只有名称与买入股票不同的两行；
- ``branch_trades``：只卖出的一条记录（``ACT_BUY`` 为 null）；
- ``stock_buy_two_reasons``：000530 冰山冷热 11-02 两个上榜原因各 5 个买入席位；
- ``stock_sell``：000026 飞亚达 11-11 的 5 个卖出席位。
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

import em
from em.application import market_data, registry
from em.channels.eastmoney.ashare_billboard.billboard_branch_active import (
    BILLBOARD_BRANCH_ACTIVE,
    billboard_branch_active_request,
)
from em.channels.eastmoney.ashare_billboard.billboard_branch_rank import (
    BILLBOARD_BRANCH_RANK,
    billboard_branch_rank_request,
)
from em.channels.eastmoney.ashare_billboard.billboard_branch_stats import (
    BILLBOARD_BRANCH_STATS,
    billboard_branch_stats_request,
)
from em.channels.eastmoney.ashare_billboard.billboard_branch_trades import (
    BILLBOARD_BRANCH_TRADES,
    billboard_branch_trades_request,
)
from em.channels.eastmoney.ashare_billboard.billboard_institution import (
    BILLBOARD_INSTITUTION,
    billboard_institution_request,
)
from em.channels.eastmoney.ashare_billboard.billboard_institution_stats import (
    BILLBOARD_INSTITUTION_STATS,
    billboard_institution_stats_request,
)
from em.channels.eastmoney.ashare_billboard.billboard_stock import (
    BILLBOARD_STOCK_SIDES,
    billboard_stock_request,
    normalize_side,
)
from em.channels.eastmoney.ashare_billboard.billboard_stock_dates import (
    BILLBOARD_STOCK_DATES,
    billboard_stock_dates_request,
)
from em.channels.eastmoney.ashare_billboard.billboard_stock_stats import (
    BILLBOARD_STOCK_STATS,
    billboard_stock_stats_request,
)
from em.channels.eastmoney.datacenter import ReportSpec, normalize_period, to_report_chunk
from em.core.errors import InvalidContentError
from em.core.settings import Settings
from em.domain.models import ReportPage
from em.domain.queries import (
    BillboardBranchActiveQuery,
    BillboardBranchRankQuery,
    BillboardBranchStatsQuery,
    BillboardBranchTradesQuery,
    BillboardInstitutionQuery,
    BillboardInstitutionStatsQuery,
    BillboardStockDatesQuery,
    BillboardStockQuery,
    BillboardStockStatsQuery,
)

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "eastmoney"
    / "datacenter_billboard_reports.json"
)

# 固定报文段 -> 解析它的报表声明
_SPECS: dict[str, ReportSpec[Any]] = {
    "stock_stats": BILLBOARD_STOCK_STATS,
    "institution": BILLBOARD_INSTITUTION,
    "institution_two_reasons": BILLBOARD_INSTITUTION,
    "institution_stats": BILLBOARD_INSTITUTION_STATS,
    "branch_active": BILLBOARD_BRANCH_ACTIVE,
    "branch_active_same_code": BILLBOARD_BRANCH_ACTIVE,
    "branch_rank": BILLBOARD_BRANCH_RANK,
    "branch_stats": BILLBOARD_BRANCH_STATS,
    "branch_trades": BILLBOARD_BRANCH_TRADES,
    "stock_dates": BILLBOARD_STOCK_DATES,
    "stock_buy_two_reasons": BILLBOARD_STOCK_SIDES["buy"],
    "stock_sell": BILLBOARD_STOCK_SIDES["sell"],
}


def _fx() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _items(name: str) -> tuple[Any, ...]:
    return to_report_chunk(_fx()[name], _SPECS[name].map_row).items


# ---------------------------------------------------------------- 报文与声明对齐


@pytest.mark.parametrize("name", sorted(_SPECS))
def test_fixture_carries_every_requested_column(name: str) -> None:
    # 声明里的上游列名写错时，row.get 会静默得到 None；这里用真实报文把列名锁住
    rows = _fx()[name]["result"]["data"]
    spec = _SPECS[name]
    wanted = {s for c in spec.columns for s in c.sources()} | set(spec.key_columns)
    for row in rows:
        assert wanted <= set(row), f"{name} 缺列 {sorted(wanted - set(row))}"


@pytest.mark.parametrize("spec", list(dict.fromkeys(_SPECS.values())), ids=lambda s: s.report)
def test_sort_columns_are_requested(spec: ReportSpec[Any]) -> None:
    # 排序列也一并请求：上游对拼错的返回列报 9501，借此把改名暴露出来
    request = spec.request()
    assert set(request.sort_columns) <= set(request.columns)
    assert len(request.sort_columns) == len(request.sort_types)


# ---------------------------------------------------------------- 行映射


def test_stock_stats_fields() -> None:
    e = _items("stock_stats")[0]
    assert (e.code, e.name, e.market, e.latest_date) == ("000530", "冰山冷热", "sz", "2026-11-11")
    assert (e.billboard_times, e.institution_buy_times, e.institution_sell_times) == (23, 81, 81)
    assert isinstance(e.billboard_times, int)
    assert e.close == pytest.approx(11.28)
    assert e.change_pct == pytest.approx(7.1225)
    assert e.buy - e.sell == pytest.approx(e.net_buy)
    assert e.billboard_turnover == pytest.approx(e.buy + e.sell)
    assert e.institution_buy - e.institution_sell == pytest.approx(e.institution_net_buy)
    assert (e.change_1mo, e.change_1y) == (pytest.approx(111.63227017), pytest.approx(59.80928777))


def test_institution_fields() -> None:
    e = _items("institution")[0]
    assert (e.code, e.name, e.market, e.trade_date) == ("002384", "东山精密", "sz", "2026-11-11")
    assert e.reason == "日涨幅偏离值达到7%的前5只证券"
    assert (e.buy_institutions, e.sell_institutions) == (3, 4)
    assert e.institution_buy - e.institution_sell == pytest.approx(e.institution_net_buy)
    # 占比是 %：机构净买额 / 市场总成交额
    assert e.net_buy_ratio == pytest.approx(100 * e.institution_net_buy / e.turnover)
    # 流通市值上游给亿元（1276.25），统一成元
    assert e.float_market_cap == pytest.approx(127_625_000_000)
    # 抓取当天上榜：上榜后各日涨跌幅都还没到期
    assert (
        e.change_after_1d,
        e.change_after_2d,
        e.change_after_3d,
        e.change_after_5d,
        e.change_after_10d,
    ) == (None, None, None, None, None)


def test_institution_same_stock_same_day_two_reasons_are_two_entries() -> None:
    first, second = _items("institution_two_reasons")
    assert (
        (first.code, first.trade_date)
        == (second.code, second.trade_date)
        == ("688836", "2026-10-26")
    )
    assert first.reason != second.reason
    # 各按自己的上榜原因统计：机构数、金额、统计区间成交额都不同，不能相加
    assert (first.buy_institutions, second.buy_institutions) == (1, 2)
    assert first.turnover != second.turnover
    assert first.change_after_10d == pytest.approx(6.54761905)


def test_institution_stats_fields() -> None:
    e = _items("institution_stats")[0]
    assert (e.code, e.name, e.market) == ("000530", "冰山冷热", "sz")
    assert (e.billboard_times, e.institution_buy_times, e.institution_sell_times) == (22, 81, 81)
    assert e.billboard_turnover == pytest.approx(10395854562.3)
    assert e.institution_buy - e.institution_sell == pytest.approx(e.institution_net_buy)
    assert (e.change_1mo, e.change_3mo, e.change_6mo, e.change_1y) == (
        pytest.approx(111.63227017),
        pytest.approx(123.80952381),
        pytest.approx(87.40793121),
        pytest.approx(59.80928777),
    )


def test_branch_active_fields() -> None:
    e = _items("branch_active")[0]
    assert (e.branch_code, e.branch_name, e.trade_date) == ("10634757", "深股通专用", "2026-11-11")
    assert (e.buy_stock_count, e.sell_stock_count) == (21, 22)
    assert e.buy - e.sell == pytest.approx(e.net_buy)
    assert e.stock_codes[:2] == ("000026", "000593")
    # 简称与代码一一对应。东财页面叫“买入股票”，实际是当日买入或卖出过的全部上榜股票
    # （2026-11-12 用营业部详情核对 36 家全部一致），所以个数可以大于买入个股数（本条 22 对 21）
    assert len(e.stock_codes) == len(e.stocks.split()) == 22
    assert all(code.isdigit() and len(code) == 6 for code in e.stock_codes)


def test_branch_active_same_code_rows_are_both_kept() -> None:
    # 上游对同一营业部代码、同一上榜日给了两行：金额相同，名称与买入股票不同
    name = "branch_active_same_code"
    chunk = to_report_chunk(_fx()[name], _SPECS[name].map_row)
    first, second = chunk.items
    assert (first.branch_code, first.trade_date, first.net_buy) == (
        second.branch_code,
        second.trade_date,
        second.net_buy,
    )
    assert first.branch_name != second.branch_name
    assert set(first.stock_codes).isdisjoint(second.stock_codes)
    # 整行去重键不同：即使打开 distinct 也不会被当成重复行丢掉
    assert len(set(chunk.keys)) == 2


def test_branch_rank_fields() -> None:
    e = _items("branch_rank")[0]
    assert (e.branch_code, e.branch_name) == ("10004865", "国泰海通")
    assert (e.buy_times_1d, e.buy_times_2d, e.buy_times_3d, e.buy_times_5d, e.buy_times_10d) == (
        355,
        339,
        324,
        287,
        214,
    )
    assert (e.avg_change_1d, e.rise_prob_1d) == (
        pytest.approx(-0.366519958563),
        pytest.approx(41.971830985916),
    )
    assert (e.avg_change_10d, e.rise_prob_10d) == (
        pytest.approx(-8.733084272804),
        pytest.approx(21.495327102804),
    )


def test_branch_stats_fields() -> None:
    e = _items("branch_stats")[0]
    assert (e.branch_code, e.branch_name) == ("10634757", "深股通专用")
    assert (e.billboard_times, e.buy_times, e.sell_times) == (426, 425, 425)
    assert e.billboard_turnover == pytest.approx(e.buy + e.sell)


def test_branch_trades_sell_only_record() -> None:
    (e,) = _items("branch_trades")
    assert (e.branch_code, e.branch_short_name) == (
        "10188715",
        "东方证券上海普陀区云岭东路证券营业部",
    )
    assert e.branch_name == "东方证券股份有限公司上海普陀区云岭东路证券营业部"
    assert (e.code, e.name, e.market, e.trade_date) == ("603131", "上海沪工", "sh", "2026-10-30")
    # 只卖出：买入金额为 None 而不是 0
    assert e.buy is None
    assert (e.sell, e.net_buy) == (pytest.approx(5265000), pytest.approx(-5265000))
    assert e.reason == "有价格涨跌幅限制的日收盘价格涨幅偏离值达到7%的前五只证券"
    assert e.change_after_5d == pytest.approx(-7.97720798)
    assert (e.change_after_10d, e.change_after_20d, e.change_after_30d) == (None, None, None)


def test_stock_dates_fields() -> None:
    dates = _items("stock_dates")
    assert {d.code for d in dates} == {"000530"}
    assert [d.trade_date for d in dates] == ["2026-11-11", "2026-11-10", "2026-11-06"]


def test_stock_seats_grouped_by_reason() -> None:
    seats = _items("stock_buy_two_reasons")
    assert len(seats) == 10
    first, second = seats[:5], seats[5:]
    assert len({s.reason for s in first}) == len({s.reason for s in second}) == 1
    assert first[0].reason != second[0].reason
    for group in (first, second):
        buys = [s.buy for s in group]
        assert buys == sorted(buys, reverse=True)  # 组内按买入金额倒序
    top = first[0]
    assert (top.code, top.market, top.trade_date) == ("000530", "sz", "2026-11-02")
    assert top.branch_name == "国泰海通证券股份有限公司武汉紫阳东路证券营业部"
    assert top.buy - top.sell == pytest.approx(top.net_buy)
    # 上游给比例（0.0535），统一成 %：买入 / 该上榜原因统计区间的总成交额
    assert top.buy_ratio == pytest.approx(5.3536779728)
    assert top.buy_ratio == pytest.approx(100 * top.buy / top.turnover)
    assert top.sell_ratio == pytest.approx(100 * top.sell / top.turnover)


def test_stock_seats_institution_code_is_zero() -> None:
    # 机构专用席位的营业部代码是 "0"：要保留成文本，不能被当成空值
    seats = _items("stock_buy_two_reasons")[:5]
    institutions = [s for s in seats if s.branch_name == "机构专用"]
    assert len(institutions) == 2
    assert {s.branch_code for s in institutions} == {"0"}
    assert institutions[0].buy != institutions[1].buy  # 同名同代码的两个席位是两条记录


def test_stock_sell_side_sorted_by_sell() -> None:
    seats = _items("stock_sell")
    assert len(seats) == 5 and {s.code for s in seats} == {"000026"}
    sells = [s.sell for s in seats]
    assert sells == sorted(sells, reverse=True)
    assert seats[0].branch_name == "深股通专用"
    assert seats[0].sell_ratio == pytest.approx(6.2860882396)


# ---------------------------------------------------------------- 请求：按统计周期

_PERIOD_REQUESTS: list[tuple[Callable[[Any], Any], Callable[..., Any], str, str]] = [
    (
        billboard_stock_stats_request,
        BillboardStockStatsQuery,
        "RPT_BILLBOARD_TRADEALL",
        "STATISTICS_CYCLE",
    ),
    (
        billboard_institution_stats_request,
        BillboardInstitutionStatsQuery,
        "RPT_ORGANIZATION_SEATNEW",
        "STATISTICSCYCLE",
    ),
    (
        billboard_branch_rank_request,
        BillboardBranchRankQuery,
        "RPT_RATEDEPT_RETURNT_RANKING",
        "STATISTICSCYCLE",
    ),
    (
        billboard_branch_stats_request,
        BillboardBranchStatsQuery,
        "RPT_OPERATEDEPT_LIST_STATISTICS",
        "STATISTICSCYCLE",
    ),
]
_PERIOD_IDS = ["stock_stats", "institution_stats", "branch_rank", "branch_stats"]


@pytest.mark.parametrize("build,query,report,column", _PERIOD_REQUESTS, ids=_PERIOD_IDS)
def test_period_request(
    build: Callable[[Any], Any], query: Callable[..., Any], report: str, column: str
) -> None:
    params = build(query()).params()
    assert params["reportName"] == report
    assert params["filter"] == f'({column}="01")'  # 默认近 1 个月
    # 周期列名各报表不同（有无下划线）；一并请求，上游改名时报 9501 而不是静默返回整张表
    assert column in params["columns"].split(",")
    assert params["sortTypes"].startswith("-1")
    for period, code in (("3mo", "02"), ("6mo", "03"), ("1y", "04")):
        assert build(query(period=period)).filter == f'({column}="{code}")'
    assert build(query(period="5m")).filter == f'({column}="01")'  # 未知回退 1mo
    assert build(query()).latest_of == ""


def test_normalize_period() -> None:
    assert [normalize_period(p) for p in ("1mo", "3mo", "6mo", "1y")] == ["1mo", "3mo", "6mo", "1y"]
    assert normalize_period("") == normalize_period("1m") == "1mo"


# ---------------------------------------------------------------- 请求：按上榜日期区间

_SPAN_REQUESTS: list[tuple[Callable[[Any], Any], Callable[..., Any], str, str]] = [
    (
        billboard_institution_request,
        BillboardInstitutionQuery,
        "RPT_ORGANIZATION_TRADE_DETAILS",
        "TRADE_DATE",
    ),
    (
        billboard_branch_active_request,
        BillboardBranchActiveQuery,
        "RPT_OPERATEDEPT_ACTIVE",
        "ONLIST_DATE",
    ),
]
_SPAN_IDS = ["institution", "branch_active"]


@pytest.mark.parametrize("build,query,report,column", _SPAN_REQUESTS, ids=_SPAN_IDS)
def test_span_request(
    build: Callable[[Any], Any], query: Callable[..., Any], report: str, column: str
) -> None:
    request = build(query("20261102", "20261106"))
    params = request.params()
    assert params["reportName"] == report
    assert params["filter"] == f"({column}>='2026-11-02')({column}<='2026-11-06')"
    assert request.latest_of == ""
    # 只给 end_date：只取那一天
    assert build(query(end_date="20261106")).filter == (
        f"({column}>='2026-11-06')({column}<='2026-11-06')"
    )
    # 日期都留空：先查最新上榜日
    latest = build(query())
    assert (latest.latest_of, latest.filter) == (column, "")
    assert column in latest.columns


@pytest.mark.parametrize("build,query,report,column", _SPAN_REQUESTS, ids=_SPAN_IDS)
def test_span_request_rejects_bad_dates(
    build: Callable[[Any], Any], query: Callable[..., Any], report: str, column: str
) -> None:
    with pytest.raises(ValueError, match="YYYYMMDD"):
        build(query("2026-11-06"))
    with pytest.raises(ValueError, match="晚于"):
        build(query("20261106", "20261101"))


def test_institution_sort_ends_with_reason() -> None:
    # 本报表没有 TRADE_ID：同股同日多条记录靠上榜原因排在固定位置，翻页顺序才稳定
    params = billboard_institution_request(BillboardInstitutionQuery("20261111")).params()
    assert (params["sortColumns"], params["sortTypes"]) == (
        "NET_BUY_AMT,TRADE_DATE,SECURITY_CODE,EXPLANATION",
        "-1,-1,1,1",
    )


def test_branch_active_sort_ends_with_name() -> None:
    # 同一营业部代码、同一上榜日可能有金额相同的两行（见 branch_active_same_code）：
    # 末尾补营业部名称，这两行才有固定先后，跨页时不会一条重复、一条丢失
    params = billboard_branch_active_request(BillboardBranchActiveQuery("20261111")).params()
    assert (params["sortColumns"], params["sortTypes"]) == (
        "TOTAL_NETAMT,ONLIST_DATE,OPERATEDEPT_CODE,OPERATEDEPT_NAME",
        "-1,-1,1,1",
    )


# ---------------------------------------------------------------- 请求：按营业部 / 个股


def test_branch_trades_request() -> None:
    request = billboard_branch_trades_request(
        BillboardBranchTradesQuery("10188715", "20261001", "20261031")
    )
    params = request.params()
    assert params["reportName"] == "RPT_OPERATEDEPT_TRADE_DETAILSNEW"
    assert params["filter"] == (
        "(OPERATEDEPT_CODE=\"10188715\")(TRADE_DATE>='2026-10-01')(TRADE_DATE<='2026-10-31')"
    )
    assert (params["sortColumns"], params["sortTypes"]) == (
        "TRADE_DATE,SECURITY_CODE,EXPLANATION",
        "-1,1,1",
    )


def test_branch_trades_without_dates_takes_full_history() -> None:
    # 与按日期的报表不同：留空不是“最近一天”，而是该营业部的全部历史
    request = billboard_branch_trades_request(BillboardBranchTradesQuery("10188715"))
    assert request.filter == '(OPERATEDEPT_CODE="10188715")'
    assert request.latest_of == ""


def test_stock_dates_request() -> None:
    params = billboard_stock_dates_request(BillboardStockDatesQuery("000530")).params()
    assert params["reportName"] == "RPT_LHB_BOARDDATE"
    assert params["filter"] == '(SECURITY_CODE="000530")'
    assert (params["sortColumns"], params["sortTypes"]) == ("TRADE_DATE", "-1")
    assert params["columns"] == "SECURITY_CODE,TRADE_DATE"


@pytest.mark.parametrize(
    "side,report,amount",
    [
        ("buy", "RPT_BILLBOARD_DAILYDETAILSBUY", "BUY"),
        ("sell", "RPT_BILLBOARD_DAILYDETAILSSELL", "SELL"),
    ],
)
def test_stock_request_per_side(side: str, report: str, amount: str) -> None:
    request = billboard_stock_request(BillboardStockQuery("000530", "20261102", side))
    params = request.params()
    assert params["reportName"] == report
    assert params["filter"] == "(TRADE_DATE='2026-11-02')(SECURITY_CODE=\"000530\")"
    # 先按 TRADE_ID 把同一上榜原因的席位排在一起，组内按该侧金额倒序
    assert (params["sortColumns"], params["sortTypes"]) == (
        f"TRADE_ID,{amount},OPERATEDEPT_CODE",
        "1,-1,1",
    )
    assert "TRADE_ID" in params["columns"].split(",")
    assert request.latest_of == ""


def test_stock_request_unknown_side_falls_back_to_buy() -> None:
    assert normalize_side("sell") == "sell"
    assert normalize_side("both") == normalize_side("") == "buy"
    request = billboard_stock_request(BillboardStockQuery("000530", "20261102", "both"))
    assert request.report == "RPT_BILLBOARD_DAILYDETAILSBUY"


def test_stock_request_without_date_takes_latest_day_of_that_stock() -> None:
    request = billboard_stock_request(BillboardStockQuery("000530"))
    assert (request.latest_of, request.filter) == ("TRADE_DATE", '(SECURITY_CODE="000530")')
    # 最新上榜日要在这只股票里找，不是全市场的最新上榜日
    assert request.latest_lookup().filter == '(SECURITY_CODE="000530")'
    assert request.on_day("2026-11-11").filter == (
        "(SECURITY_CODE=\"000530\")(TRADE_DATE='2026-11-11')"
    )


def test_stock_request_rejects_bad_date() -> None:
    with pytest.raises(ValueError, match="YYYYMMDD"):
        billboard_stock_request(BillboardStockQuery("000530", "2026-11-02"))


@pytest.mark.parametrize("bad", ["", '1")(X="', "1'", "(1)"])
def test_code_values_reject_filter_injection(bad: str) -> None:
    # 代码拼进过滤条件：含引号 / 括号会改写过滤语法，本地直接拒绝
    with pytest.raises(ValueError, match="branch_code"):
        billboard_branch_trades_request(BillboardBranchTradesQuery(bad))
    with pytest.raises(ValueError, match="code"):
        billboard_stock_dates_request(BillboardStockDatesQuery(bad))
    with pytest.raises(ValueError, match="code"):
        billboard_stock_request(BillboardStockQuery(bad))


# ---------------------------------------------------------------- 注册表与对外导出

_NAMES = [
    "billboard_stock_stats",
    "billboard_institution",
    "billboard_institution_stats",
    "billboard_branch_active",
    "billboard_branch_rank",
    "billboard_branch_stats",
    "billboard_branch_trades",
    "billboard_stock_dates",
    "billboard_stock",
]
_BUILDERS = [
    billboard_stock_stats_request,
    billboard_institution_request,
    billboard_institution_stats_request,
    billboard_branch_active_request,
    billboard_branch_rank_request,
    billboard_branch_stats_request,
    billboard_branch_trades_request,
    billboard_stock_dates_request,
    billboard_stock_request,
]


@pytest.mark.parametrize("name,build", list(zip(_NAMES, _BUILDERS, strict=True)), ids=_NAMES)
def test_registry_exposes_request(name: str, build: object) -> None:
    assert getattr(registry, f"{name}_request") is build
    assert f"{name}_request" in registry.__all__


@pytest.mark.parametrize("name", _NAMES)
def test_package_exports_interface(name: str) -> None:
    for exported in (f"{name}_em", f"df_{name}_em", f"to_{name}_dataframe"):
        assert exported in em.__all__
        assert callable(getattr(em, exported))


# ---------------------------------------------------------------- 端到端：应用层取数


class _ReportClient:
    """按报表名返回固定报文的 HttpClient 桩：与真实传输层一样执行协议校验。

    固定报文是每页 2 条的第 1 页（``pages`` 上百）；这里改写成“只有这一页”，免得翻页器去取其余页。
    """

    def __init__(self, bodies: dict[str, dict[str, Any]], latest: str = "") -> None:
        self.bodies = bodies
        self.latest = latest
        self.calls: list[dict[str, Any]] = []

    def get_text(
        self,
        url: str,
        params: dict[str, Any],
        headers: object,
        validator: Callable[[str], bool] | None = None,
        read_timeout: float | None = None,
    ) -> str:
        self.calls.append(dict(params))
        if params["pageSize"] == "1":  # 最新上榜日查询
            rows: list[dict[str, Any]] = [{params["columns"]: self.latest}]
        else:
            rows = self.bodies[params["reportName"]]["result"]["data"]
        body = {"code": 0, "result": {"count": len(rows), "pages": 1, "data": rows}}
        text = json.dumps(body, ensure_ascii=False)
        if validator is not None and not validator(text):
            raise InvalidContentError(f"桩：未通过校验 {text[:40]}")
        return text

    def available_proxies(self, url: str) -> int:
        return 0


def _client(monkeypatch: pytest.MonkeyPatch, name: str, latest: str = "") -> _ReportClient:
    client = _ReportClient({_SPECS[name].report: _fx()[name]}, latest)
    monkeypatch.setattr(market_data, "_build_client", lambda settings: client)
    return client


_SETTINGS = Settings()

# 接口 -> (固定报文段, 查询, 条数)：给了日期 / 周期 / 代码，一次请求取完
_DIRECT_CASES: list[tuple[str, str, Any, int]] = [
    ("billboard_stock_stats_em", "stock_stats", BillboardStockStatsQuery("3mo"), 2),
    (
        "billboard_institution_em",
        "institution",
        BillboardInstitutionQuery("20261111", "20261111"),
        2,
    ),
    ("billboard_institution_stats_em", "institution_stats", BillboardInstitutionStatsQuery(), 2),
    (
        "billboard_branch_active_em",
        "branch_active",
        BillboardBranchActiveQuery("20261111", "20261111"),
        2,
    ),
    ("billboard_branch_rank_em", "branch_rank", BillboardBranchRankQuery(), 2),
    ("billboard_branch_stats_em", "branch_stats", BillboardBranchStatsQuery("1y"), 2),
    ("billboard_branch_trades_em", "branch_trades", BillboardBranchTradesQuery("10188715"), 1),
    ("billboard_stock_dates_em", "stock_dates", BillboardStockDatesQuery("000530"), 3),
    (
        "billboard_stock_em",
        "stock_buy_two_reasons",
        BillboardStockQuery("000530", "20261102"),
        10,
    ),
    ("billboard_stock_em", "stock_sell", BillboardStockQuery("000026", "20261111", "sell"), 5),
]


@pytest.mark.parametrize(
    "func,name,query,count", _DIRECT_CASES, ids=[f"{c[0]}:{c[1]}" for c in _DIRECT_CASES]
)
def test_interface_fetches_report(
    monkeypatch: pytest.MonkeyPatch, func: str, name: str, query: Any, count: int
) -> None:
    client = _client(monkeypatch, name)
    page = getattr(market_data, func)(query, _SETTINGS)
    assert isinstance(page, ReportPage)
    assert page.total == len(page.items) == count
    assert page.items == _items(name)
    (call,) = client.calls
    assert call["reportName"] == _SPECS[name].report


@pytest.mark.parametrize(
    "func,name,column",
    [
        ("billboard_institution_em", "institution", "TRADE_DATE"),
        ("billboard_branch_active_em", "branch_active", "ONLIST_DATE"),
    ],
)
def test_interface_without_query_takes_latest_day(
    monkeypatch: pytest.MonkeyPatch, func: str, name: str, column: str
) -> None:
    client = _client(monkeypatch, name, latest="2026-11-11 00:00:00")
    page = getattr(market_data, func)(settings=_SETTINGS)
    assert len(page.items) == 2
    lookup, data = client.calls
    assert (lookup["columns"], lookup["sortColumns"], lookup["sortTypes"]) == (column, column, "-1")
    assert data["filter"] == f"({column}='2026-11-11')"


def test_stock_without_date_looks_up_latest_day_of_that_stock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(monkeypatch, "stock_sell", latest="2026-11-11 00:00:00")
    page = market_data.billboard_stock_em(BillboardStockQuery("000026", side="sell"), _SETTINGS)
    assert len(page.items) == 5
    lookup, data = client.calls
    assert lookup["filter"] == '(SECURITY_CODE="000026")'
    assert data["filter"] == "(SECURITY_CODE=\"000026\")(TRADE_DATE='2026-11-11')"
    assert lookup["reportName"] == data["reportName"] == "RPT_BILLBOARD_DAILYDETAILSSELL"


@pytest.mark.parametrize(
    "func",
    [
        "billboard_stock_stats_em",
        "billboard_institution_stats_em",
        "billboard_branch_rank_em",
        "billboard_branch_stats_em",
    ],
)
def test_period_interface_defaults_to_one_month(monkeypatch: pytest.MonkeyPatch, func: str) -> None:
    name = func.removeprefix("billboard_").removesuffix("_em")
    client = _client(monkeypatch, name)
    getattr(market_data, func)(settings=_SETTINGS)
    (call,) = client.calls
    assert call["filter"].endswith('="01")')


# ---------------------------------------------------------------- DataFrame

# 转换函数 -> (固定报文段, 行数, 开头几列, 另外必须有的列)
_FRAME_CASES: list[tuple[str, str, int, list[str], list[str]]] = [
    (
        "to_billboard_stock_stats_dataframe",
        "stock_stats",
        2,
        ["代码", "名称", "市场", "最近上榜日", "收盘价"],
        ["上榜次数", "龙虎榜净买额", "机构买入净额", "近1年涨跌幅"],
    ),
    (
        "to_billboard_institution_dataframe",
        "institution",
        2,
        ["代码", "名称", "市场", "收盘价", "涨跌幅"],
        ["买方机构数", "机构买入净额", "流通市值", "上榜原因", "上榜日期", "上榜后10日"],
    ),
    (
        "to_billboard_institution_stats_dataframe",
        "institution_stats",
        2,
        ["代码", "名称", "市场", "收盘价", "涨跌幅"],
        ["龙虎榜成交金额", "上榜次数", "机构净买额", "近1年涨跌幅"],
    ),
    (
        "to_billboard_branch_active_dataframe",
        "branch_active",
        2,
        ["营业部名称", "上榜日", "买入个股数", "卖出个股数", "买入总金额"],
        ["总买卖净额", "买入股票", "营业部代码", "买入股票代码"],
    ),
    (
        "to_billboard_branch_rank_dataframe",
        "branch_rank",
        2,
        ["营业部名称", "上榜后1天-买入次数", "上榜后1天-平均涨幅", "上榜后1天-上涨概率"],
        ["上榜后10天-上涨概率", "营业部代码"],
    ),
    (
        "to_billboard_branch_stats_dataframe",
        "branch_stats",
        2,
        ["营业部名称", "龙虎榜成交金额", "上榜次数", "买入额", "买入次数"],
        ["卖出额", "卖出次数", "营业部代码"],
    ),
    (
        "to_billboard_branch_trades_dataframe",
        "branch_trades",
        1,
        ["营业部代码", "营业部名称", "营业部简称", "交易日期", "股票代码", "股票名称", "市场"],
        ["买入金额", "卖出金额", "净额", "上榜原因", "30日后涨跌幅"],
    ),
    (
        "to_billboard_stock_dates_dataframe",
        "stock_dates",
        3,
        ["股票代码", "交易日"],
        [],
    ),
    (
        "to_billboard_stock_dataframe",
        "stock_buy_two_reasons",
        10,
        ["交易营业部名称", "买入金额", "买入金额-占总成交比例", "卖出金额"],
        ["卖出金额-占总成交比例", "净额", "类型", "营业部代码", "代码", "上榜日", "总成交额"],
    ),
]


@pytest.mark.parametrize(
    "func,name,rows,head,others", _FRAME_CASES, ids=[c[0] for c in _FRAME_CASES]
)
def test_dataframe_columns(
    func: str, name: str, rows: int, head: list[str], others: list[str]
) -> None:
    pd = pytest.importorskip("pandas")
    from em.application import dataframe

    convert = getattr(dataframe, func)
    items = _items(name)
    df = convert(ReportPage(total=len(items), items=items))
    assert isinstance(df, pd.DataFrame) and len(df) == rows
    assert list(df.columns)[: len(head)] == head
    assert set(others) <= set(df.columns)
    assert len(set(df.columns)) == len(df.columns)  # 中文列名不重复
    # 模型的每个字段都有一列
    assert len(df.columns) == len(items[0].__dataclass_fields__)
    # 空结果也保留列头
    empty = convert(ReportPage(total=0, items=()))
    assert empty.empty and list(empty.columns) == list(df.columns)


def test_dataframe_values_keep_model_units() -> None:
    pytest.importorskip("pandas")
    from em.application.dataframe import (
        to_billboard_branch_active_dataframe,
        to_billboard_branch_trades_dataframe,
        to_billboard_stock_dataframe,
    )

    active = _items("branch_active")
    df = to_billboard_branch_active_dataframe(ReportPage(total=2, items=active))
    assert df.loc[0, "营业部代码"] == "10634757"
    assert df.loc[0, "买入股票代码"] == active[0].stock_codes  # 元组原样保留

    trades = _items("branch_trades")
    df = to_billboard_branch_trades_dataframe(ReportPage(total=1, items=trades))
    assert df["买入金额"].isna().all()  # 只卖出：买入金额为空值
    assert df.loc[0, "卖出金额"] == pytest.approx(5265000)

    seats = _items("stock_buy_two_reasons")
    df = to_billboard_stock_dataframe(ReportPage(total=10, items=seats))
    assert df["类型"].nunique() == 2
    assert df.loc[0, "买入金额-占总成交比例"] == pytest.approx(5.3536779728)  # %


def test_dataframe_accepts_custom_column_names() -> None:
    pytest.importorskip("pandas")
    from em.application.dataframe import (
        BILLBOARD_STOCK_DATES_COLUMNS_ZH,
        to_billboard_stock_dates_dataframe,
    )

    items = _items("stock_dates")
    naming = {"code": "code", "trade_date": "date"}
    df = to_billboard_stock_dates_dataframe(ReportPage(total=3, items=items), naming)
    assert list(df.columns) == ["code", "date"]
    assert list(BILLBOARD_STOCK_DATES_COLUMNS_ZH) == ["code", "trade_date"]


def test_df_interface_returns_dataframe(monkeypatch: pytest.MonkeyPatch) -> None:
    pd = pytest.importorskip("pandas")
    _client(monkeypatch, "stock_dates")
    df = market_data.df_billboard_stock_dates_em(BillboardStockDatesQuery("000530"), _SETTINGS)
    assert isinstance(df, pd.DataFrame)
    assert list(df["交易日"]) == ["2026-11-11", "2026-11-10", "2026-11-06"]

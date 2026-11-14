"""大宗交易 6 张报表的映射、请求构建、端到端取数与 DataFrame 行为锁（不触网）。

固定报文 ``datacenter_block_trade.json`` 是 2026-11-13 抓取的真实响应（每页 2 条的第 1 页，
个别为专门挑出的边界样本）：

- ``detail_same_trades``：300750 宁德时代 11-10 三笔买卖双方、价格、数量完全相同的成交；
- ``detail_fund`` / ``detail_bond`` / ``detail_bshare``：基金、债券、B 股各一笔；
- ``branch_active_sell_only``：只卖出的营业部（买入的股票为 null）；
- ``branch_rank_partial``：只有 1 日档到期、5 / 10 / 20 日档都还是 null 的营业部。
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

import em
from em.application import market_data, registry
from em.channels.eastmoney import config
from em.channels.eastmoney.ashare_block_trade import (
    block_trade_branch_active,
    block_trade_branch_rank,
    block_trade_stock_stats,
)
from em.channels.eastmoney.ashare_block_trade.block_trade_branch_active import (
    BLOCK_TRADE_BRANCH_ACTIVE,
    block_trade_branch_active_request,
)
from em.channels.eastmoney.ashare_block_trade.block_trade_branch_rank import (
    BLOCK_TRADE_BRANCH_RANK,
    block_trade_branch_rank_request,
)
from em.channels.eastmoney.ashare_block_trade.block_trade_detail import (
    BLOCK_TRADE_DETAIL,
    block_trade_detail_request,
    normalize_security_type,
)
from em.channels.eastmoney.ashare_block_trade.block_trade_market_daily import (
    BLOCK_TRADE_MARKET_DAILY,
    block_trade_market_daily_request,
)
from em.channels.eastmoney.ashare_block_trade.block_trade_stock_daily import (
    BLOCK_TRADE_STOCK_DAILY,
    block_trade_stock_daily_request,
)
from em.channels.eastmoney.ashare_block_trade.block_trade_stock_stats import (
    BLOCK_TRADE_STOCK_STATS,
    block_trade_stock_stats_request,
)
from em.channels.eastmoney.datacenter import (
    ReportSpec,
    pair_codes,
    pair_names,
    required_day,
    to_report_chunk,
)
from em.core.errors import InvalidContentError
from em.core.settings import Settings
from em.domain.models import ReportPage
from em.domain.queries import (
    BlockTradeBranchActiveQuery,
    BlockTradeBranchRankQuery,
    BlockTradeDetailQuery,
    BlockTradeMarketDailyQuery,
    BlockTradeStockDailyQuery,
    BlockTradeStockStatsQuery,
)

FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "eastmoney" / "datacenter_block_trade.json"
)

# 固定报文段 -> 解析它的报表声明
_SPECS: dict[str, ReportSpec[Any]] = {
    "market_daily": BLOCK_TRADE_MARKET_DAILY,
    "detail": BLOCK_TRADE_DETAIL,
    "detail_same_trades": BLOCK_TRADE_DETAIL,
    "detail_fund": BLOCK_TRADE_DETAIL,
    "detail_bond": BLOCK_TRADE_DETAIL,
    "detail_bshare": BLOCK_TRADE_DETAIL,
    "stock_daily": BLOCK_TRADE_STOCK_DAILY,
    "stock_stats": BLOCK_TRADE_STOCK_STATS,
    "branch_active": BLOCK_TRADE_BRANCH_ACTIVE,
    "branch_active_sell_only": BLOCK_TRADE_BRANCH_ACTIVE,
    "branch_rank": BLOCK_TRADE_BRANCH_RANK,
    "branch_rank_partial": BLOCK_TRADE_BRANCH_RANK,
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


def test_pair_converters() -> None:
    raw = "000338|潍柴动力,000725|京东方A, 603031|安孚科技"
    assert pair_codes(raw) == ("000338", "000725", "603031")
    assert pair_names(raw) == "潍柴动力 京东方A 安孚科技"
    assert pair_codes(None) == pair_codes("") == pair_codes("-") == ()
    assert pair_names(None) is None and pair_names("") is None
    assert pair_codes("000338") == ("000338",) and pair_names("000338") is None  # 没有简称
    assert required_day("2026-11-12 00:00:00") == "2026-11-12" and required_day(None) == ""


# ---------------------------------------------------------------- 行映射


def test_market_daily_fields() -> None:
    latest, previous = _items("market_daily")
    assert (latest.trade_date, previous.trade_date) == ("2026-11-12", "2026-11-11")
    # 上游列名 SZ_INDEX 的 SZ 是“上证”的拼音首字母：值是上证指数收盘点位，且以字符串给出
    assert latest.sh_index == pytest.approx(3655.8295) and isinstance(latest.sh_index, float)
    assert latest.sh_index_change_pct == pytest.approx(-0.674156698933)
    assert latest.amount == pytest.approx(843_182_600)
    # 两个占比都是 %：溢价 / 折价成交额占成交总额；其余是平价成交
    assert latest.premium_ratio == pytest.approx(100 * latest.premium_amount / latest.amount)
    assert latest.discount_ratio == pytest.approx(100 * latest.discount_amount / latest.amount)
    assert latest.premium_amount + latest.discount_amount < latest.amount


def test_detail_fields() -> None:
    e = _items("detail")[0]
    assert (e.code, e.name, e.market, e.trade_date) == ("000656", "金科股份", "sz", "2026-11-12")
    assert (e.close, e.price) == (pytest.approx(1.04), pytest.approx(1.02))
    # 折溢率上游给比例（-0.0192），统一成 %：成交价 / 收盘价 - 1
    assert e.premium_rate == pytest.approx(-1.9230769231)
    assert e.premium_rate == pytest.approx(100 * (e.price / e.close - 1))
    assert (e.volume, e.amount) == (pytest.approx(3_000_000), pytest.approx(3_060_000))
    assert e.amount == pytest.approx(e.price * e.volume)  # A 股：成交量是股
    assert e.float_market_cap_ratio == pytest.approx(0.031349961031)
    assert (e.buyer_code, e.buyer_name) == ("10126062", "招商证券股份有限公司温州府东路证券营业部")
    assert (e.seller_code, e.seller_name) == (
        "10046604",
        "中信证券股份有限公司杭州凤起路证券营业部",
    )
    # 11-13 抓取时 11-12 成交的只有 1 日后涨跌幅到期
    assert e.change_after_1d == pytest.approx(-0.96153846)
    assert (e.change_after_5d, e.change_after_10d, e.change_after_20d) == (None, None, None)


def test_detail_institution_code_is_zero() -> None:
    # 机构专用的营业部代码是 "0"：要保留成文本，不能被当成空值
    e = _items("detail")[1]
    assert (e.buyer_name, e.seller_name) == ("机构专用", "机构专用")
    assert (e.buyer_code, e.seller_code) == ("0", "0")
    assert e.premium_rate == 0.0  # 平价成交是 0 而不是 None


def test_detail_identical_trades_are_all_kept() -> None:
    # 上游没有成交编号：同一只股票同一天三笔买卖双方、价格、数量都相同的成交
    name = "detail_same_trades"
    chunk = to_report_chunk(_fx()[name], _SPECS[name].map_row)
    assert len(chunk.items) == 3 and len(set(chunk.items)) == 1  # 映射后三条完全相同
    assert chunk.items[0].code == "300750" and chunk.items[0].volume == pytest.approx(12_000)
    # DAILY_RANK 不映射但一并请求：整行去重键各不相同，即使打开 distinct 也不会丢成一条
    assert "DAILY_RANK" in BLOCK_TRADE_DETAIL.key_columns
    assert len(set(chunk.keys)) == 3
    assert [row["DAILY_RANK"] for row in _fx()[name]["result"]["data"]] == [1, 3, 4]


@pytest.mark.parametrize(
    "name,code,market",
    [
        ("detail_fund", "159352", "sz"),
        ("detail_bond", "123088", "sz"),
        ("detail_bshare", "900905", "sh"),
    ],
)
def test_detail_other_security_types(name: str, code: str, market: str) -> None:
    (e,) = _items(name)
    assert (e.code, e.market) == (code, market)
    # 收盘价、涨跌幅、折溢率上游都有（akshare 对非 A 股直接丢掉）
    assert e.close is not None and e.change_pct is not None
    assert e.premium_rate == pytest.approx(100 * (e.price / e.close - 1))
    # 没有流通市值占比和之后 N 日涨跌幅
    assert e.float_market_cap_ratio is None
    assert (e.change_after_1d, e.change_after_5d, e.change_after_10d, e.change_after_20d) == (
        None,
        None,
        None,
        None,
    )


def test_detail_bond_volume_is_in_lots() -> None:
    # 债券的成交量是手（1 手 = 10 张）：成交额 = 成交价 × 成交量 × 10，与股票、基金不同
    (bond,) = _items("detail_bond")
    assert bond.amount == pytest.approx(bond.price * bond.volume * 10)
    (fund,) = _items("detail_fund")
    assert fund.amount == pytest.approx(fund.price * fund.volume, rel=0.01)  # 基金：份
    (bshare,) = _items("detail_bshare")
    assert bshare.amount == pytest.approx(bshare.price * bshare.volume, rel=0.01)


def test_stock_daily_fields() -> None:
    e = _items("stock_daily")[0]
    assert (e.code, e.name, e.market, e.trade_date) == ("301395", "仁信新材", "sz", "2026-11-12")
    assert (e.deal_times, e.premium_times, e.discount_times) == (4, 0, 4)
    assert isinstance(e.deal_times, int)
    # 上游给万股、万元（225.3 / 2570.67），统一成股、元
    assert (e.volume, e.amount) == (pytest.approx(2_253_000), pytest.approx(25_706_700))
    assert e.avg_price == pytest.approx(e.amount / e.volume, abs=0.006)
    # 折溢率上游给比例，统一成 %：成交均价 / 收盘价 - 1
    assert e.premium_rate == pytest.approx(-17.9726815241)
    assert e.premium_rate == pytest.approx(100 * (e.avg_price / e.close - 1))
    assert e.float_market_cap_ratio == pytest.approx(1.428730961632)
    assert e.change_after_1d == pytest.approx(5.89503954)
    assert (e.change_after_5d, e.change_after_10d, e.change_after_20d) == (None, None, None)


def test_stock_daily_flat_trades_count_as_neither() -> None:
    # 平价成交既不算溢价也不算折价：溢价笔数 + 折价笔数可以小于成交笔数
    e = _items("stock_daily")[1]
    assert (e.deal_times, e.premium_times, e.discount_times) == (2, 0, 0)
    assert e.premium_rate == 0.0


def test_stock_stats_fields() -> None:
    e = _items("stock_stats")[0]
    assert (e.code, e.name, e.market, e.latest_date) == ("688293", "奥浦迈", "sh", "2026-11-12")
    assert (e.deal_times, e.premium_times, e.discount_times) == (67, 0, 67)
    assert e.amount == pytest.approx(259_695_700)  # 上游给万元（25969.57）
    assert e.premium_rate == pytest.approx(-9.1888054148)  # 上游给比例
    assert e.float_market_cap_ratio == pytest.approx(3.254831334014)
    assert (e.close, e.change_pct) == (pytest.approx(68.83), pytest.approx(2.1368))
    assert (
        e.avg_change_after_1d,
        e.avg_change_after_5d,
        e.avg_change_after_10d,
        e.avg_change_after_20d,
    ) == (
        pytest.approx(-1.512896822985),
        pytest.approx(0.690675921642),
        pytest.approx(2.61638878806),
        pytest.approx(0.944005806269),
    )


def test_branch_active_fields() -> None:
    first, second = _items("branch_active")
    assert (first.branch_code, first.branch_name) == ("0", "机构专用")
    assert (first.latest_date, first.buy_times, first.sell_times) == ("2026-11-13", 77, 63)
    # 上游给万元，统一成元；净买入额 = 买入 - 卖出
    assert first.buy == pytest.approx(1_836_215_300)
    assert first.buy - first.sell == pytest.approx(first.net_buy)
    assert (second.branch_code, second.branch_name) == ("10388201", "平安证券深圳金田路证券营业部")
    # “代码|简称”逗号分隔 -> 简称（空格分隔）与代码元组，一一对应
    assert second.buy_stocks == "中际旭创 中国化学 仙鹤股份 道通科技"
    assert second.buy_stock_codes == ("300308", "601117", "603733", "688208")
    assert len(first.buy_stock_codes) == len(first.buy_stocks.split()) == 61
    # 买入的股票去重：买入 6 笔只涉及 4 只
    assert second.buy_times == 6 and len(second.buy_stock_codes) == 4


def test_branch_active_sell_only() -> None:
    # 只卖出的营业部：买入的股票上游为 null；这里确实只含买入的（不同于龙虎榜的“买入股票”）
    (e,) = _items("branch_active_sell_only")
    assert (e.buy_times, e.sell_times) == (0, 4)
    assert (e.buy, e.sell, e.net_buy) == (0.0, pytest.approx(8_800_000), pytest.approx(-8_800_000))
    assert e.buy_stocks is None and e.buy_stock_codes == ()


def test_branch_rank_fields() -> None:
    e = _items("branch_rank")[1]
    assert (e.branch_code, e.branch_name) == ("10510599", "广发证券慈溪浒山路证券营业部")
    assert (e.buy_times_1d, e.buy_times_5d, e.buy_times_10d, e.buy_times_20d) == (64, 62, 58, 22)
    assert (e.avg_change_1d, e.rise_prob_1d) == (
        pytest.approx(-1.285870166719),
        pytest.approx(32.8125),
    )
    assert (e.avg_change_20d, e.rise_prob_20d) == (
        pytest.approx(-9.319462768182),
        pytest.approx(27.272727272727),
    )


def test_branch_rank_undue_tiers_are_none() -> None:
    # 5 / 10 / 20 日档还没有到期的买入：三列都是 None，不是 0
    (e,) = _items("branch_rank_partial")
    assert (e.buy_times_1d, e.avg_change_1d, e.rise_prob_1d) == (
        1,
        pytest.approx(7.11574953),
        pytest.approx(100.0),
    )
    for days in (5, 10, 20):
        assert getattr(e, f"buy_times_{days}d") is None
        assert getattr(e, f"avg_change_{days}d") is None
        assert getattr(e, f"rise_prob_{days}d") is None


# ---------------------------------------------------------------- 请求：按日期区间


def test_market_daily_request() -> None:
    request = block_trade_market_daily_request(BlockTradeMarketDailyQuery("20261109", "20261113"))
    params = request.params()
    assert params["reportName"] == "PRT_BLOCKTRADE_MARKET_STA"  # 上游就是 PRT 开头
    assert params["filter"] == "(TRADE_DATE>='2026-11-09')(TRADE_DATE<='2026-11-13')"
    assert (params["sortColumns"], params["sortTypes"]) == ("TRADE_DATE", "-1")
    assert request.latest_of == ""


def test_market_daily_without_dates_takes_full_history() -> None:
    # 与其余按日期的报表不同：一天一行的时间序列，留空取全部历史，不先查最新交易日
    request = block_trade_market_daily_request(BlockTradeMarketDailyQuery())
    assert (request.filter, request.latest_of) == ("", "")
    assert "filter" not in request.params()


def test_stock_daily_request() -> None:
    request = block_trade_stock_daily_request(BlockTradeStockDailyQuery("20261012", "20261112"))
    params = request.params()
    assert params["reportName"] == "RPT_BLOCKTRADE_STA"
    assert params["filter"] == "(TRADE_DATE>='2026-10-12')(TRADE_DATE<='2026-11-12')"
    # 占比并列时靠日期、代码排在固定位置，翻页顺序才稳定
    assert (params["sortColumns"], params["sortTypes"]) == (
        "TURNOVERRATE,TRADE_DATE,SECURITY_CODE",
        "-1,-1,1",
    )
    latest = block_trade_stock_daily_request(BlockTradeStockDailyQuery())
    assert (latest.latest_of, latest.filter) == ("TRADE_DATE", "")


@pytest.mark.parametrize(
    "security_type,code",
    [("ashare", "1"), ("bshare", "2"), ("fund", "3"), ("bond", "4")],
)
def test_detail_request_per_security_type(security_type: str, code: str) -> None:
    request = block_trade_detail_request(
        BlockTradeDetailQuery("20261112", "20261112", security_type)
    )
    params = request.params()
    assert params["reportName"] == "RPT_DATA_BLOCKTRADE"
    assert params["filter"] == (
        f"(SECURITY_TYPE_WEB=\"{code}\")(TRADE_DATE>='2026-11-12')(TRADE_DATE<='2026-11-12')"
    )
    # 类型列一并请求：上游对拼错的过滤字段静默忽略、返回整张表（68 万行）
    assert "SECURITY_TYPE_WEB" in params["columns"].split(",")


def test_detail_request_sort_is_unique() -> None:
    # akshare 只按代码排序，翻页会重复和丢行；补日期与 DAILY_RANK 后（代码, 日期, 序号）唯一
    params = block_trade_detail_request(BlockTradeDetailQuery("20261112")).params()
    assert (params["sortColumns"], params["sortTypes"]) == (
        "SECURITY_CODE,TRADE_DATE,DAILY_RANK",
        "1,-1,1",
    )
    assert "DAILY_RANK" in params["columns"].split(",")


def test_detail_request_unknown_type_falls_back_to_ashare() -> None:
    assert normalize_security_type("fund") == "fund"
    assert normalize_security_type("stock") == normalize_security_type("") == "ashare"
    request = block_trade_detail_request(BlockTradeDetailQuery("20261112", security_type="etf"))
    assert request.filter.startswith('(SECURITY_TYPE_WEB="1")')
    assert BlockTradeDetailQuery().security_type == "ashare"


def test_detail_request_without_dates_takes_latest_day_of_that_type() -> None:
    request = block_trade_detail_request(BlockTradeDetailQuery(security_type="bshare"))
    assert (request.latest_of, request.filter) == ("TRADE_DATE", '(SECURITY_TYPE_WEB="2")')
    # 最新交易日要在这一类证券里找：B 股几个月才有一笔，全市场的最新交易日多半没有 B 股成交
    assert request.latest_lookup().filter == '(SECURITY_TYPE_WEB="2")'
    assert request.on_day("2026-06-23").filter == (
        "(SECURITY_TYPE_WEB=\"2\")(TRADE_DATE='2026-06-23')"
    )


_SPAN_BUILDERS: list[tuple[Callable[[Any], Any], Callable[..., Any]]] = [
    (block_trade_market_daily_request, BlockTradeMarketDailyQuery),
    (block_trade_detail_request, BlockTradeDetailQuery),
    (block_trade_stock_daily_request, BlockTradeStockDailyQuery),
]
_SPAN_IDS = ["market_daily", "detail", "stock_daily"]


@pytest.mark.parametrize("build,query", _SPAN_BUILDERS, ids=_SPAN_IDS)
def test_span_request_date_rules(build: Callable[[Any], Any], query: Callable[..., Any]) -> None:
    # 只给 end_date：只取那一天
    assert build(query(end_date="20261112")).filter.endswith(
        "(TRADE_DATE>='2026-11-12')(TRADE_DATE<='2026-11-12')"
    )
    with pytest.raises(ValueError, match="YYYYMMDD"):
        build(query("2026-11-12"))
    with pytest.raises(ValueError, match="晚于"):
        build(query("20261112", "20261101"))


# ---------------------------------------------------------------- 请求：按统计周期

_PERIOD_CASES: list[tuple[Callable[[Any], Any], Callable[..., Any], str, str, dict[str, str]]] = [
    (
        block_trade_stock_stats_request,
        BlockTradeStockStatsQuery,
        "RPT_BLOCKTRADE_ACSTA",
        "DATE_TYPE_CODE",
        {"1mo": "1", "3mo": "3", "6mo": "6", "1y": "12"},
    ),
    (
        block_trade_branch_active_request,
        BlockTradeBranchActiveQuery,
        "RPT_BLOCKTRADE_OPERATEDEPTSTATISTICS",
        "N_DATE",
        {"1d": "0", "3d": "-3", "5d": "-5", "10d": "-10", "30d": "-30"},
    ),
    (
        block_trade_branch_rank_request,
        BlockTradeBranchRankQuery,
        "RPT_BLOCKTRADE_OPERATEDEPT_RANK",
        "N_DATE",
        {"30d": "-30", "90d": "-90", "180d": "-180", "360d": "-360"},
    ),
]
_PERIOD_IDS = ["stock_stats", "branch_active", "branch_rank"]


@pytest.mark.parametrize("build,query,report,column,values", _PERIOD_CASES, ids=_PERIOD_IDS)
def test_period_request(
    build: Callable[[Any], Any],
    query: Callable[..., Any],
    report: str,
    column: str,
    values: dict[str, str],
) -> None:
    default = next(iter(values))
    params = build(query()).params()
    assert params["reportName"] == report
    assert params["filter"] == f'({column}="{values[default]}")'  # 默认取第一个周期
    assert query().period == default
    # 周期列一并请求：上游改名时报 9501，而不是静默返回全部周期的行
    assert column in params["columns"].split(",")
    for period, value in values.items():
        assert build(query(period=period)).filter == f'({column}="{value}")'
    assert build(query(period="2w")).filter == params["filter"]  # 未知回退默认周期
    assert build(query()).latest_of == ""


def test_period_values_match_config() -> None:
    assert _PERIOD_CASES[0][4] == config.BLOCK_TRADE_STOCK_PERIODS
    assert _PERIOD_CASES[1][4] == config.BLOCK_TRADE_ACTIVE_PERIODS
    assert _PERIOD_CASES[2][4] == config.BLOCK_TRADE_RANK_PERIODS


def test_branch_active_latest_day_is_zero_not_minus_one() -> None:
    # akshare 的“当前交易日”传 N_DATE=-1，实测查不到任何行；上游的“最新”是 0
    request = block_trade_branch_active_request(BlockTradeBranchActiveQuery("1d"))
    assert request.filter == '(N_DATE="0")'


def test_normalize_period_fallbacks() -> None:
    assert block_trade_stock_stats.normalize_period("1y") == "1y"
    assert block_trade_stock_stats.normalize_period("30d") == "1mo"
    assert block_trade_branch_active.normalize_period("30d") == "30d"
    assert block_trade_branch_active.normalize_period("1mo") == "1d"
    assert block_trade_branch_rank.normalize_period("360d") == "360d"
    # 营业部排行的周期是交易日数：360 个交易日约一年半，不接受 1y 这种写法
    assert block_trade_branch_rank.normalize_period("1y") == "30d"


def test_period_sorts_end_with_a_unique_key() -> None:
    # 活跃营业部：只卖出的营业部买入次数、金额都是 0，大量并列；排行不带唯一键翻页会重复和丢行
    assert block_trade_branch_active_request(BlockTradeBranchActiveQuery()).params()[
        "sortColumns"
    ] == ("BUYER_NUM,TOTAL_BUYAMT,OPERATEDEPT_CODE")
    assert block_trade_branch_rank_request(BlockTradeBranchRankQuery()).params()["sortColumns"] == (
        "D5_BUYER_NUM,D1_AVERAGE_INCREASE,OPERATEDEPT_CODE"
    )
    assert block_trade_stock_stats_request(BlockTradeStockStatsQuery()).params()["sortColumns"] == (
        "DEAL_NUM,SECURITY_CODE"
    )


# ---------------------------------------------------------------- 注册表与对外导出

_NAMES = [
    "block_trade_market_daily",
    "block_trade_detail",
    "block_trade_stock_daily",
    "block_trade_stock_stats",
    "block_trade_branch_active",
    "block_trade_branch_rank",
]
_BUILDERS = [
    block_trade_market_daily_request,
    block_trade_detail_request,
    block_trade_stock_daily_request,
    block_trade_stock_stats_request,
    block_trade_branch_active_request,
    block_trade_branch_rank_request,
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
        if params["pageSize"] == "1":  # 最新交易日查询
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

# 接口 -> (固定报文段, 查询, 条数)：一次请求取完
_DIRECT_CASES: list[tuple[str, str, Any, int]] = [
    ("block_trade_market_daily_em", "market_daily", None, 2),
    (
        "block_trade_market_daily_em",
        "market_daily",
        BlockTradeMarketDailyQuery("20261111", "20261112"),
        2,
    ),
    ("block_trade_detail_em", "detail", BlockTradeDetailQuery("20261112", "20261112"), 2),
    (
        "block_trade_detail_em",
        "detail_same_trades",
        BlockTradeDetailQuery("20261110", "20261110"),
        3,
    ),
    (
        "block_trade_detail_em",
        "detail_bond",
        BlockTradeDetailQuery("20261112", "20261112", "bond"),
        1,
    ),
    (
        "block_trade_stock_daily_em",
        "stock_daily",
        BlockTradeStockDailyQuery("20261112", "20261112"),
        2,
    ),
    ("block_trade_stock_stats_em", "stock_stats", None, 2),
    ("block_trade_stock_stats_em", "stock_stats", BlockTradeStockStatsQuery("1y"), 2),
    ("block_trade_branch_active_em", "branch_active", None, 2),
    ("block_trade_branch_active_em", "branch_active", BlockTradeBranchActiveQuery("3d"), 2),
    ("block_trade_branch_rank_em", "branch_rank", None, 2),
    ("block_trade_branch_rank_em", "branch_rank", BlockTradeBranchRankQuery("360d"), 2),
]


@pytest.mark.parametrize(
    "func,name,query,count",
    _DIRECT_CASES,
    ids=[f"{c[0]}:{c[1]}:{'default' if c[2] is None else 'query'}" for c in _DIRECT_CASES],
)
def test_interface_fetches_report(
    monkeypatch: pytest.MonkeyPatch, func: str, name: str, query: Any, count: int
) -> None:
    client = _client(monkeypatch, name)
    page = getattr(market_data, func)(query, _SETTINGS)
    assert isinstance(page, ReportPage)
    assert page.total == len(page.items) == count
    assert page.items == _items(name)  # 相同的几笔成交也一条不少
    (call,) = client.calls  # 没有“先查最新交易日”的额外请求
    assert call["reportName"] == _SPECS[name].report


@pytest.mark.parametrize(
    "func,name,prefix",
    [
        ("block_trade_detail_em", "detail", '(SECURITY_TYPE_WEB="1")'),
        ("block_trade_stock_daily_em", "stock_daily", ""),
    ],
)
def test_interface_without_dates_takes_latest_day(
    monkeypatch: pytest.MonkeyPatch, func: str, name: str, prefix: str
) -> None:
    client = _client(monkeypatch, name, latest="2026-11-12 00:00:00")
    page = getattr(market_data, func)(settings=_SETTINGS)
    assert len(page.items) == 2
    lookup, data = client.calls
    assert (lookup["columns"], lookup["sortColumns"], lookup["sortTypes"]) == (
        "TRADE_DATE",
        "TRADE_DATE",
        "-1",
    )
    assert lookup.get("filter", "") == prefix  # 最新交易日在同一证券类型里找
    assert data["filter"] == f"{prefix}(TRADE_DATE='2026-11-12')"


def test_market_daily_without_dates_sends_no_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch, "market_daily")
    market_data.block_trade_market_daily_em(settings=_SETTINGS)
    (call,) = client.calls
    assert "filter" not in call


# ---------------------------------------------------------------- DataFrame

# 转换函数 -> (固定报文段, 行数, 开头几列, 另外必须有的列)
_FRAME_CASES: list[tuple[str, str, int, list[str], list[str]]] = [
    (
        "to_block_trade_market_daily_dataframe",
        "market_daily",
        2,
        ["交易日期", "上证指数", "上证指数涨跌幅", "大宗交易成交总额", "溢价成交总额"],
        ["溢价成交总额占比", "折价成交总额", "折价成交总额占比"],
    ),
    (
        "to_block_trade_detail_dataframe",
        "detail",
        2,
        ["交易日期", "证券代码", "证券简称", "市场", "涨跌幅", "收盘价", "成交价", "折溢率"],
        ["成交量", "成交额", "成交额/流通市值", "买方营业部", "卖方营业部", "20日后涨跌幅"],
    ),
    (
        "to_block_trade_stock_daily_dataframe",
        "stock_daily",
        2,
        ["交易日期", "证券代码", "证券简称", "市场", "涨跌幅", "收盘价", "成交价", "折溢率"],
        ["成交笔数", "成交总量", "成交总额", "成交总额/流通市值", "溢价笔数", "折价笔数"],
    ),
    (
        "to_block_trade_stock_stats_dataframe",
        "stock_stats",
        2,
        ["证券代码", "证券简称", "市场", "最新价", "涨跌幅", "最近上榜日"],
        ["上榜次数-总计", "上榜次数-溢价", "上榜次数-折价", "总成交额", "上榜日后平均涨跌幅-20日"],
    ),
    (
        "to_block_trade_branch_active_dataframe",
        "branch_active",
        2,
        ["最近上榜日", "营业部名称", "次数总计-买入", "次数总计-卖出", "成交金额统计-买入"],
        ["成交金额统计-卖出", "成交金额统计-净买入额", "买入的股票", "营业部代码", "买入股票代码"],
    ),
    (
        "to_block_trade_branch_rank_dataframe",
        "branch_rank",
        2,
        ["营业部名称", "上榜后1天-买入次数", "上榜后1天-平均涨幅", "上榜后1天-上涨概率"],
        ["上榜后5天-买入次数", "上榜后10天-平均涨幅", "上榜后20天-上涨概率", "营业部代码"],
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
        to_block_trade_branch_active_dataframe,
        to_block_trade_branch_rank_dataframe,
        to_block_trade_detail_dataframe,
        to_block_trade_stock_daily_dataframe,
    )

    detail = _items("detail_same_trades")
    df = to_block_trade_detail_dataframe(ReportPage(total=3, items=detail))
    assert len(df) == 3 and df.duplicated().sum() == 2  # 相同的三笔都在
    assert df.loc[0, "买方营业部代码"] == "0"

    daily = _items("stock_daily")
    df = to_block_trade_stock_daily_dataframe(ReportPage(total=2, items=daily))
    assert df.loc[0, "成交总额"] == pytest.approx(25_706_700)  # 元
    assert df.loc[0, "折溢率"] == pytest.approx(-17.9726815241)  # %

    sell_only = _items("branch_active_sell_only")
    df = to_block_trade_branch_active_dataframe(ReportPage(total=1, items=sell_only))
    assert df["买入的股票"].isna().all() and df.loc[0, "买入股票代码"] == ()

    partial = _items("branch_rank_partial")
    df = to_block_trade_branch_rank_dataframe(ReportPage(total=1, items=partial))
    assert df["上榜后5天-买入次数"].isna().all() and df.loc[0, "上榜后1天-买入次数"] == 1


def test_df_interface_returns_dataframe(monkeypatch: pytest.MonkeyPatch) -> None:
    pd = pytest.importorskip("pandas")
    _client(monkeypatch, "market_daily")
    df = market_data.df_block_trade_market_daily_em(settings=_SETTINGS)
    assert isinstance(df, pd.DataFrame)
    assert list(df["交易日期"]) == ["2026-11-12", "2026-11-11"]
    naming = {
        "trade_date": "date",
        "sh_index": "index",
        "sh_index_change_pct": "index_pct",
        "amount": "amount",
        "premium_amount": "premium",
        "premium_ratio": "premium_pct",
        "discount_amount": "discount",
        "discount_ratio": "discount_pct",
    }
    custom = market_data.df_block_trade_market_daily_em(settings=_SETTINGS, columns=naming)
    assert list(custom.columns) == list(naming.values())

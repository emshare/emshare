"""业绩与财报 7 张报表的映射、请求构建、端到端取数与 DataFrame 行为锁（不触网）。

固定报文 ``datacenter_financials.json`` 是 2026-11-14 抓取的真实响应（每页 2 条的第 1 页，或按代码
挑出的单行样本）：

- ``report_annual``：000001 平安银行 2025 年报（有扣非每股收益、分配方案、股息率）；
- ``forecast_one_company``：688845 傲拓科技 2026 年报预告的 3 项预测指标；
- ``schedule_changed``：920438 戈碧迦，预约披露日期变更过一次；
- ``balance_bank`` / ``income_insurer`` / ``cash_flow_broker``：招商银行、中国平安、中信证券，
  用来锁住金融类专用科目与一般公司科目互为空值。
"""

import json
import re
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

import em
from em.application import market_data, registry
from em.channels.eastmoney import config
from em.channels.eastmoney.ashare_earnings.earnings_express import (
    EARNINGS_EXPRESS,
    earnings_express_request,
)
from em.channels.eastmoney.ashare_earnings.earnings_forecast import (
    EARNINGS_FORECAST,
    earnings_forecast_request,
)
from em.channels.eastmoney.ashare_earnings.earnings_report import (
    EARNINGS_REPORT,
    earnings_report_request,
)
from em.channels.eastmoney.ashare_earnings.earnings_schedule import (
    EARNINGS_SCHEDULE,
    earnings_schedule_request,
)
from em.channels.eastmoney.ashare_financial_statements.balance_sheet import (
    BALANCE_SHEET,
    balance_sheet_request,
)
from em.channels.eastmoney.ashare_financial_statements.cash_flow_statement import (
    CASH_FLOW_STATEMENT,
    cash_flow_statement_request,
)
from em.channels.eastmoney.ashare_financial_statements.income_statement import (
    INCOME_STATEMENT,
    income_statement_request,
)
from em.channels.eastmoney.datacenter import (
    ReportSpec,
    last_quarter_end,
    report_period_filter,
    to_report_chunk,
)
from em.core.errors import InvalidContentError
from em.core.settings import Settings
from em.domain.models import ReportPage
from em.domain.queries import (
    BalanceSheetQuery,
    CashFlowStatementQuery,
    EarningsExpressQuery,
    EarningsForecastQuery,
    EarningsReportQuery,
    EarningsScheduleQuery,
    IncomeStatementQuery,
)

FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "eastmoney" / "datacenter_financials.json"
)
A_SHARE = '(SECURITY_TYPE_CODE in ("058001001","058001008"))'

# 固定报文段 -> 解析它的报表声明
_SPECS: dict[str, ReportSpec[Any]] = {
    "report": EARNINGS_REPORT,
    "report_annual": EARNINGS_REPORT,
    "express": EARNINGS_EXPRESS,
    "forecast": EARNINGS_FORECAST,
    "forecast_one_company": EARNINGS_FORECAST,
    "schedule": EARNINGS_SCHEDULE,
    "schedule_changed": EARNINGS_SCHEDULE,
    "balance": BALANCE_SHEET,
    "balance_bank": BALANCE_SHEET,
    "income": INCOME_STATEMENT,
    "income_insurer": INCOME_STATEMENT,
    "cash_flow": CASH_FLOW_STATEMENT,
    "cash_flow_broker": CASH_FLOW_STATEMENT,
}

# 接口名 -> (请求构建, 查询, 报表名, 报告期列, 固定报文段)
_INTERFACES: dict[str, tuple[Callable[[Any], Any], Callable[..., Any], str, str, str]] = {
    "earnings_report": (
        earnings_report_request,
        EarningsReportQuery,
        "RPT_LICO_FN_CPD",
        "REPORTDATE",
        "report",
    ),
    "earnings_express": (
        earnings_express_request,
        EarningsExpressQuery,
        "RPT_FCI_PERFORMANCEE",
        "REPORT_DATE",
        "express",
    ),
    "earnings_forecast": (
        earnings_forecast_request,
        EarningsForecastQuery,
        "RPT_PUBLIC_OP_NEWPREDICT",
        "REPORT_DATE",
        "forecast",
    ),
    "earnings_schedule": (
        earnings_schedule_request,
        EarningsScheduleQuery,
        "RPT_PUBLIC_BS_APPOIN",
        "REPORT_DATE",
        "schedule",
    ),
    "balance_sheet": (
        balance_sheet_request,
        BalanceSheetQuery,
        "RPT_DMSK_FN_BALANCE",
        "REPORT_DATE",
        "balance",
    ),
    "income_statement": (
        income_statement_request,
        IncomeStatementQuery,
        "RPT_DMSK_FN_INCOME",
        "REPORT_DATE",
        "income",
    ),
    "cash_flow_statement": (
        cash_flow_statement_request,
        CashFlowStatementQuery,
        "RPT_DMSK_FN_CASHFLOW",
        "REPORT_DATE",
        "cash_flow",
    ),
}
_NAMES = list(_INTERFACES)


def _fx() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _items(name: str) -> tuple[Any, ...]:
    return to_report_chunk(_fx()[name], _SPECS[name].map_row).items


def _one(name: str) -> Any:
    (item,) = _items(name)
    return item


# ---------------------------------------------------------------- 报文与声明对齐


@pytest.mark.parametrize("name", sorted(_SPECS))
def test_fixture_carries_every_requested_column(name: str) -> None:
    # 声明里的上游列名写错时，row.get 会静默得到 None；这里用真实报文把 190 个列名锁住
    spec = _SPECS[name]
    wanted = {s for c in spec.columns for s in c.sources()} | set(spec.key_columns)
    for row in _fx()[name]["result"]["data"]:
        assert wanted <= set(row), f"{name} 缺列 {sorted(wanted - set(row))}"


@pytest.mark.parametrize("spec", list(dict.fromkeys(_SPECS.values())), ids=lambda s: s.report)
def test_spec_is_consistent(spec: ReportSpec[Any]) -> None:
    request = spec.request()
    assert set(request.sort_columns) <= set(request.columns)  # 排序列一并请求
    fields = [c.field for c in spec.columns]
    assert fields == list(spec.model.__dataclass_fields__)  # 列声明与模型字段一一对应
    sources = [s for c in spec.columns for s in c.sources()]
    assert len(set(sources)) == len(sources)  # 没有两个字段读同一列


# ---------------------------------------------------------------- 行映射：业绩


def test_report_fields() -> None:
    e = _items("report")[0]
    assert (e.code, e.name, e.market, e.report_date) == ("688662", "富信科技", "sh", "2026-09-30")
    assert (e.eps, e.bps, e.roe) == (
        pytest.approx(0.43),
        pytest.approx(6.310869210324),
        pytest.approx(6.63),
    )
    assert (e.revenue, e.net_profit) == (pytest.approx(505380545.2), pytest.approx(48402201.93))
    assert (e.revenue_yoy, e.revenue_qoq) == (pytest.approx(20.6198218507), pytest.approx(21.1176))
    assert (e.net_profit_yoy, e.net_profit_qoq) == (pytest.approx(50.04), pytest.approx(85.1868))
    assert e.gross_margin == pytest.approx(31.3859942704) and e.industry == "其他电子Ⅱ"
    # 有更正公告时最新公告日期晚于首次公告日期
    assert (e.notice_date, e.update_date) == ("2026-10-21", "2026-11-14")
    # 季报没有扣非每股收益、分配方案
    assert (e.deducted_eps, e.dividend_plan, e.dividend_yield) == (None, None, None)


def test_report_annual_has_dividend_plan() -> None:
    e = _one("report_annual")
    assert (e.code, e.report_date, e.market) == ("000001", "2025-12-31", "sz")
    assert e.deducted_eps == pytest.approx(2.07)
    assert e.dividend_plan == "10派3.60元(含税,扣税后3.24元)"
    assert e.dividend_yield == pytest.approx(3.185840707965)
    assert e.gross_margin is None  # 银行没有销售毛利率


def test_express_fields() -> None:
    e = _one("express")
    assert (e.code, e.name, e.market, e.report_date) == ("688981", "中芯国际", "sh", "2025-12-31")
    assert (e.revenue, e.revenue_prev_year) == (pytest.approx(67.3232e9), pytest.approx(57.7956e9))
    assert e.revenue_yoy == pytest.approx(100 * (e.revenue / e.revenue_prev_year - 1))
    assert e.net_profit_yoy == pytest.approx(100 * (e.net_profit / e.net_profit_prev_year - 1))
    assert (e.bps, e.notice_date) == (pytest.approx(18.86), "2026-02-11")
    assert (e.eps, e.roe) == (None, None)  # 快报不一定披露每一项


def test_forecast_fields() -> None:
    e = _items("forecast")[0]
    assert (e.code, e.name, e.market) == ("603378", "*ST亚士", "sh")
    assert (e.report_date, e.notice_date) == ("2025-12-31", "2026-04-29")
    assert (e.indicator, e.forecast_type) == ("归属于上市公司股东的净利润", "增亏")
    assert (e.lower, e.upper) == (pytest.approx(-1.395e9), pytest.approx(-1.355e9))
    # 预测数值、变动幅度是上下限的均值
    assert e.forecast_value == pytest.approx((e.lower + e.upper) / 2)
    assert e.change_pct == pytest.approx((e.change_pct_lower + e.change_pct_upper) / 2)
    assert e.prev_year == pytest.approx(-329285000.0)
    assert e.summary.startswith("预计2025年1-12月") and "资产计提减值准备" in e.reason


def test_forecast_one_company_has_one_row_per_indicator() -> None:
    rows = _items("forecast_one_company")
    assert {r.code for r in rows} == {"688845"} and len(rows) == 3
    assert [r.indicator for r in rows] == [
        "归属于上市公司股东的净利润",
        "扣除非经常性损益后的净利润",
        "营业收入",
    ]
    assert len({r.forecast_value for r in rows}) == 3  # 各指标各有预测值，不能按行数数公司


def test_schedule_fields() -> None:
    changed = _one("schedule_changed")
    assert (changed.code, changed.name, changed.market) == ("920438", "戈碧迦", "bj")
    assert (changed.first_appoint_date, changed.first_change_date) == ("2026-09-29", "2026-10-29")
    # 当前生效的预约日期是最后一次变更后的日期
    assert changed.appoint_date == changed.actual_date == "2026-10-29"
    assert (changed.second_change_date, changed.third_change_date) == (None, None)
    plain = _items("schedule")[1]
    assert plain.first_change_date is None
    assert plain.first_appoint_date == plain.appoint_date == plain.actual_date == "2026-10-10"


# ---------------------------------------------------------------- 行映射：三大报表


def test_balance_sheet_fields() -> None:
    e = _one("balance")
    assert (e.code, e.name, e.market, e.industry) == ("600519", "贵州茅台", "sh", "白酒Ⅱ")
    assert (e.report_date, e.notice_date) == ("2026-09-30", "2026-10-31")
    assert e.total_assets == pytest.approx(318304891882.72)
    assert e.total_assets == pytest.approx(e.total_liabilities + e.total_equity)
    assert e.debt_asset_ratio == pytest.approx(100 * e.total_liabilities / e.total_assets)
    assert e.debt_asset_ratio == pytest.approx(11.9015685357)
    assert e.current_ratio == pytest.approx(718.6652766903)  # 以 % 表示：约 7.19 倍
    assert (e.cash, e.cash_yoy) == (pytest.approx(49926813769.81), pytest.approx(-3.5287655505))
    assert e.inventory == pytest.approx(61390820964.46)
    # 银行、券商、保险专用科目，一般公司为 None
    assert (e.deposits, e.loans_advances, e.settlement_reserves, e.advance_premiums) == (
        None,
        None,
        None,
        None,
    )


def test_balance_sheet_bank_row() -> None:
    e = _one("balance_bank")
    assert (e.code, e.industry) == ("600036", "银行Ⅱ")
    assert (e.deposits, e.loans_advances) == (
        pytest.approx(10.336364e12),
        pytest.approx(7.191994e12),
    )
    assert e.cash_deposit_pbc == e.cash  # 银行的货币资金即现金及存放中央银行款项
    assert e.debt_asset_ratio == pytest.approx(89.8952040543)
    # 一般公司的科目，银行为 None
    assert (e.inventory, e.accounts_receivable, e.fixed_assets, e.current_ratio) == (
        None,
        None,
        None,
        None,
    )


def test_income_statement_fields() -> None:
    e = _one("income")
    assert (e.code, e.name, e.report_date) == ("600519", "贵州茅台", "2026-09-30")
    assert (e.revenue, e.net_profit) == (
        pytest.approx(133283652508.95),
        pytest.approx(64467425981.95),
    )
    assert (e.revenue_yoy, e.net_profit_yoy) == (pytest.approx(1.8179466483), pytest.approx(-0.25))
    assert e.deducted_net_profit == pytest.approx(64324824599.18)
    # 一般公司的营业支出就是营业成本
    assert e.operating_expense == e.operating_cost == pytest.approx(13645718932.9)
    assert e.finance_expense == pytest.approx(-366975810.84)  # 负数：利息收入大于支出
    assert e.total_profit - e.income_tax > e.net_profit  # 差额是少数股东损益
    assert (e.operating_income, e.earned_premiums, e.business_admin_expense) == (None, None, None)


def test_income_statement_insurer_row() -> None:
    e = _one("income_insurer")
    assert (e.code, e.industry) == ("601318", "保险Ⅱ")
    assert e.operating_income == e.revenue == pytest.approx(728134000000)
    assert e.earned_premiums == pytest.approx(422944000000)
    assert e.investment_income == pytest.approx(103699000000)
    assert e.operating_expense == e.total_operating_cost  # 保险：营业支出即营业总支出
    assert (e.operating_cost, e.selling_expense, e.finance_expense) == (None, None, None)


def test_cash_flow_statement_fields() -> None:
    e = _one("cash_flow")
    assert (e.code, e.name, e.report_date) == ("600519", "贵州茅台", "2026-09-30")
    assert e.net_cash_flow == pytest.approx(69565494580.54)
    assert (e.operating_net, e.investing_net, e.financing_net) == (
        pytest.approx(84058979832.29),
        pytest.approx(25825156841.9),
        pytest.approx(-40316159517.78),
    )
    # *_share 是该科目 ÷ |净现金流| × 100，不是同比；可以大于 100、可以为负
    assert e.operating_net_share == pytest.approx(100 * e.operating_net / abs(e.net_cash_flow))
    assert e.financing_net_share == pytest.approx(100 * e.financing_net / abs(e.net_cash_flow))
    assert e.operating_net_share == pytest.approx(120.8343020331)
    assert e.net_cash_flow_yoy == pytest.approx(764.5775125707)  # 只有这一项是同比
    assert (e.begin_cash, e.end_cash, e.loans_increase, e.premiums_cash) == (None, None, None, None)


def test_cash_flow_statement_broker_row() -> None:
    e = _one("cash_flow_broker")
    assert (e.code, e.industry) == ("600030", "证券Ⅱ")
    assert e.end_cash - e.begin_cash == pytest.approx(e.net_cash_flow)
    assert e.interest_commission_cash == pytest.approx(63579263083.52)
    assert e.sales_cash is None  # 销售商品收到的现金：券商没有


# ---------------------------------------------------------------- 请求


@pytest.mark.parametrize("name", _NAMES)
def test_request_filters_by_type_scope_and_period(name: str) -> None:
    build, query, report, column, _ = _INTERFACES[name]
    request = build(query("20260930"))
    params = request.params()
    assert params["reportName"] == report
    # A 股与存托凭证 + 报告期；报告期列名业绩报告是 REPORTDATE，其余是 REPORT_DATE
    assert params["filter"] == f"{A_SHARE}({column}='2026-09-30')"
    # 过滤用到的列一并请求：上游对拼错的过滤字段静默忽略、返回整张表
    assert {"SECURITY_TYPE_CODE", column} <= set(params["columns"].split(","))
    assert request.latest_of == ""
    for scope, extra in config.DATACENTER_SCOPE_FILTERS.items():
        scoped = build(query("20251231", scope))
        assert scoped.filter == f"{A_SHARE}{extra}({column}='2025-12-31')"
        if extra:
            assert "TRADE_MARKET_CODE" in scoped.columns
    assert build(query("20260930", "hk")).filter == request.filter  # 未知范围回退 all


@pytest.mark.parametrize("name", _NAMES)
def test_request_without_period_takes_last_quarter_end(name: str) -> None:
    build, query, _, column, _ = _INTERFACES[name]
    assert (query().report_date, query().scope) == (None, "all")
    today = datetime.now(timezone(timedelta(hours=8))).date()
    expected = last_quarter_end(today).isoformat()
    assert build(query()).filter == f"{A_SHARE}({column}='{expected}')"
    assert re.fullmatch(r"\d{4}-(03-31|06-30|09-30|12-31)", expected)


@pytest.mark.parametrize("name", _NAMES)
@pytest.mark.parametrize("bad,message", [("20260815", "季末"), ("2026-09-30", "YYYYMMDD")])
def test_request_rejects_bad_period(name: str, bad: str, message: str) -> None:
    build, query, *_ = _INTERFACES[name]
    with pytest.raises(ValueError, match=message):
        build(query(bad))


def test_report_period_filter_composes_in_fixed_order() -> None:
    assert report_period_filter("REPORT_DATE", "20260630", "bj") == (
        f"{A_SHARE}(TRADE_MARKET_CODE=\"069001017\")(REPORT_DATE='2026-06-30')"
    )
    assert config.DATACENTER_A_SHARE_FILTER == A_SHARE


def test_sorts_end_with_a_unique_key() -> None:
    def sort_of(name: str) -> tuple[str, str]:
        params = _INTERFACES[name][0](_INTERFACES[name][1]("20260930")).params()
        return params["sortColumns"], params["sortTypes"]

    assert sort_of("earnings_report") == ("UPDATE_DATE,SECURITY_CODE", "-1,-1")
    assert sort_of("earnings_express") == ("UPDATE_DATE,SECURITY_CODE", "-1,-1")
    # 一家公司多项预测指标：末尾补指标代码，（代码, 指标）唯一
    assert sort_of("earnings_forecast") == (
        "NOTICE_DATE,SECURITY_CODE,PREDICT_FINANCE_CODE",
        "-1,-1,1",
    )
    assert sort_of("earnings_schedule") == ("FIRST_APPOINT_DATE,SECURITY_CODE", "1,1")
    for name in ("balance_sheet", "income_statement", "cash_flow_statement"):
        assert sort_of(name) == ("NOTICE_DATE,SECURITY_CODE", "-1,-1")


# ---------------------------------------------------------------- 注册表与对外导出


@pytest.mark.parametrize("name", _NAMES)
def test_registry_and_package_exports(name: str) -> None:
    assert getattr(registry, f"{name}_request") is _INTERFACES[name][0]
    assert f"{name}_request" in registry.__all__
    for exported in (f"{name}_em", f"df_{name}_em", f"to_{name}_dataframe"):
        assert exported in em.__all__ and callable(getattr(em, exported))


# ---------------------------------------------------------------- 端到端：应用层取数


class _ReportClient:
    """按报表名返回固定报文的 HttpClient 桩：与真实传输层一样执行协议校验。

    固定报文是每页 2 条的第 1 页（``pages`` 上千）；这里改写成“只有这一页”，免得翻页器去取其余页。
    """

    def __init__(self, bodies: dict[str, dict[str, Any]]) -> None:
        self.bodies = bodies
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
        rows = self.bodies[params["reportName"]]["result"]["data"]
        body = {"code": 0, "result": {"count": len(rows), "pages": 1, "data": rows}}
        text = json.dumps(body, ensure_ascii=False)
        if validator is not None and not validator(text):
            raise InvalidContentError(f"桩：未通过校验 {text[:40]}")
        return text

    def available_proxies(self, url: str) -> int:
        return 0


def _client(monkeypatch: pytest.MonkeyPatch, name: str) -> _ReportClient:
    client = _ReportClient({_SPECS[name].report: _fx()[name]})
    monkeypatch.setattr(market_data, "_build_client", lambda settings: client)
    return client


_SETTINGS = Settings()


@pytest.mark.parametrize("name", _NAMES)
def test_interface_fetches_report(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    _, query, report, column, segment = _INTERFACES[name]
    client = _client(monkeypatch, segment)
    page = getattr(market_data, f"{name}_em")(query("20260930", "sh"), _SETTINGS)
    assert isinstance(page, ReportPage)
    assert page.total == len(page.items) and page.items == _items(segment)
    (call,) = client.calls  # 报告期在本地算出，不需要额外请求
    assert call["reportName"] == report
    assert call["filter"].endswith(f"({column}='2026-09-30')")
    # 查询可省略：默认最近的季末、全部市场
    default = getattr(market_data, f"{name}_em")(settings=_SETTINGS)
    assert default.items == page.items
    assert "TRADE_MARKET_CODE" not in client.calls[-1]["filter"]


# ---------------------------------------------------------------- DataFrame

_FRAME_HEADS: dict[str, tuple[str, list[str]]] = {
    "earnings_report": (
        "report",
        ["每股收益", "营业总收入-营业总收入", "净利润-同比增长", "销售毛利率"],
    ),
    "earnings_express": (
        "express",
        ["营业收入-去年同期", "净利润-净利润", "每股净资产", "公告日期"],
    ),
    "earnings_forecast": (
        "forecast",
        ["预测指标", "业绩变动", "预测数值", "预告类型", "上年同期值"],
    ),
    "earnings_schedule": ("schedule", ["首次预约时间", "一次变更日期", "实际披露时间"]),
    "balance_sheet": ("balance", ["资产-货币资金", "资产-总资产", "负债-总负债", "资产负债率"]),
    "income_statement": ("income", ["净利润", "营业总收入", "营业总支出-营业支出", "利润总额"]),
    "cash_flow_statement": (
        "cash_flow",
        ["净现金流-净现金流", "经营性现金流-现金流量净额", "融资性现金流-净现金流占比"],
    ),
}


@pytest.mark.parametrize("name", _NAMES)
def test_dataframe_columns(name: str) -> None:
    pd = pytest.importorskip("pandas")
    from em.application import dataframe

    segment, wanted = _FRAME_HEADS[name]
    convert = getattr(dataframe, f"to_{name}_dataframe")
    items = _items(segment)
    df = convert(ReportPage(total=len(items), items=items))
    assert isinstance(df, pd.DataFrame) and len(df) == len(items)
    assert list(df.columns)[:3] == ["股票代码", "股票简称", "市场"]
    assert set(wanted) <= set(df.columns)
    assert len(set(df.columns)) == len(df.columns)  # 中文列名不重复
    assert len(df.columns) == len(items[0].__dataclass_fields__)  # 模型的每个字段都有一列
    assert df.loc[0, "股票代码"] == items[0].code  # 代码保持文本，不丢前导 0
    empty = convert(ReportPage(total=0, items=()))
    assert empty.empty and list(empty.columns) == list(df.columns)


def test_df_interface_returns_dataframe(monkeypatch: pytest.MonkeyPatch) -> None:
    pd = pytest.importorskip("pandas")
    _client(monkeypatch, "forecast_one_company")
    df = market_data.df_earnings_forecast_em(EarningsForecastQuery("20261231"), _SETTINGS)
    assert isinstance(df, pd.DataFrame) and len(df) == 3
    assert df["股票代码"].nunique() == 1 and df["预测指标"].nunique() == 3
    custom = market_data.df_earnings_forecast_em(
        EarningsForecastQuery("20261231"),
        _SETTINGS,
        columns=dict.fromkeys(df.columns, "")
        | {f: f for f in _items("forecast_one_company")[0].__dataclass_fields__},
    )
    assert "indicator" in custom.columns

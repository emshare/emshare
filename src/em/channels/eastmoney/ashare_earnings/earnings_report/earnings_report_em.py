"""业绩报告（数据中心 RPT_LICO_FN_CPD），按报告期取各公司的数据，一家公司一行。"""

from em.channels.eastmoney.datacenter import (
    Column,
    ReportSpec,
    day,
    market_of,
    number,
    report_period_filter,
    required_text,
)
from em.channels.eastmoney.request import DatacenterRequest
from em.domain.models import EarningsReport
from em.domain.queries import EarningsReportQuery

# 排序对齐 akshare（最新公告日期、代码倒序）；报告期内一家公司一行，代码即唯一键
EARNINGS_REPORT = ReportSpec(
    report="RPT_LICO_FN_CPD",
    model=EarningsReport,
    columns=(
        Column("code", "SECURITY_CODE", required_text),
        Column("name", "SECURITY_NAME_ABBR", required_text),
        Column("market", "SECUCODE", market_of),
        Column("report_date", "REPORTDATE", day),
        Column("eps", "BASIC_EPS", number),
        Column("deducted_eps", "DEDUCT_BASIC_EPS", number),
        Column("revenue", "TOTAL_OPERATE_INCOME", number),
        Column("revenue_yoy", "YSTZ", number),
        Column("revenue_qoq", "YSHZ", number),
        Column("net_profit", "PARENT_NETPROFIT", number),
        Column("net_profit_yoy", "SJLTZ", number),
        Column("net_profit_qoq", "SJLHZ", number),
        Column("bps", "BPS", number),
        Column("roe", "WEIGHTAVG_ROE", number),
        Column("cash_flow_per_share", "MGJYXJJE", number),
        Column("gross_margin", "XSMLL", number),
        Column("dividend_plan", "ASSIGNDSCRPT"),
        Column("dividend_yield", "ZXGXL", number),
        Column("industry", "PUBLISHNAME"),
        Column("notice_date", "NOTICE_DATE", day),
        Column("update_date", "UPDATE_DATE", day),
    ),
    sort=(("UPDATE_DATE", -1), ("SECURITY_CODE", -1)),
)

__all__ = ["EARNINGS_REPORT", "earnings_report_request"]


def earnings_report_request(query: EarningsReportQuery) -> DatacenterRequest[EarningsReport]:
    """报告期留空时取今天之前最近的季末；``scope`` 未知回退 all。只取 A 股与存托凭证。"""
    return EARNINGS_REPORT.request(
        report_period_filter("REPORTDATE", query.report_date, query.scope)
    )

"""业绩快报（数据中心 RPT_FCI_PERFORMANCEE），按报告期取各公司的数据，一家公司一行。"""

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
from em.domain.models import EarningsExpress
from em.domain.queries import EarningsExpressQuery

# 排序对齐 akshare（最新公告日期、代码倒序）；报告期内一家公司一行，代码即唯一键
EARNINGS_EXPRESS = ReportSpec(
    report="RPT_FCI_PERFORMANCEE",
    model=EarningsExpress,
    columns=(
        Column("code", "SECURITY_CODE", required_text),
        Column("name", "SECURITY_NAME_ABBR", required_text),
        Column("market", "SECUCODE", market_of),
        Column("report_date", "REPORT_DATE", day),
        Column("eps", "BASIC_EPS", number),
        Column("revenue", "TOTAL_OPERATE_INCOME", number),
        Column("revenue_prev_year", "TOTAL_OPERATE_INCOME_SQ", number),
        Column("revenue_yoy", "YSTZ", number),
        Column("revenue_qoq", "DJDYSHZ", number),
        Column("net_profit", "PARENT_NETPROFIT", number),
        Column("net_profit_prev_year", "PARENT_NETPROFIT_SQ", number),
        Column("net_profit_yoy", "JLRTBZCL", number),
        Column("net_profit_qoq", "DJDJLHZ", number),
        Column("bps", "PARENT_BVPS", number),
        Column("roe", "WEIGHTAVG_ROE", number),
        Column("industry", "PUBLISHNAME"),
        Column("notice_date", "NOTICE_DATE", day),
        Column("update_date", "UPDATE_DATE", day),
    ),
    sort=(("UPDATE_DATE", -1), ("SECURITY_CODE", -1)),
)

__all__ = ["EARNINGS_EXPRESS", "earnings_express_request"]


def earnings_express_request(query: EarningsExpressQuery) -> DatacenterRequest[EarningsExpress]:
    """报告期留空时取今天之前最近的季末；``scope`` 未知回退 all。只取 A 股与存托凭证。"""
    return EARNINGS_EXPRESS.request(
        report_period_filter("REPORT_DATE", query.report_date, query.scope)
    )

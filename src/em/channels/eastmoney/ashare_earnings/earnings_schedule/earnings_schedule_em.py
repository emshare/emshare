"""预约披露时间（数据中心 RPT_PUBLIC_BS_APPOIN），按报告期取各公司的数据，一家公司一行。"""

from em.channels.eastmoney.datacenter import (
    Column,
    ReportSpec,
    day,
    market_of,
    report_period_filter,
    required_text,
)
from em.channels.eastmoney.request import DatacenterRequest
from em.domain.models import EarningsSchedule
from em.domain.queries import EarningsScheduleQuery

# 排序对齐 akshare（首次预约时间、代码升序）；报告期内一家公司一行，代码即唯一键
EARNINGS_SCHEDULE = ReportSpec(
    report="RPT_PUBLIC_BS_APPOIN",
    model=EarningsSchedule,
    columns=(
        Column("code", "SECURITY_CODE", required_text),
        Column("name", "SECURITY_NAME_ABBR", required_text),
        Column("market", "SECUCODE", market_of),
        Column("report_date", "REPORT_DATE", day),
        Column("first_appoint_date", "FIRST_APPOINT_DATE", day),
        Column("first_change_date", "FIRST_CHANGE_DATE", day),
        Column("second_change_date", "SECOND_CHANGE_DATE", day),
        Column("third_change_date", "THIRD_CHANGE_DATE", day),
        Column("appoint_date", "APPOINT_PUBLISH_DATE", day),
        Column("actual_date", "ACTUAL_PUBLISH_DATE", day),
    ),
    sort=(("FIRST_APPOINT_DATE", 1), ("SECURITY_CODE", 1)),
)

__all__ = ["EARNINGS_SCHEDULE", "earnings_schedule_request"]


def earnings_schedule_request(query: EarningsScheduleQuery) -> DatacenterRequest[EarningsSchedule]:
    """报告期留空时取今天之前最近的季末；``scope`` 未知回退 all。只取 A 股与存托凭证。"""
    return EARNINGS_SCHEDULE.request(
        report_period_filter("REPORT_DATE", query.report_date, query.scope)
    )

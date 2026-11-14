"""业绩预告（数据中心 RPT_PUBLIC_OP_NEWPREDICT），按报告期取各公司的业绩预告，一家公司每项预测指标一行。"""

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
from em.domain.models import EarningsForecast
from em.domain.queries import EarningsForecastQuery

# 排序对齐 akshare（公告日期、代码倒序）；一家公司每项预测指标一行，末尾补指标代码，
# （代码, 指标）唯一，翻页顺序稳定；指标代码不映射但一并请求（上游对拼错的返回列报 9501）
EARNINGS_FORECAST = ReportSpec(
    report="RPT_PUBLIC_OP_NEWPREDICT",
    model=EarningsForecast,
    columns=(
        Column("code", "SECURITY_CODE", required_text),
        Column("name", "SECURITY_NAME_ABBR", required_text),
        Column("market", "SECUCODE", market_of),
        Column("report_date", "REPORT_DATE", day),
        Column("notice_date", "NOTICE_DATE", day),
        Column("indicator", "PREDICT_FINANCE"),
        Column("summary", "PREDICT_CONTENT"),
        Column("forecast_value", "FORECAST_JZ", number),
        Column("lower", "PREDICT_AMT_LOWER", number),
        Column("upper", "PREDICT_AMT_UPPER", number),
        Column("change_pct", "INCREASE_JZ", number),
        Column("change_pct_lower", "ADD_AMP_LOWER", number),
        Column("change_pct_upper", "ADD_AMP_UPPER", number),
        Column("reason", "CHANGE_REASON_EXPLAIN"),
        Column("forecast_type", "PREDICT_TYPE"),
        Column("prev_year", "PREYEAR_SAME_PERIOD", number),
    ),
    sort=(("NOTICE_DATE", -1), ("SECURITY_CODE", -1), ("PREDICT_FINANCE_CODE", 1)),
    key_columns=("PREDICT_FINANCE_CODE",),
)

__all__ = ["EARNINGS_FORECAST", "earnings_forecast_request"]


def earnings_forecast_request(query: EarningsForecastQuery) -> DatacenterRequest[EarningsForecast]:
    """报告期留空时取今天之前最近的季末；``scope`` 未知回退 all。只取 A 股与存托凭证。"""
    return EARNINGS_FORECAST.request(
        report_period_filter("REPORT_DATE", query.report_date, query.scope)
    )

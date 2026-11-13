"""机构席位追踪（数据中心 RPT_ORGANIZATION_SEATNEW），按统计周期取有机构席位参与的股票。"""

from em.channels.eastmoney.datacenter import (
    Column,
    ReportSpec,
    integer,
    market_of,
    number,
    period_filter,
    required_text,
)
from em.channels.eastmoney.request import DatacenterRequest
from em.domain.models import BillboardInstitutionStats
from em.domain.queries import BillboardInstitutionStatsQuery

# 排序对齐 akshare（上榜次数倒序，代码升序）；周期内一只股票一行
BILLBOARD_INSTITUTION_STATS = ReportSpec(
    report="RPT_ORGANIZATION_SEATNEW",
    model=BillboardInstitutionStats,
    columns=(
        Column("code", "SECURITY_CODE", required_text),
        Column("name", "SECURITY_NAME_ABBR", required_text),
        Column("market", "SECUCODE", market_of),
        Column("close", "CLOSE_PRICE", number),
        Column("change_pct", "CHANGE_RATE", number),
        Column("billboard_turnover", "AMOUNT", number),
        Column("billboard_times", "ONLIST_TIMES", integer),
        Column("institution_buy", "BUY_AMT", number),
        Column("institution_buy_times", "BUY_TIMES", integer),
        Column("institution_sell", "SELL_AMT", number),
        Column("institution_sell_times", "SELL_TIMES", integer),
        Column("institution_net_buy", "NET_BUY_AMT", number),
        Column("change_1mo", "M1_CLOSE_ADJCHRATE", number),
        Column("change_3mo", "M3_CLOSE_ADJCHRATE", number),
        Column("change_6mo", "M6_CLOSE_ADJCHRATE", number),
        Column("change_1y", "Y1_CLOSE_ADJCHRATE", number),
    ),
    sort=(("ONLIST_TIMES", -1), ("SECURITY_CODE", 1)),
)

__all__ = ["BILLBOARD_INSTITUTION_STATS", "billboard_institution_stats_request"]


def billboard_institution_stats_request(
    query: BillboardInstitutionStatsQuery,
) -> DatacenterRequest[BillboardInstitutionStats]:
    return BILLBOARD_INSTITUTION_STATS.request(period_filter("STATISTICSCYCLE", query.period))

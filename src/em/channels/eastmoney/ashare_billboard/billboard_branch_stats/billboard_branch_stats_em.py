"""营业部统计（数据中心 RPT_OPERATEDEPT_LIST_STATISTICS），按统计周期取各营业部的上榜次数与买卖合计。"""

from em.channels.eastmoney.datacenter import (
    Column,
    ReportSpec,
    integer,
    number,
    period_filter,
    required_text,
)
from em.channels.eastmoney.request import DatacenterRequest
from em.domain.models import BillboardBranchStats
from em.domain.queries import BillboardBranchStatsQuery

# 排序对齐 akshare（龙虎榜成交金额倒序，营业部代码升序）；周期内一家营业部一行
BILLBOARD_BRANCH_STATS = ReportSpec(
    report="RPT_OPERATEDEPT_LIST_STATISTICS",
    model=BillboardBranchStats,
    columns=(
        Column("branch_code", "OPERATEDEPT_CODE", required_text),
        Column("branch_name", "OPERATEDEPT_NAME", required_text),
        Column("billboard_turnover", "AMOUNT", number),
        Column("billboard_times", "SALES_ONLIST_TIMES", integer),
        Column("buy", "ACT_BUY", number),
        Column("buy_times", "TOTAL_BUYER_SALESTIMES", integer),
        Column("sell", "ACT_SELL", number),
        Column("sell_times", "TOTAL_SELLER_SALESTIMES", integer),
    ),
    sort=(("AMOUNT", -1), ("OPERATEDEPT_CODE", 1)),
)

__all__ = ["BILLBOARD_BRANCH_STATS", "billboard_branch_stats_request"]


def billboard_branch_stats_request(
    query: BillboardBranchStatsQuery,
) -> DatacenterRequest[BillboardBranchStats]:
    return BILLBOARD_BRANCH_STATS.request(period_filter("STATISTICSCYCLE", query.period))

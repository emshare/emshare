"""营业部排行（数据中心 RPT_RATEDEPT_RETURNT_RANKING），按统计周期取各营业部买入上榜后的表现。"""

from em.channels.eastmoney.datacenter import (
    Column,
    ReportSpec,
    integer,
    number,
    period_filter,
    required_text,
)
from em.channels.eastmoney.request import DatacenterRequest
from em.domain.models import BillboardBranchRank
from em.domain.queries import BillboardBranchRankQuery

# 排序对齐 akshare（上榜后 1 天买入次数倒序，营业部代码升序）；周期内一家营业部一行
BILLBOARD_BRANCH_RANK = ReportSpec(
    report="RPT_RATEDEPT_RETURNT_RANKING",
    model=BillboardBranchRank,
    columns=(
        Column("branch_code", "OPERATEDEPT_CODE", required_text),
        Column("branch_name", "OPERATEDEPT_NAME", required_text),
        Column("buy_times_1d", "TOTAL_BUYER_SALESTIMES_1DAY", integer),
        Column("avg_change_1d", "AVERAGE_INCREASE_1DAY", number),
        Column("rise_prob_1d", "RISE_PROBABILITY_1DAY", number),
        Column("buy_times_2d", "TOTAL_BUYER_SALESTIMES_2DAY", integer),
        Column("avg_change_2d", "AVERAGE_INCREASE_2DAY", number),
        Column("rise_prob_2d", "RISE_PROBABILITY_2DAY", number),
        Column("buy_times_3d", "TOTAL_BUYER_SALESTIMES_3DAY", integer),
        Column("avg_change_3d", "AVERAGE_INCREASE_3DAY", number),
        Column("rise_prob_3d", "RISE_PROBABILITY_3DAY", number),
        Column("buy_times_5d", "TOTAL_BUYER_SALESTIMES_5DAY", integer),
        Column("avg_change_5d", "AVERAGE_INCREASE_5DAY", number),
        Column("rise_prob_5d", "RISE_PROBABILITY_5DAY", number),
        Column("buy_times_10d", "TOTAL_BUYER_SALESTIMES_10DAY", integer),
        Column("avg_change_10d", "AVERAGE_INCREASE_10DAY", number),
        Column("rise_prob_10d", "RISE_PROBABILITY_10DAY", number),
    ),
    sort=(("TOTAL_BUYER_SALESTIMES_1DAY", -1), ("OPERATEDEPT_CODE", 1)),
)

__all__ = ["BILLBOARD_BRANCH_RANK", "billboard_branch_rank_request"]


def billboard_branch_rank_request(
    query: BillboardBranchRankQuery,
) -> DatacenterRequest[BillboardBranchRank]:
    return BILLBOARD_BRANCH_RANK.request(period_filter("STATISTICSCYCLE", query.period))

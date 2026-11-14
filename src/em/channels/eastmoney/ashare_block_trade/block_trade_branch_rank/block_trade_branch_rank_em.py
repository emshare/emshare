"""大宗交易营业部排行（数据中心 RPT_BLOCKTRADE_OPERATEDEPT_RANK），按最近 N 个交易日取各营业部买入后 1 / 5 / 10 / 20 日的表现。"""

from em.channels.eastmoney import config
from em.channels.eastmoney.datacenter import (
    Column,
    ReportSpec,
    equals,
    integer,
    number,
    required_text,
)
from em.channels.eastmoney.request import DatacenterRequest
from em.domain.models import BlockTradeBranchRank
from em.domain.queries import BlockTradeBranchRankQuery

# 只统计 A 股。各档的买入次数只算已经有 N 日后涨跌幅的买入，还没有到期买入的档三列都是 null。
# 实测与每日明细逐家核对：5 日档全部一致；1 / 10 / 20 日档有少数营业部比明细少（90d 933 家里 11 家，
# 360d 2766 家里 140 家，多数是这三档数值相同且小于 5 日档），是上游数据自身的出入，原样返回。
# 排序对齐 akshare（5 日档买入次数、1 日档平均涨幅倒序）；末尾补营业部代码保证翻页顺序稳定
# （不带排序翻页会重复和丢行：实测 360 日档 2766 行里重复 612 行）。周期内一家营业部一行
BLOCK_TRADE_BRANCH_RANK = ReportSpec(
    report="RPT_BLOCKTRADE_OPERATEDEPT_RANK",
    model=BlockTradeBranchRank,
    columns=(
        Column("branch_code", "OPERATEDEPT_CODE", required_text),
        Column("branch_name", "OPERATEDEPT_NAME", required_text),
        Column("buy_times_1d", "D1_BUYER_NUM", integer),
        Column("avg_change_1d", "D1_AVERAGE_INCREASE", number),
        Column("rise_prob_1d", "D1_RISE_PROBABILITY", number),
        Column("buy_times_5d", "D5_BUYER_NUM", integer),
        Column("avg_change_5d", "D5_AVERAGE_INCREASE", number),
        Column("rise_prob_5d", "D5_RISE_PROBABILITY", number),
        Column("buy_times_10d", "D10_BUYER_NUM", integer),
        Column("avg_change_10d", "D10_AVERAGE_INCREASE", number),
        Column("rise_prob_10d", "D10_RISE_PROBABILITY", number),
        Column("buy_times_20d", "D20_BUYER_NUM", integer),
        Column("avg_change_20d", "D20_AVERAGE_INCREASE", number),
        Column("rise_prob_20d", "D20_RISE_PROBABILITY", number),
    ),
    sort=(("D5_BUYER_NUM", -1), ("D1_AVERAGE_INCREASE", -1), ("OPERATEDEPT_CODE", 1)),
)

__all__ = ["BLOCK_TRADE_BRANCH_RANK", "block_trade_branch_rank_request", "normalize_period"]


def normalize_period(period: str) -> str:
    """未知回退 30d。"""
    return period if period in config.BLOCK_TRADE_RANK_PERIODS else "30d"


def block_trade_branch_rank_request(
    query: BlockTradeBranchRankQuery,
) -> DatacenterRequest[BlockTradeBranchRank]:
    days = config.BLOCK_TRADE_RANK_PERIODS[normalize_period(query.period)]
    return BLOCK_TRADE_BRANCH_RANK.request(equals("N_DATE", days))

"""大宗交易活跃营业部统计（数据中心 RPT_BLOCKTRADE_OPERATEDEPTSTATISTICS），按最近 N 个交易日取各营业部的买卖汇总。"""

from em.channels.eastmoney import config
from em.channels.eastmoney.datacenter import (
    Column,
    ReportSpec,
    day,
    equals,
    from_wan,
    integer,
    pair_codes,
    pair_names,
    required_text,
)
from em.channels.eastmoney.request import DatacenterRequest
from em.domain.models import BlockTradeBranchActive
from em.domain.queries import BlockTradeBranchActiveQuery

# 只统计 A 股（实测各周期的买卖次数、金额与每日明细里 A 股部分逐家一致）。金额上游给万元，统一成元。
# STOCK_DETAILS 是逗号分隔的“代码|简称”，确实只含买入的股票（实测各周期逐家一致），只卖出的营业部为 null。
# 排序对齐 akshare（买入次数、买入金额倒序）；只卖出的营业部两列都是 0（实测近 30 日 691 家里 288 家
# 并列），末尾补营业部代码保证翻页顺序稳定。周期内一家营业部一行
BLOCK_TRADE_BRANCH_ACTIVE = ReportSpec(
    report="RPT_BLOCKTRADE_OPERATEDEPTSTATISTICS",
    model=BlockTradeBranchActive,
    columns=(
        Column("branch_code", "OPERATEDEPT_CODE", required_text),
        Column("branch_name", "OPERATEDEPT_NAME", required_text),
        Column("latest_date", "ONLIST_DATE", day),
        Column("buy_times", "BUYER_NUM", integer),
        Column("sell_times", "SELLER_NUM", integer),
        Column("buy", "TOTAL_BUYAMT", from_wan),
        Column("sell", "TOTAL_SELLAMT", from_wan),
        Column("net_buy", "TOTAL_NETAMT", from_wan),
        Column("buy_stocks", "STOCK_DETAILS", pair_names),
        Column("buy_stock_codes", "STOCK_DETAILS", pair_codes),
    ),
    sort=(("BUYER_NUM", -1), ("TOTAL_BUYAMT", -1), ("OPERATEDEPT_CODE", 1)),
)

__all__ = ["BLOCK_TRADE_BRANCH_ACTIVE", "block_trade_branch_active_request", "normalize_period"]


def normalize_period(period: str) -> str:
    """未知回退 1d。"""
    return period if period in config.BLOCK_TRADE_ACTIVE_PERIODS else "1d"


def block_trade_branch_active_request(
    query: BlockTradeBranchActiveQuery,
) -> DatacenterRequest[BlockTradeBranchActive]:
    days = config.BLOCK_TRADE_ACTIVE_PERIODS[normalize_period(query.period)]
    return BLOCK_TRADE_BRANCH_ACTIVE.request(equals("N_DATE", days))

"""营业部详情（数据中心 RPT_OPERATEDEPT_TRADE_DETAILSNEW），取一家营业部的上榜买卖记录。"""

from em.channels.eastmoney.datacenter import (
    Column,
    ReportSpec,
    between,
    date_span,
    day,
    equals,
    market_of,
    number,
    required_text,
    safe_value,
)
from em.channels.eastmoney.request import DatacenterRequest
from em.domain.models import BillboardBranchTrade
from em.domain.queries import BillboardBranchTradesQuery

# 排序对齐 akshare（交易日期倒序，股票代码升序）。同股同日多个上榜原因为多条记录，
# 本报表没有 TRADE_ID，末尾补上榜原因保证翻页顺序稳定
BILLBOARD_BRANCH_TRADES = ReportSpec(
    report="RPT_OPERATEDEPT_TRADE_DETAILSNEW",
    model=BillboardBranchTrade,
    columns=(
        Column("branch_code", "OPERATEDEPT_CODE", required_text),
        Column("branch_name", "OPERATEDEPT_NAME", required_text),
        Column("branch_short_name", "ORG_NAME_ABBR"),
        Column("trade_date", "TRADE_DATE", day),
        Column("code", "SECURITY_CODE", required_text),
        Column("name", "SECURITY_NAME_ABBR", required_text),
        Column("market", "SECUCODE", market_of),
        Column("change_pct", "CHANGE_RATE", number),
        Column("buy", "ACT_BUY", number),
        Column("sell", "ACT_SELL", number),
        Column("net_buy", "NET_AMT", number),
        Column("reason", "EXPLANATION"),
        Column("change_after_1d", "D1_CLOSE_ADJCHRATE", number),
        Column("change_after_2d", "D2_CLOSE_ADJCHRATE", number),
        Column("change_after_3d", "D3_CLOSE_ADJCHRATE", number),
        Column("change_after_5d", "D5_CLOSE_ADJCHRATE", number),
        Column("change_after_10d", "D10_CLOSE_ADJCHRATE", number),
        Column("change_after_20d", "D20_CLOSE_ADJCHRATE", number),
        Column("change_after_30d", "D30_CLOSE_ADJCHRATE", number),
    ),
    sort=(("TRADE_DATE", -1), ("SECURITY_CODE", 1), ("EXPLANATION", 1)),
)

__all__ = ["BILLBOARD_BRANCH_TRADES", "billboard_branch_trades_request"]


def billboard_branch_trades_request(
    query: BillboardBranchTradesQuery,
) -> DatacenterRequest[BillboardBranchTrade]:
    """日期都留空时取该营业部的全部历史记录。"""
    branch = equals("OPERATEDEPT_CODE", safe_value(query.branch_code, "branch_code"))
    span = date_span(query.start_date, query.end_date)
    if span is None:
        return BILLBOARD_BRANCH_TRADES.request(branch)
    return BILLBOARD_BRANCH_TRADES.request(branch + between("TRADE_DATE", *span))

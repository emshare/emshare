"""每日活跃营业部（数据中心 RPT_OPERATEDEPT_ACTIVE），按上榜日期区间取各营业部的买卖合计。"""

from em.channels.eastmoney.datacenter import (
    Column,
    ReportSpec,
    between,
    codes_of,
    date_span,
    day,
    integer,
    number,
    required_text,
)
from em.channels.eastmoney.request import DatacenterRequest
from em.domain.models import BillboardBranchActive
from em.domain.queries import BillboardBranchActiveQuery

# 排序对齐 akshare（总买卖净额、上榜日倒序，营业部代码升序）。上游对同一营业部代码、同一上榜日
# 会给出金额相同、名称不同的两行（实测 10025080），末尾补营业部名称保证翻页顺序稳定
BILLBOARD_BRANCH_ACTIVE = ReportSpec(
    report="RPT_OPERATEDEPT_ACTIVE",
    model=BillboardBranchActive,
    columns=(
        Column("branch_code", "OPERATEDEPT_CODE", required_text),
        Column("branch_name", "OPERATEDEPT_NAME", required_text),
        Column("trade_date", "ONLIST_DATE", day),
        Column("buy_stock_count", "BUYER_APPEAR_NUM", integer),
        Column("sell_stock_count", "SELLER_APPEAR_NUM", integer),
        Column("buy", "TOTAL_BUYAMT", number),
        Column("sell", "TOTAL_SELLAMT", number),
        Column("net_buy", "TOTAL_NETAMT", number),
        Column("stocks", "SECURITY_NAME_ABBR"),
        Column("stock_codes", "BUY_STOCK", codes_of),
    ),
    sort=(
        ("TOTAL_NETAMT", -1),
        ("ONLIST_DATE", -1),
        ("OPERATEDEPT_CODE", 1),
        ("OPERATEDEPT_NAME", 1),
    ),
)

__all__ = ["BILLBOARD_BRANCH_ACTIVE", "billboard_branch_active_request"]


def billboard_branch_active_request(
    query: BillboardBranchActiveQuery,
) -> DatacenterRequest[BillboardBranchActive]:
    """日期都留空时取最近一个有龙虎榜的交易日（先查一次最新上榜日）。"""
    span = date_span(query.start_date, query.end_date)
    if span is None:
        return BILLBOARD_BRANCH_ACTIVE.request(latest_of="ONLIST_DATE")
    return BILLBOARD_BRANCH_ACTIVE.request(between("ONLIST_DATE", *span))

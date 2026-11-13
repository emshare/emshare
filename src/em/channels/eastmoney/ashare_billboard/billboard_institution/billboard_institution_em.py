"""机构买卖每日统计（数据中心 RPT_ORGANIZATION_TRADE_DETAILS），按上榜日期区间取有机构席位参与的上榜记录。"""

from em.channels.eastmoney.datacenter import (
    Column,
    ReportSpec,
    between,
    date_span,
    day,
    from_yi,
    integer,
    market_of,
    number,
    required_text,
)
from em.channels.eastmoney.request import DatacenterRequest
from em.domain.models import BillboardInstitutionTrade
from em.domain.queries import BillboardInstitutionQuery

# 排序对齐 akshare（机构净买额、上榜日倒序，代码升序）。同股同日多个上榜原因为多条记录，
# 本报表没有 TRADE_ID，末尾补上榜原因保证翻页顺序稳定
BILLBOARD_INSTITUTION = ReportSpec(
    report="RPT_ORGANIZATION_TRADE_DETAILS",
    model=BillboardInstitutionTrade,
    columns=(
        Column("code", "SECURITY_CODE", required_text),
        Column("name", "SECURITY_NAME_ABBR", required_text),
        Column("market", "SECUCODE", market_of),
        Column("trade_date", "TRADE_DATE", day),
        Column("reason", "EXPLANATION"),
        Column("close", "CLOSE_PRICE", number),
        Column("change_pct", "CHANGE_RATE", number),
        Column("buy_institutions", "BUY_TIMES", integer),
        Column("sell_institutions", "SELL_TIMES", integer),
        Column("institution_buy", "BUY_AMT", number),
        Column("institution_sell", "SELL_AMT", number),
        Column("institution_net_buy", "NET_BUY_AMT", number),
        Column("turnover", "ACCUM_AMOUNT", number),
        Column("net_buy_ratio", "RATIO", number),
        Column("turnover_rate", "TURNOVERRATE", number),
        Column("float_market_cap", "FREECAP", from_yi),
        Column("change_after_1d", "D1_CLOSE_ADJCHRATE", number),
        Column("change_after_2d", "D2_CLOSE_ADJCHRATE", number),
        Column("change_after_3d", "D3_CLOSE_ADJCHRATE", number),
        Column("change_after_5d", "D5_CLOSE_ADJCHRATE", number),
        Column("change_after_10d", "D10_CLOSE_ADJCHRATE", number),
    ),
    sort=(("NET_BUY_AMT", -1), ("TRADE_DATE", -1), ("SECURITY_CODE", 1), ("EXPLANATION", 1)),
)

__all__ = ["BILLBOARD_INSTITUTION", "billboard_institution_request"]


def billboard_institution_request(
    query: BillboardInstitutionQuery,
) -> DatacenterRequest[BillboardInstitutionTrade]:
    """日期都留空时取最近一个有机构席位上榜的交易日（先查一次最新上榜日）。"""
    span = date_span(query.start_date, query.end_date)
    if span is None:
        return BILLBOARD_INSTITUTION.request(latest_of="TRADE_DATE")
    return BILLBOARD_INSTITUTION.request(between("TRADE_DATE", *span))

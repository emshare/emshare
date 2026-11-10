"""龙虎榜详情（数据中心 RPT_DAILYBILLBOARD_DETAILSNEW），按上榜日期区间取全部上榜记录。"""

from em.channels.eastmoney.datacenter import (
    Column,
    ReportSpec,
    between,
    date_span,
    day,
    market_of,
    number,
    required_text,
)
from em.channels.eastmoney.request import DatacenterRequest
from em.domain.models import BillboardEntry
from em.domain.queries import BillboardDetailQuery

# 排序对齐 akshare（代码升序、日期倒序）；TRADE_ID 是每条上榜记录的唯一号，补在最后保证翻页顺序稳定
BILLBOARD_DETAIL = ReportSpec(
    report="RPT_DAILYBILLBOARD_DETAILSNEW",
    model=BillboardEntry,
    columns=(
        Column("code", "SECURITY_CODE", required_text),
        Column("name", "SECURITY_NAME_ABBR", required_text),
        Column("market", "SECUCODE", market_of),
        Column("trade_date", "TRADE_DATE", day),
        Column("reason", "EXPLANATION"),
        Column("interpretation", "EXPLAIN"),
        Column("close", "CLOSE_PRICE", number),
        Column("change_pct", "CHANGE_RATE", number),
        Column("net_buy", "BILLBOARD_NET_AMT", number),
        Column("buy", "BILLBOARD_BUY_AMT", number),
        Column("sell", "BILLBOARD_SELL_AMT", number),
        Column("billboard_turnover", "BILLBOARD_DEAL_AMT", number),
        Column("turnover", "ACCUM_AMOUNT", number),
        Column("net_buy_ratio", "DEAL_NET_RATIO", number),
        Column("billboard_turnover_ratio", "DEAL_AMOUNT_RATIO", number),
        Column("turnover_rate", "TURNOVERRATE", number),
        Column("float_market_cap", "FREE_MARKET_CAP", number),
        Column("change_after_1d", "D1_CLOSE_ADJCHRATE", number),
        Column("change_after_2d", "D2_CLOSE_ADJCHRATE", number),
        Column("change_after_5d", "D5_CLOSE_ADJCHRATE", number),
        Column("change_after_10d", "D10_CLOSE_ADJCHRATE", number),
    ),
    sort=(("SECURITY_CODE", 1), ("TRADE_DATE", -1), ("TRADE_ID", 1)),
    key_columns=("TRADE_ID",),
)

__all__ = ["BILLBOARD_DETAIL", "billboard_detail_request"]


def billboard_detail_request(query: BillboardDetailQuery) -> DatacenterRequest[BillboardEntry]:
    """日期都留空时取最近一个有龙虎榜的交易日（先查一次最新上榜日）。"""
    span = date_span(query.start_date, query.end_date)
    if span is None:
        return BILLBOARD_DETAIL.request(latest_of="TRADE_DATE")
    return BILLBOARD_DETAIL.request(between("TRADE_DATE", *span))

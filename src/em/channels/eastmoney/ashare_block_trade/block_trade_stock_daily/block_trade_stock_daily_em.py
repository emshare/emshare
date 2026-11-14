"""大宗交易每日统计（数据中心 RPT_BLOCKTRADE_STA），按交易日期区间取各 A 股当天的大宗交易汇总，一只股票一天一行。"""

from em.channels.eastmoney.datacenter import (
    Column,
    ReportSpec,
    between,
    date_span,
    day,
    from_wan,
    integer,
    market_of,
    number,
    pct_of_ratio,
    required_text,
)
from em.channels.eastmoney.request import DatacenterRequest
from em.domain.models import BlockTradeStockDaily
from em.domain.queries import BlockTradeStockDailyQuery

# 只有 A 股（实测与每日明细里 A 股的（代码, 日期）集合完全一致）。成交总量、成交总额上游给万股、
# 万元（两位小数），统一成股、元；折溢率上游给比例，统一成 %。
# 排序对齐 akshare（成交总额 / 流通市值倒序）；末尾补日期倒序、代码升序，（代码, 日期）唯一，
# 占比并列时翻页顺序也稳定
BLOCK_TRADE_STOCK_DAILY = ReportSpec(
    report="RPT_BLOCKTRADE_STA",
    model=BlockTradeStockDaily,
    columns=(
        Column("code", "SECURITY_CODE", required_text),
        Column("name", "SECURITY_NAME_ABBR", required_text),
        Column("market", "SECUCODE", market_of),
        Column("trade_date", "TRADE_DATE", day),
        Column("change_pct", "CHANGE_RATE", number),
        Column("close", "CLOSE_PRICE", number),
        Column("avg_price", "AVERAGE_PRICE", number),
        Column("premium_rate", "PREMIUM_RATIO", pct_of_ratio),
        Column("deal_times", "DEAL_NUM", integer),
        Column("premium_times", "PREMIUM_TIMES", integer),
        Column("discount_times", "DISCOUNT_TIMES", integer),
        Column("volume", "VOLUME", from_wan),
        Column("amount", "DEAL_AMT", from_wan),
        Column("float_market_cap_ratio", "TURNOVERRATE", number),
        Column("change_after_1d", "D1_CLOSE_ADJCHRATE", number),
        Column("change_after_5d", "D5_CLOSE_ADJCHRATE", number),
        Column("change_after_10d", "D10_CLOSE_ADJCHRATE", number),
        Column("change_after_20d", "D20_CLOSE_ADJCHRATE", number),
    ),
    sort=(("TURNOVERRATE", -1), ("TRADE_DATE", -1), ("SECURITY_CODE", 1)),
)

__all__ = ["BLOCK_TRADE_STOCK_DAILY", "block_trade_stock_daily_request"]


def block_trade_stock_daily_request(
    query: BlockTradeStockDailyQuery,
) -> DatacenterRequest[BlockTradeStockDaily]:
    """日期都留空时取最近一个有大宗交易的交易日（先查一次最新交易日）。"""
    span = date_span(query.start_date, query.end_date)
    if span is None:
        return BLOCK_TRADE_STOCK_DAILY.request(latest_of="TRADE_DATE")
    return BLOCK_TRADE_STOCK_DAILY.request(between("TRADE_DATE", *span))

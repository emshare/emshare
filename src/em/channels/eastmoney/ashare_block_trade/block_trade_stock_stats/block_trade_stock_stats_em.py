"""大宗交易活跃 A 股统计（数据中心 RPT_BLOCKTRADE_ACSTA），按统计周期取有过大宗交易的 A 股，一只股票一行。"""

from em.channels.eastmoney import config
from em.channels.eastmoney.datacenter import (
    Column,
    ReportSpec,
    day,
    equals,
    from_wan,
    integer,
    market_of,
    number,
    pct_of_ratio,
    required_text,
)
from em.channels.eastmoney.request import DatacenterRequest
from em.domain.models import BlockTradeStockStats
from em.domain.queries import BlockTradeStockStatsQuery

# 总成交额上游给万元，统一成元；折溢率上游给比例，统一成 %。
# 排序对齐 akshare（成交笔数倒序、代码倒序）；周期内一只股票一行，代码即唯一键
BLOCK_TRADE_STOCK_STATS = ReportSpec(
    report="RPT_BLOCKTRADE_ACSTA",
    model=BlockTradeStockStats,
    columns=(
        Column("code", "SECURITY_CODE", required_text),
        Column("name", "SECURITY_NAME_ABBR", required_text),
        Column("market", "SECUCODE", market_of),
        Column("close", "CLOSE_PRICE", number),
        Column("change_pct", "CHANGE_RATE", number),
        Column("latest_date", "TRADE_DATE", day),
        Column("deal_times", "DEAL_NUM", integer),
        Column("premium_times", "PREMIUM_TIMES", integer),
        Column("discount_times", "DISCOUNT_TIMES", integer),
        Column("amount", "DEAL_AMT", from_wan),
        Column("premium_rate", "PREMIUM_RATIO", pct_of_ratio),
        Column("float_market_cap_ratio", "SUM_TURNOVERRATE", number),
        Column("avg_change_after_1d", "D1_AVG_ADJCHRATE", number),
        Column("avg_change_after_5d", "D5_AVG_ADJCHRATE", number),
        Column("avg_change_after_10d", "D10_AVG_ADJCHRATE", number),
        Column("avg_change_after_20d", "D20_AVG_ADJCHRATE", number),
    ),
    sort=(("DEAL_NUM", -1), ("SECURITY_CODE", -1)),
)

__all__ = ["BLOCK_TRADE_STOCK_STATS", "block_trade_stock_stats_request", "normalize_period"]


def normalize_period(period: str) -> str:
    """未知回退 1mo。"""
    return period if period in config.BLOCK_TRADE_STOCK_PERIODS else "1mo"


def block_trade_stock_stats_request(
    query: BlockTradeStockStatsQuery,
) -> DatacenterRequest[BlockTradeStockStats]:
    code = config.BLOCK_TRADE_STOCK_PERIODS[normalize_period(query.period)]
    return BLOCK_TRADE_STOCK_STATS.request(equals("DATE_TYPE_CODE", code))

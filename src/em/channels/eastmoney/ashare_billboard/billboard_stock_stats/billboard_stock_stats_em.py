"""个股上榜统计（数据中心 RPT_BILLBOARD_TRADEALL），按统计周期取全部上过榜的股票。"""

from em.channels.eastmoney.datacenter import (
    Column,
    ReportSpec,
    day,
    integer,
    market_of,
    number,
    period_filter,
    required_text,
)
from em.channels.eastmoney.request import DatacenterRequest
from em.domain.models import BillboardStockStats
from em.domain.queries import BillboardStockStatsQuery

# 排序对齐 akshare（上榜次数、最近上榜日倒序，代码升序）；周期内一只股票一行，代码即唯一键
BILLBOARD_STOCK_STATS = ReportSpec(
    report="RPT_BILLBOARD_TRADEALL",
    model=BillboardStockStats,
    columns=(
        Column("code", "SECURITY_CODE", required_text),
        Column("name", "SECURITY_NAME_ABBR", required_text),
        Column("market", "SECUCODE", market_of),
        Column("latest_date", "LATEST_TDATE", day),
        Column("close", "CLOSE_PRICE", number),
        Column("change_pct", "CHANGE_RATE", number),
        Column("billboard_times", "BILLBOARD_TIMES", integer),
        Column("net_buy", "BILLBOARD_NET_BUY", number),
        Column("buy", "BILLBOARD_BUY_AMT", number),
        Column("sell", "BILLBOARD_SELL_AMT", number),
        Column("billboard_turnover", "BILLBOARD_DEAL_AMT", number),
        Column("institution_buy_times", "ORG_BUY_TIMES", integer),
        Column("institution_sell_times", "ORG_SELL_TIMES", integer),
        Column("institution_net_buy", "ORG_NET_BUY", number),
        Column("institution_buy", "ORG_BUY_AMT", number),
        Column("institution_sell", "ORG_SELL_AMT", number),
        Column("change_1mo", "IPCT1M", number),
        Column("change_3mo", "IPCT3M", number),
        Column("change_6mo", "IPCT6M", number),
        Column("change_1y", "IPCT1Y", number),
    ),
    sort=(("BILLBOARD_TIMES", -1), ("LATEST_TDATE", -1), ("SECURITY_CODE", 1)),
)

__all__ = ["BILLBOARD_STOCK_STATS", "billboard_stock_stats_request"]


def billboard_stock_stats_request(
    query: BillboardStockStatsQuery,
) -> DatacenterRequest[BillboardStockStats]:
    return BILLBOARD_STOCK_STATS.request(period_filter("STATISTICS_CYCLE", query.period))

"""大宗交易市场统计（数据中心 PRT_BLOCKTRADE_MARKET_STA），一个交易日一行：全市场 A 股大宗交易的成交总额与溢价、折价成交额。"""

from em.channels.eastmoney.datacenter import (
    Column,
    ReportSpec,
    between,
    date_span,
    number,
    required_day,
)
from em.channels.eastmoney.request import DatacenterRequest
from em.domain.models import BlockTradeMarketDaily
from em.domain.queries import BlockTradeMarketDailyQuery

# 上游报表名就是 PRT 开头（不是 RPT 的笔误）。SZ_INDEX 的 SZ 是“上证”的拼音首字母：值是上证指数
# 收盘点位（实测与明细里沪市股票的 INDEX_CLOSE 逐日相等），以字符串给出。
# 排序对齐 akshare（交易日期倒序）；一个交易日一行，日期即唯一键
BLOCK_TRADE_MARKET_DAILY = ReportSpec(
    report="PRT_BLOCKTRADE_MARKET_STA",
    model=BlockTradeMarketDaily,
    columns=(
        Column("trade_date", "TRADE_DATE", required_day),
        Column("sh_index", "SZ_INDEX", number),
        Column("sh_index_change_pct", "SZ_CHANGE_RATE", number),
        Column("amount", "BLOCKTRADE_DEAL_AMT", number),
        Column("premium_amount", "PREMIUM_DEAL_AMT", number),
        Column("premium_ratio", "PREMIUM_RATIO", number),
        Column("discount_amount", "DISCOUNT_DEAL_AMT", number),
        Column("discount_ratio", "DISCOUNT_RATIO", number),
    ),
    sort=(("TRADE_DATE", -1),),
)

__all__ = ["BLOCK_TRADE_MARKET_DAILY", "block_trade_market_daily_request"]


def block_trade_market_daily_request(
    query: BlockTradeMarketDailyQuery,
) -> DatacenterRequest[BlockTradeMarketDaily]:
    """日期都留空时取全部历史（2000-08-29 起），不是最近一天：本报表是一天一行的时间序列。"""
    span = date_span(query.start_date, query.end_date)
    if span is None:
        return BLOCK_TRADE_MARKET_DAILY.request()
    return BLOCK_TRADE_MARKET_DAILY.request(between("TRADE_DATE", *span))

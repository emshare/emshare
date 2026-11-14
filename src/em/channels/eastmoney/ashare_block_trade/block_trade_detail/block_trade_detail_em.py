"""大宗交易每日明细（数据中心 RPT_DATA_BLOCKTRADE），按证券类型和交易日期区间取全部成交，一笔成交一行。"""

from em.channels.eastmoney import config
from em.channels.eastmoney.datacenter import (
    Column,
    ReportSpec,
    between,
    date_span,
    day,
    equals,
    market_of,
    number,
    pct_of_ratio,
    required_text,
)
from em.channels.eastmoney.request import DatacenterRequest
from em.domain.models import BlockTrade
from em.domain.queries import BlockTradeDetailQuery

# A 股、B 股、基金、债券是同一张表（SECURITY_TYPE_WEB 区分），列相同；B 股、基金、债券没有
# “成交额 / 流通市值”和之后 N 日涨跌幅，这些列为 null。
# 上游没有成交编号，同一只证券同一天可以有几笔买卖双方、价格、数量完全相同的成交；DAILY_RANK 是
# 这只证券当天各笔成交的序号，(代码, 日期, DAILY_RANK) 唯一（实测 2025-11 起 34678 条无重复）。
# 只按代码排序（akshare 的排序）时同一只证券的各笔成交先后不定，按页取会重复和丢行（实测一个月
# 1794 条、每页 500 条时重复 7 条）；这里在代码升序后补日期倒序与 DAILY_RANK，并把 DAILY_RANK
# 一并请求，相同的几笔成交也各自保留
BLOCK_TRADE_DETAIL = ReportSpec(
    report="RPT_DATA_BLOCKTRADE",
    model=BlockTrade,
    columns=(
        Column("code", "SECURITY_CODE", required_text),
        Column("name", "SECURITY_NAME_ABBR", required_text),
        Column("market", "SECUCODE", market_of),
        Column("trade_date", "TRADE_DATE", day),
        Column("change_pct", "CHANGE_RATE", number),
        Column("close", "CLOSE_PRICE", number),
        Column("price", "DEAL_PRICE", number),
        Column("premium_rate", "PREMIUM_RATIO", pct_of_ratio),
        Column("volume", "DEAL_VOLUME", number),
        Column("amount", "DEAL_AMT", number),
        Column("float_market_cap_ratio", "TURNOVER_RATE", number),
        Column("buyer_code", "BUYER_CODE"),
        Column("buyer_name", "BUYER_NAME"),
        Column("seller_code", "SELLER_CODE"),
        Column("seller_name", "SELLER_NAME"),
        Column("change_after_1d", "CHANGE_RATE_1DAYS", number),
        Column("change_after_5d", "CHANGE_RATE_5DAYS", number),
        Column("change_after_10d", "CHANGE_RATE_10DAYS", number),
        Column("change_after_20d", "CHANGE_RATE_20DAYS", number),
    ),
    sort=(("SECURITY_CODE", 1), ("TRADE_DATE", -1), ("DAILY_RANK", 1)),
    key_columns=("DAILY_RANK",),
)

__all__ = ["BLOCK_TRADE_DETAIL", "block_trade_detail_request", "normalize_security_type"]


def normalize_security_type(security_type: str) -> str:
    """未知回退 ashare。"""
    return security_type if security_type in config.BLOCK_TRADE_SECURITY_TYPES else "ashare"


def block_trade_detail_request(query: BlockTradeDetailQuery) -> DatacenterRequest[BlockTrade]:
    """日期都留空时取最近一个有这类证券大宗交易的交易日（先在该类型范围内查一次最新交易日）。"""
    kind = equals(
        "SECURITY_TYPE_WEB",
        config.BLOCK_TRADE_SECURITY_TYPES[normalize_security_type(query.security_type)],
    )
    span = date_span(query.start_date, query.end_date)
    if span is None:
        return BLOCK_TRADE_DETAIL.request(kind, latest_of="TRADE_DATE")
    return BLOCK_TRADE_DETAIL.request(kind + between("TRADE_DATE", *span))

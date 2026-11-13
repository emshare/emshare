"""个股龙虎榜详情（数据中心 RPT_BILLBOARD_DAILYDETAILSBUY / SELL），取一只股票某个上榜日的买入或卖出席位。"""

from em.channels.eastmoney.datacenter import (
    Column,
    ReportSpec,
    dash_date,
    day,
    equals,
    market_of,
    number,
    on,
    pct_of_ratio,
    required_text,
    safe_value,
    text,
)
from em.channels.eastmoney.request import DatacenterRequest
from em.domain.models import BillboardSeat
from em.domain.queries import BillboardStockQuery

# 买入、卖出两张报表列相同，只是各取买入 / 卖出金额最大的前 5 家营业部
_COLUMNS = (
    Column("code", "SECURITY_CODE", required_text),
    Column("market", "SECUCODE", market_of),
    Column("trade_date", "TRADE_DATE", day),
    Column("reason", "EXPLANATION"),
    Column("branch_code", "OPERATEDEPT_CODE", text),
    Column("branch_name", "OPERATEDEPT_NAME"),
    Column("buy", "BUY", number),
    Column("buy_ratio", "TOTAL_BUYRIO", pct_of_ratio),
    Column("sell", "SELL", number),
    Column("sell_ratio", "TOTAL_SELLRIO", pct_of_ratio),
    Column("net_buy", "NET", number),
    Column("close", "CLOSE_PRICE", number),
    Column("change_pct", "CHANGE_RATE", number),
    Column("turnover", "ACCUM_AMOUNT", number),
)

# side -> 报表。先按 TRADE_ID 把同一上榜原因的席位排在一起，组内按买入 / 卖出金额倒序（同东财页面）；
# 末尾补营业部代码保证顺序稳定
BILLBOARD_STOCK_SIDES = {
    "buy": ReportSpec(
        report="RPT_BILLBOARD_DAILYDETAILSBUY",
        model=BillboardSeat,
        columns=_COLUMNS,
        sort=(("TRADE_ID", 1), ("BUY", -1), ("OPERATEDEPT_CODE", 1)),
        key_columns=("TRADE_ID",),
    ),
    "sell": ReportSpec(
        report="RPT_BILLBOARD_DAILYDETAILSSELL",
        model=BillboardSeat,
        columns=_COLUMNS,
        sort=(("TRADE_ID", 1), ("SELL", -1), ("OPERATEDEPT_CODE", 1)),
        key_columns=("TRADE_ID",),
    ),
}

__all__ = ["BILLBOARD_STOCK_SIDES", "billboard_stock_request", "normalize_side"]


def normalize_side(side: str) -> str:
    """未知回退 buy。"""
    return side if side in BILLBOARD_STOCK_SIDES else "buy"


def billboard_stock_request(query: BillboardStockQuery) -> DatacenterRequest[BillboardSeat]:
    """``date`` 留空时取该股最近一个上榜日（先查一次最新上榜日）。"""
    spec = BILLBOARD_STOCK_SIDES[normalize_side(query.side)]
    stock = equals("SECURITY_CODE", safe_value(query.code, "code"))
    if not query.date:
        return spec.request(stock, latest_of="TRADE_DATE")
    return spec.request(on("TRADE_DATE", dash_date(query.date)) + stock)

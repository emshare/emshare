"""个股上榜日期（数据中心 RPT_LHB_BOARDDATE），取一只股票历次上榜的日期。"""

from em.channels.eastmoney.datacenter import (
    Column,
    ReportSpec,
    day,
    equals,
    required_text,
    safe_value,
)
from em.channels.eastmoney.request import DatacenterRequest
from em.domain.models import BillboardStockDate
from em.domain.queries import BillboardStockDatesQuery

# 排序对齐 akshare（上榜日倒序）；一个上榜日一行
BILLBOARD_STOCK_DATES = ReportSpec(
    report="RPT_LHB_BOARDDATE",
    model=BillboardStockDate,
    columns=(
        Column("code", "SECURITY_CODE", required_text),
        Column("trade_date", "TRADE_DATE", day),
    ),
    sort=(("TRADE_DATE", -1),),
)

__all__ = ["BILLBOARD_STOCK_DATES", "billboard_stock_dates_request"]


def billboard_stock_dates_request(
    query: BillboardStockDatesQuery,
) -> DatacenterRequest[BillboardStockDate]:
    return BILLBOARD_STOCK_DATES.request(equals("SECURITY_CODE", safe_value(query.code, "code")))

"""大宗交易每日统计接口族。"""

from em.channels.eastmoney.ashare_block_trade.block_trade_stock_daily.block_trade_stock_daily_em import (
    BLOCK_TRADE_STOCK_DAILY,
    block_trade_stock_daily_request,
)

__all__ = ["BLOCK_TRADE_STOCK_DAILY", "block_trade_stock_daily_request"]

"""大宗交易市场统计接口族。"""

from em.channels.eastmoney.ashare_block_trade.block_trade_market_daily.block_trade_market_daily_em import (
    BLOCK_TRADE_MARKET_DAILY,
    block_trade_market_daily_request,
)

__all__ = ["BLOCK_TRADE_MARKET_DAILY", "block_trade_market_daily_request"]

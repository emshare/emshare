"""分时行情接口族。"""

from em.channels.eastmoney.ashare_stocks.stock_trends.stock_trends_em import (
    secid_of,
    trends_request,
)

__all__ = ["secid_of", "trends_request"]

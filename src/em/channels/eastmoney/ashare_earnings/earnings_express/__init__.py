"""业绩快报接口族。"""

from em.channels.eastmoney.ashare_earnings.earnings_express.earnings_express_em import (
    EARNINGS_EXPRESS,
    earnings_express_request,
)

__all__ = ["EARNINGS_EXPRESS", "earnings_express_request"]

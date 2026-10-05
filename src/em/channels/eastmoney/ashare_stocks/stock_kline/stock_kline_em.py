"""个股 / 指数历史 K 线（push2his，日 / 周 / 月，前 / 后 / 不复权）。"""

from em.channels.eastmoney import config
from em.channels.eastmoney.request import KlineRequest
from em.domain.queries import KlineQuery


def secid_of(query: KlineQuery) -> str:
    """把「市场 + 代码」拼成东财 secid；未知市场回退深市。"""
    return f"{config.MARKET_IDS.get(query.market, '0')}.{query.code}"


def normalize_period(period: str) -> str:
    """把周期规范为已知值；未知周期回退日 K。"""
    return period if period in config.KLT_PERIODS else "day"


def normalize_adjust(adjust: str) -> str:
    """把复权方式规范为已知值；未知方式回退前复权。"""
    return adjust if adjust in config.FQT_ADJUSTS else "qfq"


def kline_request(query: KlineQuery) -> KlineRequest:
    period = normalize_period(query.period)
    adjust = normalize_adjust(query.adjust)
    return KlineRequest(
        host=config.KLINE_HOST,
        secid=secid_of(query),
        klt=config.KLT_PERIODS[period],
        fqt=config.FQT_ADJUSTS[adjust],
        beg=query.beg,
        end=query.end,
        period=period,
        adjust=adjust,
    )

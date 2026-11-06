"""板块历史 K 线（push2his，行业 / 概念 / 地域板块，日 / 周 / 月 / 分钟）。"""

from em.channels.eastmoney import config
from em.channels.eastmoney.request import KlineRequest
from em.domain.queries import BoardKlineQuery

# 板块是指数，复权无意义：固定不复权（实测 fqt=0 / fqt=1 返回一致）
_ADJUST = "none"


def secid_of(query: BoardKlineQuery) -> str:
    """把板块代码拼成东财 secid；板块统一 90 前缀。"""
    return f"{config.BOARD_MARKET_ID}.{query.board}"


def normalize_period(period: str) -> str:
    """把周期规范为已知值；未知周期回退日 K。"""
    return period if period in config.KLT_PERIODS else "day"


def board_kline_request(query: BoardKlineQuery) -> KlineRequest:
    period = normalize_period(query.period)
    return KlineRequest(
        host=config.KLINE_HOST,
        secid=secid_of(query),
        klt=config.KLT_PERIODS[period],
        fqt=config.FQT_ADJUSTS[_ADJUST],
        beg=query.beg,
        end=query.end,
        period=period,
        adjust=_ADJUST,
    )

"""应用层服务：面向自然语言的高层便捷接口（先 resolve 再调 ``*_em``）。

供 LLM/Agent 等自然语言输入场景使用：传中文名，内部 ``resolve`` → 代码 → 取数。
底层 ``*_em`` 接口不受影响，仍只收代码（与 akshare 对齐、channels 纯净）。

返回约定：名字 ``resolve`` 不到返回 ``None``（调用方据此换说法重试）；
resolve 命中后下游 ``*_em`` 的异常原样上抛。
"""

from __future__ import annotations

from em.application.market_data import (
    board_constituent_em,
    board_fund_flow_em,
    stock_fund_flow_em,
    stock_kline_em,
    stock_trends_em,
)
from em.application.resolve import resolve_board, resolve_code
from em.domain.models import (
    BoardFundFlowSeries,
    FundFlowSeries,
    KlineSeries,
    QuotePage,
    TrendSeries,
)
from em.domain.queries import (
    BoardFundFlowQuery,
    BoardQuery,
    FundFlowQuery,
    KlineQuery,
    TrendQuery,
)


def kline_by_name(
    name: str,
    *,
    period: str = "day",
    adjust: str = "qfq",
    beg: str = "0",
    end: str = "20500101",
) -> KlineSeries | None:
    """按中文名取 K 线（``resolve_code`` → ``stock_kline_em``）。查不到返回 ``None``。"""
    ref = resolve_code(name)
    if ref is None:
        return None
    return stock_kline_em(
        KlineQuery(code=ref.code, market=ref.market, period=period, adjust=adjust, beg=beg, end=end)
    )


def trends_by_name(
    name: str,
    *,
    ndays: int = 1,
    iscr: int = 0,
    iscca: int = 0,
) -> TrendSeries | None:
    """按中文名取分时行情（``resolve_code`` → ``stock_trends_em``）。查不到返回 ``None``。"""
    ref = resolve_code(name)
    if ref is None:
        return None
    return stock_trends_em(
        TrendQuery(code=ref.code, market=ref.market, ndays=ndays, iscr=iscr, iscca=iscca)
    )


def stock_fund_flow_by_name(name: str) -> FundFlowSeries | None:
    """按中文名取个股历史资金流。查不到返回 ``None``。"""
    ref = resolve_code(name)
    if ref is None:
        return None
    return stock_fund_flow_em(FundFlowQuery(code=ref.code, market=ref.market))


def board_constituent_by_name(
    name: str,
    *,
    period: str = "10d",
    page: int = 1,
    size: int = 8,
) -> QuotePage | None:
    """按中文名取板块成分股（``resolve_board`` → ``board_constituent_em``）。查不到返回 ``None``。"""
    ref = resolve_board(name)
    if ref is None:
        return None
    return board_constituent_em(BoardQuery(board=ref.code, period=period, page=page, size=size))


def board_fund_flow_by_name(name: str) -> BoardFundFlowSeries | None:
    """按中文名取板块历史资金流。查不到返回 ``None``。"""
    ref = resolve_board(name)
    if ref is None:
        return None
    return board_fund_flow_em(BoardFundFlowQuery(board=ref.code))

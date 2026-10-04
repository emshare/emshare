"""查询句柄：渠道无关的检索意图，把渠道参数挡在领域边界之外。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class BoardQuery:
    """板块成分股（可按资金流周期排序）。"""

    board: str = "BK0438"
    period: str = "10d"  # day / 5d / 10d
    page: int = 1
    size: int = 8


@dataclass(frozen=True)
class MarketQuery:
    """沪深京 A 股全市场列表。"""

    sort: str = "f3"
    page: int = 1
    size: int = 20


@dataclass(frozen=True)
class KlineQuery:
    """历史 K 线（日 / 周 / 月，前 / 后 / 不复权）。"""

    code: str = "000001"
    market: str = "sz"  # sz 深市 / sh 沪市 / bj 北交所
    period: str = "day"  # day / week / month
    adjust: str = "qfq"  # qfq 前复权 / hfq 后复权 / none 不复权
    beg: str = "0"  # 起始日期 YYYYMMDD，0 表示不限
    end: str = "20500101"  # 结束日期 YYYYMMDD


@dataclass(frozen=True)
class TrendQuery:
    """分时行情（trends2，ndays 日分时）。"""

    code: str = "000001"
    market: str = "sz"  # sz 深市 / sh 沪市 / bj 北交所
    ndays: int = 1  # 分时天数，1 当日 / 5 五日
    iscr: int = 0  # 是否含前收盘
    iscca: int = 0  # 是否含成交额累计


@dataclass(frozen=True)
class FundFlowQuery:
    """个股历史资金流（fflow/daykline，日线）。"""

    code: str = "000001"
    market: str = "sz"  # sz 深市 / sh 沪市 / bj 北交所


@dataclass(frozen=True)
class BoardFundFlowQuery:
    """板块（行业 / 概念 / 地域）历史资金流（fflow/daykline，日线）。"""

    board: str = "BK0438"  # 板块代码，如 BK0438

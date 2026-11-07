"""领域模型：与渠道无关的行情对象。缺字段一律 None，绝不臆造。"""

from dataclasses import dataclass

from em.domain.units import Lot, Pct, Point, Yuan


@dataclass(frozen=True)
class Quote:
    """单条行情记录。数值字段单位见 ``domain.units``。"""

    code: str
    name: str
    price: Yuan = None  # 最新价
    change_pct: Pct = None  # 涨跌幅
    change: Yuan = None  # 涨跌额
    main_net_inflow: Yuan = None  # 主力净流入（按查询周期）
    turnover: Yuan = None  # 成交额
    turnover_rate: Pct = None  # 换手率


@dataclass(frozen=True)
class QuotePage:
    """一页行情结果。"""

    total: int
    items: tuple[Quote, ...]


@dataclass(frozen=True)
class Kline:
    """单根 K 线。价格单位为元，比率单位为 %，成交量单位为手。"""

    date: str  # 交易日期/时间（日/周/月为 YYYY-MM-DD；分钟级为 YYYY-MM-DD HH:MM）
    open: Yuan = None  # 开盘价
    close: Yuan = None  # 收盘价
    high: Yuan = None  # 最高价
    low: Yuan = None  # 最低价
    volume: Lot = None  # 成交量
    amount: Yuan = None  # 成交额
    amplitude: Pct = None  # 振幅
    change_pct: Pct = None  # 涨跌幅
    change: Yuan = None  # 涨跌额
    turnover_rate: Pct = None  # 换手率


@dataclass(frozen=True)
class KlineSeries:
    """一只证券在一段区间内的 K 线序列。"""

    code: str
    name: str
    period: str  # day / week / month / 5m / 15m / 30m / 60m
    adjust: str  # qfq / hfq / none
    items: tuple[Kline, ...]


@dataclass(frozen=True)
class Trend:
    """一个分时点。价格单位为元，成交量单位为手。"""

    time: str  # YYYY-MM-DD HH:MM
    price: Yuan = None  # 最新价
    avg_price: Yuan = None  # 均价
    high: Yuan = None  # 该分钟最高
    low: Yuan = None  # 该分钟最低
    volume: Lot = None  # 成交量
    amount: Yuan = None  # 成交额
    avg_price2: Yuan = None  # 均价（3 位精度，f58）


@dataclass(frozen=True)
class TrendSeries:
    """一只证券的分时序列。"""

    code: str
    name: str
    pre_close: Yuan  # 昨收
    pre_price: Yuan  # 昨结算 / 盘前价
    ndays: int  # 分时天数
    items: tuple[Trend, ...]


@dataclass(frozen=True)
class FundFlow:
    """单日资金流。净额单位为元，占比单位为 %，价格单位为元。"""

    date: str  # 交易日期 YYYY-MM-DD
    main_net_inflow: Yuan = None  # 主力净流入-净额（f52 = 大单 + 超大单）
    small_net_inflow: Yuan = None  # 小单净流入-净额（f53）
    medium_net_inflow: Yuan = None  # 中单净流入-净额（f54）
    large_net_inflow: Yuan = None  # 大单净流入-净额（f55）
    xlarge_net_inflow: Yuan = None  # 超大单净流入-净额（f56）
    main_net_pct: Pct = None  # 主力净流入-净占比（f57）
    small_net_pct: Pct = None  # 小单净流入-净占比（f58）
    medium_net_pct: Pct = None  # 中单净流入-净占比（f59）
    large_net_pct: Pct = None  # 大单净流入-净占比（f60）
    xlarge_net_pct: Pct = None  # 超大单净流入-净占比（f61）
    close: Yuan = None  # 收盘价（f62）
    change_pct: Pct = None  # 涨跌幅（f63）


@dataclass(frozen=True)
class FundFlowSeries:
    """一只证券的历史资金流序列。"""

    code: str
    name: str
    market: str  # sz 深市 / sh 沪市 / bj 北交所 / bk 板块
    items: tuple[FundFlow, ...]


@dataclass(frozen=True)
class BoardFundFlow:
    """单日板块资金流（行业 / 概念 / 地域）。净额单位为元，占比单位为 %。

    与个股 ``FundFlow`` 的差异：板块口径不含收盘价 / 涨跌幅
    （上游 ``f62``/``f63`` 为板块指数点位 / 涨跌幅，东财页面与 akshare
    ``stock_sector_fund_flow_hist`` 均不展示，故字段集为 11 个）。
    """

    date: str  # 交易日期 YYYY-MM-DD
    main_net_inflow: Yuan = None  # 主力净流入-净额（f52 = 大单 + 超大单）
    small_net_inflow: Yuan = None  # 小单净流入-净额（f53）
    medium_net_inflow: Yuan = None  # 中单净流入-净额（f54）
    large_net_inflow: Yuan = None  # 大单净流入-净额（f55）
    xlarge_net_inflow: Yuan = None  # 超大单净流入-净额（f56）
    main_net_pct: Pct = None  # 主力净流入-净占比（f57）
    small_net_pct: Pct = None  # 小单净流入-净占比（f58）
    medium_net_pct: Pct = None  # 中单净流入-净占比（f59）
    large_net_pct: Pct = None  # 大单净流入-净占比（f60）
    xlarge_net_pct: Pct = None  # 超大单净流入-净占比（f61）


@dataclass(frozen=True)
class BoardFundFlowSeries:
    """板块（行业 / 概念 / 地域）历史资金流序列。"""

    code: str
    name: str
    items: tuple[BoardFundFlow, ...]


@dataclass(frozen=True)
class Board:
    """单条板块行情（行业 / 概念 / 地域）。数值字段单位见 ``domain.units``。

    与个股 ``Quote`` 的差异：板块含上涨 / 下跌家数与领涨 / 领跌股，
    不含主力净流入（板块列表接口不返回资金流字段）。
    """

    code: str
    name: str
    price: Yuan = None  # 板块指数最新点位
    change_pct: Pct = None  # 涨跌幅
    change: Yuan = None  # 涨跌额
    turnover: Yuan = None  # 成交额
    turnover_rate: Pct = None  # 换手率
    up_count: int | None = None  # 上涨家数
    down_count: int | None = None  # 下跌家数
    leader_code: str | None = None  # 领涨股代码
    leader_name: str | None = None  # 领涨股名称
    leader_change_pct: Pct = None  # 领涨股涨跌幅
    laggard_code: str | None = None  # 领跌股代码
    laggard_name: str | None = None  # 领跌股名称
    laggard_change_pct: Pct = None  # 领跌股涨跌幅


@dataclass(frozen=True)
class BoardListPage:
    """一页板块列表结果。"""

    total: int
    items: tuple[Board, ...]


@dataclass(frozen=True)
class IndexQuote:
    """单条指数行情（上证 / 深证 / 北证 / 中证）。点位类字段单位为点。

    ``code`` 单独不能唯一定位：``000001`` 在沪市是上证指数、在深市是平安银行，
    取 K 线等后续请求要连同 ``market`` 一起用。
    """

    code: str
    name: str
    market: str | None = None  # sh 沪市 / sz 深市 / bj 北交所 / csi 中证
    price: Point = None  # 最新点位
    change_pct: Pct = None  # 涨跌幅
    change: Point = None  # 涨跌额
    volume: Lot = None  # 成交量
    turnover: Yuan = None  # 成交额
    amplitude: Pct = None  # 振幅
    high: Point = None  # 最高
    low: Point = None  # 最低
    open: Point = None  # 今开
    pre_close: Point = None  # 昨收
    volume_ratio: float | None = None  # 量比


@dataclass(frozen=True)
class IndexListPage:
    """一页指数列表结果。"""

    total: int
    items: tuple[IndexQuote, ...]

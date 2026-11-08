"""领域模型：与渠道无关的行情对象。缺字段一律 None，绝不臆造。"""

from dataclasses import dataclass

from em.domain.units import Hkd, Lot, Pct, Point, Shares, Yuan


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


@dataclass(frozen=True)
class HkQuote:
    """单条港股行情。价格与成交额单位为港元，成交量单位为股（不是手）。"""

    code: str
    name: str
    price: Hkd = None  # 最新价
    change_pct: Pct = None  # 涨跌幅
    change: Hkd = None  # 涨跌额
    open: Hkd = None  # 今开
    high: Hkd = None  # 最高
    low: Hkd = None  # 最低
    pre_close: Hkd = None  # 昨收
    volume: Shares = None  # 成交量
    turnover: Hkd = None  # 成交额


@dataclass(frozen=True)
class HkStockListPage:
    """一页港股列表结果。"""

    total: int
    items: tuple[HkQuote, ...]


@dataclass(frozen=True)
class FundQuote:
    """单条场内基金行情（ETF / LOF）。价格单位为元，成交量单位为手。

    ``code`` 连同 ``market`` 可直接传给 ``stock_kline_em`` 取基金 K 线。
    """

    code: str
    name: str
    market: str | None = None  # sh 沪市 / sz 深市
    price: Yuan = None  # 最新价
    iopv: Yuan = None  # IOPV 实时估值（仅 ETF 有，LOF 为 None）
    discount_rate: Pct = None  # 基金折价率，负值表示溢价
    change_pct: Pct = None  # 涨跌幅
    change: Yuan = None  # 涨跌额
    volume: Lot = None  # 成交量
    turnover: Yuan = None  # 成交额
    open: Yuan = None  # 开盘价
    high: Yuan = None  # 最高价
    low: Yuan = None  # 最低价
    pre_close: Yuan = None  # 昨收
    turnover_rate: Pct = None  # 换手率
    float_market_cap: Yuan = None  # 流通市值
    total_market_cap: Yuan = None  # 总市值


@dataclass(frozen=True)
class FundListPage:
    """一页场内基金列表结果。"""

    total: int
    items: tuple[FundQuote, ...]


@dataclass(frozen=True)
class LimitPoolStock:
    """涨跌停股池中的一只股票。价格单位为元。

    6 个股池共用本模型：前 10 个字段各股池都有，其余为股池专属字段，
    不适用的股池为 None（如跌停池没有涨停价）。时间为 ``HH:MM:SS``，日期为 ``YYYY-MM-DD``。
    """

    code: str
    name: str
    market: str | None = None  # sh 沪市 / sz 深市 / bj 北交所
    price: Yuan = None  # 最新价
    change_pct: Pct = None  # 涨跌幅
    turnover: Yuan = None  # 成交额
    float_market_cap: Yuan = None  # 流通市值
    total_market_cap: Yuan = None  # 总市值
    turnover_rate: Pct = None  # 换手率
    industry: str | None = None  # 所属行业
    # 涨停统计：近 stat_days 天内涨停 stat_limit_ups 次（上游 zttj，如“10 天 6 板”）
    stat_days: int | None = None
    stat_limit_ups: int | None = None
    limit_up_price: Yuan = None  # 涨停价（昨日涨停 / 强势 / 次新 / 炸板）
    seal_fund: Yuan = None  # 封板资金（涨停池）/ 封单资金（跌停池）
    first_seal_time: str | None = None  # 首次封板时间（涨停 / 炸板）
    last_seal_time: str | None = None  # 最后封板时间（涨停 / 跌停）
    broken_count: int | None = None  # 炸板次数（涨停 / 炸板）
    limit_up_streak: int | None = None  # 连板数（涨停）
    prev_seal_time: str | None = None  # 昨日封板时间（昨日涨停）
    prev_limit_up_streak: int | None = None  # 昨日连板数（昨日涨停）
    amplitude: Pct = None  # 振幅（昨日涨停 / 炸板）
    speed: Pct = None  # 涨速（昨日涨停 / 强势 / 炸板）
    volume_ratio: float | None = None  # 量比（强势）
    new_high: bool | None = None  # 是否 60 日新高（强势 / 次新）
    reason: str | None = None  # 入选理由（强势）
    open_days: int | None = None  # 开板几日（次新）
    open_date: str | None = None  # 开板日期（次新）
    listing_date: str | None = None  # 上市日期（次新）
    pe: float | None = None  # 动态市盈率（跌停）
    board_turnover: Yuan = None  # 板上成交额（跌停）
    limit_down_streak: int | None = None  # 连续跌停天数（跌停）
    open_count: int | None = None  # 开板次数（跌停）


@dataclass(frozen=True)
class LimitPoolPage:
    """一个交易日的涨跌停股池。``date`` 是数据实际所属的交易日（``YYYY-MM-DD``）。"""

    pool_type: str
    date: str
    total: int
    items: tuple[LimitPoolStock, ...]


@dataclass(frozen=True)
class StockInfo:
    """个股基本信息（对齐 akshare stock_individual_info_em）。"""

    code: str
    name: str
    market: str | None = None  # sh 沪市 / sz 深市 / bj 北交所
    industry: str | None = None  # 所属行业
    listing_date: str | None = None  # 上市日期 YYYY-MM-DD
    price: Yuan = None  # 最新价
    total_shares: Shares = None  # 总股本
    float_shares: Shares = None  # 流通股
    total_market_cap: Yuan = None  # 总市值
    float_market_cap: Yuan = None  # 流通市值


@dataclass(frozen=True)
class OrderLevel:
    """盘口一档：价格与挂单量。无挂单时两者为 None。"""

    price: Yuan = None
    volume: Lot = None


@dataclass(frozen=True)
class StockBidAsk:
    """个股五档盘口与当日行情快照。

    ``bids`` / ``asks`` 各 5 档，下标 0 为买一 / 卖一。上游默认字段集不含涨跌额、涨跌幅、
    换手率、内盘，本模型不提供（见 stock_bid_ask_em 文档）。
    """

    code: str
    name: str
    market: str | None = None
    price: Yuan = None  # 最新价
    avg_price: Yuan = None  # 均价
    open: Yuan = None  # 今开
    high: Yuan = None  # 最高
    low: Yuan = None  # 最低
    pre_close: Yuan = None  # 昨收
    limit_up: Yuan = None  # 涨停价（无涨跌幅限制时为 None）
    limit_down: Yuan = None  # 跌停价
    volume: Lot = None  # 成交量（总手）
    turnover: Yuan = None  # 成交额
    outer_volume: Lot = None  # 外盘
    volume_ratio: float | None = None  # 量比
    bids: tuple[OrderLevel, ...] = ()  # 买一 ~ 买五
    asks: tuple[OrderLevel, ...] = ()  # 卖一 ~ 卖五


@dataclass(frozen=True)
class StockChange:
    """一条盘口异动。``time`` 为 ``HH:MM:SS``，上游不给日期（属于最近一个交易日）。

    ``volume`` / ``amount`` 只有大笔买入 / 大笔卖出（成交量 / 成交额）与有大买盘 / 有大卖盘
    （挂单量 / 挂单金额）四类有，其余类型为 None。``info`` 是上游原始“相关信息”，各类型格式不同。
    """

    time: str
    code: str
    name: str
    market: str | None = None  # sh 沪市 / sz 深市 / bj 北交所
    change_type: str | None = None  # 异动类型（英文，如 big_buy）
    price: Yuan = None  # 异动时的价格（大笔买卖为成交价）
    change_pct: Pct = None  # 异动时的涨跌幅
    volume: Shares = None  # 成交量 / 挂单量
    amount: Yuan = None  # 成交额 / 挂单金额
    info: str | None = None  # 上游原始相关信息（逗号分隔）


@dataclass(frozen=True)
class StockChangesPage:
    """最近一个交易日某一类盘口异动的全部记录，按时间倒序。"""

    change_type: str
    total: int
    items: tuple[StockChange, ...]


@dataclass(frozen=True)
class ChangeTypeCount:
    """板块内某一类异动的出现次数。"""

    change_type: str
    count: int


@dataclass(frozen=True)
class BoardChange:
    """一个板块当日的异动汇总。

    ``change_count`` 是上游原值，含东财未公开的 6 种类型；``type_counts`` 只列 22 种已知类型，
    所以两者之和可能对不上。最频繁个股的类型是未公开类型时 ``top_stock_change_type`` 为 None。
    """

    code: str
    name: str
    change_pct: Pct = None  # 板块涨跌幅
    main_net_inflow: Yuan = None  # 主力净流入
    change_count: int | None = None  # 板块异动总次数
    top_stock_code: str | None = None  # 异动最频繁个股：代码
    top_stock_name: str | None = None  # 异动最频繁个股：名称
    top_stock_market: str | None = None  # 异动最频繁个股：sh / sz / bj
    top_stock_change_type: str | None = None  # 异动最频繁个股：所属异动类型
    type_counts: tuple[ChangeTypeCount, ...] = ()  # 各类异动次数，按次数倒序


@dataclass(frozen=True)
class BoardChangesPage:
    """最近一个交易日全部有异动的板块，按异动总次数倒序。``date`` / ``time`` 是上游数据时间。"""

    date: str  # YYYY-MM-DD
    time: str  # HH:MM:SS
    total: int
    items: tuple[BoardChange, ...]

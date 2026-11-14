"""领域模型：与渠道无关的行情对象。缺字段一律 None，绝不臆造。"""

from dataclasses import dataclass
from typing import Generic, TypeVar

from em.domain.units import Hkd, Lot, Pct, Point, Shares, Yuan

T = TypeVar("T")


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


@dataclass(frozen=True)
class ReportPage(Generic[T]):
    """报表查询结果（龙虎榜 / 大宗交易 / 业绩财报等数据中心报表），已翻完全部页，``items`` 保持上游排序。

    ``total`` 是上游报告的条数，通常等于 ``len(items)``。两种情况会不等：上游会重复返回同一行的
    报表去重后变少（如商誉减值预期）；翻页期间上游持续增删、重抓后仍对不上（会记 warning）。
    """

    total: int
    items: tuple[T, ...]


@dataclass(frozen=True)
class BillboardEntry:
    """龙虎榜的一条上榜记录。金额单位元，比率单位 %。

    同一只股票同一天因多个原因上榜时有多条记录，各条按自己的上榜原因统计金额，
    不能直接相加（单日原因与“连续三个交易日”类原因的统计区间不同）。
    """

    code: str
    name: str
    market: str | None = None  # sh 沪市 / sz 深市 / bj 北交所
    trade_date: str | None = None  # 上榜日 YYYY-MM-DD
    reason: str | None = None  # 上榜原因
    interpretation: str | None = None  # 解读，如“2家机构卖出，成功率18.37%”
    close: Yuan = None  # 收盘价
    change_pct: Pct = None  # 涨跌幅
    net_buy: Yuan = None  # 龙虎榜净买额
    buy: Yuan = None  # 龙虎榜买入额
    sell: Yuan = None  # 龙虎榜卖出额
    billboard_turnover: Yuan = None  # 龙虎榜成交额
    turnover: Yuan = None  # 市场总成交额（该股当日成交额）
    net_buy_ratio: Pct = None  # 净买额占总成交比
    billboard_turnover_ratio: Pct = None  # 龙虎榜成交额占总成交比
    turnover_rate: Pct = None  # 换手率
    float_market_cap: Yuan = None  # 流通市值
    change_after_1d: Pct = None  # 上榜后 1 日涨跌幅（尚未到期为 None）
    change_after_2d: Pct = None  # 上榜后 2 日涨跌幅
    change_after_5d: Pct = None  # 上榜后 5 日涨跌幅
    change_after_10d: Pct = None  # 上榜后 10 日涨跌幅


@dataclass(frozen=True)
class BillboardStockStats:
    """个股上榜统计：统计周期内一只股票的上榜次数与龙虎榜、机构买卖合计。金额单位元。"""

    code: str
    name: str
    market: str | None = None  # sh 沪市 / sz 深市 / bj 北交所
    latest_date: str | None = None  # 最近上榜日 YYYY-MM-DD
    close: Yuan = None  # 收盘价
    change_pct: Pct = None  # 涨跌幅
    billboard_times: int | None = None  # 上榜次数
    net_buy: Yuan = None  # 龙虎榜净买额
    buy: Yuan = None  # 龙虎榜买入额
    sell: Yuan = None  # 龙虎榜卖出额
    billboard_turnover: Yuan = None  # 龙虎榜总成交额
    institution_buy_times: int | None = None  # 买方机构次数
    institution_sell_times: int | None = None  # 卖方机构次数
    institution_net_buy: Yuan = None  # 机构买入净额
    institution_buy: Yuan = None  # 机构买入总额
    institution_sell: Yuan = None  # 机构卖出总额
    change_1mo: Pct = None  # 近 1 个月涨跌幅
    change_3mo: Pct = None  # 近 3 个月涨跌幅
    change_6mo: Pct = None  # 近 6 个月涨跌幅
    change_1y: Pct = None  # 近 1 年涨跌幅


@dataclass(frozen=True)
class BillboardInstitutionTrade:
    """机构买卖每日统计的一条记录：某只股票某次上榜中机构席位的买卖合计。金额单位元，比率单位 %。

    同一只股票同一天因多个原因上榜时有多条记录，各按自己的上榜原因统计，不能直接相加。
    """

    code: str
    name: str
    market: str | None = None  # sh 沪市 / sz 深市 / bj 北交所
    trade_date: str | None = None  # 上榜日 YYYY-MM-DD
    reason: str | None = None  # 上榜原因
    close: Yuan = None  # 收盘价
    change_pct: Pct = None  # 涨跌幅
    buy_institutions: int | None = None  # 买方机构数
    sell_institutions: int | None = None  # 卖方机构数
    institution_buy: Yuan = None  # 机构买入总额
    institution_sell: Yuan = None  # 机构卖出总额
    institution_net_buy: Yuan = None  # 机构买入净额
    turnover: Yuan = None  # 市场总成交额
    net_buy_ratio: Pct = None  # 机构净买额占总成交额比
    turnover_rate: Pct = None  # 换手率
    float_market_cap: Yuan = None  # 流通市值
    change_after_1d: Pct = None  # 上榜后 1 日涨跌幅（尚未到期为 None）
    change_after_2d: Pct = None  # 上榜后 2 日涨跌幅
    change_after_3d: Pct = None  # 上榜后 3 日涨跌幅
    change_after_5d: Pct = None  # 上榜后 5 日涨跌幅
    change_after_10d: Pct = None  # 上榜后 10 日涨跌幅


@dataclass(frozen=True)
class BillboardInstitutionStats:
    """机构席位追踪：统计周期内一只股票上榜时机构席位的买卖合计。金额单位元。"""

    code: str
    name: str
    market: str | None = None  # sh 沪市 / sz 深市 / bj 北交所
    close: Yuan = None  # 收盘价
    change_pct: Pct = None  # 涨跌幅
    billboard_turnover: Yuan = None  # 龙虎榜成交金额
    billboard_times: int | None = None  # 上榜次数
    institution_buy: Yuan = None  # 机构买入额
    institution_buy_times: int | None = None  # 机构买入次数
    institution_sell: Yuan = None  # 机构卖出额
    institution_sell_times: int | None = None  # 机构卖出次数
    institution_net_buy: Yuan = None  # 机构净买额
    change_1mo: Pct = None  # 近 1 个月涨跌幅
    change_3mo: Pct = None  # 近 3 个月涨跌幅
    change_6mo: Pct = None  # 近 6 个月涨跌幅
    change_1y: Pct = None  # 近 1 年涨跌幅


@dataclass(frozen=True)
class BillboardBranchActive:
    """每日活跃营业部：一家营业部某个上榜日的买卖合计与当日上榜交易的股票。金额单位元。

    ``stocks`` / ``stock_codes`` 是该营业部当日买入或卖出过的全部上榜股票（实测与营业部详情逐家一致），
    个数可以大于 ``buy_stock_count``。东财页面与上游列名（``BUY_STOCK``）把它叫“买入股票”，名不副实。
    """

    branch_code: str
    branch_name: str
    trade_date: str | None = None  # 上榜日 YYYY-MM-DD
    buy_stock_count: int | None = None  # 买入个股数
    sell_stock_count: int | None = None  # 卖出个股数
    buy: Yuan = None  # 买入总金额
    sell: Yuan = None  # 卖出总金额
    net_buy: Yuan = None  # 总买卖净额
    stocks: str | None = None  # 当日买入或卖出过的股票简称，空格分隔（上游原文）
    stock_codes: tuple[str, ...] = ()  # 上述股票的代码，与 stocks 一一对应


@dataclass(frozen=True)
class BillboardBranchRank:
    """营业部排行：统计周期内一家营业部买入上榜后 1 / 2 / 3 / 5 / 10 天的表现。涨幅、概率单位 %。"""

    branch_code: str
    branch_name: str
    buy_times_1d: int | None = None  # 上榜后 1 天：买入次数
    avg_change_1d: Pct = None  # 上榜后 1 天：平均涨幅
    rise_prob_1d: Pct = None  # 上榜后 1 天：上涨概率
    buy_times_2d: int | None = None
    avg_change_2d: Pct = None
    rise_prob_2d: Pct = None
    buy_times_3d: int | None = None
    avg_change_3d: Pct = None
    rise_prob_3d: Pct = None
    buy_times_5d: int | None = None
    avg_change_5d: Pct = None
    rise_prob_5d: Pct = None
    buy_times_10d: int | None = None
    avg_change_10d: Pct = None
    rise_prob_10d: Pct = None


@dataclass(frozen=True)
class BillboardBranchStats:
    """营业部统计：统计周期内一家营业部的上榜次数与买卖合计。金额单位元。"""

    branch_code: str
    branch_name: str
    billboard_turnover: Yuan = None  # 龙虎榜成交金额
    billboard_times: int | None = None  # 上榜次数
    buy: Yuan = None  # 买入额
    buy_times: int | None = None  # 买入次数
    sell: Yuan = None  # 卖出额
    sell_times: int | None = None  # 卖出次数


@dataclass(frozen=True)
class BillboardBranchTrade:
    """营业部详情的一条记录：一家营业部在某只股票某次上榜中的买卖。金额单位元。

    同一只股票同一天因多个原因上榜时有多条记录（上榜原因不同）。
    """

    branch_code: str
    branch_name: str
    branch_short_name: str | None = None  # 营业部简称
    trade_date: str | None = None  # 交易日期 YYYY-MM-DD
    code: str = ""  # 股票代码
    name: str = ""  # 股票名称
    market: str | None = None  # sh 沪市 / sz 深市 / bj 北交所
    change_pct: Pct = None  # 涨跌幅
    buy: Yuan = None  # 买入金额（该营业部只卖出时为 None）
    sell: Yuan = None  # 卖出金额（该营业部只买入时为 None）
    net_buy: Yuan = None  # 净额
    reason: str | None = None  # 上榜原因
    change_after_1d: Pct = None  # 1 日后涨跌幅（尚未到期为 None）
    change_after_2d: Pct = None
    change_after_3d: Pct = None
    change_after_5d: Pct = None
    change_after_10d: Pct = None
    change_after_20d: Pct = None
    change_after_30d: Pct = None


@dataclass(frozen=True)
class BillboardStockDate:
    """一只股票的一个上榜日。"""

    code: str
    trade_date: str | None = None  # 上榜日 YYYY-MM-DD


@dataclass(frozen=True)
class BillboardSeat:
    """个股龙虎榜详情的一个席位：某只股票某次上榜中，买入或卖出金额最大的前 5 家营业部之一。

    金额单位元，占比单位 %（占该次上榜统计区间的总成交额）。同一天因多个原因上榜时，
    每个原因各有一组席位，``reason`` 区分。
    """

    code: str
    market: str | None = None  # sh 沪市 / sz 深市 / bj 北交所
    trade_date: str | None = None  # 上榜日 YYYY-MM-DD
    reason: str | None = None  # 上榜原因
    branch_code: str | None = None  # 营业部代码（机构专用为 "0"）
    branch_name: str | None = None  # 交易营业部名称
    buy: Yuan = None  # 买入金额
    buy_ratio: Pct = None  # 买入金额占总成交比例
    sell: Yuan = None  # 卖出金额
    sell_ratio: Pct = None  # 卖出金额占总成交比例
    net_buy: Yuan = None  # 净额
    close: Yuan = None  # 收盘价
    change_pct: Pct = None  # 涨跌幅
    turnover: Yuan = None  # 总成交额（该上榜原因统计区间内）


@dataclass(frozen=True)
class BlockTradeMarketDaily:
    """大宗交易市场统计的一个交易日：全市场 A 股大宗交易的成交总额与溢价、折价成交额。

    金额单位元，占比单位 %。只统计 A 股，不含 B 股、基金、债券；溢价、折价之外的是平价成交。
    """

    trade_date: str  # 交易日期 YYYY-MM-DD
    sh_index: Point = None  # 上证指数收盘点位
    sh_index_change_pct: Pct = None  # 上证指数涨跌幅
    amount: Yuan = None  # 大宗交易成交总额
    premium_amount: Yuan = None  # 溢价成交总额
    premium_ratio: Pct = None  # 溢价成交总额占比
    discount_amount: Yuan = None  # 折价成交总额
    discount_ratio: Pct = None  # 折价成交总额占比


@dataclass(frozen=True)
class BlockTrade:
    """大宗交易的一笔成交。A 股的金额单位元、成交量单位股，比率单位 %。

    上游没有成交编号：同一只证券同一天可以有几笔买卖双方、价格、数量完全相同的成交，各算一笔，
    不能去重。B 股、基金、债券没有“成交额 / 流通市值”和之后 N 日涨跌幅（为 None）。
    """

    code: str
    name: str
    market: str | None = None  # sh 沪市 / sz 深市 / bj 北交所
    trade_date: str | None = None  # 交易日期 YYYY-MM-DD
    change_pct: Pct = None  # 当日涨跌幅
    close: Yuan = None  # 当日收盘价
    price: Yuan = None  # 成交价
    premium_rate: Pct = None  # 折溢率 = 成交价 / 收盘价 - 1，正为溢价、负为折价
    # 成交量，上游原值：A 股、B 股为股，基金为份；债券 2015 年以来为手（1 手 = 10 张），更早口径不一
    volume: float | None = None
    amount: Yuan = None  # 成交额；B 股为交易币种（沪市 B 股 2008–2020 年间的记录多为人民币）
    float_market_cap_ratio: Pct = None  # 成交额 / 流通市值（按当日收盘价与流通 A 股计，仅 A 股有）
    buyer_code: str | None = None  # 买方营业部代码（机构专用为 "0"）
    buyer_name: str | None = None  # 买方营业部
    seller_code: str | None = None  # 卖方营业部代码（机构专用为 "0"）
    seller_name: str | None = None  # 卖方营业部
    change_after_1d: Pct = None  # 1 日后涨跌幅（仅 A 股有；尚未到期为 None）
    change_after_5d: Pct = None  # 5 日后涨跌幅
    change_after_10d: Pct = None  # 10 日后涨跌幅
    change_after_20d: Pct = None  # 20 日后涨跌幅


@dataclass(frozen=True)
class BlockTradeStockDaily:
    """大宗交易每日统计：一只 A 股一个交易日的大宗交易汇总。金额单位元，成交量单位股，比率单位 %。"""

    code: str
    name: str
    market: str | None = None  # sh 沪市 / sz 深市 / bj 北交所
    trade_date: str | None = None  # 交易日期 YYYY-MM-DD
    change_pct: Pct = None  # 当日涨跌幅
    close: Yuan = None  # 当日收盘价
    avg_price: Yuan = None  # 成交均价：各笔成交价按成交量加权（约等于 成交总额 / 成交总量）
    premium_rate: Pct = None  # 折溢率 = 成交均价 / 收盘价 - 1，正为溢价、负为折价
    deal_times: int | None = None  # 成交笔数
    premium_times: int | None = None  # 其中溢价成交的笔数
    discount_times: int | None = None  # 其中折价成交的笔数
    volume: Shares = None  # 成交总量
    amount: Yuan = None  # 成交总额
    float_market_cap_ratio: Pct = None  # 成交总额 / 流通市值
    change_after_1d: Pct = None  # 1 日后涨跌幅（尚未到期为 None）
    change_after_5d: Pct = None  # 5 日后涨跌幅
    change_after_10d: Pct = None  # 10 日后涨跌幅
    change_after_20d: Pct = None  # 20 日后涨跌幅


@dataclass(frozen=True)
class BlockTradeStockStats:
    """活跃 A 股统计：统计周期内一只 A 股的大宗交易汇总。金额单位元，比率单位 %。

    ``avg_change_after_*`` 是“已到期各笔的 N 日后涨跌幅之和 ÷ 周期内全部笔数”：还没到期的成交
    按 0 计入，周期越短、N 越大，被摊薄得越多。
    """

    code: str
    name: str
    market: str | None = None  # sh 沪市 / sz 深市 / bj 北交所
    close: Yuan = None  # 最近上榜日的收盘价
    change_pct: Pct = None  # 最近上榜日的涨跌幅
    latest_date: str | None = None  # 最近上榜日 YYYY-MM-DD（周期内最后一次有大宗交易的交易日）
    deal_times: int | None = None  # 成交笔数（东财页面叫“上榜次数”）
    premium_times: int | None = None  # 其中溢价成交的笔数
    discount_times: int | None = None  # 其中折价成交的笔数
    amount: Yuan = None  # 总成交额
    premium_rate: Pct = None  # 折溢率 = 总成交额 / Σ(成交量 × 当日收盘价) - 1
    float_market_cap_ratio: Pct = None  # 成交总额 / 流通市值（各笔之和）
    avg_change_after_1d: Pct = None  # 上榜日后 1 日平均涨跌幅
    avg_change_after_5d: Pct = None  # 上榜日后 5 日平均涨跌幅
    avg_change_after_10d: Pct = None  # 上榜日后 10 日平均涨跌幅
    avg_change_after_20d: Pct = None  # 上榜日后 20 日平均涨跌幅


@dataclass(frozen=True)
class BlockTradeBranchActive:
    """活跃营业部统计：最近 N 个交易日内一家营业部的 A 股大宗交易买卖汇总。金额单位元。"""

    branch_code: str  # 营业部代码（机构专用为 "0"）
    branch_name: str
    latest_date: str | None = None  # 最近上榜日 YYYY-MM-DD（周期内最后一次买入或卖出的交易日）
    buy_times: int | None = None  # 买入笔数
    sell_times: int | None = None  # 卖出笔数
    buy: Yuan = None  # 买入金额
    sell: Yuan = None  # 卖出金额
    net_buy: Yuan = None  # 净买入额 = 买入 - 卖出
    buy_stocks: str | None = None  # 买入股票的简称，空格分隔；只卖出的营业部为 None
    buy_stock_codes: tuple[str, ...] = ()  # 买入股票的代码，与 buy_stocks 一一对应


@dataclass(frozen=True)
class BlockTradeBranchRank:
    """营业部排行：最近 N 个交易日内一家营业部买入的 A 股在成交后 1 / 5 / 10 / 20 日的表现。

    涨幅、概率单位 %。各档只统计已经有 N 日后涨跌幅的买入；某一档还没有到期的买入时三项都是 None。
    5 日档与每日明细逐家一致；1 / 10 / 20 日档有少数营业部比明细少（上游数据自身的出入）。
    """

    branch_code: str  # 营业部代码（机构专用为 "0"）
    branch_name: str
    buy_times_1d: int | None = None  # 上榜后 1 天：买入次数
    avg_change_1d: Pct = None  # 上榜后 1 天：平均涨幅
    rise_prob_1d: Pct = None  # 上榜后 1 天：上涨概率
    buy_times_5d: int | None = None
    avg_change_5d: Pct = None
    rise_prob_5d: Pct = None
    buy_times_10d: int | None = None
    avg_change_10d: Pct = None
    rise_prob_10d: Pct = None
    buy_times_20d: int | None = None
    avg_change_20d: Pct = None
    rise_prob_20d: Pct = None


@dataclass(frozen=True)
class EarningsReport:
    """业绩报告：一家公司一个报告期的主要业绩指标。金额单位元，比率单位 %。"""

    code: str
    name: str
    market: str | None = None  # 市场：sh / sz / bj，可连同 code 传给 stock_kline_em
    report_date: str | None = None  # 报告期 YYYY-MM-DD
    eps: Yuan = None  # 基本每股收益
    deducted_eps: Yuan = None  # 扣非每股收益（年报才有，其余报告期多为 None）
    revenue: Yuan = None  # 营业总收入
    revenue_yoy: Pct = None  # 营业总收入同比增长
    revenue_qoq: Pct = None  # 营业总收入季度环比增长
    net_profit: Yuan = None  # 归属于母公司股东的净利润
    net_profit_yoy: Pct = None  # 净利润同比增长
    net_profit_qoq: Pct = None  # 净利润季度环比增长
    bps: Yuan = None  # 每股净资产
    roe: Pct = None  # 加权平均净资产收益率
    cash_flow_per_share: Yuan = None  # 每股经营现金流量
    gross_margin: Pct = None  # 销售毛利率
    # 利润分配方案，如“10派3.60元(含税,扣税后3.24元)”（年报、中报才有）
    dividend_plan: str | None = None
    dividend_yield: Pct = None  # 股息率（有现金分红方案时才有）
    industry: str | None = None  # 所处行业
    notice_date: str | None = None  # 首次公告日期 YYYY-MM-DD
    update_date: str | None = None  # 最新公告日期 YYYY-MM-DD（有更正公告时晚于首次公告日期）


@dataclass(frozen=True)
class EarningsExpress:
    """业绩快报：一家公司一个报告期的快报数据。金额单位元，比率单位 %。只有部分公司发布快报，年报期最多。"""

    code: str
    name: str
    market: str | None = None  # 市场：sh / sz / bj，可连同 code 传给 stock_kline_em
    report_date: str | None = None  # 报告期 YYYY-MM-DD
    eps: Yuan = None  # 基本每股收益
    revenue: Yuan = None  # 营业收入
    revenue_prev_year: Yuan = None  # 去年同期营业收入
    revenue_yoy: Pct = None  # 营业收入同比增长
    revenue_qoq: Pct = None  # 营业收入季度环比增长
    net_profit: Yuan = None  # 归属于母公司股东的净利润
    net_profit_prev_year: Yuan = None  # 去年同期净利润
    net_profit_yoy: Pct = None  # 净利润同比增长
    net_profit_qoq: Pct = None  # 净利润季度环比增长
    bps: Yuan = None  # 每股净资产
    roe: Pct = None  # 加权平均净资产收益率
    industry: str | None = None  # 所处行业
    notice_date: str | None = None  # 公告日期 YYYY-MM-DD
    update_date: str | None = None  # 最新公告日期 YYYY-MM-DD


@dataclass(frozen=True)
class EarningsForecast:
    """业绩预告的一项预测指标。金额单位元（指标为每股收益时是元 / 股），幅度单位 %。

    一家公司每项预测指标一行（净利润、扣非净利润、营业收入、每股收益等），不能按行数统计公司数。
    """

    code: str
    name: str
    market: str | None = None  # 市场：sh / sz / bj，可连同 code 传给 stock_kline_em
    report_date: str | None = None  # 报告期 YYYY-MM-DD
    notice_date: str | None = None  # 公告日期 YYYY-MM-DD
    # 预测指标，如“归属于上市公司股东的净利润”“每股收益”（一家公司每项指标一行）
    indicator: str | None = None
    summary: str | None = None  # 业绩变动的文字说明
    forecast_value: Yuan = None  # 预测数值：上下限的均值（指标为每股收益时单位是元 / 股）
    lower: Yuan = None  # 预测下限
    upper: Yuan = None  # 预测上限
    change_pct: Pct = None  # 业绩变动幅度：同比变动上下限的均值
    change_pct_lower: Pct = None  # 同比变动幅度下限
    change_pct_upper: Pct = None  # 同比变动幅度上限
    reason: str | None = None  # 业绩变动原因
    # 预告类型：预增 / 预减 / 略增 / 略减 / 扭亏 / 首亏 / 续亏 / 续盈 / 减亏 / 增亏 / 不确定
    forecast_type: str | None = None
    prev_year: Yuan = None  # 上年同期值


@dataclass(frozen=True)
class EarningsSchedule:
    """定期报告预约披露时间：一家公司一个报告期的预约、变更与实际披露日期。"""

    code: str
    name: str
    market: str | None = None  # 市场：sh / sz / bj，可连同 code 传给 stock_kline_em
    report_date: str | None = None  # 报告期 YYYY-MM-DD
    first_appoint_date: str | None = None  # 首次预约披露日期 YYYY-MM-DD
    first_change_date: str | None = None  # 第一次变更后的预约日期（没有变更为 None）
    second_change_date: str | None = None  # 第二次变更后的预约日期
    third_change_date: str | None = None  # 第三次变更后的预约日期
    appoint_date: str | None = None  # 当前生效的预约披露日期（最后一次变更后的日期）
    actual_date: str | None = None  # 实际披露日期（尚未披露为 None）


@dataclass(frozen=True)
class BalanceSheet:
    """资产负债表：一家公司一个报告期的主要科目。金额单位元，同比与比率单位 %。

    银行、券商、保险专用科目只有对应行业有值，一般公司为 None；反之存货、应收账款等金融类为 None。
    """

    code: str
    name: str
    market: str | None = None  # 市场：sh / sz / bj，可连同 code 传给 stock_kline_em
    industry: str | None = None  # 所处行业
    report_date: str | None = None  # 报告期 YYYY-MM-DD
    notice_date: str | None = None  # 公告日期 YYYY-MM-DD
    cash: Yuan = None  # 货币资金
    cash_yoy: Pct = None  # 货币资金同比
    accounts_receivable: Yuan = None  # 应收账款
    accounts_receivable_yoy: Pct = None  # 应收账款同比
    inventory: Yuan = None  # 存货
    inventory_yoy: Pct = None  # 存货同比
    fixed_assets: Yuan = None  # 固定资产
    total_assets: Yuan = None  # 总资产
    total_assets_yoy: Pct = None  # 总资产同比
    accounts_payable: Yuan = None  # 应付账款
    accounts_payable_yoy: Pct = None  # 应付账款同比
    advance_receipts: Yuan = None  # 预收账款
    advance_receipts_yoy: Pct = None  # 预收账款同比
    total_liabilities: Yuan = None  # 总负债
    total_liabilities_yoy: Pct = None  # 总负债同比
    debt_asset_ratio: Pct = None  # 资产负债率 = 总负债 / 总资产
    current_ratio: Pct = None  # 流动比率（以 % 表示，180 即 1.8 倍；金融类为 None）
    total_equity: Yuan = None  # 股东权益合计
    total_equity_yoy: Pct = None  # 股东权益同比
    cash_deposit_pbc: Yuan = None  # 现金及存放中央银行款项（银行）
    cash_deposit_pbc_yoy: Pct = None  # 现金及存放中央银行款项同比
    loans_advances: Yuan = None  # 发放贷款及垫款（银行）
    loans_advances_yoy: Pct = None  # 发放贷款及垫款同比
    available_for_sale_assets: Yuan = None  # 可供出售金融资产（新金融工具准则后多为 None）
    available_for_sale_assets_yoy: Pct = None  # 可供出售金融资产同比
    borrowings_from_pbc: Yuan = None  # 向中央银行借款（银行）
    borrowings_from_pbc_yoy: Pct = None  # 向中央银行借款同比
    deposits: Yuan = None  # 吸收存款（银行）
    deposits_yoy: Pct = None  # 吸收存款同比
    repo_sold: Yuan = None  # 卖出回购金融资产款（银行、保险、券商）
    repo_sold_yoy: Pct = None  # 卖出回购金融资产款同比
    settlement_reserves: Yuan = None  # 结算备付金（券商）
    settlement_reserves_yoy: Pct = None  # 结算备付金同比
    interbank_borrowings: Yuan = None  # 拆入资金（券商）
    interbank_borrowings_yoy: Pct = None  # 拆入资金同比
    customer_brokerage_deposits: Yuan = None  # 代理买卖证券款（券商）
    customer_brokerage_deposits_yoy: Pct = None  # 代理买卖证券款同比
    premiums_receivable: Yuan = None  # 应收保费（保险）
    premiums_receivable_yoy: Pct = None  # 应收保费同比
    short_term_loans: Yuan = None  # 短期借款（保险）
    short_term_loans_yoy: Pct = None  # 短期借款同比
    advance_premiums: Yuan = None  # 预收保费（保险）
    advance_premiums_yoy: Pct = None  # 预收保费同比


@dataclass(frozen=True)
class IncomeStatement:
    """利润表：一家公司一个报告期的主要科目（年初至报告期末累计）。金额单位元，同比单位 %。

    银行、券商、保险专用科目只有对应行业有值，一般公司为 None。
    """

    code: str
    name: str
    market: str | None = None  # 市场：sh / sz / bj，可连同 code 传给 stock_kline_em
    industry: str | None = None  # 所处行业
    report_date: str | None = None  # 报告期 YYYY-MM-DD
    notice_date: str | None = None  # 公告日期 YYYY-MM-DD
    net_profit: Yuan = None  # 归属于母公司股东的净利润
    net_profit_yoy: Pct = None  # 净利润同比
    deducted_net_profit: Yuan = None  # 扣除非经常性损益后的净利润
    deducted_net_profit_yoy: Pct = None  # 扣非净利润同比
    revenue: Yuan = None  # 营业总收入
    revenue_yoy: Pct = None  # 营业总收入同比
    operating_expense: Yuan = None  # 营业支出：一般公司等于营业成本，银行、保险为营业支出
    operating_expense_yoy: Pct = None  # 营业支出同比
    operating_cost: Yuan = None  # 营业成本（金融类为 None）
    selling_expense: Yuan = None  # 销售费用
    admin_expense: Yuan = None  # 管理费用（银行、券商为业务及管理费）
    finance_expense: Yuan = None  # 财务费用
    taxes_and_surcharges: Yuan = None  # 税金及附加
    total_operating_cost: Yuan = None  # 营业总支出
    total_operating_cost_yoy: Pct = None  # 营业总支出同比
    operating_profit: Yuan = None  # 营业利润
    operating_profit_yoy: Pct = None  # 营业利润同比
    total_profit: Yuan = None  # 利润总额
    income_tax: Yuan = None  # 所得税费用
    operating_income: Yuan = None  # 营业收入（只有银行、保险有，等于营业总收入）
    net_interest_income: Yuan = None  # 利息净收入
    net_interest_income_yoy: Pct = None  # 利息净收入同比（银行）
    net_fee_income: Yuan = None  # 手续费及佣金净收入
    net_fee_income_yoy: Pct = None  # 手续费及佣金净收入同比
    business_admin_expense: Yuan = None  # 业务及管理费（银行，等于 admin_expense）
    earned_premiums: Yuan = None  # 已赚保费（保险）
    earned_premiums_yoy: Pct = None  # 已赚保费同比
    investment_income: Yuan = None  # 投资收益（保险）
    surrenders: Yuan = None  # 退保金（保险）
    claims_expense: Yuan = None  # 赔付支出（保险）


@dataclass(frozen=True)
class CashFlowStatement:
    """现金流量表：一家公司一个报告期的主要科目（年初至报告期末累计）。金额单位元，比率单位 %。

    ``*_share`` 是该科目 ÷ 净现金流（现金及现金等价物净增加额）的绝对值 × 100，可以远大于 100 或为负；
    只有 ``net_cash_flow_yoy`` 是同比。银行、券商、保险专用科目只有对应行业有值。
    """

    code: str
    name: str
    market: str | None = None  # 市场：sh / sz / bj，可连同 code 传给 stock_kline_em
    industry: str | None = None  # 所处行业
    report_date: str | None = None  # 报告期 YYYY-MM-DD
    notice_date: str | None = None  # 公告日期 YYYY-MM-DD
    net_cash_flow: Yuan = None  # 现金及现金等价物净增加额
    net_cash_flow_yoy: Pct = None  # 净现金流同比增长
    operating_net: Yuan = None  # 经营活动产生的现金流量净额
    operating_net_share: Pct = None  # 经营活动现金流量净额的净现金流占比
    sales_cash: Yuan = None  # 销售商品、提供劳务收到的现金
    sales_cash_share: Pct = None  # 销售商品、提供劳务收到的现金的净现金流占比
    staff_cash_paid: Yuan = None  # 支付给职工以及为职工支付的现金
    staff_cash_paid_share: Pct = None  # 支付给职工的现金的净现金流占比
    investing_net: Yuan = None  # 投资活动产生的现金流量净额
    investing_net_share: Pct = None  # 投资活动现金流量净额的净现金流占比
    investment_income_cash: Yuan = None  # 取得投资收益收到的现金
    investment_income_cash_share: Pct = None  # 取得投资收益收到的现金的净现金流占比
    capex: Yuan = None  # 购建固定资产、无形资产和其他长期资产支付的现金
    capex_share: Pct = None  # 购建长期资产支付的现金的净现金流占比
    financing_net: Yuan = None  # 筹资活动产生的现金流量净额
    financing_net_share: Pct = None  # 筹资活动现金流量净额的净现金流占比
    customer_deposits_increase: Yuan = None  # 客户存款和同业存放款项净增加额（银行）
    customer_deposits_increase_share: Pct = None  # 客户存款净增加额的净现金流占比
    interbank_deposits_increase: Yuan = None  # 同业及其他金融机构存放款净增加额（银行）
    interbank_deposits_increase_share: Pct = None  # 同业存放款净增加额的净现金流占比
    loans_increase: Yuan = None  # 客户贷款及垫款净增加额（银行）
    loans_increase_share: Pct = None  # 客户贷款及垫款净增加额的净现金流占比
    interest_commission_cash: Yuan = None  # 收取利息、手续费及佣金的现金（券商）
    interest_commission_cash_share: Pct = None  # 收取利息、手续费及佣金的现金的净现金流占比
    investment_cash_paid: Yuan = None  # 投资支付的现金（保险、券商）
    investment_cash_paid_share: Pct = None  # 投资支付的现金的净现金流占比
    begin_cash: Yuan = None  # 期初现金及现金等价物余额（券商）
    begin_cash_share: Pct = None  # 期初现金及现金等价物余额的净现金流占比
    end_cash: Yuan = None  # 期末现金及现金等价物余额（券商）
    end_cash_share: Pct = None  # 期末现金及现金等价物余额的净现金流占比
    premiums_cash: Yuan = None  # 收到原保险合同保费取得的现金（保险）
    premiums_cash_share: Pct = None  # 收到原保险合同保费取得的现金的净现金流占比
    claims_cash_paid: Yuan = None  # 支付原保险合同赔付款项的现金（保险）
    claims_cash_paid_share: Pct = None  # 支付原保险合同赔付款项的现金的净现金流占比

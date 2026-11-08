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
    """沪深京 A 股全市场列表（可按市场 / 板块范围筛选）。"""

    sort: str = "f3"
    page: int = 1
    size: int = 20
    scope: str = "all"  # all / sh / sz / bj / kc 科创板 / cy 创业板 / new 新股 / st 风险警示


@dataclass(frozen=True)
class KlineQuery:
    """历史 K 线（日 / 周 / 月，前 / 后 / 不复权）。

    ``market="hk"`` 时价格单位为港元、成交量单位为股（不是手）。
    """

    code: str = "000001"
    market: str = "sz"  # sz 深市 / sh 沪市 / bj 北交所 / csi 中证指数 / hk 港股
    period: str = "day"  # day / week / month / 5m / 15m / 30m / 60m
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


@dataclass(frozen=True)
class BoardKlineQuery:
    """板块（行业 / 概念 / 地域）历史 K 线（push2his，日 / 周 / 月 / 分钟）。

    板块是指数，复权对其无意义（实测 ``fqt=0`` 与 ``fqt=1`` 返回完全一致），故不设 ``adjust``。
    """

    board: str = "BK0438"  # 板块代码，如 BK0438
    period: str = "day"  # day / week / month / 5m / 15m / 30m / 60m
    beg: str = "0"  # 起始日期 YYYYMMDD，0 表示不限
    end: str = "20500101"  # 结束日期 YYYYMMDD


@dataclass(frozen=True)
class BoardListQuery:
    """板块列表（行业 / 概念 / 地域，clist 游客接口）。

    ``board_type`` 为 ``industry`` 时 ``level`` 控制行业分级（1/2/3 级）；
    为 ``concept`` / ``region`` 时 ``level`` 被忽略（概念 / 地域无分级）。
    """

    board_type: str = "industry"  # industry / concept / region
    level: str = "1"  # 1 / 2 / 3 / all（仅 industry 有效，未知回退 1）
    sort: str = "f3"  # 排序字段（上游 f* 字段名）
    page: int = 1
    size: int = 20


@dataclass(frozen=True)
class IndexListQuery:
    """指数列表（clist 游客接口），按指数系列筛选。"""

    series: str = "main"  # main 沪深重要指数 / sh 上证系列 / sz 深证系列 / csi 中证系列
    sort: str = "f3"  # 排序字段（上游 f* 字段名）
    page: int = 1
    size: int = 20


@dataclass(frozen=True)
class HkStockListQuery:
    """港股列表（clist 游客接口），按板块范围筛选。"""

    scope: str = "all"  # all 主板 + 创业板 / main 主板 / gem 创业板
    sort: str = "f3"  # 排序字段（上游 f* 字段名）
    page: int = 1
    size: int = 20


@dataclass(frozen=True)
class FundListQuery:
    """场内基金列表（clist 游客接口），按基金类型筛选。"""

    fund_type: str = "etf"  # etf / lof / all（ETF + LOF）
    sort: str = "f3"  # 排序字段（上游 f* 字段名）
    page: int = 1
    size: int = 20


@dataclass(frozen=True)
class LimitPoolQuery:
    """涨跌停股池（push2ex），一次返回某个交易日的整池。

    ``date`` 为 ``YYYYMMDD``；留空取北京时间今天，上游会返回最近交易日的数据。
    上游只保留最近约 15 个交易日，更早或过去的非交易日返回空池。
    """

    pool_type: str = "limit_up"  # limit_up / prev_limit_up / strong / sub_new / broken / limit_down
    date: str | None = None


@dataclass(frozen=True)
class StockInfoQuery:
    """个股基本信息（push2 stock/get）。"""

    code: str = "000001"
    market: str = "sz"  # sz 深市 / sh 沪市 / bj 北交所


@dataclass(frozen=True)
class StockBidAskQuery:
    """个股五档盘口（push2 stock/get 默认字段集）。"""

    code: str = "000001"
    market: str = "sz"  # sz 深市 / sh 沪市 / bj 北交所


@dataclass(frozen=True)
class StockChangesQuery:
    """盘口异动（push2ex），一次返回最近一个交易日某一类异动的全部记录。

    上游只有最近一个交易日的数据，不接受日期参数。``change_type`` 共 22 种，见 stock_changes_em 文档。
    """

    change_type: str = "big_buy"  # 大笔买入；未知回退 big_buy


@dataclass(frozen=True)
class BoardChangesQuery:
    """板块异动（push2ex），一次返回最近一个交易日全部有异动的板块。上游无可选参数。"""

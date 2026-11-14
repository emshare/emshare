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


@dataclass(frozen=True)
class BillboardDetailQuery:
    """龙虎榜详情（数据中心），按上榜日期区间取全部上榜记录。

    日期为 ``YYYYMMDD``：都留空取最近一个有龙虎榜的交易日；只给 ``start_date`` 时取到今天
    （北京时间）；只给 ``end_date`` 时只取那一天。
    """

    start_date: str | None = None
    end_date: str | None = None


@dataclass(frozen=True)
class BillboardStockStatsQuery:
    """个股上榜统计（数据中心）。``period`` 统计周期：1mo / 3mo / 6mo / 1y，未知回退 1mo。"""

    period: str = "1mo"


@dataclass(frozen=True)
class BillboardInstitutionQuery:
    """机构买卖每日统计（数据中心），按上榜日期区间。日期规则同 ``BillboardDetailQuery``。"""

    start_date: str | None = None
    end_date: str | None = None


@dataclass(frozen=True)
class BillboardInstitutionStatsQuery:
    """机构席位追踪（数据中心）。``period`` 统计周期：1mo / 3mo / 6mo / 1y，未知回退 1mo。"""

    period: str = "1mo"


@dataclass(frozen=True)
class BillboardBranchActiveQuery:
    """每日活跃营业部（数据中心），按上榜日期区间。日期规则同 ``BillboardDetailQuery``。"""

    start_date: str | None = None
    end_date: str | None = None


@dataclass(frozen=True)
class BillboardBranchRankQuery:
    """营业部排行（数据中心）。``period`` 统计周期：1mo / 3mo / 6mo / 1y，未知回退 1mo。"""

    period: str = "1mo"


@dataclass(frozen=True)
class BillboardBranchStatsQuery:
    """营业部统计（数据中心）。``period`` 统计周期：1mo / 3mo / 6mo / 1y，未知回退 1mo。"""

    period: str = "1mo"


@dataclass(frozen=True)
class BillboardBranchTradesQuery:
    """营业部详情（数据中心）：一家营业部的全部上榜买卖记录。

    ``branch_code`` 是营业部代码（见活跃营业部 / 营业部排行 / 营业部统计的 ``branch_code``）。
    日期为 ``YYYYMMDD``：都留空取全部历史（活跃营业部有上万条）；只给 ``start_date`` 时取到今天
    （北京时间）；只给 ``end_date`` 时只取那一天。
    """

    branch_code: str
    start_date: str | None = None
    end_date: str | None = None


@dataclass(frozen=True)
class BillboardStockDatesQuery:
    """个股上榜日期（数据中心）：一只股票历次上榜的日期。"""

    code: str


@dataclass(frozen=True)
class BillboardStockQuery:
    """个股龙虎榜详情（数据中心）：一只股票某个上榜日的买入或卖出席位。

    ``date`` 为 ``YYYYMMDD``，留空取该股最近一个上榜日；``side``：buy 买入金额最大的前 5 名 /
    sell 卖出金额最大的前 5 名，未知回退 buy。
    """

    code: str
    date: str | None = None
    side: str = "buy"


@dataclass(frozen=True)
class BlockTradeMarketDailyQuery:
    """大宗交易市场统计（数据中心），按交易日期区间，一个交易日一行。

    日期为 ``YYYYMMDD``：都留空取全部历史（2000-08-29 起）；只给 ``start_date`` 时取到今天
    （北京时间）；只给 ``end_date`` 时只取那一天。
    """

    start_date: str | None = None
    end_date: str | None = None


@dataclass(frozen=True)
class BlockTradeDetailQuery:
    """大宗交易每日明细（数据中心），按证券类型和交易日期区间取全部成交。

    日期为 ``YYYYMMDD``：都留空取最近一个有这类证券大宗交易的交易日；只给 ``start_date`` 时取到今天
    （北京时间）；只给 ``end_date`` 时只取那一天。``security_type``：ashare A 股 / bshare B 股 /
    fund 基金 / bond 债券，未知回退 ashare。
    """

    start_date: str | None = None
    end_date: str | None = None
    security_type: str = "ashare"


@dataclass(frozen=True)
class BlockTradeStockDailyQuery:
    """大宗交易每日统计（数据中心），按交易日期区间，只有 A 股。

    日期为 ``YYYYMMDD``：都留空取最近一个有大宗交易的交易日；只给 ``start_date`` 时取到今天
    （北京时间）；只给 ``end_date`` 时只取那一天。
    """

    start_date: str | None = None
    end_date: str | None = None


@dataclass(frozen=True)
class BlockTradeStockStatsQuery:
    """大宗交易活跃 A 股统计（数据中心）。``period`` 统计周期（自然月）：1mo / 3mo / 6mo / 1y，未知回退 1mo。"""

    period: str = "1mo"


@dataclass(frozen=True)
class BlockTradeBranchActiveQuery:
    """大宗交易活跃营业部统计（数据中心）。``period`` 最近 N 个交易日：1d / 3d / 5d / 10d / 30d，未知回退 1d。"""

    period: str = "1d"


@dataclass(frozen=True)
class BlockTradeBranchRankQuery:
    """大宗交易营业部排行（数据中心）。``period`` 最近 N 个交易日：30d / 90d / 180d / 360d，未知回退 30d。"""

    period: str = "30d"


@dataclass(frozen=True)
class EarningsReportQuery:
    """业绩报告（数据中心），按报告期取。

    ``report_date`` 为 ``YYYYMMDD`` 且必须是季末（0331 / 0630 / 0930 / 1231），留空取今天（北京时间）
    之前最近的季末。``scope``：all / sh / sz / bj / kc 科创板 / cy 创业板 / st 风险警示，未知回退 all。
    """

    report_date: str | None = None
    scope: str = "all"


@dataclass(frozen=True)
class EarningsExpressQuery:
    """业绩快报（数据中心），按报告期取。

    ``report_date`` 为 ``YYYYMMDD`` 且必须是季末（0331 / 0630 / 0930 / 1231），留空取今天（北京时间）
    之前最近的季末。``scope``：all / sh / sz / bj / kc 科创板 / cy 创业板 / st 风险警示，未知回退 all。
    """

    report_date: str | None = None
    scope: str = "all"


@dataclass(frozen=True)
class EarningsForecastQuery:
    """业绩预告（数据中心），按报告期取。

    ``report_date`` 为 ``YYYYMMDD`` 且必须是季末（0331 / 0630 / 0930 / 1231），留空取今天（北京时间）
    之前最近的季末。``scope``：all / sh / sz / bj / kc 科创板 / cy 创业板 / st 风险警示，未知回退 all。
    """

    report_date: str | None = None
    scope: str = "all"


@dataclass(frozen=True)
class EarningsScheduleQuery:
    """预约披露时间（数据中心），按报告期取。

    ``report_date`` 为 ``YYYYMMDD`` 且必须是季末（0331 / 0630 / 0930 / 1231），留空取今天（北京时间）
    之前最近的季末。``scope``：all / sh / sz / bj / kc 科创板 / cy 创业板 / st 风险警示，未知回退 all。
    """

    report_date: str | None = None
    scope: str = "all"


@dataclass(frozen=True)
class BalanceSheetQuery:
    """资产负债表（数据中心），按报告期取。

    ``report_date`` 为 ``YYYYMMDD`` 且必须是季末（0331 / 0630 / 0930 / 1231），留空取今天（北京时间）
    之前最近的季末。``scope``：all / sh / sz / bj / kc 科创板 / cy 创业板 / st 风险警示，未知回退 all。
    """

    report_date: str | None = None
    scope: str = "all"


@dataclass(frozen=True)
class IncomeStatementQuery:
    """利润表（数据中心），按报告期取。

    ``report_date`` 为 ``YYYYMMDD`` 且必须是季末（0331 / 0630 / 0930 / 1231），留空取今天（北京时间）
    之前最近的季末。``scope``：all / sh / sz / bj / kc 科创板 / cy 创业板 / st 风险警示，未知回退 all。
    """

    report_date: str | None = None
    scope: str = "all"


@dataclass(frozen=True)
class CashFlowStatementQuery:
    """现金流量表（数据中心），按报告期取。

    ``report_date`` 为 ``YYYYMMDD`` 且必须是季末（0331 / 0630 / 0930 / 1231），留空取今天（北京时间）
    之前最近的季末。``scope``：all / sh / sz / bj / kc 科创板 / cy 创业板 / st 风险警示，未知回退 all。
    """

    report_date: str | None = None
    scope: str = "all"

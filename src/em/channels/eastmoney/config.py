"""东财渠道配置：域名、请求头、公共参数与字段集。"""

CLIST_PATH = "/api/qt/clist/get"
KLINE_PATH = "/api/qt/stock/kline/get"
TRENDS_PATH = "/api/qt/stock/trends2/get"
FFLOW_PATH = "/api/qt/stock/fflow/daykline/get"

# 三个上游主机：push2（板块/个股）、pushguest（游客全市场）、push2his（历史 K 线 / 分时 / 资金流）
QUOTE_HOST = "https://push2.eastmoney.com"
GUEST_HOST = "https://pushguest.eastmoney.com"
KLINE_HOST = "https://push2his.eastmoney.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://quote.eastmoney.com/center/gridlist.html",
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

UT = "fa5fd1943c7b386f172d6893dbfba10b"  # 东财公开 ut 常量

# 资金流排行周期 -> 排序字段 fid
FUND_FLOW_FIELDS = {"day": "f62", "5d": "f164", "10d": "f174"}

# 字段集：板块成分股（含当日/5日/10日资金流）与全市场
BOARD_FIELDS = "f12,f14,f2,f3,f4,f62,f164,f174,f6,f8"
MARKET_FIELDS = "f12,f14,f2,f3,f4,f6,f8"
# K 线周期 -> klt、复权 -> fqt
KLT_PERIODS = {
    "day": 101,
    "week": 102,
    "month": 103,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "60m": 60,
}
FQT_ADJUSTS = {"qfq": 1, "hfq": 2, "none": 0}
# K 线字段集：fields1 取证券元信息，fields2 逐条返回
KLINE_FIELDS1 = "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13"
KLINE_FIELDS2 = "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
# K 线一次返回全量序列（实测 8502 行）：响应体远大于 clist 的 100 行，全局 3s 读预算
# 会在首轮就判超时（实测 3 次请求 2 次失败、15.1s）。该接口是单请求、无分页，
# 放宽读预算不会放大失败成本
KLINE_READ_TIMEOUT_SEC = 8.0
# 分时字段集：fields1 取证券元信息，fields2 逐分钟返回
TRENDS_FIELDS1 = "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13,f17"
TRENDS_FIELDS2 = "f51,f52,f53,f54,f55,f56,f57,f58"
# 资金流字段集：fields1 取证券元信息，fields2 逐日返回（f64/f65 语义未确认，映射层忽略）
FFLOW_FIELDS1 = "f1,f2,f3,f7"
FFLOW_FIELDS2 = "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65"
FFLOW_UT = "b2884a393a59ad64002292a3e90d46a5"  # 资金流接口专用 ut
# 板块（行业 / 概念 / 地域）secid 前缀，统一为 90
BOARD_MARKET_ID = "90"
# 沪深京市场代码 -> 东财 secid 前缀（0 深市 / 1 沪市；北交所亦为 0）
MARKET_IDS = {"sz": "0", "sh": "1", "bj": "0"}
# 板块列表字段集（行业 / 概念 / 地域通用，对齐 akshare stock_board_industry_name_em）
# f12 代码 / f14 名称 / f2 指数点位 / f3 涨跌幅 / f4 涨跌额 / f8 换手率 / f20 成交额
# f104 上涨家数 / f105 下跌家数 / f128 领涨股名称 / f140 领涨股代码 / f136 领涨股涨跌幅
# f207 领跌股名称 / f208 领跌股代码 / f222 领跌股涨跌幅
BOARD_LIST_FIELDS = "f12,f14,f2,f3,f4,f8,f20,f104,f105,f128,f140,f136,f207,f208,f222"
# 行业板块分级 level -> fs 中的 s 值（s:2 一级 / s:4 二级 / s:8 三级）
BOARD_INDUSTRY_LEVEL_S = {"1": "2", "2": "4", "3": "8"}
# 行业板块全级别总列表（t:2，含一/二/三级共 496 个）
BOARD_INDUSTRY_ALL_FS = "m:90+t:2+f:!50"
# 板块类型 -> fs 模板（industry 用 s 分级或 t:2 全量，concept / region 用 t 固定值）
BOARD_CONCEPT_FS = "m:90+t:3+f:!50"
BOARD_REGION_FS = "m:90+t:1+f:!50"
# 指数列表字段集（对齐 akshare stock_zh_index_spot_em 输出列）
# f12 代码 / f13 市场前缀 / f14 名称 / f2 最新点位 / f3 涨跌幅 / f4 涨跌额 / f5 成交量
# f6 成交额 / f7 振幅 / f10 量比 / f15 最高 / f16 最低 / f17 今开 / f18 昨收
INDEX_LIST_FIELDS = "f12,f13,f14,f2,f3,f4,f5,f6,f7,f10,f15,f16,f17,f18"
# 指数 f13（secid 市场前缀）-> 领域市场；北证指数也挂在 0 前缀下，按代码段另行区分
INDEX_MARKETS = {0: "sz", 1: "sh", 2: "csi"}
BJ_INDEX_CODE_PREFIX = "899"
# 港股列表字段集（对齐 akshare stock_hk_spot_em 输出列）
# f1 价格小数位 / f12 代码 / f14 名称 / f2 最新价 / f3 涨跌幅 / f4 涨跌额 / f5 成交量（股）
# f6 成交额 / f15 最高 / f16 最低 / f17 今开 / f18 昨收
HK_STOCK_LIST_FIELDS = "f1,f12,f14,f2,f3,f4,f5,f6,f15,f16,f17,f18"
# fltt=1 时价格放大 10**f1 倍；A 股与指数 f1=2，港股 f1=3。缺 f1 时按 A 股口径
DEFAULT_PRICE_DECIMALS = 2
# 场内基金列表字段集（对齐 akshare fund_etf_spot_em / fund_lof_spot_em 的共有列 + IOPV / 折价率）
# f1 价格小数位 / f12 代码 / f13 市场前缀 / f14 名称 / f2 最新价 / f3 涨跌幅 / f4 涨跌额
# f5 成交量（手） / f6 成交额 / f8 换手率 / f15 最高 / f16 最低 / f17 开盘 / f18 昨收
# f20 总市值 / f21 流通市值 / f402 折价率 / f441 IOPV（原值，fltt=1 时也不放大）
FUND_LIST_FIELDS = "f1,f12,f13,f14,f2,f3,f4,f5,f6,f8,f15,f16,f17,f18,f20,f21,f402,f441"
# 基金 f13（secid 市场前缀）-> 领域市场
FUND_MARKETS = {0: "sz", 1: "sh"}

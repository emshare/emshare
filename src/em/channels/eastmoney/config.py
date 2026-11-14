"""东财渠道配置：域名、请求头、公共参数与字段集。"""

CLIST_PATH = "/api/qt/clist/get"
KLINE_PATH = "/api/qt/stock/kline/get"
TRENDS_PATH = "/api/qt/stock/trends2/get"
FFLOW_PATH = "/api/qt/stock/fflow/daykline/get"

# 三个上游主机：push2（板块/个股）、pushguest（游客全市场）、push2his（历史 K 线 / 分时 / 资金流）
QUOTE_HOST = "https://push2.eastmoney.com"
GUEST_HOST = "https://pushguest.eastmoney.com"
KLINE_HOST = "https://push2his.eastmoney.com"
PUSH2EX_HOST = "https://push2ex.eastmoney.com"  # 涨跌停股池 / 盘口异动 / 板块异动

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
# K 线额外支持的市场：csi 中证指数（2）/ hk 港股（116）。只用于 K 线，
# 分时与资金流仍用 MARKET_IDS（上游虽也接受，但未纳入本次范围）
KLINE_MARKET_IDS = {**MARKET_IDS, "csi": "2", "hk": "116"}
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
# push2ex 公开 ut 常量（涨跌停股池 / 盘口异动 / 板块异动共用）
PUSH2EX_UT = "7eea3edcaed734bea9cbfc24409ed989"
# 股池一次取整池：实测单日最多一两百只，上游 pagesize 取 10000 即不分页（对齐 akshare）
LIMIT_POOL_PAGE_SIZE = 10000
# push2ex 价格（p / ztp）固定放大 1000 倍，与 clist 的 f1 无关
PUSH2EX_PRICE_FACTOR = 1000.0
# 北交所新股首日不设涨停价，上游 ztp 用此哨兵值，映射为 None
NO_LIMIT_PRICE_SENTINEL = 1000000000
# push2ex 个股 m（secid 市场前缀）-> 领域市场（股池 / 盘口异动 / 板块异动最频繁个股）；
# 北交所也挂在 0 前缀下，按代码段区分
PUSH2EX_MARKETS = {0: "sz", 1: "sh"}
BJ_STOCK_CODE_PREFIXES = ("4", "8", "92")
# 强势股池入选理由（上游 cc，对齐 akshare explained_map）
STRONG_POOL_REASONS = {1: "60日新高", 2: "近期多次涨停", 3: "60日新高且近期多次涨停"}
# 单只证券快照（个股信息 / 五档盘口）
STOCK_GET_PATH = "/api/qt/stock/get"
# 个股信息字段集（对齐 akshare stock_individual_info_em 的 9 项）：
# f57 代码 / f58 简称 / f59 价格小数位 / f43 最新价 / f84 总股本 / f85 流通股
# f116 总市值 / f117 流通市值 / f127 行业 / f189 上市日期
STOCK_INFO_FIELDS = "f57,f58,f59,f43,f84,f85,f116,f117,f127,f189"
# stock/get 查无此券时的 rc（实测：不存在的代码 100，含非数字的代码 102），data 为 null
STOCK_NOT_FOUND_RCS = (100, 102)
# 盘口异动 / 板块异动（push2ex），上游只有最近一个交易日的数据，不接受日期参数
STOCK_CHANGES_PATH = "/getAllStockChanges"
BOARD_CHANGES_PATH = "/getAllBKChanges"
# 一次取全量：实测 11-06 单类型最多 2576 条（快速反弹）、板块 1052 个；上游不限 pagesize
# （50000 也一次返回全部），取 50000 留足余量。akshare 用 5000，超过时只拿到前 5000 条
CHANGES_PAGE_SIZE = 50000
# 响应体与全量 K 线同量级（板块异动 435KB、快速反弹 243KB，K 线 650KB），读预算同 K 线
CHANGES_READ_TIMEOUT_SEC = KLINE_READ_TIMEOUT_SEC
# 盘口异动类型：英文 change_type -> 上游 type，顺序同东财页面与 akshare（前 11 个偏多，后 11 个偏空）。
# 上游另有 8217–8222 六种类型，东财页面与 akshare 都没有名字，本工程不纳入
CHANGE_TYPE_CODES = {
    "rocket_launch": 8201,  # 火箭发射
    "quick_rebound": 8202,  # 快速反弹
    "big_buy": 8193,  # 大笔买入
    "limit_up_sealed": 4,  # 封涨停板
    "limit_down_opened": 32,  # 打开跌停板
    "big_bid": 64,  # 有大买盘
    "auction_up": 8207,  # 竞价上涨
    "open_above_ma5": 8209,  # 高开5日线
    "gap_up": 8211,  # 向上缺口
    "new_high_60d": 8213,  # 60日新高
    "big_rise_60d": 8215,  # 60日大幅上涨
    "accelerated_drop": 8204,  # 加速下跌
    "high_dive": 8203,  # 高台跳水
    "big_sell": 8194,  # 大笔卖出
    "limit_down_sealed": 8,  # 封跌停板
    "limit_up_opened": 16,  # 打开涨停板
    "big_ask": 128,  # 有大卖盘
    "auction_down": 8208,  # 竞价下跌
    "open_below_ma5": 8210,  # 低开5日线
    "gap_down": 8212,  # 向下缺口
    "new_low_60d": 8214,  # 60日新低
    "big_drop_60d": 8216,  # 60日大幅下跌
}
# 数据中心（datacenter-web）报表接口：龙虎榜 / 大宗交易 / 业绩与财报等，按 reportName 区分报表
DATACENTER_HOST = "https://datacenter-web.eastmoney.com"
DATACENTER_PATH = "/api/data/v1/get"
# 单页上限：pageSize 传 5000 / 50000 也只返回 500 条（实测），全量要翻页。上限因报表而异：龙虎榜详情、
# 大宗交易市场统计是 500；大宗交易每日明细、每日统计实测 2026-11-13 传 5000 能一页取回 5000 条。
# 目前所有报表统一按 500 翻页
DATACENTER_PAGE_SIZE = 500
# 返回码（实测）：0 成功；9201 查无数据（过滤后为空、页号越界）。查询写错的两种：9501（报表 / 列名 /
# 排序列不存在、日期格式不对）、200（参数类型不对，如页码不是整数；这种 code 是字符串 "200"）——
# 换 IP 也一样，不重试。9701 服务器繁忙与其余未知码按渠道异常换 IP 重试
DATACENTER_OK = 0
DATACENTER_EMPTY = 9201
DATACENTER_QUERY_ERRORS = (9501, 200)
# 单页 500 行，响应体实测几十到几百 KB（龙虎榜详情 22 列 347KB、全部列 572KB），与全量 K 线同量级，读预算同 K 线
DATACENTER_READ_TIMEOUT_SEC = KLINE_READ_TIMEOUT_SEC
# 市场范围 -> TRADE_MARKET_CODE 过滤（取值同 stock_list_em 的 scope；实测 2026-09-30 资产负债表
# all 5578 = sh 2318 + sz 2905 + bj 355，kc 616 / cy 1372 / st 181）
DATACENTER_SCOPE_FILTERS = {
    "all": "",
    "sh": '(TRADE_MARKET_CODE in ("069001001001","069001001003","069001001006"))',
    "sz": '(TRADE_MARKET_CODE in ("069001002001","069001002002","069001002003","069001002005"))',
    "bj": '(TRADE_MARKET_CODE="069001017")',
    "kc": '(TRADE_MARKET_CODE="069001001006")',
    "cy": '(TRADE_MARKET_CODE="069001002002")',
    "st": '(TRADE_MARKET_CODE in ("069001001003","069001002005"))',
}
# 业绩与财报类报表只取 A 股与存托凭证（上游同表里还有 B 股、新三板：实测 2026 三季报业绩报告
# 5797 行里 B 股 77、三板股 140）
DATACENTER_A_SHARE_FILTER = '(SECURITY_TYPE_CODE in ("058001001","058001008"))'
# 统计周期 -> 上游取值（用户定 1mo / 3mo / 6mo / 1y，避免与 K 线分钟周期 5m 混淆）
# 龙虎榜个股统计 / 机构席位追踪 / 营业部排行与统计（STATISTICS_CYCLE / STATISTICSCYCLE）
BILLBOARD_PERIODS = {"1mo": "01", "3mo": "02", "6mo": "03", "1y": "04"}
# 大宗交易（block_trade_*）的枚举参数 -> 上游取值
# 证券类型 -> SECURITY_TYPE_WEB（实测 2026-11-13 明细总条数：A 股 337441 / B 股 1661 / 基金 12589 /
# 债券 333728；另有取值 5 的 2 条 2004 年回购记录，不开放）
BLOCK_TRADE_SECURITY_TYPES = {"ashare": "1", "bshare": "2", "fund": "3", "bond": "4"}
# 活跃 A 股统计的周期 -> DATE_TYPE_CODE：自然月，从 N 个月前同一天的次日算起（实测与明细逐只一致）
BLOCK_TRADE_STOCK_PERIODS = {"1mo": "1", "3mo": "3", "6mo": "6", "1y": "12"}
# 活跃营业部统计的周期 -> N_DATE：最近 N 个交易日；0 是上游的“最新”，即最近一个交易日
# （akshare 的“当前交易日”传 -1，实测查不到任何行）
BLOCK_TRADE_ACTIVE_PERIODS = {"1d": "0", "3d": "-3", "5d": "-5", "10d": "-10", "30d": "-30"}
# 营业部排行的周期 -> N_DATE：最近 N 个交易日。东财页面与 akshare 叫近一月 / 三月 / 六月 / 一年，
# 实测是 30 / 90 / 180 / 360 个交易日（360 个交易日约一年半），所以取值按“日”命名
BLOCK_TRADE_RANK_PERIODS = {"30d": "-30", "90d": "-90", "180d": "-180", "360d": "-360"}

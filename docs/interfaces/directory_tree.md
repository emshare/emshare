# 工程目录结构

`em` 包采用分层 + 领域模型架构，依赖方向 `domain ← core ← channels ← application`，由 `tests/guards/test_layering.py` 守卫。本页给出整个工程的目录树；渠道内代码与文档的逐目录对照见 [eastmoney/directory_tree.md](./eastmoney/directory_tree.md)。

```
em/                                          # 东方财富行情抓取
├── src/em/                                  # 源码包
│   ├── domain/                              # 领域模型（最内层，零渠道依赖）
│   │   ├── models.py                        # Quote/Kline/Trend/FundFlow/IndexQuote/HkQuote/FundQuote/LimitPoolStock/StockInfo/StockBidAsk/StockChange/BoardChange 及各自 Series/Page，BillboardEntry 及其余龙虎榜模型（BillboardStockStats/BillboardInstitutionTrade/BillboardInstitutionStats/BillboardBranchActive/BillboardBranchRank/BillboardBranchStats/BillboardBranchTrade/BillboardStockDate/BillboardSeat）、大宗交易模型（BlockTradeMarketDaily/BlockTrade/BlockTradeStockDaily/BlockTradeStockStats/BlockTradeBranchActive/BlockTradeBranchRank）、业绩与财报模型（EarningsReport/EarningsExpress/EarningsForecast/EarningsSchedule/BalanceSheet/IncomeStatement/CashFlowStatement），报表结果 ReportPage
│   │   ├── queries.py                       # BoardQuery/MarketQuery/KlineQuery/TrendQuery/FundFlowQuery/BoardKlineQuery/IndexListQuery/HkStockListQuery/FundListQuery/LimitPoolQuery/StockInfoQuery/StockBidAskQuery/StockChangesQuery/BoardChangesQuery/BillboardDetailQuery 及其余 9 个 Billboard*Query、6 个 BlockTrade*Query、7 个业绩与财报 Query 等
│   │   ├── units.py                         # 单位别名与换算（元 / % / 手 / 点 / 港元 / 股）
│   │   └── __init__.py
│   ├── core/                                # 基座：配置 / 弹性 / 代理 / 传输
│   │   ├── errors.py                        # 异常分层 + retryable 归类
│   │   ├── settings.py                      # 环境变量配置（Settings.from_env）
│   │   ├── resilience.py                    # RetryPolicy 退避重试
│   │   ├── proxy.py                         # ProxyPool + ProxyRouter（预筛 / 连败熔断 / TTL 续期 / 按 host 路由）
│   │   ├── transport.py                     # HttpClient（重试 + 代理 + 异常归类）
│   │   ├── env.py                           # .env 加载：import em 时自动读取（只取 EM_ 变量；含 & 不被 bash 截断）
│   │   ├── defaults.py                      # 默认值常量
│   │   └── __init__.py
│   ├── channels/eastmoney/                  # 东财渠道适配
│   │   ├── ashare_boards/                   # 沪深京板块
│   │   │   ├── board_constituent/           # 板块成分股（board_constituent_em.py）
│   │   │   ├── board_fund_flow/             # 板块历史资金流（board_fund_flow_em.py）
│   │   │   ├── board_kline/                 # 板块历史 K 线（board_kline_em.py）
│   │   │   ├── board_industry_list/         # 板块列表（board_industry_list_em.py）
│   │   │   └── board_changes/               # 板块异动（board_changes_em.py，push2ex）
│   │   ├── ashare_stocks/                   # 沪深京个股
│   │   │   ├── stock_list/                  # 全市场列表（stock_list_em.py）
│   │   │   ├── stock_kline/                 # 历史 K 线（stock_kline_em.py）
│   │   │   ├── stock_trends/                # 分时行情（stock_trends_em.py）
│   │   │   ├── stock_fund_flow/             # 个股历史资金流（stock_fund_flow_em.py）
│   │   │   ├── stock_limit_pool/            # 涨跌停股池（stock_limit_pool_em.py，push2ex）
│   │   │   ├── stock_info/                  # 个股基本信息（stock_info_em.py，stock/get）
│   │   │   ├── stock_bid_ask/               # 个股五档盘口（stock_bid_ask_em.py，stock/get）
│   │   │   └── stock_changes/               # 盘口异动（stock_changes_em.py，push2ex）
│   │   ├── ashare_billboard/                # 龙虎榜（数据中心）
│   │   │   ├── billboard_detail/            # 龙虎榜详情（billboard_detail_em.py）
│   │   │   ├── billboard_stock_stats/       # 个股上榜统计（billboard_stock_stats_em.py）
│   │   │   ├── billboard_institution/       # 机构买卖每日统计（billboard_institution_em.py）
│   │   │   ├── billboard_institution_stats/ # 机构席位追踪（billboard_institution_stats_em.py）
│   │   │   ├── billboard_branch_active/     # 每日活跃营业部（billboard_branch_active_em.py）
│   │   │   ├── billboard_branch_rank/       # 营业部排行（billboard_branch_rank_em.py）
│   │   │   ├── billboard_branch_stats/      # 营业部统计（billboard_branch_stats_em.py）
│   │   │   ├── billboard_branch_trades/     # 营业部详情（billboard_branch_trades_em.py）
│   │   │   ├── billboard_stock_dates/       # 个股上榜日期（billboard_stock_dates_em.py）
│   │   │   └── billboard_stock/             # 个股龙虎榜详情（billboard_stock_em.py）
│   │   ├── ashare_block_trade/              # 大宗交易（数据中心）
│   │   │   ├── block_trade_market_daily/    # 市场统计（block_trade_market_daily_em.py）
│   │   │   ├── block_trade_detail/          # 每日明细（block_trade_detail_em.py）
│   │   │   ├── block_trade_stock_daily/     # 每日统计（block_trade_stock_daily_em.py）
│   │   │   ├── block_trade_stock_stats/     # 活跃 A 股统计（block_trade_stock_stats_em.py）
│   │   │   ├── block_trade_branch_active/   # 活跃营业部统计（block_trade_branch_active_em.py）
│   │   │   └── block_trade_branch_rank/     # 营业部排行（block_trade_branch_rank_em.py）
│   │   ├── ashare_earnings/                 # 业绩（数据中心）
│   │   │   ├── earnings_report/             # 业绩报告（earnings_report_em.py）
│   │   │   ├── earnings_express/            # 业绩快报（earnings_express_em.py）
│   │   │   ├── earnings_forecast/           # 业绩预告（earnings_forecast_em.py）
│   │   │   └── earnings_schedule/           # 预约披露时间（earnings_schedule_em.py）
│   │   ├── ashare_financial_statements/     # 三大财务报表（数据中心）
│   │   │   ├── balance_sheet/               # 资产负债表（balance_sheet_em.py）
│   │   │   ├── income_statement/            # 利润表（income_statement_em.py）
│   │   │   └── cash_flow_statement/         # 现金流量表（cash_flow_statement_em.py）
│   │   ├── ashare_indices/                  # 沪深京指数
│   │   │   └── index_list/                  # 指数列表（index_list_em.py）
│   │   ├── hk_market/                       # 港股市场
│   │   │   └── hk_stock_list/               # 港股列表（hk_stock_list_em.py）
│   │   ├── us_market/.gitkeep               # 美股市场（占位）
│   │   ├── fund_market/                     # 基金市场
│   │   │   └── fund_list/                   # 场内基金列表（fund_list_em.py）
│   │   ├── bond_market/.gitkeep             # 债券市场（占位）
│   │   ├── global_indices/.gitkeep          # 全球指数（占位）
│   │   ├── forex_market/.gitkeep            # 外汇市场（占位）
│   │   ├── gold_market/.gitkeep             # 黄金市场（占位）
│   │   ├── option_market/.gitkeep           # 期权市场（占位）
│   │   ├── futures_market/.gitkeep          # 期货市场（占位）
│   │   ├── special_quotes/.gitkeep          # 特色行情（占位）
│   │   ├── stock_connect/.gitkeep           # 沪深港通（占位）
│   │   ├── config.py                        # 域名 / 请求头 / 字段集 / 周期与复权映射
│   │   ├── request.py                       # ClistRequest / KlineRequest / TrendsRequest / FundFlowRequest / LimitPoolRequest / StockGetRequest / StockChangesRequest / BoardChangesRequest / DatacenterRequest
│   │   ├── datacenter.py                    # 数据中心报表公共部分：列映射 / 单位换算 / 过滤条件 / 单页解析
│   │   ├── mapping.py                       # JSONP 解析 + f* -> 领域模型
│   │   ├── source.py                        # 取数来源
│   │   └── __init__.py
│   ├── application/                         # 组合根
│   │   ├── registry.py                      # 唯一的渠道入口登记
│   │   ├── market_data.py                   # board_constituent_em/industry_list/board_kline/market/index_list/hk_stock_list/fund_list/limit_pool/stock_info/bid_ask/stock_changes/board_changes/billboard_*（10 个龙虎榜接口）/block_trade_*（6 个大宗交易接口）/earnings_*（4 个业绩接口）/三大报表/kline/trends/fund_flow + _df 版
│   │   ├── reports.py                       # 数据中心报表翻页（并发取页、条数校验、取最近一天）
│   │   ├── dataframe.py                     # 领域模型 -> DataFrame（中文列名）
│   │   ├── catalog.py                       # 接口检索：search/interface_info/list_categories
│   │   ├── hints.py                         # 出口被封且代理用不上时的配置指引（库异常与命令行共用）
│   │   └── __init__.py
│   ├── cli.py                               # 命令行入口
│   ├── __main__.py                          # python -m em
│   ├── py.typed                             # PEP 561 类型标记
│   ├── env.example                          # 随包分发的 .env 模板（emshare --init-env 写出）
│   └── __init__.py                          # 公共面：*_em / df_*_em / search / interface_info
├── tests/                                   # 测试
│   ├── unit/                                # 单元测试（不触网，固定报文）
│   │   ├── test_kline.py                    # K 线映射 / 周期规范化 / 分钟级 klt
│   │   ├── test_kline_dataframe.py          # K 线 DataFrame 列名
│   │   ├── test_trends.py / test_trend_dataframe.py
│   │   ├── test_fund_flow.py / test_fund_flow_dataframe.py
│   │   ├── test_board_fund_flow.py / test_board_fund_flow_dataframe.py
│   │   ├── test_board_kline.py / test_board_kline_dataframe.py
│   │   ├── test_index_list.py / test_index_list_dataframe.py
│   │   ├── test_hk_stock_list.py / test_hk_stock_list_dataframe.py
│   │   ├── test_fund_list.py / test_fund_list_dataframe.py
│   │   ├── test_stock_limit_pool.py / test_stock_limit_pool_dataframe.py
│   │   ├── test_stock_info_bid_ask.py / test_stock_info_bid_ask_dataframe.py
│   │   ├── test_stock_changes.py / test_board_changes.py / test_changes_dataframe.py
│   │   ├── test_datacenter.py               # 数据中心底座：协议校验 / 单页解析 / 查询条件 / 翻页器
│   │   ├── test_billboard_detail.py
│   │   ├── test_billboard_reports.py        # 龙虎榜其余 9 张报表：映射 / 请求 / 端到端取数 / DataFrame
│   │   ├── test_block_trade.py              # 大宗交易 6 张报表：映射 / 请求 / 端到端取数 / DataFrame
│   │   ├── test_financials.py               # 业绩与财报 7 张报表：映射 / 请求 / 端到端取数 / DataFrame
│   │   ├── test_board_industry_list.py / test_board_industry_list_dataframe.py
│   │   ├── test_dataframe.py                # QuotePage DataFrame
│   │   ├── test_mapping.py                  # 报文映射
│   │   ├── test_catalog.py                  # 接口检索
│   │   ├── test_cli.py                      # CLI 渲染 + IP 封禁提示 + --init-env
│   │   ├── test_hints.py                    # 出口失败提示：何时给、内容、库异常是否携带
│   │   ├── test_proxy_pool.py / test_proxy_router.py
│   │   ├── test_transport.py / test_resilience.py
│   │   ├── test_settings.py / test_env.py
│   │   └── __init__.py
│   ├── guards/                              # 架构 / 文档守卫
│   │   ├── test_layering.py                 # 分层依赖方向守卫
│   │   ├── test_docs_sync.py                # 文档与源码同步守卫
│   │   ├── test_env_example.py              # .env 模板（src/em/env.example）完整性守卫
│   │   └── __init__.py
│   ├── fixtures/eastmoney/                  # 固定报文（kline/trends/fund_flow/board_fund_flow/board_kline/clist_board/clist_board_industry/clist_index/clist_hk_stock/clist_fund/push2ex_limit_pool/stock_get/push2ex_changes/datacenter_billboard/datacenter_billboard_reports/datacenter_block_trade/datacenter_financials）
│   ├── conftest.py
│   └── __init__.py
├── docs/interfaces/eastmoney/               # 接口文档（按渠道分组，详见该目录 directory_tree.md）
├── em_fetch.py                              # 抓取入口脚本（CLI 薄封装）
├── pyproject.toml                           # 项目配置（ruff / pytest / mypy）
├── uv.lock                                  # 依赖锁
├── README.md                                # 用法与目录说明
└── .env                                     # 环境变量（不入库，含代理 API 凭证；模板在 src/em/env.example）
```

> - 除 `ashare_boards/`、`ashare_stocks/`、`ashare_billboard/`、`ashare_block_trade/`、`ashare_earnings/`、`ashare_financial_statements/`、`ashare_indices/`、`hk_market/`、`fund_market/` 外，其余市场目录暂为空占位，待对应功能实现后填充。
> - `.env`、`uv.lock`、`123.txt` 不纳入接口文档视野，仅在此标注存在。
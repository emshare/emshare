# 工程目录结构

`em` 包采用分层 + 领域模型架构，依赖方向 `domain ← core ← channels ← application`，由 `tests/guards/test_layering.py` 守卫。本页给出整个工程的目录树；渠道内代码与文档的逐目录对照见 [eastmoney/directory_tree.md](./eastmoney/directory_tree.md)。

```
em/                                          # 东方财富行情抓取
├── src/em/                                  # 源码包
│   ├── domain/                              # 领域模型（最内层，零渠道依赖）
│   │   ├── models.py                        # Quote/Kline/Trend/FundFlow/IndexQuote 及各自 Series/Page
│   │   ├── queries.py                       # BoardQuery/MarketQuery/KlineQuery/TrendQuery/FundFlowQuery/BoardKlineQuery/IndexListQuery 等
│   │   ├── units.py                         # 单位别名与换算（元 / % / 手 / 点）
│   │   └── __init__.py
│   ├── core/                                # 基座：配置 / 弹性 / 代理 / 传输
│   │   ├── errors.py                        # 异常分层 + retryable 归类
│   │   ├── settings.py                      # 环境变量配置（Settings.from_env）
│   │   ├── resilience.py                    # RetryPolicy 退避重试
│   │   ├── proxy.py                         # ProxyPool + ProxyRouter（预筛 / 连败熔断 / TTL 续期 / 按 host 路由）
│   │   ├── transport.py                     # HttpClient（重试 + 代理 + 异常归类）
│   │   ├── env.py                           # .env 安全加载（含 & 不被 bash 截断）
│   │   ├── defaults.py                      # 默认值常量
│   │   └── __init__.py
│   ├── channels/eastmoney/                  # 东财渠道适配
│   │   ├── ashare_boards/                   # 沪深京板块
│   │   │   ├── board_constituent/           # 板块成分股（board_constituent_em.py）
│   │   │   ├── board_fund_flow/             # 板块历史资金流（board_fund_flow_em.py）
│   │   │   ├── board_kline/                 # 板块历史 K 线（board_kline_em.py）
│   │   │   └── board_industry_list/         # 板块列表（board_industry_list_em.py）
│   │   ├── ashare_stocks/                   # 沪深京个股
│   │   │   ├── stock_list/                  # 全市场列表（stock_list_em.py）
│   │   │   ├── stock_kline/                 # 历史 K 线（stock_kline_em.py）
│   │   │   ├── stock_trends/                # 分时行情（stock_trends_em.py）
│   │   │   └── stock_fund_flow/             # 个股历史资金流（stock_fund_flow_em.py）
│   │   ├── ashare_indices/                  # 沪深京指数
│   │   │   └── index_list/                  # 指数列表（index_list_em.py）
│   │   ├── hk_market/.gitkeep               # 港股市场（占位）
│   │   ├── us_market/.gitkeep               # 美股市场（占位）
│   │   ├── fund_market/.gitkeep             # 基金市场（占位）
│   │   ├── bond_market/.gitkeep             # 债券市场（占位）
│   │   ├── global_indices/.gitkeep          # 全球指数（占位）
│   │   ├── forex_market/.gitkeep            # 外汇市场（占位）
│   │   ├── gold_market/.gitkeep             # 黄金市场（占位）
│   │   ├── option_market/.gitkeep           # 期权市场（占位）
│   │   ├── futures_market/.gitkeep          # 期货市场（占位）
│   │   ├── special_quotes/.gitkeep          # 特色行情（占位）
│   │   ├── stock_connect/.gitkeep           # 沪深港通（占位）
│   │   ├── config.py                        # 域名 / 请求头 / 字段集 / 周期与复权映射
│   │   ├── request.py                       # ClistRequest / KlineRequest / TrendsRequest / FundFlowRequest
│   │   ├── mapping.py                       # JSONP 解析 + f* -> 领域模型
│   │   ├── source.py                        # 取数来源
│   │   └── __init__.py
│   ├── application/                         # 组合根
│   │   ├── registry.py                      # 唯一的渠道入口登记
│   │   ├── market_data.py                   # board_constituent_em/industry_list/board_kline/market/index_list/kline/trends/fund_flow + _df 版
│   │   ├── dataframe.py                     # 领域模型 -> DataFrame（中文列名）
│   │   ├── catalog.py                       # 接口检索：search/interface_info/list_categories
│   │   └── __init__.py
│   ├── cli.py                               # 命令行入口
│   ├── __main__.py                          # python -m em
│   ├── py.typed                             # PEP 561 类型标记
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
│   │   ├── test_board_industry_list.py / test_board_industry_list_dataframe.py
│   │   ├── test_dataframe.py                # QuotePage DataFrame
│   │   ├── test_mapping.py                  # 报文映射
│   │   ├── test_catalog.py                  # 接口检索
│   │   ├── test_cli.py                      # CLI 渲染 + IP 封禁提示
│   │   ├── test_proxy_pool.py / test_proxy_router.py
│   │   ├── test_transport.py / test_resilience.py
│   │   ├── test_settings.py / test_env.py
│   │   └── __init__.py
│   ├── guards/                              # 架构 / 文档守卫
│   │   ├── test_layering.py                 # 分层依赖方向守卫
│   │   ├── test_docs_sync.py                # 文档与源码同步守卫
│   │   ├── test_env_example.py              # .env.example 完整性守卫
│   │   └── __init__.py
│   ├── fixtures/eastmoney/                  # 固定报文（kline/trends/fund_flow/board_fund_flow/board_kline/clist_board/clist_board_industry/clist_index）
│   ├── conftest.py
│   └── __init__.py
├── docs/interfaces/eastmoney/               # 接口文档（按渠道分组，详见该目录 directory_tree.md）
├── em_fetch.py                              # 抓取入口脚本（CLI 薄封装）
├── pyproject.toml                           # 项目配置（ruff / pytest / mypy）
├── uv.lock                                  # 依赖锁
├── README.md                                # 用法与目录说明
├── .env.example                             # 环境变量示例（入库）
└── .env                                     # 环境变量（不入库，含代理 API 凭证）
```

> - 除 `ashare_boards/`、`ashare_stocks/`、`ashare_indices/` 外，其余市场目录暂为空占位，待对应功能实现后填充。
> - `.env`、`uv.lock`、`123.txt` 不纳入接口文档视野，仅在此标注存在。
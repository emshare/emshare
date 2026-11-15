# eastmoney 渠道接口

本页描述 `em` 包对外公共面的三十九个取数接口：板块成分股资金流、板块列表、沪深京 A 股全市场列表、指数列表、港股列表、场内基金列表、历史 K 线、分时行情、个股历史资金流、板块（行业 / 概念 / 地域）历史资金流、板块历史 K 线、涨跌停股池、个股基本信息、五档盘口、盘口异动、板块异动、龙虎榜详情，以及龙虎榜的另外 9 张报表（个股上榜统计、机构买卖每日统计、机构席位追踪、每日活跃营业部、营业部排行、营业部统计、营业部详情、个股上榜日期、个股龙虎榜详情），和大宗交易的 6 张报表（市场统计、每日明细、每日统计、活跃 A 股统计、活跃营业部统计、营业部排行），以及业绩与财报的 7 张报表（业绩报告、业绩快报、业绩预告、预约披露时间、资产负债表、利润表、现金流量表）。列表类六者走东方财富 `clist` 接口，历史类五者走 `kline` / `trends2` / `fflow` 接口（个股与板块 K 线共用 `kline/get`，个股与板块资金流共用 `fflow/daykline`），涨跌停股池、盘口异动与板块异动走 `push2ex` 主机，个股信息与五档盘口走 `stock/get`，龙虎榜、大宗交易、业绩与财报等报表走数据中心 `datacenter-web`（自动翻页），均经动态代理自动换 IP 重试，返回领域模型（`QuotePage` / `BoardListPage` / `IndexListPage` / `HkStockListPage` / `FundListPage` / `LimitPoolPage` / `StockInfo` / `StockBidAsk` / `StockChangesPage` / `BoardChangesPage` / `ReportPage` / `KlineSeries` / `TrendSeries` / `FundFlowSeries` / `BoardFundFlowSeries`）；另提供 `df_*_em` 便捷函数直接返回 pandas DataFrame（akshare 风格中文列名）。

公共面统一从 `em` 顶层导出：

```python
from em import (
    board_constituent_em,
    stock_list_em,
    stock_kline_em,
    stock_trends_em,
    stock_fund_flow_em,
    board_fund_flow_em,
    board_industry_list_em,
    board_kline_em,
    index_list_em,
    hk_stock_list_em,
    fund_list_em,
    stock_limit_pool_em,
    stock_info_em,
    stock_bid_ask_em,
    stock_changes_em,
    board_changes_em,
    billboard_detail_em,
    billboard_stock_stats_em,
    billboard_institution_em,
    billboard_institution_stats_em,
    billboard_branch_active_em,
    billboard_branch_rank_em,
    billboard_branch_stats_em,
    billboard_branch_trades_em,
    billboard_stock_dates_em,
    billboard_stock_em,
    block_trade_market_daily_em,
    block_trade_detail_em,
    block_trade_stock_daily_em,
    block_trade_stock_stats_em,
    block_trade_branch_active_em,
    block_trade_branch_rank_em,
    earnings_report_em,
    earnings_express_em,
    earnings_forecast_em,
    earnings_schedule_em,
    balance_sheet_em,
    income_statement_em,
    cash_flow_statement_em,
    df_board_constituent_em,
    df_stock_list_em,
    df_stock_kline_em,
    df_stock_trends_em,
    df_stock_fund_flow_em,
    df_board_fund_flow_em,
    df_board_industry_list_em,
    df_board_kline_em,
    df_index_list_em,
    df_hk_stock_list_em,
    df_fund_list_em,
    df_stock_limit_pool_em,
    df_stock_info_em,
    df_stock_bid_ask_em,
    df_stock_changes_em,
    df_board_changes_em,
    df_billboard_detail_em,
    df_billboard_stock_stats_em,
    df_billboard_institution_em,
    df_billboard_institution_stats_em,
    df_billboard_branch_active_em,
    df_billboard_branch_rank_em,
    df_billboard_branch_stats_em,
    df_billboard_branch_trades_em,
    df_billboard_stock_dates_em,
    df_billboard_stock_em,
    df_block_trade_market_daily_em,
    df_block_trade_detail_em,
    df_block_trade_stock_daily_em,
    df_block_trade_stock_stats_em,
    df_block_trade_branch_active_em,
    df_block_trade_branch_rank_em,
    df_earnings_report_em,
    df_earnings_express_em,
    df_earnings_forecast_em,
    df_earnings_schedule_em,
    df_balance_sheet_em,
    df_income_statement_em,
    df_cash_flow_statement_em,
    to_dataframe,
    to_kline_dataframe,
    to_trend_dataframe,
    to_fund_flow_dataframe,
    to_board_fund_flow_dataframe,
    to_board_list_dataframe,
    to_index_list_dataframe,
    to_hk_stock_list_dataframe,
    to_fund_list_dataframe,
    to_limit_pool_dataframe,
    to_stock_info_dataframe,
    to_stock_bid_ask_dataframe,
    to_stock_changes_dataframe,
    to_board_changes_dataframe,
    to_billboard_detail_dataframe,
    to_billboard_stock_stats_dataframe,
    to_billboard_institution_dataframe,
    to_billboard_institution_stats_dataframe,
    to_billboard_branch_active_dataframe,
    to_billboard_branch_rank_dataframe,
    to_billboard_branch_stats_dataframe,
    to_billboard_branch_trades_dataframe,
    to_billboard_stock_dates_dataframe,
    to_billboard_stock_dataframe,
    to_block_trade_market_daily_dataframe,
    to_block_trade_detail_dataframe,
    to_block_trade_stock_daily_dataframe,
    to_block_trade_stock_stats_dataframe,
    to_block_trade_branch_active_dataframe,
    to_block_trade_branch_rank_dataframe,
    to_earnings_report_dataframe,
    to_earnings_express_dataframe,
    to_earnings_forecast_dataframe,
    to_earnings_schedule_dataframe,
    to_balance_sheet_dataframe,
    to_income_statement_dataframe,
    to_cash_flow_statement_dataframe,
    search,
    search_df,
    interface_info,
    interface_info_df,
    list_categories,
    list_categories_df,
)
```

`board_constituent_em` / `stock_list_em` 返回 `QuotePage`，`stock_kline_em` / `board_kline_em` 返回 `KlineSeries`，`stock_trends_em` 返回 `TrendSeries`，`stock_fund_flow_em` 返回 `FundFlowSeries`，`board_fund_flow_em` 返回 `BoardFundFlowSeries`，`board_industry_list_em` 返回 `BoardListPage`，`index_list_em` 返回 `IndexListPage`，`hk_stock_list_em` 返回 `HkStockListPage`，`fund_list_em` 返回 `FundListPage`，`stock_limit_pool_em` 返回 `LimitPoolPage`，`stock_info_em` 返回 `StockInfo`，`stock_bid_ask_em` 返回 `StockBidAsk`，`stock_changes_em` 返回 `StockChangesPage`，`board_changes_em` 返回 `BoardChangesPage`，`billboard_detail_em` 返回 `ReportPage[BillboardEntry]`，其余 9 个龙虎榜报表接口、6 个大宗交易接口、7 个业绩与财报接口同样返回 `ReportPage`（元素类型见各接口文档），`df_*_em` 返回 `pd.DataFrame`（需 `pip install pandas`）。`to_dataframe` / `to_kline_dataframe` / `to_trend_dataframe` / `to_fund_flow_dataframe` / `to_board_fund_flow_dataframe` / `to_board_list_dataframe` / `to_index_list_dataframe` / `to_hk_stock_list_dataframe` / `to_fund_list_dataframe` / `to_limit_pool_dataframe` / `to_stock_info_dataframe` / `to_stock_bid_ask_dataframe` / `to_stock_changes_dataframe` / `to_board_changes_dataframe` / `to_billboard_detail_dataframe` 及其余 9 个 `to_billboard_*_dataframe`、6 个 `to_block_trade_*_dataframe`、7 个业绩与财报的 `to_*_dataframe` 把对应领域模型转为 DataFrame，均默认中文列名，传 `columns` 可覆盖。

## 功能

| 功能 | 接口文档 | 源码 | 公共面 |
| --- | --- | --- | --- |
| 板块成分股资金流 | [board_constituent_em.md](./ashare_boards/board_constituent_em.md) | `channels/eastmoney/ashare_boards/board_constituent/board_constituent_em.py` | `board_constituent_em` / `df_board_constituent_em` |
| 板块列表（行业 / 概念 / 地域） | [board_industry_list_em.md](./ashare_boards/board_industry_list_em.md) | `channels/eastmoney/ashare_boards/board_industry_list/board_industry_list_em.py` | `board_industry_list_em` / `df_board_industry_list_em` |
| 沪深京 A 股全市场列表 | [stock_list_em.md](./ashare_stocks/stock_list_em.md) | `channels/eastmoney/ashare_stocks/stock_list/stock_list_em.py` | `stock_list_em` / `df_stock_list_em` |
| 历史 K 线 | [stock_kline_em.md](./ashare_stocks/stock_kline_em.md) | `channels/eastmoney/ashare_stocks/stock_kline/stock_kline_em.py` | `stock_kline_em` / `df_stock_kline_em` |
| 分时行情 | [stock_trends_em.md](./ashare_stocks/stock_trends_em.md) | `channels/eastmoney/ashare_stocks/stock_trends/stock_trends_em.py` | `stock_trends_em` / `df_stock_trends_em` |
| 个股历史资金流 | [stock_fund_flow_em.md](./ashare_stocks/stock_fund_flow_em.md) | `channels/eastmoney/ashare_stocks/stock_fund_flow/stock_fund_flow_em.py` | `stock_fund_flow_em` / `df_stock_fund_flow_em` |
| 板块（行业 / 概念 / 地域）历史资金流 | [board_fund_flow_em.md](./ashare_boards/board_fund_flow_em.md) | `channels/eastmoney/ashare_boards/board_fund_flow/board_fund_flow_em.py` | `board_fund_flow_em` / `df_board_fund_flow_em` |
| 板块（行业 / 概念 / 地域）历史 K 线 | [board_kline_em.md](./ashare_boards/board_kline_em.md) | `channels/eastmoney/ashare_boards/board_kline/board_kline_em.py` | `board_kline_em` / `df_board_kline_em` |
| 指数列表（沪深重要 / 上证 / 深证 / 中证） | [index_list_em.md](./ashare_indices/index_list_em.md) | `channels/eastmoney/ashare_indices/index_list/index_list_em.py` | `index_list_em` / `df_index_list_em` |
| 港股列表（主板 / 创业板） | [hk_stock_list_em.md](./hk_market/hk_stock_list_em.md) | `channels/eastmoney/hk_market/hk_stock_list/hk_stock_list_em.py` | `hk_stock_list_em` / `df_hk_stock_list_em` |
| 场内基金列表（ETF / LOF） | [fund_list_em.md](./fund_market/fund_list_em.md) | `channels/eastmoney/fund_market/fund_list/fund_list_em.py` | `fund_list_em` / `df_fund_list_em` |
| 涨跌停股池（涨停 / 昨日涨停 / 强势 / 次新 / 炸板 / 跌停） | [stock_limit_pool_em.md](./ashare_stocks/stock_limit_pool_em.md) | `channels/eastmoney/ashare_stocks/stock_limit_pool/stock_limit_pool_em.py` | `stock_limit_pool_em` / `df_stock_limit_pool_em` |
| 个股基本信息 | [stock_info_em.md](./ashare_stocks/stock_info_em.md) | `channels/eastmoney/ashare_stocks/stock_info/stock_info_em.py` | `stock_info_em` / `df_stock_info_em` |
| 个股五档盘口 | [stock_bid_ask_em.md](./ashare_stocks/stock_bid_ask_em.md) | `channels/eastmoney/ashare_stocks/stock_bid_ask/stock_bid_ask_em.py` | `stock_bid_ask_em` / `df_stock_bid_ask_em` |
| 盘口异动（22 种） | [stock_changes_em.md](./ashare_stocks/stock_changes_em.md) | `channels/eastmoney/ashare_stocks/stock_changes/stock_changes_em.py` | `stock_changes_em` / `df_stock_changes_em` |
| 板块异动 | [board_changes_em.md](./ashare_boards/board_changes_em.md) | `channels/eastmoney/ashare_boards/board_changes/board_changes_em.py` | `board_changes_em` / `df_board_changes_em` |
| 龙虎榜详情 | [billboard_detail_em.md](./ashare_billboard/billboard_detail_em.md) | `channels/eastmoney/ashare_billboard/billboard_detail/billboard_detail_em.py` | `billboard_detail_em` / `df_billboard_detail_em` |
| 个股上榜统计 | [billboard_stock_stats_em.md](./ashare_billboard/billboard_stock_stats_em.md) | `channels/eastmoney/ashare_billboard/billboard_stock_stats/billboard_stock_stats_em.py` | `billboard_stock_stats_em` / `df_billboard_stock_stats_em` |
| 机构买卖每日统计 | [billboard_institution_em.md](./ashare_billboard/billboard_institution_em.md) | `channels/eastmoney/ashare_billboard/billboard_institution/billboard_institution_em.py` | `billboard_institution_em` / `df_billboard_institution_em` |
| 机构席位追踪 | [billboard_institution_stats_em.md](./ashare_billboard/billboard_institution_stats_em.md) | `channels/eastmoney/ashare_billboard/billboard_institution_stats/billboard_institution_stats_em.py` | `billboard_institution_stats_em` / `df_billboard_institution_stats_em` |
| 每日活跃营业部 | [billboard_branch_active_em.md](./ashare_billboard/billboard_branch_active_em.md) | `channels/eastmoney/ashare_billboard/billboard_branch_active/billboard_branch_active_em.py` | `billboard_branch_active_em` / `df_billboard_branch_active_em` |
| 营业部排行 | [billboard_branch_rank_em.md](./ashare_billboard/billboard_branch_rank_em.md) | `channels/eastmoney/ashare_billboard/billboard_branch_rank/billboard_branch_rank_em.py` | `billboard_branch_rank_em` / `df_billboard_branch_rank_em` |
| 营业部统计 | [billboard_branch_stats_em.md](./ashare_billboard/billboard_branch_stats_em.md) | `channels/eastmoney/ashare_billboard/billboard_branch_stats/billboard_branch_stats_em.py` | `billboard_branch_stats_em` / `df_billboard_branch_stats_em` |
| 营业部详情 | [billboard_branch_trades_em.md](./ashare_billboard/billboard_branch_trades_em.md) | `channels/eastmoney/ashare_billboard/billboard_branch_trades/billboard_branch_trades_em.py` | `billboard_branch_trades_em` / `df_billboard_branch_trades_em` |
| 个股上榜日期 | [billboard_stock_dates_em.md](./ashare_billboard/billboard_stock_dates_em.md) | `channels/eastmoney/ashare_billboard/billboard_stock_dates/billboard_stock_dates_em.py` | `billboard_stock_dates_em` / `df_billboard_stock_dates_em` |
| 个股龙虎榜详情 | [billboard_stock_em.md](./ashare_billboard/billboard_stock_em.md) | `channels/eastmoney/ashare_billboard/billboard_stock/billboard_stock_em.py` | `billboard_stock_em` / `df_billboard_stock_em` |
| 大宗交易市场统计 | [block_trade_market_daily_em.md](./ashare_block_trade/block_trade_market_daily_em.md) | `channels/eastmoney/ashare_block_trade/block_trade_market_daily/block_trade_market_daily_em.py` | `block_trade_market_daily_em` / `df_block_trade_market_daily_em` |
| 大宗交易每日明细 | [block_trade_detail_em.md](./ashare_block_trade/block_trade_detail_em.md) | `channels/eastmoney/ashare_block_trade/block_trade_detail/block_trade_detail_em.py` | `block_trade_detail_em` / `df_block_trade_detail_em` |
| 大宗交易每日统计 | [block_trade_stock_daily_em.md](./ashare_block_trade/block_trade_stock_daily_em.md) | `channels/eastmoney/ashare_block_trade/block_trade_stock_daily/block_trade_stock_daily_em.py` | `block_trade_stock_daily_em` / `df_block_trade_stock_daily_em` |
| 大宗交易活跃 A 股统计 | [block_trade_stock_stats_em.md](./ashare_block_trade/block_trade_stock_stats_em.md) | `channels/eastmoney/ashare_block_trade/block_trade_stock_stats/block_trade_stock_stats_em.py` | `block_trade_stock_stats_em` / `df_block_trade_stock_stats_em` |
| 大宗交易活跃营业部统计 | [block_trade_branch_active_em.md](./ashare_block_trade/block_trade_branch_active_em.md) | `channels/eastmoney/ashare_block_trade/block_trade_branch_active/block_trade_branch_active_em.py` | `block_trade_branch_active_em` / `df_block_trade_branch_active_em` |
| 大宗交易营业部排行 | [block_trade_branch_rank_em.md](./ashare_block_trade/block_trade_branch_rank_em.md) | `channels/eastmoney/ashare_block_trade/block_trade_branch_rank/block_trade_branch_rank_em.py` | `block_trade_branch_rank_em` / `df_block_trade_branch_rank_em` |
| 业绩报告 | [earnings_report_em.md](./ashare_earnings/earnings_report_em.md) | `channels/eastmoney/ashare_earnings/earnings_report/earnings_report_em.py` | `earnings_report_em` / `df_earnings_report_em` |
| 业绩快报 | [earnings_express_em.md](./ashare_earnings/earnings_express_em.md) | `channels/eastmoney/ashare_earnings/earnings_express/earnings_express_em.py` | `earnings_express_em` / `df_earnings_express_em` |
| 业绩预告 | [earnings_forecast_em.md](./ashare_earnings/earnings_forecast_em.md) | `channels/eastmoney/ashare_earnings/earnings_forecast/earnings_forecast_em.py` | `earnings_forecast_em` / `df_earnings_forecast_em` |
| 预约披露时间 | [earnings_schedule_em.md](./ashare_earnings/earnings_schedule_em.md) | `channels/eastmoney/ashare_earnings/earnings_schedule/earnings_schedule_em.py` | `earnings_schedule_em` / `df_earnings_schedule_em` |
| 资产负债表 | [balance_sheet_em.md](./ashare_financial_statements/balance_sheet_em.md) | `channels/eastmoney/ashare_financial_statements/balance_sheet/balance_sheet_em.py` | `balance_sheet_em` / `df_balance_sheet_em` |
| 利润表 | [income_statement_em.md](./ashare_financial_statements/income_statement_em.md) | `channels/eastmoney/ashare_financial_statements/income_statement/income_statement_em.py` | `income_statement_em` / `df_income_statement_em` |
| 现金流量表 | [cash_flow_statement_em.md](./ashare_financial_statements/cash_flow_statement_em.md) | `channels/eastmoney/ashare_financial_statements/cash_flow_statement/cash_flow_statement_em.py` | `cash_flow_statement_em` / `df_cash_flow_statement_em` |

## 接口检索

对齐 akshare 的离线接口自省能力，检索完全在本地进行，不发起网络请求。核心函数返回 `list[dict]` / `dict`（不依赖 pandas）；`search_df` / `list_categories_df` 为 DataFrame 包装（需 pandas）。

```python
import em

# 按关键词检索接口
print(em.search("板块 资金流"))
# [{'接口名': 'board_constituent_em', '类目': 'board', '描述': '板块成分股（含主力净流入...）', '有无文档': True, '匹配分': 15.0},
#  {'接口名': 'stock_list_em', '类目': 'market', ...}]

# 查看单个接口的输入参数、输出字段与调用示例
print(em.interface_info("board_constituent_em"))
# {'name': 'board_constituent_em', 'category': 'board', 'inputs': [...], 'outputs': [...], 'example': '...', 'dataframe_variant': 'df_board_constituent_em'}

# 列出全部类目及其接口数量
print(em.list_categories())
# [{'类目': 'billboard', '接口数': 10}, {'类目': 'block_trade', '接口数': 6}, {'类目': 'board', '接口数': 2}, {'类目': 'changes', '接口数': 2}, {'类目': 'earnings', '接口数': 4}, {'类目': 'financial_statements', '接口数': 3}, {'类目': 'fund', '接口数': 1}, {'类目': 'fund_flow', '接口数': 2}, {'类目': 'hk', '接口数': 1}, {'类目': 'index', '接口数': 1}, {'类目': 'kline', '接口数': 2}, {'类目': 'market', '接口数': 1}, {'类目': 'pool', '接口数': 1}, {'类目': 'stock', '接口数': 2}, {'类目': 'trends', '接口数': 1}]
```

DataFrame 版（需 pandas，对齐 akshare `print(ak.search(...))` 体验）：

```python
print(em.search_df("板块 资金流"))
#            接口名      类目                              描述  有无文档  匹配分
# 0   board_constituent_em   board  板块成分股（含主力净流入...）   True  15.0
# 1  stock_list_em  market  沪深京 A 股全市场列表...        True  10.0

print(em.list_categories_df())
#                       类目  接口数
# 0              billboard   10
# 1            block_trade    6
# 2                  board    2
# 3                changes    2
# 4               earnings    4
# 5   financial_statements    3
# 6                   fund    1
# 7              fund_flow    2
# 8                     hk    1
# 9                  index    1
# 10                 kline    2
# 11                market    1
# 12                  pool    1
# 13                 stock    2
# 14                trends    1
```

`interface_info_df(name)` 返回 ``{"inputs": 参数表, "outputs": 字段表}``，中文列名对齐文档参数表：

```python
tables = em.interface_info_df("board_constituent_em")
print(tables["inputs"])
#       名称   类型     必填       默认值                          描述
# 0   board  str  False  "BK0438"           板块代码（如 BK0438 白酒）
# 1  period  str  False     "10d"  资金流周期：day/5d/10d，未知值回退 10d
# 2    page  int  False         1                    页码，从 1 起
# 3    size  int  False         8                每页条数，上游上限 50

print(tables["outputs"])
#                名称            类型 单位                  描述
# 0             code           str  —                证券代码
# 1             name           str  —                证券简称
# 2            price  float | None  元                 最新价
# 3       change_pct  float | None  %                 涨跌幅
# 4           change  float | None  元                 涨跌额
# 5  main_net_inflow  float | None  元  主力净流入（按 period 周期）
# 6         turnover  float | None  元                 成交额
# 7    turnover_rate  float | None  %                 换手率
```

`search(query, limit=20, category=None, documented_only=False)`：按关键词检索，精确接口名置顶，未打空格时按 2-gram 降级召回。`interface_info(name)`：未知接口抛 `InterfaceNotFoundError` 并给最接近候选。

## 配置

运行期配置从环境变量读取，构造期 fail-fast 校验。`import em` 时会自动把运行目录下 `.env` 里 `EM_` 开头的变量读进环境（已设置的优先；`EM_ENV_FILE` 可指定路径或设为 `none` 关闭），`emshare --init-env` 可生成带逐项说明的模板：

| 环境变量 | 类型 | 默认值 | 描述 |
| --- | --- | --- | --- |
| `EM_PROXY_API` | `str` | 空（不配则只能直连） | 代理提取接口地址，需返回纯文本、每行一个 `ip:port`；`EM_PROXY_API_*` 为备用源 |
| `EM_PROXY_ENABLED` | `bool` | `True` | 是否启用代理 |
| `EM_PROXY_NUM` | `int` | `1` | 单次取 IP 数量，须与提取接口每次返回的条数一致 |
| `EM_PROXY_TTL_SEC` | `int` | `30` | 代理 IP 有效期（秒） |
| `EM_PROXY_SAFETY_MARGIN_SEC` | `int` | `3` | 过期前安全余量（秒）；硬到期前 3s 起后台续期，旧 IP 用到硬到期 |
| `EM_PROXY_MODE` | `str` | `auto` | `auto` / `always` / `never`，按 host 独立决策 |
| `EM_PROXY_PREFILTER` | `bool` | `True` | 回源预筛开关（同业务口径探测，判死的记黑名单不进池） |
| `EM_PROXY_PREFILTER_SOURCES` | `int` | `1` | 前 N 个源参与预筛；收费备用源建议不筛（淘汰等于浪费配额） |
| `EM_PROXY_DEGRADED_MODE` | `str` | `lenient` | 整批全死后：`lenient` 改用 1.5s 快筛继续过滤 / `adopt` 暂停预筛（回退） |
| `EM_REQUEST_TIMEOUT_SEC` | `int` | `15` | 单次请求读超时（秒），同时是预筛探测的读预算上限（3s） |
| `EM_MAX_RETRIES` | `int` | `10` | 最大重试次数（换 IP 重试次数） |

## 异常

| 异常 | `retryable` | 描述 |
| --- | --- | --- |
| `ConfigError` | 否 | 配置非法，立即上抛 |
| `NetworkError` | 是 | 连接失败 / 超时，换 IP 重试 |
| `EmptyResponseError` | 是 | 空响应（出口被封断开），换 IP 重试 |
| `QueryRejectedError` | 否 | 数据中心拒绝了查询（报表 / 列名写错、参数类型不对），换 IP 也一样，直接上抛 |
| `HttpStatusError` | 5xx / 403 / 429 | 非预期状态码，按状态码判定 |
| `PageDeadlineExceeded` | 否 | 单页超过时间预算，标记失败交给定向补漏，不阻塞整轮 |

重试耗尽后抛出的是最后一次异常。若属于出口类失败（连接断开 / 超时 / 空响应 / 403 / 429）且代理用不上（没配代理源、仍是模板占位符、或被关闭），异常的 `hint` 属性带一段配置指引，`str(exc)` 会把它接在错误信息后面；`exc.args` 不变。
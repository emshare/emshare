# eastmoney 渠道目录结构

代码（`src/em/channels/eastmoney/`）与文档（`docs/interfaces/eastmoney/`）按市场分组一一对应：

```
src/em/channels/eastmoney/                 docs/interfaces/eastmoney/
├── ashare_boards/              # 沪深京板块    ├── ashare_boards/
│   ├── board_constituent/      # 板块成分股    │   ├── board_constituent_em.md
│   ├── board_fund_flow/        # 板块资金流    │   ├── board_fund_flow_em.md
│   ├── board_kline/            # 板块K线       │   ├── board_kline_em.md
│   ├── board_industry_list/    # 板块列表      │   ├── board_industry_list_em.md
│   └── board_changes/          # 板块异动      │   └── board_changes_em.md
├── ashare_stocks/              # 沪深京个股    ├── ashare_stocks/
│   ├── stock_list/             # 个股列表      │   ├── stock_list_em.md
│   │                           # (全量翻页在   │   └── stock_list_all_em.md
│   │                           #  应用层)      │
│   ├── stock_fund_flow/        # 个股资金流    │   ├── stock_fund_flow_em.md
│   ├── stock_kline/            # K线(个股+指数)│   ├── stock_kline_em.md
│   ├── stock_trends/           # 分时(个股+指数)│   ├── stock_trends_em.md
│   ├── stock_limit_pool/       # 涨跌停股池    │   ├── stock_limit_pool_em.md
│   ├── stock_info/             # 个股信息      │   ├── stock_info_em.md
│   ├── stock_bid_ask/          # 五档盘口      │   ├── stock_bid_ask_em.md
│   └── stock_changes/          # 盘口异动      │   └── stock_changes_em.md
├── ashare_billboard/           # 龙虎榜        ├── ashare_billboard/
│   ├── billboard_detail/       # 龙虎榜详情    │   ├── billboard_detail_em.md
│   ├── billboard_stock_stats/  # 个股上榜统计  │   ├── billboard_stock_stats_em.md
│   ├── billboard_institution/  # 机构每日统计  │   ├── billboard_institution_em.md
│   ├── billboard_institution_stats/# 机构席位追踪  │   ├── billboard_institution_stats_em.md
│   ├── billboard_branch_active/# 活跃营业部    │   ├── billboard_branch_active_em.md
│   ├── billboard_branch_rank/  # 营业部排行    │   ├── billboard_branch_rank_em.md
│   ├── billboard_branch_stats/ # 营业部统计    │   ├── billboard_branch_stats_em.md
│   ├── billboard_branch_trades/# 营业部详情    │   ├── billboard_branch_trades_em.md
│   ├── billboard_stock_dates/  # 个股上榜日期  │   ├── billboard_stock_dates_em.md
│   └── billboard_stock/        # 个股龙虎榜    │   └── billboard_stock_em.md
├── ashare_block_trade/         # 大宗交易      ├── ashare_block_trade/
│   ├── block_trade_market_daily/# 市场统计      │   ├── block_trade_market_daily_em.md
│   ├── block_trade_detail/     # 每日明细      │   ├── block_trade_detail_em.md
│   ├── block_trade_stock_daily/# 每日统计      │   ├── block_trade_stock_daily_em.md
│   ├── block_trade_stock_stats/# 活跃A股统计   │   ├── block_trade_stock_stats_em.md
│   ├── block_trade_branch_active/# 活跃营业部    │   ├── block_trade_branch_active_em.md
│   └── block_trade_branch_rank/# 营业部排行    │   └── block_trade_branch_rank_em.md
├── ashare_earnings/            # 业绩          ├── ashare_earnings/
│   ├── earnings_report/        # 业绩报告      │   ├── earnings_report_em.md
│   ├── earnings_express/       # 业绩快报      │   ├── earnings_express_em.md
│   ├── earnings_forecast/      # 业绩预告      │   ├── earnings_forecast_em.md
│   └── earnings_schedule/      # 预约披露      │   └── earnings_schedule_em.md
├── ashare_financial_statements/# 三大报表      ├── ashare_financial_statements/
│   ├── balance_sheet/          # 资产负债表    │   ├── balance_sheet_em.md
│   ├── income_statement/       # 利润表        │   ├── income_statement_em.md
│   └── cash_flow_statement/    # 现金流量表    │   └── cash_flow_statement_em.md
├── ashare_indices/              # 沪深京指数    ├── ashare_indices/
│   └── index_list/             # 指数列表      │   └── index_list_em.md
├── hk_market/                  # 港股市场      ├── hk_market/
│   └── hk_stock_list/          # 港股列表      │   └── hk_stock_list_em.md
├── us_market/.gitkeep          # 美股市场      ├── us_market/.gitkeep
├── fund_market/                # 基金市场      ├── fund_market/
│   └── fund_list/              # 场内基金列表  │   └── fund_list_em.md
├── bond_market/.gitkeep        # 债券市场      ├── bond_market/.gitkeep
├── global_indices/.gitkeep     # 全球指数      ├── global_indices/.gitkeep
├── forex_market/.gitkeep       # 外汇市场      ├── forex_market/.gitkeep
├── gold_market/.gitkeep        # 黄金市场      ├── gold_market/.gitkeep
├── option_market/.gitkeep      # 期权市场      ├── option_market/.gitkeep
├── futures_market/.gitkeep     # 期货市场      ├── futures_market/.gitkeep
├── special_quotes/.gitkeep     # 特色行情      ├── special_quotes/.gitkeep
├── stock_connect/.gitkeep      # 沪深港通      ├── stock_connect/.gitkeep
├── config.py                   # 渠道配置      ├── overview.md          # 接口预览
├── request.py                  # 请求句柄      ├── directory_tree.md   # 目录结构(本页)
├── datacenter.py               # 数据中心报表公共部分（列映射 / 换算 / 过滤条件）
├── mapping.py                  # 报文映射      └── eastmoney.md         # 渠道总览
├── source.py                   # 取数来源
└── __init__.py
```

> 除 `ashare_boards/`、`ashare_stocks/`、`ashare_billboard/`、`ashare_block_trade/`、`ashare_earnings/`、`ashare_financial_statements/`、`ashare_indices/`、`hk_market/`、`fund_market/` 外，其余市场目录暂为空占位，待对应功能实现后填充。
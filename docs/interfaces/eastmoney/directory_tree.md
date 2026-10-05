# eastmoney 渠道目录结构

代码（`src/em/channels/eastmoney/`）与文档（`docs/interfaces/eastmoney/`）按市场分组一一对应：

```
src/em/channels/eastmoney/                 docs/interfaces/eastmoney/
├── ashare_boards/              # 沪深京板块    ├── ashare_boards/
│   ├── board_constituent/      # 板块成分股    │   ├── board_constituent_em.md
│   └── board_fund_flow/        # 板块资金流    │   └── board_fund_flow_em.md
├── ashare_stocks/              # 沪深京个股    ├── ashare_stocks/
│   ├── stock/                  # 个股列表      │   ├── stock_list_em.md
│   ├── fund_flow/              # 个股资金流    │   ├── stock_fund_flow_em.md
│   ├── kline/                  # K线(个股+指数)│   ├── stock_kline_em.md
│   └── trends/                 # 分时(个股+指数)│   └── stock_trends_em.md
├── ashare_indices/.gitkeep     # 沪深京指数    ├── ashare_indices/.gitkeep
├── hk_market/.gitkeep          # 港股市场      ├── hk_market/.gitkeep
├── us_market/.gitkeep          # 美股市场      ├── us_market/.gitkeep
├── config.py                   # 渠道配置      ├── overview.md          # 接口预览
├── request.py                  # 请求句柄      ├── directory_tree.md   # 目录结构(本页)
├── mapping.py                  # 报文映射      └── eastmoney.md         # 渠道总览
├── source.py                   # 取数来源
└── __init__.py
```

> `ashare_indices/`、`hk_market/`、`us_market/` 暂为空占位，待对应功能实现后填充。
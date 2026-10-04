# eastmoney 渠道接口预览

## 目录结构

代码（`src/em/channels/eastmoney/`）与文档（`docs/interfaces/eastmoney/`）按市场分组一一对应：

```
src/em/channels/eastmoney/                 docs/interfaces/eastmoney/
├── ashare_boards/              # 沪深京板块    ├── ashare_boards/
│   ├── board_constituent/      # 板块成分股    │   ├── board_constituent_em.md
│   └── board_fund_flow/        # 板块资金流    │   └── board_fund_flow_em.md
├── ashare_stocks/              # 沪深京个股    ├── ashare_stocks/
│   ├── stock/                  # 个股列表      │   ├── stock_list_em.md
│   ├── fund_flow/              # 个股资金流    │   ├── fund_flow_em.md
│   ├── kline/                  # K线(个股+指数)│   ├── kline_em.md
│   └── trends/                 # 分时(个股+指数)│   └── trends_em.md
├── ashare_indices/.gitkeep     # 沪深京指数    ├── ashare_indices/.gitkeep
├── hk_market/.gitkeep          # 港股市场      ├── hk_market/.gitkeep
├── us_market/.gitkeep          # 美股市场      ├── us_market/.gitkeep
├── config.py                   # 渠道配置      ├── overview.md          # 接口预览(本页)
├── request.py                  # 请求句柄      └── eastmoney.md         # 渠道总览
├── mapping.py                  # 报文映射
├── source.py                   # 取数来源
└── __init__.py
```

> `ashare_indices/`、`hk_market/`、`us_market/` 暂为空占位，待对应功能实现后填充。

## 行情接口一览表

### `板块成分股`
接口：`fetch_board`
描述：板块成分股（含主力净流入，可按当日/5日/10日资金流排序）。

- 详情：[board_constituent_em.md](./ashare_boards/board_constituent_em.md)
- 源码：`src/em/channels/eastmoney/ashare_boards/board_constituent/board_constituent_em.py`


### `沪深京 A 股全市场列表`
接口：`fetch_market`
描述：沪深京 A 股全市场列表（游客接口，不含资金流）。

- 详情：[stock_list_em.md](./ashare_stocks/stock_list_em.md)
- 源码：`src/em/channels/eastmoney/ashare_stocks/stock/stock_list_em.py`


### `历史 K 线`
接口：`fetch_kline`
描述：个股 / 指数历史 K 线（日 / 周 / 月，前 / 后 / 不复权）。

- 详情：[kline_em.md](./ashare_stocks/kline_em.md)
- 源码：`src/em/channels/eastmoney/ashare_stocks/kline/kline_em.py`


### `分时行情`
接口：`fetch_trends`
描述：个股 / 指数分时行情（trends2，ndays 日分时）。

- 详情：[trends_em.md](./ashare_stocks/trends_em.md)
- 源码：`src/em/channels/eastmoney/ashare_stocks/trends/trends_em.py`


### `个股历史资金流`
接口：`fetch_fund_flow`
描述：个股历史资金流（fflow/daykline，日线，主力/超大单/大单/中单/小单净流入）。

- 详情：[fund_flow_em.md](./ashare_stocks/fund_flow_em.md)
- 源码：`src/em/channels/eastmoney/ashare_stocks/fund_flow/fund_flow_em.py`


### `板块（行业 / 概念 / 地域）历史资金流`
接口：`fetch_board_fund_flow`
描述：板块历史资金流（fflow/daykline，日线，secid 前缀 90，主力/超大单/大单/中单/小单净流入，不含收盘价/涨跌幅）。

- 详情：[board_fund_flow_em.md](./ashare_boards/board_fund_flow_em.md)
- 源码：`src/em/channels/eastmoney/ashare_boards/board_fund_flow/board_fund_flow_em.py`


## DataFrame 版（需 `pip install pandas`，akshare 风格中文列名）

### `板块成分股（DataFrame）`
接口：`fetch_board_df`
描述：`fetch_board` 的 DataFrame 版。

- 详情：[board_constituent_em.md](./ashare_boards/board_constituent_em.md)


### `沪深京 A 股全市场列表（DataFrame）`
接口：`fetch_market_df`
描述：`fetch_market` 的 DataFrame 版。

- 详情：[stock_list_em.md](./ashare_stocks/stock_list_em.md)


### `历史 K 线（DataFrame）`
接口：`fetch_kline_df`
描述：`fetch_kline` 的 DataFrame 版。

- 详情：[kline_em.md](./ashare_stocks/kline_em.md)


### `分时行情（DataFrame）`
接口：`fetch_trends_df`
描述：`fetch_trends` 的 DataFrame 版。

- 详情：[trends_em.md](./ashare_stocks/trends_em.md)


### `个股历史资金流（DataFrame）`
接口：`fetch_fund_flow_df`
描述：`fetch_fund_flow` 的 DataFrame 版。

- 详情：[fund_flow_em.md](./ashare_stocks/fund_flow_em.md)


### `板块历史资金流（DataFrame）`
接口：`fetch_board_fund_flow_df`
描述：`fetch_board_fund_flow` 的 DataFrame 版。

- 详情：[board_fund_flow_em.md](./ashare_boards/board_fund_flow_em.md)


### `通用转换`
接口：`to_dataframe`
描述：任意 `QuotePage` → `DataFrame`，默认中文列名，可传 `columns` 覆盖。

- 详情：[eastmoney.md](./eastmoney.md)

```python
from em import to_dataframe

df = to_dataframe(page, columns=None)
```

## 接口检索（离线，不触网，对齐 akshare）

核心函数返回 `list[dict]` / `dict`，不依赖 pandas；`*_df` 为 DataFrame 包装。

### `关键词检索`
接口：`search`
描述：按关键词检索接口，精确名置顶，2-gram 降级召回。

```python
import em

em.search("板块 资金流")  # -> list[dict]
```

### `接口详情`
接口：`interface_info`
描述：查看单个接口的输入参数、输出字段与调用示例；未知接口抛 `InterfaceNotFoundError` 并给最接近候选。

```python
em.interface_info("fetch_board")  # -> dict
```

### `类目列表`
接口：`list_categories`
描述：列出全部类目及其接口数量。

```python
em.list_categories()  # -> [{"类目": "board", "接口数": 1}, ...]
```

### `检索 / 详情 / 类目（DataFrame）`
接口：`search_df` / `interface_info_df` / `list_categories_df`
描述：DataFrame 包装（需 pandas）。`interface_info_df` 返回 `{"inputs": 参数表, "outputs": 字段表}`，中文列名。

```python
em.search_df("板块 资金流")
em.interface_info_df("fetch_board")  # -> {"inputs": df, "outputs": df}
em.list_categories_df()
```

## 相关

- 渠道总览（公共面 / 配置 / 异常）：[eastmoney.md](./eastmoney.md)
- 检索实现：`src/em/application/catalog.py`
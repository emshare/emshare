# eastmoney 渠道接口

本页描述 `em` 包对外公共面的六个取数接口：板块成分股资金流、沪深京 A 股全市场列表、历史 K 线、分时行情、个股历史资金流与板块（行业 / 概念 / 地域）历史资金流。前两者走东方财富 `clist` 接口，后四者走 `kline` / `trends2` / `fflow` 接口（个股与板块资金流共用 `fflow/daykline`），均经动态代理自动换 IP 重试，返回领域模型（`QuotePage` / `KlineSeries` / `TrendSeries` / `FundFlowSeries` / `BoardFundFlowSeries`）；另提供 `df_*_em` 便捷函数直接返回 pandas DataFrame（akshare 风格中文列名）。

公共面统一从 `em` 顶层导出：

```python
from em import (
    board_constituent_em,
    stock_list_em,
    stock_kline_em,
    stock_trends_em,
    stock_fund_flow_em,
    board_fund_flow_em,
    df_board_constituent_em,
    df_stock_list_em,
    df_stock_kline_em,
    df_stock_trends_em,
    df_stock_fund_flow_em,
    df_board_fund_flow_em,
    to_dataframe,
    to_kline_dataframe,
    to_trend_dataframe,
    to_fund_flow_dataframe,
    to_board_fund_flow_dataframe,
    search,
    search_df,
    interface_info,
    interface_info_df,
    list_categories,
    list_categories_df,
)
```

`board_constituent_em` / `stock_list_em` 返回 `QuotePage`，`stock_kline_em` 返回 `KlineSeries`，`stock_trends_em` 返回 `TrendSeries`，`stock_fund_flow_em` 返回 `FundFlowSeries`，`board_fund_flow_em` 返回 `BoardFundFlowSeries`，`df_*_em` 返回 `pd.DataFrame`（需 `pip install pandas`）。`to_dataframe` / `to_kline_dataframe` / `to_trend_dataframe` / `to_fund_flow_dataframe` / `to_board_fund_flow_dataframe` 把对应领域模型转为 DataFrame，均默认中文列名，传 `columns` 可覆盖。

## 功能

| 功能 | 接口文档 | 源码 | 公共面 |
| --- | --- | --- | --- |
| 板块成分股资金流 | [board_constituent_em.md](./ashare_boards/board_constituent_em.md) | `channels/eastmoney/ashare_boards/board_constituent/board_constituent_em.py` | `board_constituent_em` / `df_board_constituent_em` |
| 沪深京 A 股全市场列表 | [stock_list_em.md](./ashare_stocks/stock_list_em.md) | `channels/eastmoney/ashare_stocks/stock_list/stock_list_em.py` | `stock_list_em` / `df_stock_list_em` |
| 历史 K 线 | [stock_kline_em.md](./ashare_stocks/stock_kline_em.md) | `channels/eastmoney/ashare_stocks/stock_kline/stock_kline_em.py` | `stock_kline_em` / `df_stock_kline_em` |
| 分时行情 | [stock_trends_em.md](./ashare_stocks/stock_trends_em.md) | `channels/eastmoney/ashare_stocks/stock_trends/stock_trends_em.py` | `stock_trends_em` / `df_stock_trends_em` |
| 个股历史资金流 | [stock_fund_flow_em.md](./ashare_stocks/stock_fund_flow_em.md) | `channels/eastmoney/ashare_stocks/stock_fund_flow/stock_fund_flow_em.py` | `stock_fund_flow_em` / `df_stock_fund_flow_em` |
| 板块（行业 / 概念 / 地域）历史资金流 | [board_fund_flow_em.md](./ashare_boards/board_fund_flow_em.md) | `channels/eastmoney/ashare_boards/board_fund_flow/board_fund_flow_em.py` | `board_fund_flow_em` / `df_board_fund_flow_em` |

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
# [{'类目': 'board', '接口数': 1}, {'类目': 'fund_flow', '接口数': 2}, {'类目': 'kline', '接口数': 1}, {'类目': 'market', '接口数': 1}, {'类目': 'trends', '接口数': 1}]
```

DataFrame 版（需 pandas，对齐 akshare `print(ak.search(...))` 体验）：

```python
print(em.search_df("板块 资金流"))
#            接口名      类目                              描述  有无文档  匹配分
# 0   board_constituent_em   board  板块成分股（含主力净流入...）   True  15.0
# 1  stock_list_em  market  沪深京 A 股全市场列表...        True  10.0

print(em.list_categories_df())
#        类目  接口数
# 0    board      1
# 1 fund_flow      2
# 2    kline      1
# 3   market      1
# 4   trends      1
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

运行期配置从环境变量读取（见 `.env.example`），构造期 fail-fast 校验：

| 环境变量 | 类型 | 默认值 | 描述 |
| --- | --- | --- | --- |
| `EM_PROXY_API` | `str` | 内置代理 API | 动态代理取 IP 地址 |
| `EM_PROXY_ENABLED` | `bool` | `True` | 是否启用代理 |
| `EM_PROXY_NUM` | `int` | `1` | 单次取 IP 数量 |
| `EM_PROXY_TTL_SEC` | `int` | `30` | 代理 IP 有效期（秒） |
| `EM_PROXY_SAFETY_MARGIN_SEC` | `int` | `3` | 过期前安全余量（秒），到期前自动换 IP |
| `EM_REQUEST_TIMEOUT_SEC` | `int` | `15` | 单次请求超时（秒） |
| `EM_MAX_RETRIES` | `int` | `10` | 最大重试次数 |

## 异常

| 异常 | `retryable` | 描述 |
| --- | --- | --- |
| `ConfigError` | 否 | 配置非法，立即上抛 |
| `NetworkError` | 是 | 连接失败 / 超时，换 IP 重试 |
| `EmptyResponseError` | 是 | 空响应（出口被封断开），换 IP 重试 |
| `HttpStatusError` | 5xx / 403 / 429 | 非预期状态码，按状态码判定 |
# 个股五档盘口接口

> 渠道：[eastmoney](../eastmoney.md) ｜ 源码：`src/em/channels/eastmoney/ashare_stocks/stock_bid_ask/stock_bid_ask_em.py`

## 接口名称

`stock_bid_ask_em` / `df_stock_bid_ask_em`：个股五档盘口与当日行情快照

## 目标地址

- <https://quote.eastmoney.com/sz000001.html>

## 描述

按代码与市场查询单只股票的买卖五档与当日行情，返回五档价格与挂单量、最新价、均价、今开、最高、最低、昨收、涨停价、跌停价、总手、金额、外盘、量比。走 `pushguest` 游客主机的 `stock/get`，对应 akshare `stock_bid_ask_em`。

**五档只在默认字段集里（实测）。** 不传 `fields` 时上游返回 58 个默认字段，其中含五档 `f11`–`f40`；一旦显式指定 `fields`，无论单独列出 `f11`–`f40` 还是与其他字段混在一起，五档都不返回。akshare 的字段列表里没有 `f11`–`f40` 却直接读取，按当前上游行为会报 `KeyError`。本接口不传 `fields`。

**与 akshare 相比少 4 项。** 默认字段集不含涨跌额（`f169`）、涨跌幅（`f170`）、换手率（`f168`）、内盘（`f161`），而显式请求这些字段又拿不到五档。本接口不为此多发一次请求，也不自行推算（如“内盘 = 总手 − 外盘”实测与上游差 1 手），所以不提供这 4 项。需要涨跌幅可从 `stock_list_em` 或 K 线取。

字段处理：

| 字段 | 处理 |
| --- | --- |
| 五档价格、最新、均价、高低开收、涨跌停（`f11`–`f39` 奇数位、`f43`–`f46`、`f51`、`f52`、`f60`、`f71`） | 除以 `10 ** f59`（A 股 `f59=2`） |
| 量比（`f50`） | 除以 100 |
| 五档挂单量、总手、外盘（`f12`–`f40` 偶数位、`f47`、`f49`） | 原值，单位**手**（akshare 乘 100 换成股，本接口不换） |
| 金额（`f48`） | 原值，单位元 |

北交所新股首日不设涨跌幅限制，上游涨跌停价与量比为 `"-"`，映射为 `None`。

## 查无此券

与 `stock_info_em` 相同：不存在的代码（`rc=100` / `102`、`data` 为 `null`）抛 `SecurityNotFoundError`，不换 IP 重试。详见 [stock_info_em.md](./stock_info_em.md)。

## 限量

- 单次只查一只股票，每次调用只发一个请求；`market` 支持 `sz` / `sh` / `bj`，未知回退 `sz`。
- 休市时返回最后一个交易日收盘时的盘口快照（本页数据为 2026-11-07 周六抓取，对应 11-06 收盘）。
- 上游对境外 IP 封禁 / 限流，需经国内动态代理访问；本接口已内置代理池 + 自动换 IP 重试。

## 输入参数 `StockBidAskQuery`

| 名称 | 类型 | 必填 | 默认值 | 描述 |
| --- | --- | --- | --- | --- |
| `code` | `str` | 否 | `"000001"` | 股票代码 |
| `market` | `str` | 否 | `"sz"` | 市场：`sz` 深市 / `sh` 沪市 / `bj` 北交所，未知回退 `sz` |

## 输出参数 `StockBidAsk`

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `code` / `name` / `market` | `str` | — | 代码（`f57`）/ 简称（`f58`）/ 市场 |
| `price` | `float \| None` | 元 | 最新价（`f43`） |
| `avg_price` | `float \| None` | 元 | 均价（`f71`） |
| `open` / `high` / `low` | `float \| None` | 元 | 今开（`f46`）/ 最高（`f44`）/ 最低（`f45`） |
| `pre_close` | `float \| None` | 元 | 昨收（`f60`） |
| `limit_up` / `limit_down` | `float \| None` | 元 | 涨停价（`f51`）/ 跌停价（`f52`），无涨跌幅限制时为 `None` |
| `volume` | `float \| None` | 手 | 总手（`f47`） |
| `turnover` | `float \| None` | 元 | 金额（`f48`） |
| `outer_volume` | `float \| None` | 手 | 外盘（`f49`） |
| `volume_ratio` | `float \| None` | — | 量比（`f50`） |
| `bids` | `tuple[OrderLevel, ...]` | — | 买一 ~ 买五，下标 0 为买一（`f19`/`f20` … `f11`/`f12`） |
| `asks` | `tuple[OrderLevel, ...]` | — | 卖一 ~ 卖五，下标 0 为卖一（`f39`/`f40` … `f31`/`f32`） |

`OrderLevel`：`price`（元）、`volume`（手），无挂单时为 `None`。

## 接口示例

```python
from em import stock_bid_ask_em, df_stock_bid_ask_em
from em.domain.queries import StockBidAskQuery

book = stock_bid_ask_em(StockBidAskQuery(code="000001", market="sz"))
for i, (b, a) in enumerate(zip(book.bids, book.asks), start=1):
    print(f"买{i} {b.price} {b.volume}  卖{i} {a.price} {a.volume}")

df = df_stock_bid_ask_em(StockBidAskQuery(code="600519", market="sh"))
# item / value 纵表：卖5 → 卖1、买1 → 买5（同 akshare），再接 最新/均价/总手/金额/量比/最高/最低/今开/昨收/涨停/跌停/外盘
```

## 数据示例（CLI）

```
✅ 000001 平安银行（sz）  最新:11.81  均价:11.75  昨收:11.64
------------------------------------------------------------
  卖5      11.86       16687 手
  卖4      11.85       44706 手
  卖3      11.84        3560 手
  卖2      11.83         717 手
  卖1      11.82        1019 手
  ------------------------------
  买1      11.81        4384 手
  买2      11.80        3026 手
  买3      11.79        1562 手
  买4      11.78        1001 手
  买5      11.77        1836 手
------------------------------------------------------------
  今开:11.62  最高:11.85  最低:11.57  涨停:12.80  跌停:10.48
  总手:1640276  金额:19.27亿  外盘:938074  量比:0.99
```

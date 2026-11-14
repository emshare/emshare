# 大宗交易每日统计接口

> 渠道：[eastmoney](../eastmoney.md) ｜ 源码：`src/em/channels/eastmoney/ashare_block_trade/block_trade_stock_daily/block_trade_stock_daily_em.py`

## 接口名称

`block_trade_stock_daily_em` / `df_block_trade_stock_daily_em`：大宗交易每日统计（按交易日期区间取各 A 股当天的大宗交易汇总）

## 目标地址

- <https://data.eastmoney.com/dzjy/dzjy_mrtj.html>

## 描述

按交易日期区间取各 A 股当天的大宗交易汇总，一只股票一天一行：成交笔数、成交总量、成交总额、成交均价、折溢率。对应 akshare `stock_dzjy_mrtj`（`RPT_BLOCKTRADE_STA`）。走数据中心报表，本接口按每页 500 条自动翻完全部页，返回 `ReportPage`。只请求用得到的列、查无数据返回空结果、查询写错抛 `QueryRejectedError`、翻页条数校验等公共处理见 [billboard_detail_em.md](../ashare_billboard/billboard_detail_em.md)。

akshare 不翻页，区间内超过 5000 行时只返回前 5000 行（实测一年 13255 行），本接口翻完全部页。

## 日期规则

- 日期为 `YYYYMMDD`。格式或日期不对在本地直接抛 `ValueError`。
- **都留空**：取最近一个有大宗交易的交易日（先查一次最新交易日，多 1 个请求）。
- **只给 `start_date`**：取到北京时间今天。**只给 `end_date`**：只取那一天。
- 周末、节假日没有大宗交易，单取这类日期返回 `total=0` 的空结果。

## 字段处理

- **只有 A 股**：实测 2026-11-04 至 11-12，本报表的（代码, 日期）与每日明细里 A 股的完全一致（302 组），不含 B 股、基金、债券。
- 是 `block_trade_detail_em` 按股票、按天的汇总：实测 2026-10-12 至 11-12 共 1051 行，成交笔数、成交总量、成交总额、溢价 / 折价笔数、流通市值占比与明细逐行相符。
- 单位换算：`volume` 上游给万股、`amount` 上游给万元（都是两位小数，即精确到百股、百元），统一成股、元；`premium_rate` 上游给比例，统一成 %。
- `avg_price` 成交均价是各笔成交价按成交量加权（实测上述 1051 行里 1044 行相符）；`premium_rate` 折溢率 = 成交均价 ÷ 当日收盘价 − 1。
- `premium_times` / `discount_times`：平价成交两边都不算，两者之和可以小于 `deal_times`。
- `change_after_*` 尚未到期为 `None`。`market` 由上游 `SECUCODE` 后缀得出，可连同 `code` 直接传给 `stock_kline_em`。
- 排序同 akshare：成交总额 / 流通市值倒序；末尾补交易日期倒序、代码升序，占比并列时翻页顺序也稳定。
- **当天的数据收盘后陆续入库**：实测 2026-11-13 当天，16:31 查到 A 股 30 笔、成交总额 2.85 亿元；17:48 再查是 49 笔，19:04 查到成交总额 4.90 亿元，到 20:48 没有再变。当天的数据晚些再取才完整。

## 输入参数 `BlockTradeStockDailyQuery`

| 名称 | 类型 | 必填 | 默认值 | 描述 |
| --- | --- | --- | --- | --- |
| `start_date` | `str \| None` | 否 | `None` | 起始日期 YYYYMMDD；起止都留空取最近一个有数据的交易日，只给起始取到今天 |
| `end_date` | `str \| None` | 否 | `None` | 结束日期 YYYYMMDD；只给结束日期时只取那一天 |

## 输出参数 `ReportPage[BlockTradeStockDaily]`

| 名称 | 类型 | 描述 |
| --- | --- | --- |
| `total` | `int` | 上游报告的条数，通常等于 `len(items)` |
| `items` | `tuple[BlockTradeStockDaily, ...]` | 全部记录，保持上游排序 |

`BlockTradeStockDaily` 字段：

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `code` | `str` | — | 股票代码（`SECURITY_CODE`） |
| `name` | `str` | — | 股票简称（`SECURITY_NAME_ABBR`） |
| `market` | `str \| None` | — | 市场：sh / sz / bj，可连同 code 传给 stock_kline_em（`SECUCODE`） |
| `trade_date` | `str \| None` | — | 交易日期 YYYY-MM-DD（`TRADE_DATE`） |
| `change_pct` | `float \| None` | % | 当日涨跌幅（`CHANGE_RATE`） |
| `close` | `float \| None` | 元 | 当日收盘价（`CLOSE_PRICE`） |
| `avg_price` | `float \| None` | 元 | 成交均价（各笔成交价按成交量加权）（`AVERAGE_PRICE`） |
| `premium_rate` | `float \| None` | % | 折溢率 = 成交均价 / 收盘价 - 1（上游比例，已换算）（`PREMIUM_RATIO`） |
| `deal_times` | `int \| None` | 笔 | 成交笔数（`DEAL_NUM`） |
| `premium_times` | `int \| None` | 笔 | 其中溢价成交的笔数（`PREMIUM_TIMES`） |
| `discount_times` | `int \| None` | 笔 | 其中折价成交的笔数（`DISCOUNT_TIMES`） |
| `volume` | `float \| None` | 股 | 成交总量（上游万股，已换算）（`VOLUME`） |
| `amount` | `float \| None` | 元 | 成交总额（上游万元，已换算）（`DEAL_AMT`） |
| `float_market_cap_ratio` | `float \| None` | % | 成交总额 / 流通市值（`TURNOVERRATE`） |
| `change_after_1d` | `float \| None` | % | 1 日后涨跌幅（未到期为 None）（`D1_CLOSE_ADJCHRATE`） |
| `change_after_5d` | `float \| None` | % | 5 日后涨跌幅（`D5_CLOSE_ADJCHRATE`） |
| `change_after_10d` | `float \| None` | % | 10 日后涨跌幅（`D10_CLOSE_ADJCHRATE`） |
| `change_after_20d` | `float \| None` | % | 20 日后涨跌幅（`D20_CLOSE_ADJCHRATE`） |

## DataFrame 列

`df_block_trade_stock_daily_em` 的列对齐 akshare `stock_dzjy_mrtj`，并在“证券简称”后加“市场”，末尾加溢价 / 折价笔数与 1 / 5 / 10 / 20 日后涨跌幅。“成交价”沿用 akshare 的列名，实际是成交均价（`avg_price`）。akshare 的“序号”列不输出。列顺序：交易日期 / 证券代码 / 证券简称 / 市场 / 涨跌幅 / 收盘价 / 成交价 / 折溢率 / 成交笔数 / 成交总量 / 成交总额 / 成交总额/流通市值 / 溢价笔数 / 折价笔数 / 1日后涨跌幅 / 5日后涨跌幅 / 10日后涨跌幅 / 20日后涨跌幅。

## 接口示例（领域模型）

```python
from em import block_trade_stock_daily_em
from em.domain.queries import BlockTradeStockDailyQuery

page = block_trade_stock_daily_em(BlockTradeStockDailyQuery("20261112", "20261112"))
print(page.total)
for item in page.items[:2]:
    print(item)
```

## 数据示例（领域模型）

```
40
BlockTradeStockDaily(code='301395', name='仁信新材', market='sz', trade_date='2026-11-12', change_pct=-2.386, close=13.91, avg_price=11.41, premium_rate=-17.9726815241, deal_times=4, premium_times=0, discount_times=4, volume=2253000.0, amount=25706700.0, float_market_cap_ratio=1.428730961632, change_after_1d=5.89503954, change_after_5d=None, change_after_10d=None, change_after_20d=None)
BlockTradeStockDaily(code='301051', name='信濠光电', market='sz', trade_date='2026-11-12', change_pct=-2.8996, close=13.73, avg_price=13.73, premium_rate=0.0, deal_times=2, premium_times=0, discount_times=0, volume=1483400.0, amount=20367100.0, float_market_cap_ratio=0.656845667033, change_after_1d=0.80116533, change_after_5d=None, change_after_10d=None, change_after_20d=None)
```

## 接口示例（`DataFrame`，akshare 风格中文列名）

```python
from em import df_block_trade_stock_daily_em
from em.domain.queries import BlockTradeStockDailyQuery

df = df_block_trade_stock_daily_em(BlockTradeStockDailyQuery("20261112", "20261112"))
```

## 数据示例（`DataFrame`）

```
     交易日期 证券代码  证券简称 市场  涨跌幅  收盘价  成交价     折溢率  成交笔数    成交总量     成交总额  成交总额/流通市值  溢价笔数  折价笔数  1日后涨跌幅 5日后涨跌幅 10日后涨跌幅 20日后涨跌幅
0  2026-11-12   301395  仁信新材   sz -2.3860   13.91   11.41 -17.972682         4   2253000.0   25706700.0           1.428731         0         4     5.895040        None         None         None
1  2026-11-12   301051  信濠光电   sz -2.8996   13.73   13.73   0.000000         2   1483400.0   20367100.0           0.656846         0         0     0.801165        None         None         None
2  2026-11-12   600299    安迪苏   sh -1.5513    8.25    8.25   0.000000         2  17000000.0  140250000.0           0.551988         0         0    -0.606061        None         None         None
```

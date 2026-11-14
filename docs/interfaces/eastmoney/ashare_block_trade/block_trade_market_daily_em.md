# 大宗交易市场统计接口

> 渠道：[eastmoney](../eastmoney.md) ｜ 源码：`src/em/channels/eastmoney/ashare_block_trade/block_trade_market_daily/block_trade_market_daily_em.py`

## 接口名称

`block_trade_market_daily_em` / `df_block_trade_market_daily_em`：大宗交易市场统计（一个交易日一行：A 股大宗交易成交总额与溢价、折价成交额）

## 目标地址

- <https://data.eastmoney.com/dzjy/dzjy_sctj.html>

## 描述

一个交易日一行：沪深京 A 股大宗交易的成交总额、溢价 / 折价成交额及占比，以及当日上证指数。对应 akshare `stock_dzjy_sctj`（`PRT_BLOCKTRADE_MARKET_STA`，上游报表名就是 `PRT` 开头）。akshare 没有参数、一次取全部历史；本接口另可按日期区间取。走数据中心报表，本接口按每页 500 条自动翻完全部页，返回 `ReportPage`。只请求用得到的列、查无数据返回空结果、查询写错抛 `QueryRejectedError`、翻页条数校验等公共处理见 [billboard_detail_em.md](../ashare_billboard/billboard_detail_em.md)。

## 日期规则

- 日期为 `YYYYMMDD`。格式或日期不对在本地直接抛 `ValueError`。
- **都留空**：取全部历史，**不是最近一天**（与每日明细、每日统计不同：本报表是一天一行的时间序列）。实测 2026-11-13：2000-08-29 起共 4678 行，翻 10 页。
- **只给 `start_date`**：取到北京时间今天。**只给 `end_date`**：只取那一天。
- 周末、节假日没有数据，单取这类日期返回 `total=0` 的空结果。

## 字段处理

- **只统计 A 股**：实测 2026-11-09 至 11-13 五个交易日，成交总额、溢价 / 折价成交额与 `block_trade_detail_em` 里 A 股各笔之和逐日相等，不含 B 股、基金、债券。
- 溢价 / 折价按每笔成交的折溢率正负划分；平价成交（折溢率为 0）两边都不算，所以 `premium_amount + discount_amount` 可以小于 `amount`。
- 金额单位为元。两个占比单位为 %：溢价 / 折价成交额 ÷ 成交总额。
- `sh_index` 是上证指数收盘点位：上游列名 `SZ_INDEX` 的 SZ 是“上证”的拼音首字母，不是深证；上游以字符串给出，已转成数值。实测与每日明细里沪市股票的指数收盘列（`INDEX_CLOSE`）逐日相等。
- **当天的数据收盘后陆续入库**：实测 2026-11-13 当天，16:31 查到 A 股 30 笔、成交总额 2.85 亿元；17:48 再查是 49 笔，19:04 查到成交总额 4.90 亿元，到 20:48 没有再变。当天的数据晚些再取才完整。
- 排序同 akshare：交易日期倒序。

## 输入参数 `BlockTradeMarketDailyQuery`

| 名称 | 类型 | 必填 | 默认值 | 描述 |
| --- | --- | --- | --- | --- |
| `start_date` | `str \| None` | 否 | `None` | 起始日期 YYYYMMDD；起止都留空取全部历史（2000-08-29 起），只给起始取到今天 |
| `end_date` | `str \| None` | 否 | `None` | 结束日期 YYYYMMDD；只给结束日期时只取那一天 |

## 输出参数 `ReportPage[BlockTradeMarketDaily]`

| 名称 | 类型 | 描述 |
| --- | --- | --- |
| `total` | `int` | 上游报告的条数，通常等于 `len(items)` |
| `items` | `tuple[BlockTradeMarketDaily, ...]` | 全部记录，保持上游排序 |

`BlockTradeMarketDaily` 字段：

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `trade_date` | `str` | — | 交易日期 YYYY-MM-DD（`TRADE_DATE`） |
| `sh_index` | `float \| None` | 点 | 上证指数收盘点位（`SZ_INDEX`） |
| `sh_index_change_pct` | `float \| None` | % | 上证指数涨跌幅（`SZ_CHANGE_RATE`） |
| `amount` | `float \| None` | 元 | 大宗交易成交总额（只含 A 股）（`BLOCKTRADE_DEAL_AMT`） |
| `premium_amount` | `float \| None` | 元 | 溢价成交总额（`PREMIUM_DEAL_AMT`） |
| `premium_ratio` | `float \| None` | % | 溢价成交总额占比（`PREMIUM_RATIO`） |
| `discount_amount` | `float \| None` | 元 | 折价成交总额（`DISCOUNT_DEAL_AMT`） |
| `discount_ratio` | `float \| None` | % | 折价成交总额占比（`DISCOUNT_RATIO`） |

## DataFrame 列

`df_block_trade_market_daily_em` 的列对齐 akshare `stock_dzjy_sctj`。akshare 的“序号”列不输出。列顺序：交易日期 / 上证指数 / 上证指数涨跌幅 / 大宗交易成交总额 / 溢价成交总额 / 溢价成交总额占比 / 折价成交总额 / 折价成交总额占比。

## 接口示例（领域模型）

```python
from em import block_trade_market_daily_em
from em.domain.queries import BlockTradeMarketDailyQuery

page = block_trade_market_daily_em(BlockTradeMarketDailyQuery("20261109", "20261113"))
print(page.total)
for item in page.items[:2]:
    print(item)
```

## 数据示例（领域模型）

```
5
BlockTradeMarketDaily(trade_date='2026-11-13', sh_index=3634.353, sh_index_change_pct=-0.587459015799, amount=489806500.0, premium_amount=0.0, premium_ratio=0.0, discount_amount=110190300.0, discount_ratio=22.496700227539)
BlockTradeMarketDaily(trade_date='2026-11-12', sh_index=3655.8295, sh_index_change_pct=-0.674156698933, amount=843182600.0, premium_amount=86593100.0, premium_ratio=10.269792094856, discount_amount=201519700.0, discount_ratio=23.899888351586)
```

## 接口示例（`DataFrame`，akshare 风格中文列名）

```python
from em import df_block_trade_market_daily_em
from em.domain.queries import BlockTradeMarketDailyQuery

df = df_block_trade_market_daily_em(BlockTradeMarketDailyQuery("20261109", "20261113"))
```

## 数据示例（`DataFrame`）

```
     交易日期   上证指数  上证指数涨跌幅  大宗交易成交总额  溢价成交总额  溢价成交总额占比  折价成交总额  折价成交总额占比
0  2026-11-13  3634.3530       -0.587459      4.898065e+08           0.0          0.000000   110190300.0         22.496700
1  2026-11-12  3655.8295       -0.674157      8.431826e+08    86593100.0         10.269792   201519700.0         23.899888
2  2026-11-11  3680.6428        0.461806      2.072442e+09   591500300.0         28.541221   832705900.0         40.179934
```

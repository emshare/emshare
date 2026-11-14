# 大宗交易活跃 A 股统计接口

> 渠道：[eastmoney](../eastmoney.md) ｜ 源码：`src/em/channels/eastmoney/ashare_block_trade/block_trade_stock_stats/block_trade_stock_stats_em.py`

## 接口名称

`block_trade_stock_stats_em` / `df_block_trade_stock_stats_em`：大宗交易活跃 A 股统计（统计周期内各股的成交笔数、总成交额、折溢率与之后的平均涨跌幅）

## 目标地址

- <https://data.eastmoney.com/dzjy/dzjy_hygtj.html>

## 描述

按统计周期取有过大宗交易的 A 股，一只股票一行：成交笔数（其中溢价 / 折价笔数）、总成交额、折溢率、上榜日后 1 / 5 / 10 / 20 日平均涨跌幅。对应 akshare `stock_dzjy_hygtj`（`RPT_BLOCKTRADE_ACSTA`）。走数据中心报表，本接口按每页 500 条自动翻完全部页，返回 `ReportPage`。只请求用得到的列、查无数据返回空结果、查询写错抛 `QueryRejectedError`、翻页条数校验等公共处理见 [billboard_detail_em.md](../ashare_billboard/billboard_detail_em.md)。

## 统计周期

- `period` 取 `1mo` / `3mo` / `6mo` / `1y`，对应东财页面的“近一月 / 近三月 / 近六月 / 近一年”（上游 `DATE_TYPE_CODE` 为 1 / 3 / 6 / 12）。未知值回退 `1mo`。默认 `1mo`（akshare 默认近三月）。
- **周期按自然月算，从 N 个月前同一天的次日起**：实测 2026-11-13 取 `1mo`，统计的是 10-14 至 11-13 的成交，成交笔数、总成交额与每日明细逐只一致（475 只）；`3mo` 同样逐只一致（884 只）。
- `6mo` / `1y` 比按明细统计的少几只股票：实测少 2 只 / 13 只（萃华退、退市创兴、东兴证券等），抽查其中 6 只，当前都没有行情。
- 只有这四个周期可选，不能指定起止日期。实测 2026-11-13：`1mo` 475 只，`3mo` 884 只，`6mo` 1660 只，`1y` 2595 只。

## 字段处理

- `deal_times` 是成交笔数：东财页面和 akshare 叫“上榜次数”，实测等于周期内每日明细的笔数，同一天成交多笔算多次。
- **`avg_change_after_*` 是“已到期各笔的 N 日后涨跌幅之和 ÷ 周期内全部笔数”**（实测 `1mo` / `3mo` / `1y` 逐只相符）：还没到期的成交按 0 计入，周期越短、N 越大，被摊薄得越多。实测 `1mo` 的 475 只里，20 日档与“只对已到期的求平均”结果相同的只有 38 只。
- `close` / `change_pct` 是最近上榜日（`latest_date`）当天的收盘价与涨跌幅，不是最新交易日的（实测 `1mo` 的 475 只都与当天明细一致）。
- `amount` 上游给万元，统一成元。`premium_rate` 上游给比例，统一成 %：等于 总成交额 ÷ Σ(成交量 × 当日收盘价) − 1。
- `float_market_cap_ratio` 是周期内各笔“成交额 / 流通市值”之和。
- `premium_times` / `discount_times`：平价成交两边都不算，两者之和可以小于 `deal_times`。
- `market` 由上游 `SECUCODE` 后缀得出，可连同 `code` 直接传给 `stock_kline_em`。
- 排序同 akshare：成交笔数倒序、代码倒序；周期内一只股票一行。

## 输入参数 `BlockTradeStockStatsQuery`

| 名称 | 类型 | 必填 | 默认值 | 描述 |
| --- | --- | --- | --- | --- |
| `period` | `str` | 否 | `"1mo"` | 统计周期：1mo 近一月 / 3mo 近三月 / 6mo 近六月 / 1y 近一年，未知回退 1mo |

## 输出参数 `ReportPage[BlockTradeStockStats]`

| 名称 | 类型 | 描述 |
| --- | --- | --- |
| `total` | `int` | 上游报告的条数，通常等于 `len(items)` |
| `items` | `tuple[BlockTradeStockStats, ...]` | 全部记录，保持上游排序 |

`BlockTradeStockStats` 字段：

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `code` | `str` | — | 股票代码（`SECURITY_CODE`） |
| `name` | `str` | — | 股票简称（`SECURITY_NAME_ABBR`） |
| `market` | `str \| None` | — | 市场：sh / sz / bj，可连同 code 传给 stock_kline_em（`SECUCODE`） |
| `close` | `float \| None` | 元 | 最近上榜日的收盘价（`CLOSE_PRICE`） |
| `change_pct` | `float \| None` | % | 最近上榜日的涨跌幅（`CHANGE_RATE`） |
| `latest_date` | `str \| None` | — | 最近上榜日 YYYY-MM-DD（周期内最后一次有大宗交易的交易日）（`TRADE_DATE`） |
| `deal_times` | `int \| None` | 笔 | 成交笔数（东财页面叫“上榜次数”）（`DEAL_NUM`） |
| `premium_times` | `int \| None` | 笔 | 其中溢价成交的笔数（`PREMIUM_TIMES`） |
| `discount_times` | `int \| None` | 笔 | 其中折价成交的笔数（`DISCOUNT_TIMES`） |
| `amount` | `float \| None` | 元 | 总成交额（上游万元，已换算）（`DEAL_AMT`） |
| `premium_rate` | `float \| None` | % | 折溢率 = 总成交额 / Σ(成交量 × 当日收盘价) - 1（上游比例，已换算）（`PREMIUM_RATIO`） |
| `float_market_cap_ratio` | `float \| None` | % | 成交总额 / 流通市值（各笔之和）（`SUM_TURNOVERRATE`） |
| `avg_change_after_1d` | `float \| None` | % | 上榜日后 1 日平均涨跌幅（已到期各笔之和 ÷ 全部笔数）（`D1_AVG_ADJCHRATE`） |
| `avg_change_after_5d` | `float \| None` | % | 上榜日后 5 日平均涨跌幅（已到期各笔之和 ÷ 全部笔数）（`D5_AVG_ADJCHRATE`） |
| `avg_change_after_10d` | `float \| None` | % | 上榜日后 10 日平均涨跌幅（已到期各笔之和 ÷ 全部笔数）（`D10_AVG_ADJCHRATE`） |
| `avg_change_after_20d` | `float \| None` | % | 上榜日后 20 日平均涨跌幅（已到期各笔之和 ÷ 全部笔数）（`D20_AVG_ADJCHRATE`） |

## DataFrame 列

`df_block_trade_stock_stats_em` 的列对齐 akshare `stock_dzjy_hygtj`，并在“证券简称”后加“市场”。“最新价”“上榜次数”沿用 akshare 的列名，实际是最近上榜日的收盘价（`close`）与成交笔数（`deal_times`）。akshare 的“序号”列不输出。列顺序：证券代码 / 证券简称 / 市场 / 最新价 / 涨跌幅 / 最近上榜日 / 上榜次数-总计 / 上榜次数-溢价 / 上榜次数-折价 / 总成交额 / 折溢率 / 成交总额/流通市值 / 上榜日后平均涨跌幅-1日 / 上榜日后平均涨跌幅-5日 / 上榜日后平均涨跌幅-10日 / 上榜日后平均涨跌幅-20日。

## 接口示例（领域模型）

```python
from em import block_trade_stock_stats_em
from em.domain.queries import BlockTradeStockStatsQuery

page = block_trade_stock_stats_em(BlockTradeStockStatsQuery(period="1mo"))
print(page.total)
for item in page.items[:2]:
    print(item)
```

## 数据示例（领域模型）

```
475
BlockTradeStockStats(code='688293', name='奥浦迈', market='sh', close=68.83, change_pct=2.1368, latest_date='2026-11-12', deal_times=67, premium_times=0, discount_times=67, amount=259695700.0, premium_rate=-9.1888054148, float_market_cap_ratio=3.254831334014, avg_change_after_1d=-1.512896822985, avg_change_after_5d=0.690675921642, avg_change_after_10d=2.61638878806, avg_change_after_20d=0.944005806269)
BlockTradeStockStats(code='300750', name='宁德时代', market='sz', close=237.7, change_pct=-0.9583, latest_date='2026-11-13', deal_times=39, premium_times=0, discount_times=0, amount=689137700.0, premium_rate=-0.0009417478, float_market_cap_ratio=0.065215293266, avg_change_after_1d=-0.070296745128, avg_change_after_5d=-5.449585187949, avg_change_after_10d=-1.246022444103, avg_change_after_20d=-3.264850835897)
```

## 接口示例（`DataFrame`，akshare 风格中文列名）

```python
from em import df_block_trade_stock_stats_em
from em.domain.queries import BlockTradeStockStatsQuery

df = df_block_trade_stock_stats_em(BlockTradeStockStatsQuery(period="1mo"))
```

## 数据示例（`DataFrame`）

```
  证券代码  证券简称 市场  最新价  涨跌幅  最近上榜日  上榜次数-总计  上榜次数-溢价  上榜次数-折价     总成交额    折溢率  成交总额/流通市值  上榜日后平均涨跌幅-1日  上榜日后平均涨跌幅-5日  上榜日后平均涨跌幅-10日  上榜日后平均涨跌幅-20日
0   688293    奥浦迈   sh   68.83  2.1368  2026-11-12             67              0             67  259695700.0 -9.188805           3.254831               -1.512897                0.690676                 2.616389                 0.944006
1   300750  宁德时代   sz  237.70 -0.9583  2026-11-13             39              0              0  689137700.0 -0.000942           0.065215               -0.070297               -5.449585                -1.246022                -3.264851
2   601899  紫金矿业   sh   27.86 -1.1356  2026-11-11             36              0              0  616483300.0  0.000011           0.105056               -0.100196               -0.272385                -1.682830                -1.870459
```

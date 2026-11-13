# 个股上榜统计接口

> 渠道：[eastmoney](../eastmoney.md) ｜ 源码：`src/em/channels/eastmoney/ashare_billboard/billboard_stock_stats/billboard_stock_stats_em.py`

## 接口名称

`billboard_stock_stats_em` / `df_billboard_stock_stats_em`：个股上榜统计（统计周期内各股的上榜次数与龙虎榜、机构买卖合计）

## 目标地址

- <https://data.eastmoney.com/stock/tradedetail.html>

## 描述

按统计周期取全部上过榜的股票，一只股票一行：上榜次数、龙虎榜买卖合计、机构席位买卖合计、近 1 / 3 / 6 个月与近 1 年涨跌幅。对应 akshare `stock_lhb_stock_statistic_em`（`RPT_BILLBOARD_TRADEALL`）。走数据中心报表，单页最多 500 条，本接口自动翻完全部页，返回 `ReportPage`。只请求用得到的列、查无数据返回空结果、查询写错抛 `QueryRejectedError`、翻页条数校验等公共处理见 [billboard_detail_em.md](./billboard_detail_em.md)。

## 统计周期

- `period` 取 `1mo` / `3mo` / `6mo` / `1y`，对应东财页面的“近一月 / 近三月 / 近六月 / 近一年”（上游 `STATISTICS_CYCLE` 为 `01` ~ `04`）。未知值回退 `1mo`。
- 只有这四个周期可选，不能指定起止日期。
- 周期列一并请求：上游对拼错的过滤字段静默忽略、返回整张表，而拼错的返回列会报 9501，借此把上游改名暴露出来。

## 字段处理

- 金额单位为元，涨跌幅单位为 %。
- `market` 由上游 `SECUCODE` 后缀得出（`000530.SZ` → `sz`），可连同 `code` 直接传给 `stock_kline_em`。
- `close` / `change_pct` 是最近上榜日（`latest_date`）当天的收盘价与涨跌幅，不是最新交易日的（实测 2026-11-13 抽 3 只最近上榜日较早的股票，与当日龙虎榜详情一致）。
- `institution_buy_times` / `institution_sell_times` 是机构席位出现的次数，不是机构家数。
- 排序同 akshare：上榜次数、最近上榜日倒序，代码升序。
- 实测 2026-11-13：近一月 653 只。

## 输入参数 `BillboardStockStatsQuery`

| 名称 | 类型 | 必填 | 默认值 | 描述 |
| --- | --- | --- | --- | --- |
| `period` | `str` | 否 | `"1mo"` | 统计周期：1mo 近一月 / 3mo 近三月 / 6mo 近六月 / 1y 近一年，未知回退 1mo |

## 输出参数 `ReportPage[BillboardStockStats]`

| 名称 | 类型 | 描述 |
| --- | --- | --- |
| `total` | `int` | 上游报告的条数，通常等于 `len(items)` |
| `items` | `tuple[BillboardStockStats, ...]` | 全部记录，保持上游排序 |

`BillboardStockStats` 字段：

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `code` | `str` | — | 股票代码（`SECURITY_CODE`） |
| `name` | `str` | — | 股票简称（`SECURITY_NAME_ABBR`） |
| `market` | `str \| None` | — | 市场：sh / sz / bj，可连同 code 传给 stock_kline_em（`SECUCODE`） |
| `latest_date` | `str \| None` | — | 最近上榜日 YYYY-MM-DD（`LATEST_TDATE`） |
| `close` | `float \| None` | 元 | 收盘价（`CLOSE_PRICE`） |
| `change_pct` | `float \| None` | % | 涨跌幅（`CHANGE_RATE`） |
| `billboard_times` | `int \| None` | 次 | 上榜次数（`BILLBOARD_TIMES`） |
| `net_buy` | `float \| None` | 元 | 龙虎榜净买额（`BILLBOARD_NET_BUY`） |
| `buy` | `float \| None` | 元 | 龙虎榜买入额（`BILLBOARD_BUY_AMT`） |
| `sell` | `float \| None` | 元 | 龙虎榜卖出额（`BILLBOARD_SELL_AMT`） |
| `billboard_turnover` | `float \| None` | 元 | 龙虎榜总成交额（`BILLBOARD_DEAL_AMT`） |
| `institution_buy_times` | `int \| None` | 次 | 买方机构次数（`ORG_BUY_TIMES`） |
| `institution_sell_times` | `int \| None` | 次 | 卖方机构次数（`ORG_SELL_TIMES`） |
| `institution_net_buy` | `float \| None` | 元 | 机构买入净额（`ORG_NET_BUY`） |
| `institution_buy` | `float \| None` | 元 | 机构买入总额（`ORG_BUY_AMT`） |
| `institution_sell` | `float \| None` | 元 | 机构卖出总额（`ORG_SELL_AMT`） |
| `change_1mo` | `float \| None` | % | 近 1 个月涨跌幅（`IPCT1M`） |
| `change_3mo` | `float \| None` | % | 近 3 个月涨跌幅（`IPCT3M`） |
| `change_6mo` | `float \| None` | % | 近 6 个月涨跌幅（`IPCT6M`） |
| `change_1y` | `float \| None` | % | 近 1 年涨跌幅（`IPCT1Y`） |

## DataFrame 列

`df_billboard_stock_stats_em` 的列对齐 akshare `stock_lhb_stock_statistic_em`，并在“名称”后加“市场”。akshare 的“序号”列不输出。列顺序：代码 / 名称 / 市场 / 最近上榜日 / 收盘价 / 涨跌幅 / 上榜次数 / 龙虎榜净买额 / 龙虎榜买入额 / 龙虎榜卖出额 / 龙虎榜总成交额 / 买方机构次数 / 卖方机构次数 / 机构买入净额 / 机构买入总额 / 机构卖出总额 / 近1个月涨跌幅 / 近3个月涨跌幅 / 近6个月涨跌幅 / 近1年涨跌幅。

## 接口示例（领域模型）

```python
from em import billboard_stock_stats_em
from em.domain.queries import BillboardStockStatsQuery

page = billboard_stock_stats_em(BillboardStockStatsQuery(period="1mo"))
print(page.total)
for item in page.items[:2]:
    print(item)
```

## 数据示例（领域模型）

```
653
BillboardStockStats(code='000530', name='冰山冷热', market='sz', latest_date='2026-11-12', close=10.95, change_pct=-2.9255, billboard_times=24, net_buy=164778819.27, buy=5739705799.48, sell=5574926980.21, billboard_turnover=11314632779.69, institution_buy_times=84, institution_sell_times=84, institution_net_buy=53606714.14, institution_buy=2894357177.89, institution_sell=2840750463.75, change_1mo=105.44090056, change_3mo=117.26190476, change_6mo=81.32877614, change_1y=55.13401605)
BillboardStockStats(code='002343', name='慈文传媒', market='sz', latest_date='2026-11-12', close=10.04, change_pct=3.5052, billboard_times=21, net_buy=-104200809.18, buy=4291919584.78, sell=4396120393.96, billboard_turnover=8688039978.74, institution_buy_times=68, institution_sell_times=64, institution_net_buy=92156171.58, institution_buy=1901511875.17, institution_sell=1809355703.59, change_1mo=65.13157895, change_3mo=90.87452471, change_6mo=62.45954693, change_1y=24.87562189)
```

## 接口示例（`DataFrame`，akshare 风格中文列名）

```python
from em import df_billboard_stock_stats_em
from em.domain.queries import BillboardStockStatsQuery

df = df_billboard_stock_stats_em(BillboardStockStatsQuery(period="1mo"))
```

## 数据示例（`DataFrame`）

```
     代码      名称 市场  最近上榜日  收盘价   涨跌幅  上榜次数  龙虎榜净买额  龙虎榜买入额  龙虎榜卖出额  龙虎榜总成交额  买方机构次数  卖方机构次数  机构买入净额  机构买入总额  机构卖出总额  近1个月涨跌幅  近3个月涨跌幅  近6个月涨跌幅  近1年涨跌幅
0  000530  冰山冷热   sz  2026-11-12   10.95  -2.9255        24  1.647788e+08  5.739706e+09  5.574927e+09    1.131463e+10            84            84  5.360671e+07  2.894357e+09  2.840750e+09     105.440901     117.261905      81.328776    55.134016
1  002343  慈文传媒   sz  2026-11-12   10.04   3.5052        21 -1.042008e+08  4.291920e+09  4.396120e+09    8.688040e+09            68            64  9.215617e+07  1.901512e+09  1.809356e+09      65.131579      90.874525      62.459547    24.875622
2  301052  果麦文化   sz  2026-11-12   43.88 -10.3758        20 -1.239001e+08  3.000093e+09  3.123993e+09    6.124086e+09            88            89 -1.554555e+08  2.062817e+09  2.218273e+09      72.823946      75.520000      29.134785     0.428615
```

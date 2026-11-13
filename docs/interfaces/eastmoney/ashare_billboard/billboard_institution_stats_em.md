# 机构席位追踪接口

> 渠道：[eastmoney](../eastmoney.md) ｜ 源码：`src/em/channels/eastmoney/ashare_billboard/billboard_institution_stats/billboard_institution_stats_em.py`

## 接口名称

`billboard_institution_stats_em` / `df_billboard_institution_stats_em`：机构席位追踪（统计周期内各股上榜时机构席位的买卖次数与金额合计）

## 目标地址

- <https://data.eastmoney.com/stock/jgstatistic.html>

## 描述

按统计周期取有机构席位参与的股票，一只股票一行：上榜次数、机构席位的买入 / 卖出次数与金额、机构净买额、近 1 / 3 / 6 个月与近 1 年涨跌幅。对应 akshare `stock_lhb_jgstatistic_em`（`RPT_ORGANIZATION_SEATNEW`）。走数据中心报表，单页最多 500 条，本接口自动翻完全部页，返回 `ReportPage`。只请求用得到的列、查无数据返回空结果、查询写错抛 `QueryRejectedError`、翻页条数校验等公共处理见 [billboard_detail_em.md](./billboard_detail_em.md)。

## 统计周期

- `period` 取 `1mo` / `3mo` / `6mo` / `1y`，对应东财页面的“近一月 / 近三月 / 近六月 / 近一年”（上游 `STATISTICSCYCLE` 为 `01` ~ `04`）。未知值回退 `1mo`。
- 只有这四个周期可选，不能指定起止日期。
- 周期列一并请求：上游对拼错的过滤字段静默忽略、返回整张表，而拼错的返回列会报 9501，借此把上游改名暴露出来。

## 字段处理

- 本报表的周期列是 `STATISTICSCYCLE`（没有下划线），与个股上榜统计的 `STATISTICS_CYCLE` 不同。
- 金额单位为元，涨跌幅单位为 %。
- `billboard_times` 可能小于 `billboard_stock_stats_em` 里同一只股票的上榜次数（实测 2026-11-13 近一月 000530：本接口 23 次，个股上榜统计 24 次），推测本报表只统计有机构席位参与的上榜。
- `market` 由上游 `SECUCODE` 后缀得出，可连同 `code` 直接传给 `stock_kline_em`。
- 排序同 akshare：上榜次数倒序，代码升序。
- 实测 2026-11-13：近一月 487 只。

## 输入参数 `BillboardInstitutionStatsQuery`

| 名称 | 类型 | 必填 | 默认值 | 描述 |
| --- | --- | --- | --- | --- |
| `period` | `str` | 否 | `"1mo"` | 统计周期：1mo 近一月 / 3mo 近三月 / 6mo 近六月 / 1y 近一年，未知回退 1mo |

## 输出参数 `ReportPage[BillboardInstitutionStats]`

| 名称 | 类型 | 描述 |
| --- | --- | --- |
| `total` | `int` | 上游报告的条数，通常等于 `len(items)` |
| `items` | `tuple[BillboardInstitutionStats, ...]` | 全部记录，保持上游排序 |

`BillboardInstitutionStats` 字段：

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `code` | `str` | — | 股票代码（`SECURITY_CODE`） |
| `name` | `str` | — | 股票简称（`SECURITY_NAME_ABBR`） |
| `market` | `str \| None` | — | 市场：sh / sz / bj，可连同 code 传给 stock_kline_em（`SECUCODE`） |
| `close` | `float \| None` | 元 | 收盘价（`CLOSE_PRICE`） |
| `change_pct` | `float \| None` | % | 涨跌幅（`CHANGE_RATE`） |
| `billboard_turnover` | `float \| None` | 元 | 龙虎榜成交金额（`AMOUNT`） |
| `billboard_times` | `int \| None` | 次 | 上榜次数（`ONLIST_TIMES`） |
| `institution_buy` | `float \| None` | 元 | 机构买入额（`BUY_AMT`） |
| `institution_buy_times` | `int \| None` | 次 | 机构买入次数（`BUY_TIMES`） |
| `institution_sell` | `float \| None` | 元 | 机构卖出额（`SELL_AMT`） |
| `institution_sell_times` | `int \| None` | 次 | 机构卖出次数（`SELL_TIMES`） |
| `institution_net_buy` | `float \| None` | 元 | 机构净买额（`NET_BUY_AMT`） |
| `change_1mo` | `float \| None` | % | 近 1 个月涨跌幅（`M1_CLOSE_ADJCHRATE`） |
| `change_3mo` | `float \| None` | % | 近 3 个月涨跌幅（`M3_CLOSE_ADJCHRATE`） |
| `change_6mo` | `float \| None` | % | 近 6 个月涨跌幅（`M6_CLOSE_ADJCHRATE`） |
| `change_1y` | `float \| None` | % | 近 1 年涨跌幅（`Y1_CLOSE_ADJCHRATE`） |

## DataFrame 列

`df_billboard_institution_stats_em` 的列对齐 akshare `stock_lhb_jgstatistic_em`，并在“名称”后加“市场”。akshare 的“序号”列不输出。列顺序：代码 / 名称 / 市场 / 收盘价 / 涨跌幅 / 龙虎榜成交金额 / 上榜次数 / 机构买入额 / 机构买入次数 / 机构卖出额 / 机构卖出次数 / 机构净买额 / 近1个月涨跌幅 / 近3个月涨跌幅 / 近6个月涨跌幅 / 近1年涨跌幅。

## 接口示例（领域模型）

```python
from em import billboard_institution_stats_em
from em.domain.queries import BillboardInstitutionStatsQuery

page = billboard_institution_stats_em(BillboardInstitutionStatsQuery(period="1mo"))
print(page.total)
for item in page.items[:2]:
    print(item)
```

## 数据示例（领域模型）

```
487
BillboardInstitutionStats(code='000530', name='冰山冷热', market='sz', close=10.95, change_pct=-2.9255, billboard_turnover=11022781805.91, billboard_times=23, institution_buy=2894357177.89, institution_buy_times=84, institution_sell=2840750463.75, institution_sell_times=84, institution_net_buy=53606714.14, change_1mo=105.44090056, change_3mo=117.26190476, change_6mo=81.32877614, change_1y=55.13401605)
BillboardInstitutionStats(code='002343', name='慈文传媒', market='sz', close=10.04, change_pct=3.5052, billboard_turnover=8377845221.74, billboard_times=20, institution_buy=1901511875.17, institution_buy_times=68, institution_sell=1809355703.59, institution_sell_times=64, institution_net_buy=92156171.58, change_1mo=65.13157895, change_3mo=90.87452471, change_6mo=62.45954693, change_1y=24.87562189)
```

## 接口示例（`DataFrame`，akshare 风格中文列名）

```python
from em import df_billboard_institution_stats_em
from em.domain.queries import BillboardInstitutionStatsQuery

df = df_billboard_institution_stats_em(BillboardInstitutionStatsQuery(period="1mo"))
```

## 数据示例（`DataFrame`）

```
     代码      名称 市场  收盘价   涨跌幅  龙虎榜成交金额  上榜次数    机构买入额  机构买入次数    机构卖出额  机构卖出次数    机构净买额  近1个月涨跌幅  近3个月涨跌幅  近6个月涨跌幅  近1年涨跌幅
0  000530  冰山冷热   sz   10.95  -2.9255    1.102278e+10        23  2.894357e+09            84  2.840750e+09            84  5.360671e+07     105.440901     117.261905      81.328776    55.134016
1  002343  慈文传媒   sz   10.04   3.5052    8.377845e+09        20  1.901512e+09            68  1.809356e+09            64  9.215617e+07      65.131579      90.874525      62.459547    24.875622
2  301052  果麦文化   sz   43.88 -10.3758    6.124086e+09        20  2.062817e+09            88  2.218273e+09            89 -1.554555e+08      72.823946      75.520000      29.134785     0.428615
```

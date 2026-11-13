# 营业部统计接口

> 渠道：[eastmoney](../eastmoney.md) ｜ 源码：`src/em/channels/eastmoney/ashare_billboard/billboard_branch_stats/billboard_branch_stats_em.py`

## 接口名称

`billboard_branch_stats_em` / `df_billboard_branch_stats_em`：营业部统计（统计周期内各营业部的上榜次数与买卖次数、金额合计）

## 目标地址

- <https://data.eastmoney.com/stock/traderstatistic.html>

## 描述

按统计周期取各营业部的龙虎榜成交金额、上榜次数、买入 / 卖出金额与次数，一家营业部一行。对应 akshare `stock_lhb_traderstatistic_em`（`RPT_OPERATEDEPT_LIST_STATISTICS`）。走数据中心报表，单页最多 500 条，本接口自动翻完全部页，返回 `ReportPage`。只请求用得到的列、查无数据返回空结果、查询写错抛 `QueryRejectedError`、翻页条数校验等公共处理见 [billboard_detail_em.md](./billboard_detail_em.md)。

## 统计周期

- `period` 取 `1mo` / `3mo` / `6mo` / `1y`，对应东财页面的“近一月 / 近三月 / 近六月 / 近一年”（上游 `STATISTICSCYCLE` 为 `01` ~ `04`）。未知值回退 `1mo`。
- 只有这四个周期可选，不能指定起止日期。
- 周期列一并请求：上游对拼错的过滤字段静默忽略、返回整张表，而拼错的返回列会报 9501，借此把上游改名暴露出来。

## 字段处理

- 金额单位为元，`billboard_turnover` 等于 `buy + sell`（实测 2026-11-13 近一月 996 家全部成立）。
- `branch_code` 可传给 `billboard_branch_trades_em` 取该营业部的买卖明细。
- 排序同 akshare：龙虎榜成交金额倒序，营业部代码升序。
- 实测 2026-11-13：近一月 996 家，近六月 3360 家。

## 输入参数 `BillboardBranchStatsQuery`

| 名称 | 类型 | 必填 | 默认值 | 描述 |
| --- | --- | --- | --- | --- |
| `period` | `str` | 否 | `"1mo"` | 统计周期：1mo 近一月 / 3mo 近三月 / 6mo 近六月 / 1y 近一年，未知回退 1mo |

## 输出参数 `ReportPage[BillboardBranchStats]`

| 名称 | 类型 | 描述 |
| --- | --- | --- |
| `total` | `int` | 上游报告的条数，通常等于 `len(items)` |
| `items` | `tuple[BillboardBranchStats, ...]` | 全部记录，保持上游排序 |

`BillboardBranchStats` 字段：

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `branch_code` | `str` | — | 营业部代码，可传给 billboard_branch_trades_em（`OPERATEDEPT_CODE`） |
| `branch_name` | `str` | — | 营业部名称（`OPERATEDEPT_NAME`） |
| `billboard_turnover` | `float \| None` | 元 | 龙虎榜成交金额（`AMOUNT`） |
| `billboard_times` | `int \| None` | 次 | 上榜次数（`SALES_ONLIST_TIMES`） |
| `buy` | `float \| None` | 元 | 买入额（`ACT_BUY`） |
| `buy_times` | `int \| None` | 次 | 买入次数（`TOTAL_BUYER_SALESTIMES`） |
| `sell` | `float \| None` | 元 | 卖出额（`ACT_SELL`） |
| `sell_times` | `int \| None` | 次 | 卖出次数（`TOTAL_SELLER_SALESTIMES`） |

## DataFrame 列

`df_billboard_branch_stats_em` 的列对齐 akshare `stock_lhb_traderstatistic_em`，末尾加“营业部代码”。akshare 的“序号”列不输出。列顺序：营业部名称 / 龙虎榜成交金额 / 上榜次数 / 买入额 / 买入次数 / 卖出额 / 卖出次数 / 营业部代码。

## 接口示例（领域模型）

```python
from em import billboard_branch_stats_em
from em.domain.queries import BillboardBranchStatsQuery

page = billboard_branch_stats_em(BillboardBranchStatsQuery(period="1mo"))
print(page.total)
for item in page.items[:2]:
    print(item)
```

## 数据示例（领域模型）

```
996
BillboardBranchStats(branch_code='10634757', branch_name='深股通专用', billboard_turnover=76666378770.17, billboard_times=417, buy=38994793875.67, buy_times=416, sell=37671584894.5, sell_times=416)
BillboardBranchStats(branch_code='10434470', branch_name='沪股通专用', billboard_turnover=52018030396.22, billboard_times=533, buy=27111406398.01, buy_times=263, sell=24906623998.21, sell_times=270)
```

## 接口示例（`DataFrame`，akshare 风格中文列名）

```python
from em import df_billboard_branch_stats_em
from em.domain.queries import BillboardBranchStatsQuery

df = df_billboard_branch_stats_em(BillboardBranchStatsQuery(period="1mo"))
```

## 数据示例（`DataFrame`）

```
                 营业部名称  龙虎榜成交金额  上榜次数        买入额  买入次数        卖出额  卖出次数 营业部代码
0                深股通专用    7.666638e+10       417  3.899479e+10       416  3.767158e+10       416   10634757
1                沪股通专用    5.201803e+10       533  2.711141e+10       263  2.490662e+10       270   10434470
2  国泰海通证券股份有限公司    2.391701e+10       785  1.280110e+10       389  1.111591e+10       396   10004865
```

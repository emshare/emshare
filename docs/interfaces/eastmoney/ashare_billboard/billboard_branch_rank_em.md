# 营业部排行接口

> 渠道：[eastmoney](../eastmoney.md) ｜ 源码：`src/em/channels/eastmoney/ashare_billboard/billboard_branch_rank/billboard_branch_rank_em.py`

## 接口名称

`billboard_branch_rank_em` / `df_billboard_branch_rank_em`：营业部排行（统计周期内各营业部买入上榜后 1 / 2 / 3 / 5 / 10 天的表现）

## 目标地址

- <https://data.eastmoney.com/stock/yybph.html>

## 描述

按统计周期取各营业部买入的股票在上榜后 1 / 2 / 3 / 5 / 10 天的买入次数、平均涨幅与上涨概率，一家营业部一行。对应 akshare `stock_lhb_yybph_em`（`RPT_RATEDEPT_RETURNT_RANKING`）。走数据中心报表，单页最多 500 条，本接口自动翻完全部页，返回 `ReportPage`。只请求用得到的列、查无数据返回空结果、查询写错抛 `QueryRejectedError`、翻页条数校验等公共处理见 [billboard_detail_em.md](./billboard_detail_em.md)。

## 统计周期

- `period` 取 `1mo` / `3mo` / `6mo` / `1y`，对应东财页面的“近一月 / 近三月 / 近六月 / 近一年”（上游 `STATISTICSCYCLE` 为 `01` ~ `04`）。未知值回退 `1mo`。
- 只有这四个周期可选，不能指定起止日期。
- 周期列一并请求：上游对拼错的过滤字段静默忽略、返回整张表，而拼错的返回列会报 9501，借此把上游改名暴露出来。

## 字段处理

- 平均涨幅、上涨概率单位为 %。
- 各档的买入次数随天数递减（实测 2026-11-13 近一月 995 家无一例外），推测上榜后还没满 N 天的买入不计入 N 天档。
- `branch_code` 可传给 `billboard_branch_trades_em` 取该营业部的买卖明细。
- 排序同 akshare：上榜后 1 天买入次数倒序，营业部代码升序。
- 实测 2026-11-13：近一月 995 家，近一年 4661 家。

## 输入参数 `BillboardBranchRankQuery`

| 名称 | 类型 | 必填 | 默认值 | 描述 |
| --- | --- | --- | --- | --- |
| `period` | `str` | 否 | `"1mo"` | 统计周期：1mo 近一月 / 3mo 近三月 / 6mo 近六月 / 1y 近一年，未知回退 1mo |

## 输出参数 `ReportPage[BillboardBranchRank]`

| 名称 | 类型 | 描述 |
| --- | --- | --- |
| `total` | `int` | 上游报告的条数，通常等于 `len(items)` |
| `items` | `tuple[BillboardBranchRank, ...]` | 全部记录，保持上游排序 |

`BillboardBranchRank` 字段：

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `branch_code` | `str` | — | 营业部代码，可传给 billboard_branch_trades_em（`OPERATEDEPT_CODE`） |
| `branch_name` | `str` | — | 营业部名称（`OPERATEDEPT_NAME`） |
| `buy_times_1d` | `int \| None` | 次 | 上榜后 1 天：买入次数（`TOTAL_BUYER_SALESTIMES_1DAY`） |
| `avg_change_1d` | `float \| None` | % | 上榜后 1 天：平均涨幅（`AVERAGE_INCREASE_1DAY`） |
| `rise_prob_1d` | `float \| None` | % | 上榜后 1 天：上涨概率（`RISE_PROBABILITY_1DAY`） |
| `buy_times_2d` | `int \| None` | 次 | 上榜后 2 天：买入次数（`TOTAL_BUYER_SALESTIMES_2DAY`） |
| `avg_change_2d` | `float \| None` | % | 上榜后 2 天：平均涨幅（`AVERAGE_INCREASE_2DAY`） |
| `rise_prob_2d` | `float \| None` | % | 上榜后 2 天：上涨概率（`RISE_PROBABILITY_2DAY`） |
| `buy_times_3d` | `int \| None` | 次 | 上榜后 3 天：买入次数（`TOTAL_BUYER_SALESTIMES_3DAY`） |
| `avg_change_3d` | `float \| None` | % | 上榜后 3 天：平均涨幅（`AVERAGE_INCREASE_3DAY`） |
| `rise_prob_3d` | `float \| None` | % | 上榜后 3 天：上涨概率（`RISE_PROBABILITY_3DAY`） |
| `buy_times_5d` | `int \| None` | 次 | 上榜后 5 天：买入次数（`TOTAL_BUYER_SALESTIMES_5DAY`） |
| `avg_change_5d` | `float \| None` | % | 上榜后 5 天：平均涨幅（`AVERAGE_INCREASE_5DAY`） |
| `rise_prob_5d` | `float \| None` | % | 上榜后 5 天：上涨概率（`RISE_PROBABILITY_5DAY`） |
| `buy_times_10d` | `int \| None` | 次 | 上榜后 10 天：买入次数（`TOTAL_BUYER_SALESTIMES_10DAY`） |
| `avg_change_10d` | `float \| None` | % | 上榜后 10 天：平均涨幅（`AVERAGE_INCREASE_10DAY`） |
| `rise_prob_10d` | `float \| None` | % | 上榜后 10 天：上涨概率（`RISE_PROBABILITY_10DAY`） |

## DataFrame 列

`df_billboard_branch_rank_em` 的列对齐 akshare `stock_lhb_yybph_em`，末尾加“营业部代码”。akshare 的“序号”列不输出。列顺序：营业部名称 / 上榜后1天-买入次数 / 上榜后1天-平均涨幅 / 上榜后1天-上涨概率 / 上榜后2天-买入次数 / 上榜后2天-平均涨幅 / 上榜后2天-上涨概率 / 上榜后3天-买入次数 / 上榜后3天-平均涨幅 / 上榜后3天-上涨概率 / 上榜后5天-买入次数 / 上榜后5天-平均涨幅 / 上榜后5天-上涨概率 / 上榜后10天-买入次数 / 上榜后10天-平均涨幅 / 上榜后10天-上涨概率 / 营业部代码。

## 接口示例（领域模型）

```python
from em import billboard_branch_rank_em
from em.domain.queries import BillboardBranchRankQuery

page = billboard_branch_rank_em(BillboardBranchRankQuery(period="1mo"))
print(page.total)
for item in page.items[:2]:
    print(item)
```

## 数据示例（领域模型）

```
995
BillboardBranchRank(branch_code='10004865', branch_name='国泰海通', buy_times_1d=356, avg_change_1d=-0.550098057191, rise_prob_1d=41.011235955056, buy_times_2d=333, avg_change_2d=-1.262901373844, rise_prob_2d=34.834834834835, buy_times_3d=317, avg_change_3d=-1.798390222461, rise_prob_3d=35.646687697161, buy_times_5d=286, avg_change_5d=-3.227334547483, rise_prob_5d=33.566433566434, buy_times_10d=203, avg_change_10d=-7.721242909409, rise_prob_10d=24.137931034483)
BillboardBranchRank(branch_code='10634757', branch_name='深股通专用', buy_times_1d=339, avg_change_1d=-0.068724619233, rise_prob_1d=46.607669616519, buy_times_2d=318, avg_change_2d=-0.644722193459, rise_prob_2d=42.452830188679, buy_times_3d=306, avg_change_3d=-1.061077505425, rise_prob_3d=44.117647058824, buy_times_5d=279, avg_change_5d=-1.927219165448, rise_prob_5d=37.992831541219, buy_times_10d=193, avg_change_10d=-5.116269728238, rise_prob_10d=35.751295336788)
```

## 接口示例（`DataFrame`，akshare 风格中文列名）

```python
from em import df_billboard_branch_rank_em
from em.domain.queries import BillboardBranchRankQuery

df = df_billboard_branch_rank_em(BillboardBranchRankQuery(period="1mo"))
```

## 数据示例（`DataFrame`）

```
                 营业部名称  上榜后1天-买入次数  上榜后1天-平均涨幅  上榜后1天-上涨概率  上榜后2天-买入次数  上榜后2天-平均涨幅  上榜后2天-上涨概率  上榜后3天-买入次数  上榜后3天-平均涨幅  上榜后3天-上涨概率  上榜后5天-买入次数  上榜后5天-平均涨幅  上榜后5天-上涨概率  上榜后10天-买入次数  上榜后10天-平均涨幅  上榜后10天-上涨概率   营业部代码
0                  国泰海通                 356           -0.550098           41.011236                 333           -1.262901           34.834835                 317           -1.798390           35.646688                 286           -3.227335           33.566434                  203            -7.721243            24.137931     10004865
1                深股通专用                 339           -0.068725           46.607670                 318           -0.644722           42.452830                 306           -1.061078           44.117647                 279           -1.927219           37.992832                  193            -5.116270            35.751295     10634757
2  国信证券浙江互联网分公司                 252           -2.007373           38.888889                 238           -3.576157           28.991597                 233           -4.698115           26.180258                 211           -6.121320           27.488152                  155            -8.685473            24.516129  10000213448
```

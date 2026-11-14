# 大宗交易营业部排行接口

> 渠道：[eastmoney](../eastmoney.md) ｜ 源码：`src/em/channels/eastmoney/ashare_block_trade/block_trade_branch_rank/block_trade_branch_rank_em.py`

## 接口名称

`block_trade_branch_rank_em` / `df_block_trade_branch_rank_em`：大宗交易营业部排行（最近 N 个交易日各营业部买入后 1 / 5 / 10 / 20 天的表现）

## 目标地址

- <https://data.eastmoney.com/dzjy/dzjy_yybph.html>

## 描述

按最近 N 个交易日取各营业部买入的 A 股在成交后 1 / 5 / 10 / 20 天的买入次数、平均涨幅与上涨概率，一家营业部一行。对应 akshare `stock_dzjy_yybph`（`RPT_BLOCKTRADE_OPERATEDEPT_RANK`）。走数据中心报表，本接口按每页 500 条自动翻完全部页，返回 `ReportPage`。只请求用得到的列、查无数据返回空结果、查询写错抛 `QueryRejectedError`、翻页条数校验等公共处理见 [billboard_detail_em.md](../ashare_billboard/billboard_detail_em.md)。

## 统计周期

- `period` 取 `30d` / `90d` / `180d` / `360d`，即最近 30 / 90 / 180 / 360 个**交易日**（上游 `N_DATE` 为 -30 / -90 / -180 / -360，上游自己的标注也是“近30日”…“近360日”）。未知值回退 `30d`。默认 `30d`（akshare 默认近三月，即 `90d`）。
- **东财页面和 akshare 把这四档叫“近一月 / 近三月 / 近六月 / 近一年”，实际窗口长得多**：实测 2026-11-13，`30d` 从 2026-09-28 起，`90d` 从 07-03 起，`180d` 从 02-12 起，`360d` 从 2025-05-23 起（约一年半）；各档的买入次数按交易日窗口与每日明细相符，按自然日窗口只有三到五成相符。所以取值按“日”命名，不用 `1mo` / `1y`。
- 实测 2026-11-13：`30d` 398 家，`90d` 933 家，`180d` 1689 家，`360d` 2766 家。

## 字段处理

- 只统计买入方，且只统计 A 股。平均涨幅、上涨概率单位为 %。
- 各档只算已经有 N 日后涨跌幅的买入，还没到期的不计入。**某一档没有到期的买入时，该档三项都是 `None`（不是 0）**：实测 2026-11-13 `30d` 的 398 家里，5 / 10 / 20 日档为空的有 55 / 106 / 204 家。
- **5 日档与每日明细逐家一致；1 / 10 / 20 日档有少数营业部比明细少**：实测 2026-11-13，`30d` 1 家、`90d` 11 家、`180d` 34 家、`360d` 140 家，多数是这三档数值相同且小于 5 日档（如 `10110326` 的 `90d`：1 / 5 / 10 / 20 日档为 5 / 36 / 5 / 5，按明细应为 37 / 36 / 35 / 32）。这是上游数据自身的出入，本接口原样返回；用这三档的次数时请留意。
- `branch_code`：机构专用为 `"0"`；与每日明细的买卖方营业部代码、龙虎榜的营业部代码是同一套。`branch_name` 是简称，每日明细里是全称，两边关联请用营业部代码。
- 排序同 akshare：5 日档买入次数、1 日档平均涨幅倒序；末尾补营业部代码保证翻页顺序稳定（完全不带排序翻页会重复和丢行：实测 `360d` 2766 行里重复 612 行）。周期内一家营业部一行。

## 输入参数 `BlockTradeBranchRankQuery`

| 名称 | 类型 | 必填 | 默认值 | 描述 |
| --- | --- | --- | --- | --- |
| `period` | `str` | 否 | `"30d"` | 最近 N 个交易日：30d / 90d / 180d / 360d（东财页面叫近一月 / 近三月 / 近六月 / 近一年），未知回退 30d |

## 输出参数 `ReportPage[BlockTradeBranchRank]`

| 名称 | 类型 | 描述 |
| --- | --- | --- |
| `total` | `int` | 上游报告的条数，通常等于 `len(items)` |
| `items` | `tuple[BlockTradeBranchRank, ...]` | 全部记录，保持上游排序 |

`BlockTradeBranchRank` 字段：

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `branch_code` | `str` | — | 营业部代码（机构专用为 "0"）（`OPERATEDEPT_CODE`） |
| `branch_name` | `str` | — | 营业部名称（`OPERATEDEPT_NAME`） |
| `buy_times_1d` | `int \| None` | 次 | 上榜后 1 天：买入次数（只算已到期的买入；该档没有时为 None）（`D1_BUYER_NUM`） |
| `avg_change_1d` | `float \| None` | % | 上榜后 1 天：平均涨幅（`D1_AVERAGE_INCREASE`） |
| `rise_prob_1d` | `float \| None` | % | 上榜后 1 天：上涨概率（`D1_RISE_PROBABILITY`） |
| `buy_times_5d` | `int \| None` | 次 | 上榜后 5 天：买入次数（只算已到期的买入；该档没有时为 None）（`D5_BUYER_NUM`） |
| `avg_change_5d` | `float \| None` | % | 上榜后 5 天：平均涨幅（`D5_AVERAGE_INCREASE`） |
| `rise_prob_5d` | `float \| None` | % | 上榜后 5 天：上涨概率（`D5_RISE_PROBABILITY`） |
| `buy_times_10d` | `int \| None` | 次 | 上榜后 10 天：买入次数（只算已到期的买入；该档没有时为 None）（`D10_BUYER_NUM`） |
| `avg_change_10d` | `float \| None` | % | 上榜后 10 天：平均涨幅（`D10_AVERAGE_INCREASE`） |
| `rise_prob_10d` | `float \| None` | % | 上榜后 10 天：上涨概率（`D10_RISE_PROBABILITY`） |
| `buy_times_20d` | `int \| None` | 次 | 上榜后 20 天：买入次数（只算已到期的买入；该档没有时为 None）（`D20_BUYER_NUM`） |
| `avg_change_20d` | `float \| None` | % | 上榜后 20 天：平均涨幅（`D20_AVERAGE_INCREASE`） |
| `rise_prob_20d` | `float \| None` | % | 上榜后 20 天：上涨概率（`D20_RISE_PROBABILITY`） |

## DataFrame 列

`df_block_trade_branch_rank_em` 的列对齐 akshare `stock_dzjy_yybph`，末尾加“营业部代码”。akshare 的“序号”列不输出。列顺序：营业部名称 / 上榜后1天-买入次数 / 上榜后1天-平均涨幅 / 上榜后1天-上涨概率 / 上榜后5天-买入次数 / 上榜后5天-平均涨幅 / 上榜后5天-上涨概率 / 上榜后10天-买入次数 / 上榜后10天-平均涨幅 / 上榜后10天-上涨概率 / 上榜后20天-买入次数 / 上榜后20天-平均涨幅 / 上榜后20天-上涨概率 / 营业部代码。

## 接口示例（领域模型）

```python
from em import block_trade_branch_rank_em
from em.domain.queries import BlockTradeBranchRankQuery

page = block_trade_branch_rank_em(BlockTradeBranchRankQuery(period="30d"))
print(page.total)
for item in page.items[:2]:
    print(item)
```

## 数据示例（领域模型）

```
398
BlockTradeBranchRank(branch_code='0', branch_name='机构专用', buy_times_1d=730, avg_change_1d=-0.765208804, rise_prob_1d=40.27397260274, buy_times_5d=630, avg_change_5d=-3.209395015381, rise_prob_5d=29.047619047619, buy_times_10d=512, avg_change_10d=-6.444206741113, rise_prob_10d=28.7109375, buy_times_20d=221, avg_change_20d=-12.952679051358, rise_prob_20d=13.122171945701)
BlockTradeBranchRank(branch_code='10510599', branch_name='广发证券慈溪浒山路证券营业部', buy_times_1d=64, avg_change_1d=-1.285870166719, rise_prob_1d=32.8125, buy_times_5d=62, avg_change_5d=-1.135518107097, rise_prob_5d=37.096774193548, buy_times_10d=58, avg_change_10d=-1.229660142586, rise_prob_10d=48.275862068966, buy_times_20d=22, avg_change_20d=-9.319462768182, rise_prob_20d=27.272727272727)
```

## 接口示例（`DataFrame`，akshare 风格中文列名）

```python
from em import df_block_trade_branch_rank_em
from em.domain.queries import BlockTradeBranchRankQuery

df = df_block_trade_branch_rank_em(BlockTradeBranchRankQuery(period="30d"))
```

## 数据示例（`DataFrame`）

```
                     营业部名称  上榜后1天-买入次数  上榜后1天-平均涨幅  上榜后1天-上涨概率  上榜后5天-买入次数  上榜后5天-平均涨幅  上榜后5天-上涨概率  上榜后10天-买入次数  上榜后10天-平均涨幅  上榜后10天-上涨概率  上榜后20天-买入次数  上榜后20天-平均涨幅  上榜后20天-上涨概率 营业部代码
0                      机构专用                 730           -0.765209           40.273973               630.0           -3.209395           29.047619                512.0            -6.444207            28.710938                221.0           -12.952679            13.122172          0
1  广发证券慈溪浒山路证券营业部                  64           -1.285870           32.812500                62.0           -1.135518           37.096774                 58.0            -1.229660            48.275862                 22.0            -9.319463            27.272727   10510599
2            中信证券上海分公司                  51           -0.357359           49.019608                47.0           -3.589250           29.787234                 41.0            -7.093731            26.829268                 23.0           -18.939952             4.347826   10135341
```

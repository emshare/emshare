# 营业部详情接口

> 渠道：[eastmoney](../eastmoney.md) ｜ 源码：`src/em/channels/eastmoney/ashare_billboard/billboard_branch_trades/billboard_branch_trades_em.py`

## 接口名称

`billboard_branch_trades_em` / `df_billboard_branch_trades_em`：营业部详情（一家营业部的上榜买卖记录）

## 目标地址

- <https://data.eastmoney.com/stock/lhb/yyb/10188715.html>

## 描述

取一家营业部的上榜买卖记录：股票、买入 / 卖出金额、净额、上榜原因、之后 1 ~ 30 日涨跌幅。对应 akshare `stock_lhb_yyb_detail_em`（`RPT_OPERATEDEPT_TRADE_DETAILSNEW`）；akshare 只能取全部历史，本接口另可按日期区间筛选。走数据中心报表，单页最多 500 条，本接口自动翻完全部页，返回 `ReportPage`。只请求用得到的列、查无数据返回空结果、查询写错抛 `QueryRejectedError`、翻页条数校验等公共处理见 [billboard_detail_em.md](./billboard_detail_em.md)。

## 日期规则

- `branch_code` 必填，取自 `billboard_branch_active_em` / `billboard_branch_rank_em` / `billboard_branch_stats_em` 的 `branch_code`。含引号或括号时在本地抛 `ValueError`（会改写过滤语法）。
- 日期为 `YYYYMMDD`。格式或日期不对在本地直接抛 `ValueError`。
- 营业部代码不存在时返回 `total=0` 的空结果。
- **都留空**：取该营业部的全部历史，**不是最近一天**（与按日期的龙虎榜接口不同）。活跃席位的历史很长：实测 2026-11-13 `10634757` 深股通专用共 20681 条（最早 2016-12-05），要翻 42 页；`10188715` 共 105 条（最早 2006-07-17）。
- **只给 `start_date`**：取到北京时间今天。**只给 `end_date`**：只取那一天。

## 字段处理

- **只买入或只卖出时，另一侧为 `None` 而不是 0**（上游 `ACT_BUY` / `ACT_SELL` 为 null）。求和前要先处理空值。
- **同一只股票同一天可能有多条记录**：因多个原因上榜时，每个原因一条。按条直接相加会重复计算。
- 金额单位为元，涨跌幅单位为 %。`change_after_*` 未到期时为 `None`。
- `market` 由上游 `SECUCODE` 后缀得出，可连同 `code` 直接传给 `stock_kline_em`。
- 排序同 akshare：交易日期倒序，股票代码升序。本报表没有 `TRADE_ID`，末尾补上榜原因（`EXPLANATION`），同股同日多条时翻页顺序也稳定。

## 输入参数 `BillboardBranchTradesQuery`

| 名称 | 类型 | 必填 | 默认值 | 描述 |
| --- | --- | --- | --- | --- |
| `branch_code` | `str` | 是 | — | 营业部代码（见活跃营业部 / 营业部排行 / 营业部统计的 branch_code） |
| `start_date` | `str \| None` | 否 | `None` | 起始日期 YYYYMMDD；起止都留空取该营业部的全部历史，只给起始取到今天 |
| `end_date` | `str \| None` | 否 | `None` | 结束日期 YYYYMMDD；只给结束日期时只取那一天 |

## 输出参数 `ReportPage[BillboardBranchTrade]`

| 名称 | 类型 | 描述 |
| --- | --- | --- |
| `total` | `int` | 上游报告的条数，通常等于 `len(items)` |
| `items` | `tuple[BillboardBranchTrade, ...]` | 全部记录，保持上游排序 |

`BillboardBranchTrade` 字段：

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `branch_code` | `str` | — | 营业部代码（`OPERATEDEPT_CODE`） |
| `branch_name` | `str` | — | 营业部名称（`OPERATEDEPT_NAME`） |
| `branch_short_name` | `str \| None` | — | 营业部简称（`ORG_NAME_ABBR`） |
| `trade_date` | `str \| None` | — | 交易日期 YYYY-MM-DD（`TRADE_DATE`） |
| `code` | `str` | — | 股票代码（`SECURITY_CODE`） |
| `name` | `str` | — | 股票简称（`SECURITY_NAME_ABBR`） |
| `market` | `str \| None` | — | 市场：sh / sz / bj，可连同 code 传给 stock_kline_em（`SECUCODE`） |
| `change_pct` | `float \| None` | % | 涨跌幅（`CHANGE_RATE`） |
| `buy` | `float \| None` | 元 | 买入金额（该营业部只卖出时为 None）（`ACT_BUY`） |
| `sell` | `float \| None` | 元 | 卖出金额（该营业部只买入时为 None）（`ACT_SELL`） |
| `net_buy` | `float \| None` | 元 | 净额（`NET_AMT`） |
| `reason` | `str \| None` | — | 上榜原因（同股同日多个原因时为多条记录）（`EXPLANATION`） |
| `change_after_1d` | `float \| None` | % | 1 日后涨跌幅（未到期为 None）（`D1_CLOSE_ADJCHRATE`） |
| `change_after_2d` | `float \| None` | % | 2 日后涨跌幅（`D2_CLOSE_ADJCHRATE`） |
| `change_after_3d` | `float \| None` | % | 3 日后涨跌幅（`D3_CLOSE_ADJCHRATE`） |
| `change_after_5d` | `float \| None` | % | 5 日后涨跌幅（`D5_CLOSE_ADJCHRATE`） |
| `change_after_10d` | `float \| None` | % | 10 日后涨跌幅（`D10_CLOSE_ADJCHRATE`） |
| `change_after_20d` | `float \| None` | % | 20 日后涨跌幅（`D20_CLOSE_ADJCHRATE`） |
| `change_after_30d` | `float \| None` | % | 30 日后涨跌幅（`D30_CLOSE_ADJCHRATE`） |

## DataFrame 列

`df_billboard_branch_trades_em` 的列对齐 akshare `stock_lhb_yyb_detail_em`，并在“股票名称”后加“市场”。akshare 的“序号”列不输出。列顺序：营业部代码 / 营业部名称 / 营业部简称 / 交易日期 / 股票代码 / 股票名称 / 市场 / 涨跌幅 / 买入金额 / 卖出金额 / 净额 / 上榜原因 / 1日后涨跌幅 / 2日后涨跌幅 / 3日后涨跌幅 / 5日后涨跌幅 / 10日后涨跌幅 / 20日后涨跌幅 / 30日后涨跌幅。

## 接口示例（领域模型）

```python
from em import billboard_branch_trades_em
from em.domain.queries import BillboardBranchTradesQuery

page = billboard_branch_trades_em(BillboardBranchTradesQuery("10188715", "20261001", "20261031"))
print(page.total)
for item in page.items[:2]:
    print(item)
```

## 数据示例（领域模型）

```
1
BillboardBranchTrade(branch_code='10188715', branch_name='东方证券股份有限公司上海普陀区云岭东路证券营业部', branch_short_name='东方证券上海普陀区云岭东路证券营业部', trade_date='2026-10-30', code='603131', name='上海沪工', market='sh', change_pct=10.0313, buy=None, sell=5265000.0, net_buy=-5265000.0, reason='有价格涨跌幅限制的日收盘价格涨幅偏离值达到7%的前五只证券', change_after_1d=-1.42450142, change_after_2d=-11.28205128, change_after_3d=-5.64102564, change_after_5d=-7.97720798, change_after_10d=None, change_after_20d=None, change_after_30d=None)
```

## 接口示例（`DataFrame`，akshare 风格中文列名）

```python
from em import df_billboard_branch_trades_em
from em.domain.queries import BillboardBranchTradesQuery

df = df_billboard_branch_trades_em(BillboardBranchTradesQuery("10188715", "20261001", "20261031"))
```

## 数据示例（`DataFrame`）

```
  营业部代码                                        营业部名称                            营业部简称    交易日期 股票代码  股票名称 市场   涨跌幅 买入金额   卖出金额       净额                                                  上榜原因  1日后涨跌幅  2日后涨跌幅  3日后涨跌幅  5日后涨跌幅 10日后涨跌幅 20日后涨跌幅 30日后涨跌幅
0   10188715  东方证券股份有限公司上海普陀区云岭东路证券营业部  东方证券上海普陀区云岭东路证券营业部  2026-10-30   603131  上海沪工   sh  10.0313     None  5265000.0 -5265000.0  有价格涨跌幅限制的日收盘价格涨幅偏离值达到7%的前五只证券    -1.424501   -11.282051    -5.641026    -7.977208         None         None         None
```

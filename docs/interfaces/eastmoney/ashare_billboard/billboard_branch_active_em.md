# 每日活跃营业部接口

> 渠道：[eastmoney](../eastmoney.md) ｜ 源码：`src/em/channels/eastmoney/ashare_billboard/billboard_branch_active/billboard_branch_active_em.py`

## 接口名称

`billboard_branch_active_em` / `df_billboard_branch_active_em`：每日活跃营业部（按上榜日期区间取各营业部的买卖合计与当日交易的上榜股票）

## 目标地址

- <https://data.eastmoney.com/stock/hyyyb.html>

## 描述

按上榜日期区间取各营业部的买入 / 卖出个股数、买卖合计与当日交易的上榜股票，一家营业部一个上榜日一行。对应 akshare `stock_lhb_hyyyb_em`（`RPT_OPERATEDEPT_ACTIVE`）。走数据中心报表，单页最多 500 条，本接口自动翻完全部页，返回 `ReportPage`。只请求用得到的列、查无数据返回空结果、查询写错抛 `QueryRejectedError`、翻页条数校验等公共处理见 [billboard_detail_em.md](./billboard_detail_em.md)。

## 日期规则

- 日期为 `YYYYMMDD`。格式或日期不对在本地直接抛 `ValueError`。
- **都留空**：取最近一个有龙虎榜的交易日（先查一次最新上榜日，多 1 个请求）。
- **只给 `start_date`**：取到北京时间今天。**只给 `end_date`**：只取那一天。
- 周末、节假日没有龙虎榜，单取这类日期返回 `total=0` 的空结果。

## 字段处理

- **`stocks` / `stock_codes` 不只是买入的股票**：东财页面和上游列名（`BUY_STOCK`）叫“买入股票”，实际是该营业部当日买入或卖出过的全部上榜股票，所以个数可以大于 `buy_stock_count`。实测 2026-11-11 取 36 家营业部与 `billboard_branch_trades_em` 逐家核对，股票集合全部一致；其中 8 家含只卖出的股票。
- `stock_codes` 由上游 `BUY_STOCK`（`600127.SH 600261.SH`）去掉市场后缀得到，与 `stocks` 的简称一一对应。
- **同一营业部代码同一上榜日可能有两行**：上游对个别营业部给出金额、个股数相同，只有名称与股票列表不同的两行（实测 2026-11-11 有 `10025080`、`10564259` 两家）。两行都保留；按营业部代码汇总金额时要先去重。
- 金额单位为元。`branch_code` 可传给 `billboard_branch_trades_em` 取该营业部的买卖明细。
- 排序同 akshare：总买卖净额、上榜日倒序，营业部代码升序；末尾补营业部名称，上述同代码的两行翻页顺序也稳定。
- 实测 2026-11-11 共 200 行。

## 输入参数 `BillboardBranchActiveQuery`

| 名称 | 类型 | 必填 | 默认值 | 描述 |
| --- | --- | --- | --- | --- |
| `start_date` | `str \| None` | 否 | `None` | 起始日期 YYYYMMDD；起止都留空取最近一个有数据的交易日，只给起始取到今天 |
| `end_date` | `str \| None` | 否 | `None` | 结束日期 YYYYMMDD；只给结束日期时只取那一天 |

## 输出参数 `ReportPage[BillboardBranchActive]`

| 名称 | 类型 | 描述 |
| --- | --- | --- |
| `total` | `int` | 上游报告的条数，通常等于 `len(items)` |
| `items` | `tuple[BillboardBranchActive, ...]` | 全部记录，保持上游排序 |

`BillboardBranchActive` 字段：

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `branch_code` | `str` | — | 营业部代码，可传给 billboard_branch_trades_em（`OPERATEDEPT_CODE`） |
| `branch_name` | `str` | — | 营业部名称（`OPERATEDEPT_NAME`） |
| `trade_date` | `str \| None` | — | 上榜日 YYYY-MM-DD（`ONLIST_DATE`） |
| `buy_stock_count` | `int \| None` | 只 | 买入个股数（`BUYER_APPEAR_NUM`） |
| `sell_stock_count` | `int \| None` | 只 | 卖出个股数（`SELLER_APPEAR_NUM`） |
| `buy` | `float \| None` | 元 | 买入总金额（`TOTAL_BUYAMT`） |
| `sell` | `float \| None` | 元 | 卖出总金额（`TOTAL_SELLAMT`） |
| `net_buy` | `float \| None` | 元 | 总买卖净额（`TOTAL_NETAMT`） |
| `stocks` | `str \| None` | — | 当日买入或卖出过的全部上榜股票的简称，空格分隔（东财页面叫“买入股票”，实际含只卖出的）（`SECURITY_NAME_ABBR`） |
| `stock_codes` | `tuple[str, ...]` | — | 上述股票的代码，与 stocks 一一对应（`BUY_STOCK`） |

## DataFrame 列

`df_billboard_branch_active_em` 的列对齐 akshare `stock_lhb_hyyyb_em`，末尾加“营业部代码”“买入股票代码”。“买入股票”“买入股票代码”两列沿用 akshare 的列名，对应模型的 `stocks` / `stock_codes`，同样含只卖出的股票。akshare 的“序号”列不输出。列顺序：营业部名称 / 上榜日 / 买入个股数 / 卖出个股数 / 买入总金额 / 卖出总金额 / 总买卖净额 / 买入股票 / 营业部代码 / 买入股票代码。

## 接口示例（领域模型）

```python
from em import billboard_branch_active_em
from em.domain.queries import BillboardBranchActiveQuery

page = billboard_branch_active_em(BillboardBranchActiveQuery("20261111", "20261111"))
print(page.total)
for item in page.items[:2]:
    print(item)
```

## 数据示例（领域模型）

```
200
BillboardBranchActive(branch_code='10634757', branch_name='深股通专用', trade_date='2026-11-11', buy_stock_count=21, sell_stock_count=22, buy=5014364348.87, sell=4327120769.35, net_buy=687243579.52, stocks='飞亚达 德龙汇能 襄阳轴承 胜通能源 智微智能 东方海洋 桂林三金 光迅科技 东山精密 沪电股份 光洋股份 中坚科技 奥士康 深南电路 锋龙股份 德尔股份 阿尔特 博硕科技 同飞股份 致尚科技 瑞迪智驱 贝特利', stock_codes=('000026', '000593', '000678', '001331', '001339', '002086', '002275', '002281', '002384', '002463', '002708', '002779', '002913', '002916', '002931', '300473', '300825', '300951', '300990', '301486', '301596', '301697'))
BillboardBranchActive(branch_code='10434470', branch_name='沪股通专用', trade_date='2026-11-11', buy_stock_count=15, sell_stock_count=16, buy=2181827964.5, sell=1950810545.06, net_buy=231017419.44, stocks='青山纸业 金健米业 文投控股 东方通信 上海电影 新坐标 电魂网络 永臻股份 风语筑 苏州科达 岱美股份 世运电路 新炬网络 福莱新材 龙版传媒 利扬芯片 源杰科技', stock_codes=('600103', '600127', '600715', '600776', '601595', '603040', '603258', '603381', '603466', '603660', '603730', '603920', '605398', '605488', '605577', '688135', '688498'))
```

## 接口示例（`DataFrame`，akshare 风格中文列名）

```python
from em import df_billboard_branch_active_em
from em.domain.queries import BillboardBranchActiveQuery

df = df_billboard_branch_active_em(BillboardBranchActiveQuery("20261111", "20261111"))
```

## 数据示例（`DataFrame`）

```
                                        营业部名称      上榜日  买入个股数  卖出个股数    买入总金额    卖出总金额    总买卖净额                                       买入股票   营业部代码               买入股票代码
0                                       深股通专用  2026-11-11          21          22  5.014364e+09  4.327121e+09  6.872436e+08   飞亚达 德龙汇能 襄阳轴承 胜通能源 智微智能 …     10634757  ('000026', '000593', '00…
1                                       沪股通专用  2026-11-11          15          16  2.181828e+09  1.950811e+09  2.310174e+08  青山纸业 金健米业 文投控股 东方通信 上海电影…     10434470  ('600103', '600127', '60…
2  摩根大通证券(中国)有限公司上海银城中路证券营业…  2026-11-11           5           6  4.088169e+08  2.195893e+08  1.892276e+08  金健米业 上海九百 华脉科技 电魂网络 世运电路…  10000100571  ('600127', '600838', '60…
```

示例里的长文本列为便于阅读做了截断（以 `…` 结尾），实际返回完整内容。

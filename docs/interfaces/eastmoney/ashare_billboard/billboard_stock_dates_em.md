# 个股上榜日期接口

> 渠道：[eastmoney](../eastmoney.md) ｜ 源码：`src/em/channels/eastmoney/ashare_billboard/billboard_stock_dates/billboard_stock_dates_em.py`

## 接口名称

`billboard_stock_dates_em` / `df_billboard_stock_dates_em`：个股上榜日期（一只股票历次上榜的日期）

## 目标地址

- <https://data.eastmoney.com/stock/tradedetail.html>

## 描述

取一只股票历次上榜的日期，倒序。常用来给 `billboard_stock_em` 的 `date` 提供取值。对应 akshare `stock_lhb_stock_detail_date_em`（`RPT_LHB_BOARDDATE`）。走数据中心报表，单页最多 500 条，本接口自动翻完全部页，返回 `ReportPage`。只请求用得到的列、查无数据返回空结果、查询写错抛 `QueryRejectedError`、翻页条数校验等公共处理见 [billboard_detail_em.md](./billboard_detail_em.md)。

## 字段处理

- `code` 必填。含引号或括号时在本地抛 `ValueError`（会改写过滤语法）。
- 一个上榜日一行：同一天因多个原因上榜也只有一行。
- 没上过榜的股票或不存在的代码返回 `total=0` 的空结果。
- 排序同 akshare：上榜日倒序。
- 实测 2026-11-13：000530 冰山冷热共 73 个上榜日。

## 输入参数 `BillboardStockDatesQuery`

| 名称 | 类型 | 必填 | 默认值 | 描述 |
| --- | --- | --- | --- | --- |
| `code` | `str` | 是 | — | 股票代码（如 000530） |

## 输出参数 `ReportPage[BillboardStockDate]`

| 名称 | 类型 | 描述 |
| --- | --- | --- |
| `total` | `int` | 上游报告的条数，通常等于 `len(items)` |
| `items` | `tuple[BillboardStockDate, ...]` | 全部记录，保持上游排序 |

`BillboardStockDate` 字段：

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `code` | `str` | — | 股票代码（`SECURITY_CODE`） |
| `trade_date` | `str \| None` | — | 上榜日 YYYY-MM-DD，可传给 billboard_stock_em 的 date（`TRADE_DATE`） |

## DataFrame 列

`df_billboard_stock_dates_em` 的列对齐 akshare `stock_lhb_stock_detail_date_em`。akshare 的“序号”列不输出。列顺序：股票代码 / 交易日。

## 接口示例（领域模型）

```python
from em import billboard_stock_dates_em
from em.domain.queries import BillboardStockDatesQuery

page = billboard_stock_dates_em(BillboardStockDatesQuery("000530"))
print(page.total)
for item in page.items[:2]:
    print(item)
```

## 数据示例（领域模型）

```
73
BillboardStockDate(code='000530', trade_date='2026-11-12')
BillboardStockDate(code='000530', trade_date='2026-11-11')
```

## 接口示例（`DataFrame`，akshare 风格中文列名）

```python
from em import df_billboard_stock_dates_em
from em.domain.queries import BillboardStockDatesQuery

df = df_billboard_stock_dates_em(BillboardStockDatesQuery("000530"))
```

## 数据示例（`DataFrame`）

```
  股票代码      交易日
0   000530  2026-11-12
1   000530  2026-11-11
2   000530  2026-11-10
```

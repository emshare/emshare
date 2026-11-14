# 预约披露时间接口

> 渠道：[eastmoney](../eastmoney.md) ｜ 源码：`src/em/channels/eastmoney/ashare_earnings/earnings_schedule/earnings_schedule_em.py`

## 接口名称

`earnings_schedule_em` / `df_earnings_schedule_em`：预约披露时间（按报告期取各公司定期报告的首次预约、历次变更与实际披露日期）

## 目标地址

- <https://data.eastmoney.com/bbsj/202609/yysj.html>

## 描述

按报告期取各公司定期报告的首次预约、历次变更与实际披露日期。对应 akshare `stock_yysj_em`（`RPT_PUBLIC_BS_APPOIN`）。走数据中心报表，本接口按每页 500 条自动翻完全部页，返回 `ReportPage`。只请求用得到的列、查无数据返回空结果、查询写错抛 `QueryRejectedError`、翻页条数校验等公共处理见 [billboard_detail_em.md](../ashare_billboard/billboard_detail_em.md)。

## 参数规则

- `report_date` 报告期为 `YYYYMMDD`，必须是季末（`0331` 一季报 / `0630` 中报 / `0930` 三季报 / `1231` 年报）；格式不对或不是季末在本地直接抛 `ValueError`。
- **`report_date` 留空**：取北京时间今天之前最近的季末（2026-11-14 取到的是 2026-09-30），不发额外请求。季末当天取的是上一个季末：当天还没有公司披露。
- `scope` 市场范围：`all`（默认，沪深京全部）/ `sh` / `sz` / `bj` / `kc` 科创板 / `cy` 创业板 / `st` 风险警示，取值同 `stock_list_em`（没有 `new`）；未知值回退 `all`。`sh` + `sz` + `bj` 的条数之和等于 `all`（实测）。
- **只取 A 股与存托凭证**（上游 `SECURITY_TYPE_CODE` 为 `058001001` / `058001008`）。akshare 用中文的 `symbol`（沪深A股 / 沪市A股 / 科创板…）区分市场，默认排除北交所；本接口用 `scope`，默认含北交所。
- 还没有公司披露的报告期返回 `total=0` 的空结果（实测 2026-11-14 取 2026-12-31 的三大报表为空）。

## 字段处理

- `first_appoint_date` 首次预约日期；变更过预约的公司有 `first_change_date` / `second_change_date` / `third_change_date`，没有变更为 `None`。实测 2025 年报 5476 家里变更一次 780 家、两次 56 家、三次 4 家。
- `appoint_date` 是当前生效的预约日期（最后一次变更后的日期），`actual_date` 是实际披露日期，尚未披露为 `None`。
- 各日期为 `YYYY-MM-DD`。`market` 由上游 `SECUCODE` 后缀得出。
- 排序同 akshare：首次预约时间、代码升序；报告期内一家公司一行。实测 2026 三季报 5576 家。

## 输入参数 `EarningsScheduleQuery`

| 名称 | 类型 | 必填 | 默认值 | 描述 |
| --- | --- | --- | --- | --- |
| `report_date` | `str \| None` | 否 | `None` | 报告期 YYYYMMDD，必须是季末（0331 / 0630 / 0930 / 1231）；留空取今天之前最近的季末 |
| `scope` | `str` | 否 | `"all"` | 市场范围：all / sh / sz / bj / kc 科创板 / cy 创业板 / st 风险警示，未知回退 all |

## 输出参数 `ReportPage[EarningsSchedule]`

| 名称 | 类型 | 描述 |
| --- | --- | --- |
| `total` | `int` | 上游报告的条数，通常等于 `len(items)` |
| `items` | `tuple[EarningsSchedule, ...]` | 全部记录，保持上游排序 |

`EarningsSchedule` 字段：

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `code` | `str` | — | 股票代码（`SECURITY_CODE`） |
| `name` | `str` | — | 股票简称（`SECURITY_NAME_ABBR`） |
| `market` | `str \| None` | — | 市场：sh / sz / bj，可连同 code 传给 stock_kline_em（`SECUCODE`） |
| `report_date` | `str \| None` | — | 报告期 YYYY-MM-DD（`REPORT_DATE`） |
| `first_appoint_date` | `str \| None` | — | 首次预约披露日期 YYYY-MM-DD（`FIRST_APPOINT_DATE`） |
| `first_change_date` | `str \| None` | — | 第一次变更后的预约日期（没有变更为 None）（`FIRST_CHANGE_DATE`） |
| `second_change_date` | `str \| None` | — | 第二次变更后的预约日期（`SECOND_CHANGE_DATE`） |
| `third_change_date` | `str \| None` | — | 第三次变更后的预约日期（`THIRD_CHANGE_DATE`） |
| `appoint_date` | `str \| None` | — | 当前生效的预约披露日期（最后一次变更后的日期）（`APPOINT_PUBLISH_DATE`） |
| `actual_date` | `str \| None` | — | 实际披露日期（尚未披露为 None）（`ACTUAL_PUBLISH_DATE`） |

## DataFrame 列

`df_earnings_schedule_em` 的中文列名：akshare 有的列沿用其列名，并在“股票简称”后加“市场”；其余字段按同样的写法补上，顺序同模型字段。akshare 的“序号”列不输出。列顺序：股票代码 / 股票简称 / 市场 / 报告期 / 首次预约时间 / 一次变更日期 / 二次变更日期 / 三次变更日期 / 最新预约时间 / 实际披露时间。

## 接口示例（领域模型）

```python
from em import earnings_schedule_em
from em.domain.queries import EarningsScheduleQuery

page = earnings_schedule_em(EarningsScheduleQuery("20260930"))
print(page.total)
for item in page.items[:2]:
    print(item)
```

## 数据示例（领域模型）

```
5576
EarningsSchedule(code='920438', name='戈碧迦', market='bj', report_date='2026-09-30', first_appoint_date='2026-09-29', first_change_date='2026-10-29', second_change_date=None, third_change_date=None, appoint_date='2026-10-29', actual_date='2026-10-29')
EarningsSchedule(code='002107', name='沃华医药', market='sz', report_date='2026-09-30', first_appoint_date='2026-10-10', first_change_date=None, second_change_date=None, third_change_date=None, appoint_date='2026-10-10', actual_date='2026-10-10')
```

## 接口示例（`DataFrame`，akshare 风格中文列名）

```python
from em import df_earnings_schedule_em
from em.domain.queries import EarningsScheduleQuery

df = df_earnings_schedule_em(EarningsScheduleQuery("20260930"))
```

## 数据示例（`DataFrame`）

```
  股票代码  股票简称 市场      报告期 首次预约时间 一次变更日期 二次变更日期 三次变更日期 最新预约时间 实际披露时间
0   920438    戈碧迦   bj  2026-09-30   2026-09-29   2026-10-29          NaN         None   2026-10-29   2026-10-29
1   002107  沃华医药   sz  2026-09-30   2026-10-10          NaN          NaN         None   2026-10-10   2026-10-10
2   000856  冀东装备   sz  2026-09-30   2026-10-13          NaN          NaN         None   2026-10-13   2026-10-13
```

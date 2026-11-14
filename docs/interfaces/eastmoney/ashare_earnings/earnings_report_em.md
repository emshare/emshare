# 业绩报告接口

> 渠道：[eastmoney](../eastmoney.md) ｜ 源码：`src/em/channels/eastmoney/ashare_earnings/earnings_report/earnings_report_em.py`

## 接口名称

`earnings_report_em` / `df_earnings_report_em`：业绩报告（按报告期取各公司的每股收益、营业总收入、净利润及同比环比、净资产收益率、销售毛利率）

## 目标地址

- <https://data.eastmoney.com/bbsj/202609/yjbb.html>

## 描述

按报告期取各公司的每股收益、营业总收入、净利润及同比环比、净资产收益率、销售毛利率。对应 akshare `stock_yjbb_em`（`RPT_LICO_FN_CPD`）。走数据中心报表，本接口按每页 500 条自动翻完全部页，返回 `ReportPage`。只请求用得到的列、查无数据返回空结果、查询写错抛 `QueryRejectedError`、翻页条数校验等公共处理见 [billboard_detail_em.md](../ashare_billboard/billboard_detail_em.md)。

## 参数规则

- `report_date` 报告期为 `YYYYMMDD`，必须是季末（`0331` 一季报 / `0630` 中报 / `0930` 三季报 / `1231` 年报）；格式不对或不是季末在本地直接抛 `ValueError`。
- **`report_date` 留空**：取北京时间今天之前最近的季末（2026-11-14 取到的是 2026-09-30），不发额外请求。季末当天取的是上一个季末：当天还没有公司披露。
- `scope` 市场范围：`all`（默认，沪深京全部）/ `sh` / `sz` / `bj` / `kc` 科创板 / `cy` 创业板 / `st` 风险警示，取值同 `stock_list_em`（没有 `new`）；未知值回退 `all`。`sh` + `sz` + `bj` 的条数之和等于 `all`（实测）。
- **只取 A 股与存托凭证**（上游 `SECURITY_TYPE_CODE` 为 `058001001` / `058001008`）。上游同一张表里还有 B 股和新三板 / 老三板：实测 2026 三季报全表 5797 行，其中 B 股 77、三板股 140，本接口不返回这些（akshare 全部返回）。
- 还没有公司披露的报告期返回 `total=0` 的空结果（实测 2026-11-14 取 2026-12-31 的三大报表为空）。

## 字段处理

- 金额单位为元，同比、环比、净资产收益率、毛利率单位为 %。
- `net_profit` 是归属于母公司股东的净利润；`revenue_qoq` / `net_profit_qoq` 是单季度环比。
- `deducted_eps` 扣非每股收益基本只有年报有（实测 2026 三季报 5580 家里 27 家非空）；`dividend_plan` / `dividend_yield` 只在有分配方案的报告期有（2025 年报 5583 家里 5479 家有方案，三季报 246 家）。
- `notice_date` 首次公告日期，`update_date` 最新公告日期：有更正公告时后者更晚（实测三季报 21 家）。
- 银行等没有销售毛利率的行业 `gross_margin` 为 `None`。
- 排序同 akshare：最新公告日期、代码倒序；报告期内一家公司一行。

## 输入参数 `EarningsReportQuery`

| 名称 | 类型 | 必填 | 默认值 | 描述 |
| --- | --- | --- | --- | --- |
| `report_date` | `str \| None` | 否 | `None` | 报告期 YYYYMMDD，必须是季末（0331 / 0630 / 0930 / 1231）；留空取今天之前最近的季末 |
| `scope` | `str` | 否 | `"all"` | 市场范围：all / sh / sz / bj / kc 科创板 / cy 创业板 / st 风险警示，未知回退 all |

## 输出参数 `ReportPage[EarningsReport]`

| 名称 | 类型 | 描述 |
| --- | --- | --- |
| `total` | `int` | 上游报告的条数，通常等于 `len(items)` |
| `items` | `tuple[EarningsReport, ...]` | 全部记录，保持上游排序 |

`EarningsReport` 字段：

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `code` | `str` | — | 股票代码（`SECURITY_CODE`） |
| `name` | `str` | — | 股票简称（`SECURITY_NAME_ABBR`） |
| `market` | `str \| None` | — | 市场：sh / sz / bj，可连同 code 传给 stock_kline_em（`SECUCODE`） |
| `report_date` | `str \| None` | — | 报告期 YYYY-MM-DD（`REPORTDATE`） |
| `eps` | `float \| None` | 元 | 基本每股收益（`BASIC_EPS`） |
| `deducted_eps` | `float \| None` | 元 | 扣非每股收益（年报才有，其余报告期多为 None）（`DEDUCT_BASIC_EPS`） |
| `revenue` | `float \| None` | 元 | 营业总收入（`TOTAL_OPERATE_INCOME`） |
| `revenue_yoy` | `float \| None` | % | 营业总收入同比增长（`YSTZ`） |
| `revenue_qoq` | `float \| None` | % | 营业总收入季度环比增长（`YSHZ`） |
| `net_profit` | `float \| None` | 元 | 归属于母公司股东的净利润（`PARENT_NETPROFIT`） |
| `net_profit_yoy` | `float \| None` | % | 净利润同比增长（`SJLTZ`） |
| `net_profit_qoq` | `float \| None` | % | 净利润季度环比增长（`SJLHZ`） |
| `bps` | `float \| None` | 元 | 每股净资产（`BPS`） |
| `roe` | `float \| None` | % | 加权平均净资产收益率（`WEIGHTAVG_ROE`） |
| `cash_flow_per_share` | `float \| None` | 元 | 每股经营现金流量（`MGJYXJJE`） |
| `gross_margin` | `float \| None` | % | 销售毛利率（`XSMLL`） |
| `dividend_plan` | `str \| None` | — | 利润分配方案，如“10派3.60元(含税,扣税后3.24元)”（年报、中报才有）（`ASSIGNDSCRPT`） |
| `dividend_yield` | `float \| None` | % | 股息率（有现金分红方案时才有）（`ZXGXL`） |
| `industry` | `str \| None` | — | 所处行业（`PUBLISHNAME`） |
| `notice_date` | `str \| None` | — | 首次公告日期 YYYY-MM-DD（`NOTICE_DATE`） |
| `update_date` | `str \| None` | — | 最新公告日期 YYYY-MM-DD（有更正公告时晚于首次公告日期）（`UPDATE_DATE`） |

## DataFrame 列

`df_earnings_report_em` 的中文列名：akshare 有的列沿用其列名，并在“股票简称”后加“市场”；其余字段按同样的写法补上，顺序同模型字段。akshare 的“序号”列不输出。列顺序：股票代码 / 股票简称 / 市场 / 报告期 / 每股收益 / 扣非每股收益 / 营业总收入-营业总收入 / 营业总收入-同比增长 / 营业总收入-季度环比增长 / 净利润-净利润 / 净利润-同比增长 / 净利润-季度环比增长 / 每股净资产 / 净资产收益率 / 每股经营现金流量 / 销售毛利率 / 利润分配 / 股息率 / 所处行业 / 首次公告日期 / 最新公告日期。

## 接口示例（领域模型）

```python
from em import earnings_report_em
from em.domain.queries import EarningsReportQuery

page = earnings_report_em(EarningsReportQuery("20260930"))
print(page.total)
for item in page.items[:2]:
    print(item)
```

## 数据示例（领域模型）

```
5580
EarningsReport(code='688662', name='富信科技', market='sh', report_date='2026-09-30', eps=0.43, deducted_eps=None, revenue=505380545.2, revenue_yoy=20.6198218507, revenue_qoq=21.1176, net_profit=48402201.93, net_profit_yoy=50.04, net_profit_qoq=85.1868, bps=6.310869210324, roe=6.63, cash_flow_per_share=0.448513050064, gross_margin=31.3859942704, dividend_plan=None, dividend_yield=None, industry='其他电子Ⅱ', notice_date='2026-10-21', update_date='2026-11-14')
EarningsReport(code='688981', name='中芯国际', market='sh', report_date='2026-09-30', eps=0.91, deducted_eps=None, revenue=60618050000.0, revenue_yoy=22.4349437904, revenue_qoq=4.5915, net_profit=7314195000.0, net_profit_yoy=91.6, net_profit_qoq=-8.3528, bps=20.19059218793, roe=4.6, cash_flow_per_share=3.343183675054, gross_margin=25.5895232526, dividend_plan=None, dividend_yield=None, industry='半导体', notice_date='2026-11-13', update_date='2026-11-13')
```

## 接口示例（`DataFrame`，akshare 风格中文列名）

```python
from em import df_earnings_report_em
from em.domain.queries import EarningsReportQuery

df = df_earnings_report_em(EarningsReportQuery("20260930"))
```

## 数据示例（`DataFrame`）

```
  股票代码  股票简称 市场      报告期  每股收益  扣非每股收益  营业总收入-营业总收入  营业总收入-同比增长  营业总收入-季度环比增长  净利润-净利润  净利润-同比增长  净利润-季度环比增长  每股净资产  净资产收益率
0   688662  富信科技   sh  2026-09-30      0.43           NaN           5.053805e+08            20.619822                  21.1176   4.840220e+07            50.04              85.1868    6.310869          6.63
1   688981  中芯国际   sh  2026-09-30      0.91           NaN           6.061805e+10            22.434944                   4.5915   7.314195e+09            91.60              -8.3528   20.190592          4.60
2   688845  傲拓科技   sh  2026-09-30      0.71          0.68           2.420366e+08            20.554640                   5.0753   8.048932e+07            20.68             -14.6077    6.015516         12.60
```

示例只列出前 14 列，实际返回上面的全部列。

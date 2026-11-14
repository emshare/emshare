# 业绩快报接口

> 渠道：[eastmoney](../eastmoney.md) ｜ 源码：`src/em/channels/eastmoney/ashare_earnings/earnings_express/earnings_express_em.py`

## 接口名称

`earnings_express_em` / `df_earnings_express_em`：业绩快报（按报告期取发布了快报的公司的营业收入、净利润及去年同期、同比环比、每股净资产）

## 目标地址

- <https://data.eastmoney.com/bbsj/202512/yjkb.html>

## 描述

按报告期取发布了快报的公司的营业收入、净利润及去年同期、同比环比、每股净资产。对应 akshare `stock_yjkb_em`（`RPT_FCI_PERFORMANCEE`）。走数据中心报表，本接口按每页 500 条自动翻完全部页，返回 `ReportPage`。只请求用得到的列、查无数据返回空结果、查询写错抛 `QueryRejectedError`、翻页条数校验等公共处理见 [billboard_detail_em.md](../ashare_billboard/billboard_detail_em.md)。

## 参数规则

- `report_date` 报告期为 `YYYYMMDD`，必须是季末（`0331` 一季报 / `0630` 中报 / `0930` 三季报 / `1231` 年报）；格式不对或不是季末在本地直接抛 `ValueError`。
- **`report_date` 留空**：取北京时间今天之前最近的季末（2026-11-14 取到的是 2026-09-30），不发额外请求。季末当天取的是上一个季末：当天还没有公司披露。**快报各期数量相差很大**，留空取到的季末可能只有十几行：实测 2026-11-14，2025 年报 1188 家、2026 一季报 47 家、中报 65 家、三季报 12 家。要年报快报请显式传 `1231`。
- `scope` 市场范围：`all`（默认，沪深京全部）/ `sh` / `sz` / `bj` / `kc` 科创板 / `cy` 创业板 / `st` 风险警示，取值同 `stock_list_em`（没有 `new`）；未知值回退 `all`。`sh` + `sz` + `bj` 的条数之和等于 `all`（实测）。
- **只取 A 股与存托凭证**（上游 `SECURITY_TYPE_CODE` 为 `058001001` / `058001008`）。akshare 排除北交所；本接口默认含北交所（2025 年报快报里北交所 295 家）。
- 还没有公司披露的报告期返回 `total=0` 的空结果（实测 2026-11-14 取 2026-12-31 的三大报表为空）。

## 字段处理

- 只有发布了业绩快报的公司，不是全部公司；科创板最多（2025 年报 1188 家里 600 家）。
- 金额单位为元，同比、环比、净资产收益率单位为 %。`revenue_prev_year` / `net_profit_prev_year` 是去年同期值。
- 快报不一定披露每一项，没披露的为 `None`（如中芯国际 2025 年报快报没有每股收益和净资产收益率）。
- 排序同 akshare：最新公告日期、代码倒序；报告期内一家公司一行。

## 输入参数 `EarningsExpressQuery`

| 名称 | 类型 | 必填 | 默认值 | 描述 |
| --- | --- | --- | --- | --- |
| `report_date` | `str \| None` | 否 | `None` | 报告期 YYYYMMDD，必须是季末（0331 / 0630 / 0930 / 1231）；留空取今天之前最近的季末 |
| `scope` | `str` | 否 | `"all"` | 市场范围：all / sh / sz / bj / kc 科创板 / cy 创业板 / st 风险警示，未知回退 all |

## 输出参数 `ReportPage[EarningsExpress]`

| 名称 | 类型 | 描述 |
| --- | --- | --- |
| `total` | `int` | 上游报告的条数，通常等于 `len(items)` |
| `items` | `tuple[EarningsExpress, ...]` | 全部记录，保持上游排序 |

`EarningsExpress` 字段：

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `code` | `str` | — | 股票代码（`SECURITY_CODE`） |
| `name` | `str` | — | 股票简称（`SECURITY_NAME_ABBR`） |
| `market` | `str \| None` | — | 市场：sh / sz / bj，可连同 code 传给 stock_kline_em（`SECUCODE`） |
| `report_date` | `str \| None` | — | 报告期 YYYY-MM-DD（`REPORT_DATE`） |
| `eps` | `float \| None` | 元 | 基本每股收益（`BASIC_EPS`） |
| `revenue` | `float \| None` | 元 | 营业收入（`TOTAL_OPERATE_INCOME`） |
| `revenue_prev_year` | `float \| None` | 元 | 去年同期营业收入（`TOTAL_OPERATE_INCOME_SQ`） |
| `revenue_yoy` | `float \| None` | % | 营业收入同比增长（`YSTZ`） |
| `revenue_qoq` | `float \| None` | % | 营业收入季度环比增长（`DJDYSHZ`） |
| `net_profit` | `float \| None` | 元 | 归属于母公司股东的净利润（`PARENT_NETPROFIT`） |
| `net_profit_prev_year` | `float \| None` | 元 | 去年同期净利润（`PARENT_NETPROFIT_SQ`） |
| `net_profit_yoy` | `float \| None` | % | 净利润同比增长（`JLRTBZCL`） |
| `net_profit_qoq` | `float \| None` | % | 净利润季度环比增长（`DJDJLHZ`） |
| `bps` | `float \| None` | 元 | 每股净资产（`PARENT_BVPS`） |
| `roe` | `float \| None` | % | 加权平均净资产收益率（`WEIGHTAVG_ROE`） |
| `industry` | `str \| None` | — | 所处行业（`PUBLISHNAME`） |
| `notice_date` | `str \| None` | — | 公告日期 YYYY-MM-DD（`NOTICE_DATE`） |
| `update_date` | `str \| None` | — | 最新公告日期 YYYY-MM-DD（`UPDATE_DATE`） |

## DataFrame 列

`df_earnings_express_em` 的中文列名：akshare 有的列沿用其列名，并在“股票简称”后加“市场”；其余字段按同样的写法补上，顺序同模型字段。akshare 的“序号”列不输出。列顺序：股票代码 / 股票简称 / 市场 / 报告期 / 每股收益 / 营业收入-营业收入 / 营业收入-去年同期 / 营业收入-同比增长 / 营业收入-季度环比增长 / 净利润-净利润 / 净利润-去年同期 / 净利润-同比增长 / 净利润-季度环比增长 / 每股净资产 / 净资产收益率 / 所处行业 / 公告日期 / 最新公告日期。

## 接口示例（领域模型）

```python
from em import earnings_express_em
from em.domain.queries import EarningsExpressQuery

page = earnings_express_em(EarningsExpressQuery("20251231"))
print(page.total)
for item in page.items[:2]:
    print(item)
```

## 数据示例（领域模型）

```
1188
EarningsExpress(code='603092', name='德力佳', market='sh', report_date='2025-12-31', eps=None, revenue=None, revenue_prev_year=3715339824.37, revenue_yoy=None, revenue_qoq=None, net_profit=None, net_profit_prev_year=533785548.78, net_profit_yoy=None, net_profit_qoq=None, bps=13.79, roe=None, industry='风电设备', notice_date='2026-04-23', update_date='2026-10-21')
EarningsExpress(code='300107', name='建新股份', market='sz', report_date='2025-12-31', eps=None, revenue=None, revenue_prev_year=605376475.82, revenue_yoy=None, revenue_qoq=None, net_profit=None, net_profit_prev_year=19365723.28, net_profit_yoy=None, net_profit_qoq=None, bps=2.61, roe=None, industry='化学制品', notice_date='2026-10-21', update_date='2026-10-21')
```

## 接口示例（`DataFrame`，akshare 风格中文列名）

```python
from em import df_earnings_express_em
from em.domain.queries import EarningsExpressQuery

df = df_earnings_express_em(EarningsExpressQuery("20251231"))
```

## 数据示例（`DataFrame`）

```
  股票代码  股票简称 市场      报告期  每股收益  营业收入-营业收入  营业收入-去年同期  营业收入-同比增长  营业收入-季度环比增长  净利润-净利润  净利润-去年同期  净利润-同比增长  净利润-季度环比增长
0   603092    德力佳   sh  2025-12-31       NaN                NaN       3.715340e+09                NaN                    NaN            NaN     5.337855e+08              NaN                  NaN
1   300107  建新股份   sz  2025-12-31       NaN                NaN       6.053765e+08                NaN                    NaN            NaN     1.936572e+07              NaN                  NaN
2   000028  国药一致   sz  2025-12-31       NaN                NaN       7.437849e+10                NaN                    NaN            NaN     6.424934e+08              NaN                  NaN
```

示例只列出前 13 列，实际返回上面的全部列。

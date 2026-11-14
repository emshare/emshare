# 业绩预告接口

> 渠道：[eastmoney](../eastmoney.md) ｜ 源码：`src/em/channels/eastmoney/ashare_earnings/earnings_forecast/earnings_forecast_em.py`

## 接口名称

`earnings_forecast_em` / `df_earnings_forecast_em`：业绩预告（按报告期取各公司的预测指标、预测数值上下限、业绩变动幅度、预告类型与变动原因）

## 目标地址

- <https://data.eastmoney.com/bbsj/202512/yjyg.html>

## 描述

按报告期取各公司的预测指标、预测数值上下限、业绩变动幅度、预告类型与变动原因。对应 akshare `stock_yjyg_em`（`RPT_PUBLIC_OP_NEWPREDICT`）。走数据中心报表，本接口按每页 500 条自动翻完全部页，返回 `ReportPage`。只请求用得到的列、查无数据返回空结果、查询写错抛 `QueryRejectedError`、翻页条数校验等公共处理见 [billboard_detail_em.md](../ashare_billboard/billboard_detail_em.md)。

## 参数规则

- `report_date` 报告期为 `YYYYMMDD`，必须是季末（`0331` 一季报 / `0630` 中报 / `0930` 三季报 / `1231` 年报）；格式不对或不是季末在本地直接抛 `ValueError`。
- **`report_date` 留空**：取北京时间今天之前最近的季末（2026-11-14 取到的是 2026-09-30），不发额外请求。季末当天取的是上一个季末：当天还没有公司披露。**预告各期数量相差很大**：实测 2026-11-14，2025 年报 7719 行、2026 一季报 585 行、中报 4844 行、三季报 529 行；下一个年报期（2026-12-31）已有 55 行，留空取不到它，要显式传 `20261231`。
- `scope` 市场范围：`all`（默认，沪深京全部）/ `sh` / `sz` / `bj` / `kc` 科创板 / `cy` 创业板 / `st` 风险警示，取值同 `stock_list_em`（没有 `new`）；未知值回退 `all`。`sh` + `sz` + `bj` 的条数之和等于 `all`（实测）。
- **只取 A 股与存托凭证**（上游 `SECURITY_TYPE_CODE` 为 `058001001` / `058001008`）。上游同表里还有少量 B 股（2025 年报 110 行），本接口不返回。
- 还没有公司披露的报告期返回 `total=0` 的空结果（实测 2026-11-14 取 2026-12-31 的三大报表为空）。

## 字段处理

- **一家公司每项预测指标一行，不能按行数统计公司数**：实测 2025 年报 7719 行对应 3039 家公司，多数是 2 ~ 3 行。指标有：归属于上市公司股东的净利润（3025 行）、扣除非经常性损益后的净利润（2909 行）、每股收益（847 行）、营业收入（626 行）、扣除后营业收入（261 行）。
- 金额单位为元；**指标为“每股收益”时 `forecast_value` / `lower` / `upper` / `prev_year` 的单位是元 / 股**。幅度单位为 %。
- `forecast_value` 是上下限的均值，`change_pct` 是同比变动幅度上下限的均值；只给了文字、没有数值区间的预告这些为 `None`（实测 2025 年报 13 行）。
- `forecast_type`：预增 / 预减 / 略增 / 略减 / 扭亏 / 首亏 / 续亏 / 续盈 / 减亏 / 增亏 / 不确定。
- 同一家公司各指标的 `reason`（变动原因）绝大多数是同一段文字（实测 2025 年报有多项指标的 2917 家里 2907 家）。
- 排序同 akshare：公告日期、代码倒序；末尾补指标代码，（代码, 指标）唯一，翻页顺序稳定。

## 输入参数 `EarningsForecastQuery`

| 名称 | 类型 | 必填 | 默认值 | 描述 |
| --- | --- | --- | --- | --- |
| `report_date` | `str \| None` | 否 | `None` | 报告期 YYYYMMDD，必须是季末（0331 / 0630 / 0930 / 1231）；留空取今天之前最近的季末 |
| `scope` | `str` | 否 | `"all"` | 市场范围：all / sh / sz / bj / kc 科创板 / cy 创业板 / st 风险警示，未知回退 all |

## 输出参数 `ReportPage[EarningsForecast]`

| 名称 | 类型 | 描述 |
| --- | --- | --- |
| `total` | `int` | 上游报告的条数，通常等于 `len(items)` |
| `items` | `tuple[EarningsForecast, ...]` | 全部记录，保持上游排序 |

`EarningsForecast` 字段：

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `code` | `str` | — | 股票代码（`SECURITY_CODE`） |
| `name` | `str` | — | 股票简称（`SECURITY_NAME_ABBR`） |
| `market` | `str \| None` | — | 市场：sh / sz / bj，可连同 code 传给 stock_kline_em（`SECUCODE`） |
| `report_date` | `str \| None` | — | 报告期 YYYY-MM-DD（`REPORT_DATE`） |
| `notice_date` | `str \| None` | — | 公告日期 YYYY-MM-DD（`NOTICE_DATE`） |
| `indicator` | `str \| None` | — | 预测指标，如“归属于上市公司股东的净利润”“每股收益”（一家公司每项指标一行）（`PREDICT_FINANCE`） |
| `summary` | `str \| None` | — | 业绩变动的文字说明（`PREDICT_CONTENT`） |
| `forecast_value` | `float \| None` | 元 | 预测数值：上下限的均值（指标为每股收益时单位是元 / 股）（`FORECAST_JZ`） |
| `lower` | `float \| None` | 元 | 预测下限（`PREDICT_AMT_LOWER`） |
| `upper` | `float \| None` | 元 | 预测上限（`PREDICT_AMT_UPPER`） |
| `change_pct` | `float \| None` | % | 业绩变动幅度：同比变动上下限的均值（`INCREASE_JZ`） |
| `change_pct_lower` | `float \| None` | % | 同比变动幅度下限（`ADD_AMP_LOWER`） |
| `change_pct_upper` | `float \| None` | % | 同比变动幅度上限（`ADD_AMP_UPPER`） |
| `reason` | `str \| None` | — | 业绩变动原因（`CHANGE_REASON_EXPLAIN`） |
| `forecast_type` | `str \| None` | — | 预告类型：预增 / 预减 / 略增 / 略减 / 扭亏 / 首亏 / 续亏 / 续盈 / 减亏 / 增亏 / 不确定（`PREDICT_TYPE`） |
| `prev_year` | `float \| None` | 元 | 上年同期值（`PREYEAR_SAME_PERIOD`） |

## DataFrame 列

`df_earnings_forecast_em` 的中文列名：akshare 有的列沿用其列名，并在“股票简称”后加“市场”；其余字段按同样的写法补上，顺序同模型字段。akshare 的“序号”列不输出。列顺序：股票代码 / 股票简称 / 市场 / 报告期 / 公告日期 / 预测指标 / 业绩变动 / 预测数值 / 预测下限 / 预测上限 / 业绩变动幅度 / 变动幅度下限 / 变动幅度上限 / 业绩变动原因 / 预告类型 / 上年同期值。

## 接口示例（领域模型）

```python
from em import earnings_forecast_em
from em.domain.queries import EarningsForecastQuery

page = earnings_forecast_em(EarningsForecastQuery("20251231"))
print(page.total)
for item in page.items[:2]:
    print(item)
```

## 数据示例（领域模型）

```
7719
EarningsForecast(code='603378', name='*ST亚士', market='sh', report_date='2025-12-31', notice_date='2026-04-29', indicator='归属于上市公司股东的净利润', summary='预计2025年1-12月归属于上市公司股东的净利润亏损:135,500万元至139,500万元。', forecast_value=-1375000000.0, lower=-1395000000.0, upper=-1355000000.0, change_pct=-317.575, change_pct_lower=-323.65, change_pct_upper=-311.5, reason='报告期内,受房地产和建筑行业持续疲软和订单大幅下滑影响,公司营业收入下滑,毛利率下降。此外,公司按照《企业会计准则》,基于谨慎性原则,对出现减值迹象的固定资产、在建工程、应收账款等资产计提减值准备,对前期确认的递延所得税资产予以冲回。综合以上因素,导致公司年度利润出现亏损。', forecast_type='增亏', prev_year=-329285000.0)
EarningsForecast(code='603378', name='*ST亚士', market='sh', report_date='2025-12-31', notice_date='2026-04-29', indicator='扣除非经常性损益后的净利润', summary='预计2025年1-12月扣除非经常性损益后的净利润亏损:134,500万元至138,500万元。', forecast_value=-1365000000.0, lower=-1385000000.0, upper=-1345000000.0, change_pct=-281.69, change_pct_lower=-287.28, change_pct_upper=-276.1, reason='报告期内,受房地产和建筑行业持续疲软和订单大幅下滑影响,公司营业收入下滑,毛利率下降。此外,公司按照《企业会计准则》,基于谨慎性原则,对出现减值迹象的固定资产、在建工程、应收账款等资产计提减值准备,对前期确认的递延所得税资产予以冲回。综合以上因素,导致公司年度利润出现亏损。', forecast_type='增亏', prev_year=-357617900.0)
```

## 接口示例（`DataFrame`，akshare 风格中文列名）

```python
from em import df_earnings_forecast_em
from em.domain.queries import EarningsForecastQuery

df = df_earnings_forecast_em(EarningsForecastQuery("20251231"))
```

## 数据示例（`DataFrame`）

```
  股票代码 股票简称 市场      报告期    公告日期                    预测指标                       业绩变动      预测数值      预测下限      预测上限  业绩变动幅度  变动幅度下限  变动幅度上限                          业绩变动原因 预告类型   上年同期值
0   603378  *ST亚士   sh  2025-12-31  2026-04-29  归属于上市公司股东的净利润  预计2025年1-12月归属于上市公… -1.375000e+09 -1.395000e+09 -1.355000e+09      -317.575       -323.65       -311.50  报告期内,受房地产和建筑行业持续疲软…     增亏 -329285000.0
1   603378  *ST亚士   sh  2025-12-31  2026-04-29  扣除非经常性损益后的净利润  预计2025年1-12月扣除非经常性… -1.365000e+09 -1.385000e+09 -1.345000e+09      -281.690       -287.28       -276.10  报告期内,受房地产和建筑行业持续疲软…     增亏 -357617900.0
2   603313   梦百合   sh  2025-12-31  2026-04-29  归属于上市公司股东的净利润  预计2025年1-12月归属于上市公… -9.822500e+06 -9.822500e+06 -9.822500e+06        93.510         93.51         93.51       2026年1月底,经财务部门内部测算…     减亏 -151420300.0
```

示例里的长文本列为便于阅读做了截断（以 `…` 结尾），实际返回完整内容。

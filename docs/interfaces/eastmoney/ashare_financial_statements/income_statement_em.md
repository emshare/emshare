# 利润表接口

> 渠道：[eastmoney](../eastmoney.md) ｜ 源码：`src/em/channels/eastmoney/ashare_financial_statements/income_statement/income_statement_em.py`

## 接口名称

`income_statement_em` / `df_income_statement_em`：利润表（按报告期取各公司的营业总收入、营业总支出及各项费用、营业利润、利润总额、净利润、扣非净利润及同比）

## 目标地址

- <https://data.eastmoney.com/bbsj/202609/lrb.html>

## 描述

按报告期取各公司的营业总收入、营业总支出及各项费用、营业利润、利润总额、净利润、扣非净利润及同比。对应 akshare `stock_lrb_em`（`RPT_DMSK_FN_INCOME`）。走数据中心报表，本接口按每页 500 条自动翻完全部页，返回 `ReportPage`。只请求用得到的列、查无数据返回空结果、查询写错抛 `QueryRejectedError`、翻页条数校验等公共处理见 [billboard_detail_em.md](../ashare_billboard/billboard_detail_em.md)。

## 参数规则

- `report_date` 报告期为 `YYYYMMDD`，必须是季末（`0331` 一季报 / `0630` 中报 / `0930` 三季报 / `1231` 年报）；格式不对或不是季末在本地直接抛 `ValueError`。
- **`report_date` 留空**：取北京时间今天之前最近的季末（2026-11-14 取到的是 2026-09-30），不发额外请求。季末当天取的是上一个季末：当天还没有公司披露。
- `scope` 市场范围：`all`（默认，沪深京全部）/ `sh` / `sz` / `bj` / `kc` 科创板 / `cy` 创业板 / `st` 风险警示，取值同 `stock_list_em`（没有 `new`）；未知值回退 `all`。`sh` + `sz` + `bj` 的条数之和等于 `all`（实测）。
- **只取 A 股与存托凭证**（上游 `SECURITY_TYPE_CODE` 为 `058001001` / `058001008`）。三大报表上游本来就只有这两类。akshare 默认排除北交所、资产负债表另有北交所专用函数；本接口默认含北交所，单取用 `scope="bj"`。
- 还没有公司披露的报告期返回 `total=0` 的空结果（实测 2026-11-14 取 2026-12-31 的三大报表为空）。

## 字段处理

- **只有主要科目，不是完整报表**：这是东财“数据中心—年报季报”页面的口径，每张表二三十个科目加同比 / 占比；要完整科目请用 F10 财务分析类接口（本工程未做）。
- **银行、券商、保险专用科目只有对应行业有值，一般公司为 `None`；反过来一般公司的科目金融类为 `None`**。实测 2026 三季报 5582 家里银行 42 家、券商 50 家、保险 5 家。
- 各科目是年初至报告期末的累计数（三季报是前三季度），不是单季度。
- `*_yoy` 是该科目的同比增长，单位 %（实测逐家核对：营业总收入、营业总支出、营业利润全部一致；净利润、扣非净利润各有十几家对不上，可能是上年同期数被追溯调整过）。
- `net_profit` 是归属于母公司股东的净利润。
- `operating_expense` 营业支出：一般公司等于 `operating_cost` 营业成本（实测 5482 家全部相等）；银行、保险没有营业成本，营业支出即营业总支出。
- `operating_income` 只有银行、保险有，等于 `revenue`；`business_admin_expense` 只有银行有，等于 `admin_expense`。
- `net_fee_income_yoy`（手续费及佣金净收入同比）各期全为 `None`；`surrenders`（退保金）、`claims_expense`（赔付支出）近年全为 `None`，2020 年报及以前 5 家保险公司有值。
- 金额单位为元。`market` 由上游 `SECUCODE` 后缀得出，可连同 `code` 直接传给 `stock_kline_em`。
- `notice_date` 是公告日期；有更正公告时是最新一次的日期。
- 排序同 akshare：公告日期、代码倒序；报告期内一家公司一行。
- 可取的报告期早于 akshare 文档说的 2010 年一季报（实测资产负债表 2009-12-31 有 2528 家），越早家数越少。

## 输入参数 `IncomeStatementQuery`

| 名称 | 类型 | 必填 | 默认值 | 描述 |
| --- | --- | --- | --- | --- |
| `report_date` | `str \| None` | 否 | `None` | 报告期 YYYYMMDD，必须是季末（0331 / 0630 / 0930 / 1231）；留空取今天之前最近的季末 |
| `scope` | `str` | 否 | `"all"` | 市场范围：all / sh / sz / bj / kc 科创板 / cy 创业板 / st 风险警示，未知回退 all |

## 输出参数 `ReportPage[IncomeStatement]`

| 名称 | 类型 | 描述 |
| --- | --- | --- |
| `total` | `int` | 上游报告的条数，通常等于 `len(items)` |
| `items` | `tuple[IncomeStatement, ...]` | 全部记录，保持上游排序 |

`IncomeStatement` 字段：

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `code` | `str` | — | 股票代码（`SECURITY_CODE`） |
| `name` | `str` | — | 股票简称（`SECURITY_NAME_ABBR`） |
| `market` | `str \| None` | — | 市场：sh / sz / bj，可连同 code 传给 stock_kline_em（`SECUCODE`） |
| `industry` | `str \| None` | — | 所处行业（`INDUSTRY_NAME`） |
| `report_date` | `str \| None` | — | 报告期 YYYY-MM-DD（`REPORT_DATE`） |
| `notice_date` | `str \| None` | — | 公告日期 YYYY-MM-DD（`NOTICE_DATE`） |
| `net_profit` | `float \| None` | 元 | 归属于母公司股东的净利润（`PARENT_NETPROFIT`） |
| `net_profit_yoy` | `float \| None` | % | 净利润同比（`PARENT_NETPROFIT_RATIO`） |
| `deducted_net_profit` | `float \| None` | 元 | 扣除非经常性损益后的净利润（`DEDUCT_PARENT_NETPROFIT`） |
| `deducted_net_profit_yoy` | `float \| None` | % | 扣非净利润同比（`DPN_RATIO`） |
| `revenue` | `float \| None` | 元 | 营业总收入（`TOTAL_OPERATE_INCOME`） |
| `revenue_yoy` | `float \| None` | % | 营业总收入同比（`TOI_RATIO`） |
| `operating_expense` | `float \| None` | 元 | 营业支出：一般公司等于营业成本，银行、保险为营业支出（`OPERATE_EXPENSE`） |
| `operating_expense_yoy` | `float \| None` | % | 营业支出同比（`OPERATE_EXPENSE_RATIO`） |
| `operating_cost` | `float \| None` | 元 | 营业成本（金融类为 None）（`OPERATE_COST`） |
| `selling_expense` | `float \| None` | 元 | 销售费用（`SALE_EXPENSE`） |
| `admin_expense` | `float \| None` | 元 | 管理费用（银行、券商为业务及管理费）（`MANAGE_EXPENSE`） |
| `finance_expense` | `float \| None` | 元 | 财务费用（`FINANCE_EXPENSE`） |
| `taxes_and_surcharges` | `float \| None` | 元 | 税金及附加（`OPERATE_TAX_ADD`） |
| `total_operating_cost` | `float \| None` | 元 | 营业总支出（`TOTAL_OPERATE_COST`） |
| `total_operating_cost_yoy` | `float \| None` | % | 营业总支出同比（`TOE_RATIO`） |
| `operating_profit` | `float \| None` | 元 | 营业利润（`OPERATE_PROFIT`） |
| `operating_profit_yoy` | `float \| None` | % | 营业利润同比（`OPERATE_PROFIT_RATIO`） |
| `total_profit` | `float \| None` | 元 | 利润总额（`TOTAL_PROFIT`） |
| `income_tax` | `float \| None` | 元 | 所得税费用（`INCOME_TAX`） |
| `operating_income` | `float \| None` | 元 | 营业收入（只有银行、保险有，等于营业总收入）（`OPERATE_INCOME`） |
| `net_interest_income` | `float \| None` | 元 | 利息净收入（`INTEREST_NI`） |
| `net_interest_income_yoy` | `float \| None` | % | 利息净收入同比（银行）（`INTEREST_NI_RATIO`） |
| `net_fee_income` | `float \| None` | 元 | 手续费及佣金净收入（`FEE_COMMISSION_NI`） |
| `net_fee_income_yoy` | `float \| None` | % | 手续费及佣金净收入同比（`FCN_RATIO`） |
| `business_admin_expense` | `float \| None` | 元 | 业务及管理费（银行，等于 admin_expense）（`MANAGE_EXPENSE_BANK`） |
| `earned_premiums` | `float \| None` | 元 | 已赚保费（保险）（`EARNED_PREMIUM`） |
| `earned_premiums_yoy` | `float \| None` | % | 已赚保费同比（`EARNED_PREMIUM_RATIO`） |
| `investment_income` | `float \| None` | 元 | 投资收益（保险）（`INVEST_INCOME`） |
| `surrenders` | `float \| None` | 元 | 退保金（保险）（`SURRENDER_VALUE`） |
| `claims_expense` | `float \| None` | 元 | 赔付支出（保险）（`COMPENSATE_EXPENSE`） |

## DataFrame 列

`df_income_statement_em` 的中文列名：akshare 有的列沿用其列名，并在“股票简称”后加“市场”；其余字段按同样的写法补上，顺序同模型字段。akshare 的“序号”列不输出。列顺序：股票代码 / 股票简称 / 市场 / 所处行业 / 报告期 / 公告日期 / 净利润 / 净利润同比 / 扣非净利润 / 扣非净利润同比 / 营业总收入 / 营业总收入同比 / 营业总支出-营业支出 / 营业总支出-营业支出同比 / 营业总支出-营业成本 / 营业总支出-销售费用 / 营业总支出-管理费用 / 营业总支出-财务费用 / 营业总支出-税金及附加 / 营业总支出-营业总支出 / 营业总支出-营业总支出同比 / 营业利润 / 营业利润同比 / 利润总额 / 所得税 / 金融-营业收入 / 金融-利息净收入 / 金融-利息净收入同比 / 金融-手续费及佣金净收入 / 金融-手续费及佣金净收入同比 / 银行-业务及管理费 / 保险-已赚保费 / 保险-已赚保费同比 / 保险-投资收益 / 保险-退保金 / 保险-赔付支出。

## 接口示例（领域模型）

```python
from em import income_statement_em
from em.domain.queries import IncomeStatementQuery

page = income_statement_em(IncomeStatementQuery("20260930"))
print(page.total)
for item in page.items[:2]:
    print(item)
```

## 数据示例（领域模型）

```
5582
IncomeStatement(code='688662', name='富信科技', market='sh', industry='其他电子Ⅱ', report_date='2026-09-30', notice_date='2026-11-14', net_profit=48402201.93, net_profit_yoy=50.04, deducted_net_profit=48014337.73, deducted_net_profit_yoy=58.286678382667, revenue=505380545.2, revenue_yoy=20.6198218507, operating_expense=346761836.24, operating_expense_yoy=12.1531596273, operating_cost=346761836.24, selling_expense=15177186.54, admin_expense=35020864.31, finance_expense=5944777.16, taxes_and_surcharges=3699005.6, total_operating_cost=429980438.1, total_operating_cost_yoy=12.5300015607, operating_profit=71021271.48, operating_profit_yoy=97.722044736626, total_profit=70297330.18, income_tax=15609654.69, operating_income=None, net_interest_income=None, net_interest_income_yoy=None, net_fee_income=None, net_fee_income_yoy=None, business_admin_expense=None, earned_premiums=None, earned_premiums_yoy=None, investment_income=None, surrenders=None, claims_expense=None)
IncomeStatement(code='688981', name='中芯国际', market='sh', industry='半导体', report_date='2026-09-30', notice_date='2026-11-13', net_profit=7314195000.0, net_profit_yoy=91.6, deducted_net_profit=5632734000.0, deducted_net_profit_yoy=77.30446089879, revenue=60618050000.0, revenue_yoy=22.4349437904, operating_expense=45106180000.0, operating_expense_yoy=18.5501115861, operating_cost=45106180000.0, selling_expense=227505000.0, admin_expense=2196815000.0, finance_expense=16060000.0, taxes_and_surcharges=311840000.0, total_operating_cost=52335439000.0, total_operating_cost_yoy=18.2089280725, operating_profit=11658076000.0, operating_profit_yoy=88.344556170191, total_profit=11673466000.0, income_tax=878031000.0, operating_income=None, net_interest_income=None, net_interest_income_yoy=None, net_fee_income=None, net_fee_income_yoy=None, business_admin_expense=None, earned_premiums=None, earned_premiums_yoy=None, investment_income=None, surrenders=None, claims_expense=None)
```

## 接口示例（`DataFrame`，akshare 风格中文列名）

```python
from em import df_income_statement_em
from em.domain.queries import IncomeStatementQuery

df = df_income_statement_em(IncomeStatementQuery("20260930"))
```

## 数据示例（`DataFrame`）

```
  股票代码  股票简称 市场    所处行业      报告期    公告日期        净利润  净利润同比    扣非净利润  扣非净利润同比    营业总收入  营业总收入同比  营业总支出-营业支出
0   688662  富信科技   sh   其他电子Ⅱ  2026-09-30  2026-11-14  4.840220e+07       50.04  4.801434e+07       58.286678  5.053805e+08       20.619822         3.467618e+08
1   688981  中芯国际   sh      半导体  2026-09-30  2026-11-13  7.314195e+09       91.60  5.632734e+09       77.304461  6.061805e+10       22.434944         4.510618e+10
2   688845  傲拓科技   sh  自动化设备  2026-09-30  2026-11-13  8.048932e+07       20.68  7.680105e+07       21.496892  2.420366e+08       20.554640         6.610809e+07
```

示例只列出前 13 列，实际返回上面的全部列。

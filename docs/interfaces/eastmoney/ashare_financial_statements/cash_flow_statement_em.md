# 现金流量表接口

> 渠道：[eastmoney](../eastmoney.md) ｜ 源码：`src/em/channels/eastmoney/ashare_financial_statements/cash_flow_statement/cash_flow_statement_em.py`

## 接口名称

`cash_flow_statement_em` / `df_cash_flow_statement_em`：现金流量表（按报告期取各公司的经营、投资、筹资活动现金流量净额及其净现金流占比、净现金流及同比）

## 目标地址

- <https://data.eastmoney.com/bbsj/202609/xjll.html>

## 描述

按报告期取各公司的经营、投资、筹资活动现金流量净额及其净现金流占比、净现金流及同比。对应 akshare `stock_xjll_em`（`RPT_DMSK_FN_CASHFLOW`）。走数据中心报表，本接口按每页 500 条自动翻完全部页，返回 `ReportPage`。只请求用得到的列、查无数据返回空结果、查询写错抛 `QueryRejectedError`、翻页条数校验等公共处理见 [billboard_detail_em.md](../ashare_billboard/billboard_detail_em.md)。

## 参数规则

- `report_date` 报告期为 `YYYYMMDD`，必须是季末（`0331` 一季报 / `0630` 中报 / `0930` 三季报 / `1231` 年报）；格式不对或不是季末在本地直接抛 `ValueError`。
- **`report_date` 留空**：取北京时间今天之前最近的季末（2026-11-14 取到的是 2026-09-30），不发额外请求。季末当天取的是上一个季末：当天还没有公司披露。
- `scope` 市场范围：`all`（默认，沪深京全部）/ `sh` / `sz` / `bj` / `kc` 科创板 / `cy` 创业板 / `st` 风险警示，取值同 `stock_list_em`（没有 `new`）；未知值回退 `all`。`sh` + `sz` + `bj` 的条数之和等于 `all`（实测）。
- **只取 A 股与存托凭证**（上游 `SECURITY_TYPE_CODE` 为 `058001001` / `058001008`）。三大报表上游本来就只有这两类。akshare 默认排除北交所、资产负债表另有北交所专用函数；本接口默认含北交所，单取用 `scope="bj"`。
- 还没有公司披露的报告期返回 `total=0` 的空结果（实测 2026-11-14 取 2026-12-31 的三大报表为空）。

## 字段处理

- **只有主要科目，不是完整报表**：这是东财“数据中心—年报季报”页面的口径，每张表二三十个科目加同比 / 占比；要完整科目请用 F10 财务分析类接口（本工程未做）。
- **银行、券商、保险专用科目只有对应行业有值，一般公司为 `None`；反过来一般公司的科目金融类为 `None`**。实测 2026 三季报 5582 家里银行 42 家、券商 50 家、保险 5 家。
- 各科目是年初至报告期末的累计数。
- **`*_share` 不是同比，是该科目 ÷ 净现金流的绝对值 × 100**（实测 2026 三季报逐家核对一致）：净现金流很小时可以是几千甚至上万，科目为负时为负。只有 `net_cash_flow_yoy` 是同比。
- `net_cash_flow` 净现金流是现金及现金等价物净增加额；它不一定等于经营、投资、筹资三项净额之和：按会计口径还要加上汇率变动对现金的影响（实测 2026 三季报三项之和与净现金流相差 2% 以内的有 3121 家）。
- `begin_cash` / `end_cash` 期初、期末现金余额只有券商有（实测 50 家），`end_cash` − `begin_cash` = `net_cash_flow`（50 家全部成立）。
- `premiums_cash`、`claims_cash_paid` 近年全为 `None`，2020 年报及以前 5 家保险公司有值。
- 金额单位为元。`market` 由上游 `SECUCODE` 后缀得出，可连同 `code` 直接传给 `stock_kline_em`。
- `notice_date` 是公告日期；有更正公告时是最新一次的日期。
- 排序同 akshare：公告日期、代码倒序；报告期内一家公司一行。
- 可取的报告期早于 akshare 文档说的 2010 年一季报（实测资产负债表 2009-12-31 有 2528 家），越早家数越少。

## 输入参数 `CashFlowStatementQuery`

| 名称 | 类型 | 必填 | 默认值 | 描述 |
| --- | --- | --- | --- | --- |
| `report_date` | `str \| None` | 否 | `None` | 报告期 YYYYMMDD，必须是季末（0331 / 0630 / 0930 / 1231）；留空取今天之前最近的季末 |
| `scope` | `str` | 否 | `"all"` | 市场范围：all / sh / sz / bj / kc 科创板 / cy 创业板 / st 风险警示，未知回退 all |

## 输出参数 `ReportPage[CashFlowStatement]`

| 名称 | 类型 | 描述 |
| --- | --- | --- |
| `total` | `int` | 上游报告的条数，通常等于 `len(items)` |
| `items` | `tuple[CashFlowStatement, ...]` | 全部记录，保持上游排序 |

`CashFlowStatement` 字段：

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `code` | `str` | — | 股票代码（`SECURITY_CODE`） |
| `name` | `str` | — | 股票简称（`SECURITY_NAME_ABBR`） |
| `market` | `str \| None` | — | 市场：sh / sz / bj，可连同 code 传给 stock_kline_em（`SECUCODE`） |
| `industry` | `str \| None` | — | 所处行业（`INDUSTRY_NAME`） |
| `report_date` | `str \| None` | — | 报告期 YYYY-MM-DD（`REPORT_DATE`） |
| `notice_date` | `str \| None` | — | 公告日期 YYYY-MM-DD（`NOTICE_DATE`） |
| `net_cash_flow` | `float \| None` | 元 | 现金及现金等价物净增加额（`CCE_ADD`） |
| `net_cash_flow_yoy` | `float \| None` | % | 净现金流同比增长（`CCE_ADD_RATIO`） |
| `operating_net` | `float \| None` | 元 | 经营活动产生的现金流量净额（`NETCASH_OPERATE`） |
| `operating_net_share` | `float \| None` | % | 经营活动现金流量净额的净现金流占比（`NETCASH_OPERATE_RATIO`） |
| `sales_cash` | `float \| None` | 元 | 销售商品、提供劳务收到的现金（`SALES_SERVICES`） |
| `sales_cash_share` | `float \| None` | % | 销售商品、提供劳务收到的现金的净现金流占比（`SALES_SERVICES_RATIO`） |
| `staff_cash_paid` | `float \| None` | 元 | 支付给职工以及为职工支付的现金（`PAY_STAFF_CASH`） |
| `staff_cash_paid_share` | `float \| None` | % | 支付给职工的现金的净现金流占比（`PSC_RATIO`） |
| `investing_net` | `float \| None` | 元 | 投资活动产生的现金流量净额（`NETCASH_INVEST`） |
| `investing_net_share` | `float \| None` | % | 投资活动现金流量净额的净现金流占比（`NETCASH_INVEST_RATIO`） |
| `investment_income_cash` | `float \| None` | 元 | 取得投资收益收到的现金（`RECEIVE_INVEST_INCOME`） |
| `investment_income_cash_share` | `float \| None` | % | 取得投资收益收到的现金的净现金流占比（`RII_RATIO`） |
| `capex` | `float \| None` | 元 | 购建固定资产、无形资产和其他长期资产支付的现金（`CONSTRUCT_LONG_ASSET`） |
| `capex_share` | `float \| None` | % | 购建长期资产支付的现金的净现金流占比（`CLA_RATIO`） |
| `financing_net` | `float \| None` | 元 | 筹资活动产生的现金流量净额（`NETCASH_FINANCE`） |
| `financing_net_share` | `float \| None` | % | 筹资活动现金流量净额的净现金流占比（`NETCASH_FINANCE_RATIO`） |
| `customer_deposits_increase` | `float \| None` | 元 | 客户存款和同业存放款项净增加额（银行）（`CUSTOMER_DEPOSIT_ADD`） |
| `customer_deposits_increase_share` | `float \| None` | % | 客户存款净增加额的净现金流占比（`CDA_RATIO`） |
| `interbank_deposits_increase` | `float \| None` | 元 | 同业及其他金融机构存放款净增加额（银行）（`DEPOSIT_IOFI_OTHER`） |
| `interbank_deposits_increase_share` | `float \| None` | % | 同业存放款净增加额的净现金流占比（`DIO_RATIO`） |
| `loans_increase` | `float \| None` | 元 | 客户贷款及垫款净增加额（银行）（`LOAN_ADVANCE_ADD`） |
| `loans_increase_share` | `float \| None` | % | 客户贷款及垫款净增加额的净现金流占比（`LAA_RATIO`） |
| `interest_commission_cash` | `float \| None` | 元 | 收取利息、手续费及佣金的现金（券商）（`RECEIVE_INTEREST_COMMISSION`） |
| `interest_commission_cash_share` | `float \| None` | % | 收取利息、手续费及佣金的现金的净现金流占比（`RIC_RATIO`） |
| `investment_cash_paid` | `float \| None` | 元 | 投资支付的现金（保险、券商）（`INVEST_PAY_CASH`） |
| `investment_cash_paid_share` | `float \| None` | % | 投资支付的现金的净现金流占比（`IPC_RATIO`） |
| `begin_cash` | `float \| None` | 元 | 期初现金及现金等价物余额（券商）（`BEGIN_CCE`） |
| `begin_cash_share` | `float \| None` | % | 期初现金及现金等价物余额的净现金流占比（`BEGIN_CCE_RATIO`） |
| `end_cash` | `float \| None` | 元 | 期末现金及现金等价物余额（券商）（`END_CCE`） |
| `end_cash_share` | `float \| None` | % | 期末现金及现金等价物余额的净现金流占比（`END_CCE_RATIO`） |
| `premiums_cash` | `float \| None` | 元 | 收到原保险合同保费取得的现金（保险）（`RECEIVE_ORIGIC_PREMIUM`） |
| `premiums_cash_share` | `float \| None` | % | 收到原保险合同保费取得的现金的净现金流占比（`ROP_RATIO`） |
| `claims_cash_paid` | `float \| None` | 元 | 支付原保险合同赔付款项的现金（保险）（`PAY_ORIGIC_COMPENSATE`） |
| `claims_cash_paid_share` | `float \| None` | % | 支付原保险合同赔付款项的现金的净现金流占比（`POC_RATIO`） |

## DataFrame 列

`df_cash_flow_statement_em` 的中文列名：akshare 有的列沿用其列名，并在“股票简称”后加“市场”；其余字段按同样的写法补上，顺序同模型字段。akshare 的“序号”列不输出。列顺序：股票代码 / 股票简称 / 市场 / 所处行业 / 报告期 / 公告日期 / 净现金流-净现金流 / 净现金流-同比增长 / 经营性现金流-现金流量净额 / 经营性现金流-净现金流占比 / 经营性现金流-销售商品收到的现金 / 经营性现金流-销售商品收到的现金占比 / 经营性现金流-支付给职工的现金 / 经营性现金流-支付给职工的现金占比 / 投资性现金流-现金流量净额 / 投资性现金流-净现金流占比 / 投资性现金流-取得投资收益收到的现金 / 投资性现金流-取得投资收益收到的现金占比 / 投资性现金流-购建长期资产支付的现金 / 投资性现金流-购建长期资产支付的现金占比 / 融资性现金流-现金流量净额 / 融资性现金流-净现金流占比 / 银行-客户存款净增加额 / 银行-客户存款净增加额占比 / 银行-同业及其他金融机构存放款净增加额 / 银行-同业及其他金融机构存放款净增加额占比 / 银行-客户贷款及垫款净增加额 / 银行-客户贷款及垫款净增加额占比 / 券商-收取利息手续费及佣金的现金 / 券商-收取利息手续费及佣金的现金占比 / 金融-投资支付的现金 / 金融-投资支付的现金占比 / 券商-期初现金及现金等价物余额 / 券商-期初现金及现金等价物余额占比 / 券商-期末现金及现金等价物余额 / 券商-期末现金及现金等价物余额占比 / 保险-收到原保险合同保费取得的现金 / 保险-收到原保险合同保费取得的现金占比 / 保险-支付原保险合同赔付款项的现金 / 保险-支付原保险合同赔付款项的现金占比。

## 接口示例（领域模型）

```python
from em import cash_flow_statement_em
from em.domain.queries import CashFlowStatementQuery

page = cash_flow_statement_em(CashFlowStatementQuery("20260930"))
print(page.total)
for item in page.items[:2]:
    print(item)
```

## 数据示例（领域模型）

```
5582
CashFlowStatement(code='688981', name='中芯国际', market='sh', industry='半导体', report_date='2026-09-30', notice_date='2026-11-13', net_cash_flow=14665174000.0, net_cash_flow_yoy=169.8344379171, operating_net=28625494000.0, operating_net_share=195.1936881213, sales_cash=68910888000.0, sales_cash_share=469.8947861103, staff_cash_paid=6649202000.0, staff_cash_paid_share=45.3400825657, investing_net=-38834880000.0, investing_net_share=-264.8102231859, investment_income_cash=2828383000.0, investment_income_cash_share=19.2863923742, capex=29141761000.0, capex_share=198.7140486707, financing_net=25391207000.0, financing_net_share=173.1394867869, customer_deposits_increase=None, customer_deposits_increase_share=None, interbank_deposits_increase=None, interbank_deposits_increase_share=None, loans_increase=None, loans_increase_share=None, interest_commission_cash=None, interest_commission_cash_share=None, investment_cash_paid=None, investment_cash_paid_share=None, begin_cash=None, begin_cash_share=None, end_cash=None, end_cash_share=None, premiums_cash=None, premiums_cash_share=None, claims_cash_paid=None, claims_cash_paid_share=None)
CashFlowStatement(code='688845', name='傲拓科技', market='sh', industry='自动化设备', report_date='2026-09-30', notice_date='2026-11-13', net_cash_flow=30053296.07, net_cash_flow_yoy=125.0908786462, operating_net=31217137.96, operating_net_share=103.8725931668, sales_cash=201160147.12, sales_cash_share=669.3447089845, staff_cash_paid=63478371.51, staff_cash_paid_share=211.2193330214, investing_net=575498.28, investing_net_share=1.9149256663, investment_income_cash=1028739.52, investment_income_cash_share=3.4230505619, capex=47813241.24, capex_share=159.0948331545, financing_net=-1739340.17, financing_net_share=-5.787518833, customer_deposits_increase=None, customer_deposits_increase_share=None, interbank_deposits_increase=None, interbank_deposits_increase_share=None, loans_increase=None, loans_increase_share=None, interest_commission_cash=None, interest_commission_cash_share=None, investment_cash_paid=None, investment_cash_paid_share=None, begin_cash=None, begin_cash_share=None, end_cash=None, end_cash_share=None, premiums_cash=None, premiums_cash_share=None, claims_cash_paid=None, claims_cash_paid_share=None)
```

## 接口示例（`DataFrame`，akshare 风格中文列名）

```python
from em import df_cash_flow_statement_em
from em.domain.queries import CashFlowStatementQuery

df = df_cash_flow_statement_em(CashFlowStatementQuery("20260930"))
```

## 数据示例（`DataFrame`）

```
  股票代码  股票简称 市场    所处行业      报告期    公告日期  净现金流-净现金流  净现金流-同比增长  经营性现金流-现金流量净额  经营性现金流-净现金流占比  经营性现金流-销售商品收到的现金
0   688981  中芯国际   sh      半导体  2026-09-30  2026-11-13       1.466517e+10         169.834438               2.862549e+10                 195.193688                     6.891089e+10
1   688845  傲拓科技   sh  自动化设备  2026-09-30  2026-11-13       3.005330e+07         125.090879               3.121714e+07                 103.872593                     2.011601e+08
2   688235  百济神州   sh    化学制药  2026-09-30  2026-11-10       4.466996e+09         228.404154               7.570562e+09                 169.477698                     3.616613e+10
```

示例只列出前 11 列，实际返回上面的全部列。

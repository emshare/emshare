# 资产负债表接口

> 渠道：[eastmoney](../eastmoney.md) ｜ 源码：`src/em/channels/eastmoney/ashare_financial_statements/balance_sheet/balance_sheet_em.py`

## 接口名称

`balance_sheet_em` / `df_balance_sheet_em`：资产负债表（按报告期取各公司的货币资金、应收账款、存货、总资产、总负债、股东权益及同比、资产负债率）

## 目标地址

- <https://data.eastmoney.com/bbsj/202609/zcfz.html>

## 描述

按报告期取各公司的货币资金、应收账款、存货、总资产、总负债、股东权益及同比、资产负债率。对应 akshare `stock_zcfz_em` / `stock_zcfz_bj_em`（`RPT_DMSK_FN_BALANCE`）。走数据中心报表，本接口按每页 500 条自动翻完全部页，返回 `ReportPage`。只请求用得到的列、查无数据返回空结果、查询写错抛 `QueryRejectedError`、翻页条数校验等公共处理见 [billboard_detail_em.md](../ashare_billboard/billboard_detail_em.md)。

## 参数规则

- `report_date` 报告期为 `YYYYMMDD`，必须是季末（`0331` 一季报 / `0630` 中报 / `0930` 三季报 / `1231` 年报）；格式不对或不是季末在本地直接抛 `ValueError`。
- **`report_date` 留空**：取北京时间今天之前最近的季末（2026-11-14 取到的是 2026-09-30），不发额外请求。季末当天取的是上一个季末：当天还没有公司披露。
- `scope` 市场范围：`all`（默认，沪深京全部）/ `sh` / `sz` / `bj` / `kc` 科创板 / `cy` 创业板 / `st` 风险警示，取值同 `stock_list_em`（没有 `new`）；未知值回退 `all`。`sh` + `sz` + `bj` 的条数之和等于 `all`（实测）。
- **只取 A 股与存托凭证**（上游 `SECURITY_TYPE_CODE` 为 `058001001` / `058001008`）。三大报表上游本来就只有这两类。akshare 默认排除北交所、资产负债表另有北交所专用函数；本接口默认含北交所，单取用 `scope="bj"`。
- 还没有公司披露的报告期返回 `total=0` 的空结果（实测 2026-11-14 取 2026-12-31 的三大报表为空）。

## 字段处理

- **只有主要科目，不是完整报表**：这是东财“数据中心—年报季报”页面的口径，每张表二三十个科目加同比 / 占比；要完整科目请用 F10 财务分析类接口（本工程未做）。
- **银行、券商、保险专用科目只有对应行业有值，一般公司为 `None`；反过来一般公司的科目金融类为 `None`**。实测 2026 三季报 5582 家里银行 42 家、券商 50 家、保险 5 家。
- `*_yoy` 是该科目的同比增长，单位 %（实测 2026 三季报与上年同期逐家核对一致）。
- `debt_asset_ratio` 资产负债率 = 总负债 ÷ 总资产 × 100。`current_ratio` 流动比率也以 % 表示（180 即 1.8 倍），金融类为 `None`。
- `total_assets` = `total_liabilities` + `total_equity`。
- `available_for_sale_assets`（可供出售金融资产）、`premiums_receivable`（应收保费）在近年的报告期全为 `None`（实测 2025 年报、2026 三季报），早年有值（2015 年报分别有 96 家、5 家）。
- 金额单位为元。`market` 由上游 `SECUCODE` 后缀得出，可连同 `code` 直接传给 `stock_kline_em`。
- `notice_date` 是公告日期；有更正公告时是最新一次的日期。
- 排序同 akshare：公告日期、代码倒序；报告期内一家公司一行。
- 可取的报告期早于 akshare 文档说的 2010 年一季报（实测资产负债表 2009-12-31 有 2528 家），越早家数越少。

## 输入参数 `BalanceSheetQuery`

| 名称 | 类型 | 必填 | 默认值 | 描述 |
| --- | --- | --- | --- | --- |
| `report_date` | `str \| None` | 否 | `None` | 报告期 YYYYMMDD，必须是季末（0331 / 0630 / 0930 / 1231）；留空取今天之前最近的季末 |
| `scope` | `str` | 否 | `"all"` | 市场范围：all / sh / sz / bj / kc 科创板 / cy 创业板 / st 风险警示，未知回退 all |

## 输出参数 `ReportPage[BalanceSheet]`

| 名称 | 类型 | 描述 |
| --- | --- | --- |
| `total` | `int` | 上游报告的条数，通常等于 `len(items)` |
| `items` | `tuple[BalanceSheet, ...]` | 全部记录，保持上游排序 |

`BalanceSheet` 字段：

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `code` | `str` | — | 股票代码（`SECURITY_CODE`） |
| `name` | `str` | — | 股票简称（`SECURITY_NAME_ABBR`） |
| `market` | `str \| None` | — | 市场：sh / sz / bj，可连同 code 传给 stock_kline_em（`SECUCODE`） |
| `industry` | `str \| None` | — | 所处行业（`INDUSTRY_NAME`） |
| `report_date` | `str \| None` | — | 报告期 YYYY-MM-DD（`REPORT_DATE`） |
| `notice_date` | `str \| None` | — | 公告日期 YYYY-MM-DD（`NOTICE_DATE`） |
| `cash` | `float \| None` | 元 | 货币资金（`MONETARYFUNDS`） |
| `cash_yoy` | `float \| None` | % | 货币资金同比（`MONETARYFUNDS_RATIO`） |
| `accounts_receivable` | `float \| None` | 元 | 应收账款（`ACCOUNTS_RECE`） |
| `accounts_receivable_yoy` | `float \| None` | % | 应收账款同比（`ACCOUNTS_RECE_RATIO`） |
| `inventory` | `float \| None` | 元 | 存货（`INVENTORY`） |
| `inventory_yoy` | `float \| None` | % | 存货同比（`INVENTORY_RATIO`） |
| `fixed_assets` | `float \| None` | 元 | 固定资产（`FIXED_ASSET`） |
| `total_assets` | `float \| None` | 元 | 总资产（`TOTAL_ASSETS`） |
| `total_assets_yoy` | `float \| None` | % | 总资产同比（`TOTAL_ASSETS_RATIO`） |
| `accounts_payable` | `float \| None` | 元 | 应付账款（`ACCOUNTS_PAYABLE`） |
| `accounts_payable_yoy` | `float \| None` | % | 应付账款同比（`ACCOUNTS_PAYABLE_RATIO`） |
| `advance_receipts` | `float \| None` | 元 | 预收账款（`ADVANCE_RECEIVABLES`） |
| `advance_receipts_yoy` | `float \| None` | % | 预收账款同比（`ADVANCE_RECEIVABLES_RATIO`） |
| `total_liabilities` | `float \| None` | 元 | 总负债（`TOTAL_LIABILITIES`） |
| `total_liabilities_yoy` | `float \| None` | % | 总负债同比（`TOTAL_LIAB_RATIO`） |
| `debt_asset_ratio` | `float \| None` | % | 资产负债率 = 总负债 / 总资产（`DEBT_ASSET_RATIO`） |
| `current_ratio` | `float \| None` | % | 流动比率（以 % 表示，180 即 1.8 倍；金融类为 None）（`CURRENT_RATIO`） |
| `total_equity` | `float \| None` | 元 | 股东权益合计（`TOTAL_EQUITY`） |
| `total_equity_yoy` | `float \| None` | % | 股东权益同比（`TOTAL_EQUITY_RATIO`） |
| `cash_deposit_pbc` | `float \| None` | 元 | 现金及存放中央银行款项（银行）（`CASH_DEPOSIT_PBC`） |
| `cash_deposit_pbc_yoy` | `float \| None` | % | 现金及存放中央银行款项同比（`CDP_RATIO`） |
| `loans_advances` | `float \| None` | 元 | 发放贷款及垫款（银行）（`LOAN_ADVANCE`） |
| `loans_advances_yoy` | `float \| None` | % | 发放贷款及垫款同比（`LOAN_ADVANCE_RATIO`） |
| `available_for_sale_assets` | `float \| None` | 元 | 可供出售金融资产（新金融工具准则后多为 None）（`AVAILABLE_SALE_FINASSET`） |
| `available_for_sale_assets_yoy` | `float \| None` | % | 可供出售金融资产同比（`ASF_RATIO`） |
| `borrowings_from_pbc` | `float \| None` | 元 | 向中央银行借款（银行）（`LOAN_PBC`） |
| `borrowings_from_pbc_yoy` | `float \| None` | % | 向中央银行借款同比（`LOAN_PBC_RATIO`） |
| `deposits` | `float \| None` | 元 | 吸收存款（银行）（`ACCEPT_DEPOSIT`） |
| `deposits_yoy` | `float \| None` | % | 吸收存款同比（`ACCEPT_DEPOSIT_RATIO`） |
| `repo_sold` | `float \| None` | 元 | 卖出回购金融资产款（银行、保险、券商）（`SELL_REPO_FINASSET`） |
| `repo_sold_yoy` | `float \| None` | % | 卖出回购金融资产款同比（`SRF_RATIO`） |
| `settlement_reserves` | `float \| None` | 元 | 结算备付金（券商）（`SETTLE_EXCESS_RESERVE`） |
| `settlement_reserves_yoy` | `float \| None` | % | 结算备付金同比（`SER_RATIO`） |
| `interbank_borrowings` | `float \| None` | 元 | 拆入资金（券商）（`BORROW_FUND`） |
| `interbank_borrowings_yoy` | `float \| None` | % | 拆入资金同比（`BORROW_FUND_RATIO`） |
| `customer_brokerage_deposits` | `float \| None` | 元 | 代理买卖证券款（券商）（`AGENT_TRADE_SECURITY`） |
| `customer_brokerage_deposits_yoy` | `float \| None` | % | 代理买卖证券款同比（`ATS_RATIO`） |
| `premiums_receivable` | `float \| None` | 元 | 应收保费（保险）（`PREMIUM_RECE`） |
| `premiums_receivable_yoy` | `float \| None` | % | 应收保费同比（`PREMIUM_RECE_RATIO`） |
| `short_term_loans` | `float \| None` | 元 | 短期借款（保险）（`SHORT_LOAN`） |
| `short_term_loans_yoy` | `float \| None` | % | 短期借款同比（`SHORT_LOAN_RATIO`） |
| `advance_premiums` | `float \| None` | 元 | 预收保费（保险）（`ADVANCE_PREMIUM`） |
| `advance_premiums_yoy` | `float \| None` | % | 预收保费同比（`ADVANCE_PREMIUM_RATIO`） |

## DataFrame 列

`df_balance_sheet_em` 的中文列名：akshare 有的列沿用其列名，并在“股票简称”后加“市场”；其余字段按同样的写法补上，顺序同模型字段。akshare 的“序号”列不输出。列顺序：股票代码 / 股票简称 / 市场 / 所处行业 / 报告期 / 公告日期 / 资产-货币资金 / 资产-货币资金同比 / 资产-应收账款 / 资产-应收账款同比 / 资产-存货 / 资产-存货同比 / 资产-固定资产 / 资产-总资产 / 资产-总资产同比 / 负债-应付账款 / 负债-应付账款同比 / 负债-预收账款 / 负债-预收账款同比 / 负债-总负债 / 负债-总负债同比 / 资产负债率 / 流动比率 / 股东权益合计 / 股东权益同比 / 银行-现金及存放中央银行款项 / 银行-现金及存放中央银行款项同比 / 银行-发放贷款及垫款 / 银行-发放贷款及垫款同比 / 银行-可供出售金融资产 / 银行-可供出售金融资产同比 / 银行-向中央银行借款 / 银行-向中央银行借款同比 / 银行-吸收存款 / 银行-吸收存款同比 / 金融-卖出回购金融资产款 / 金融-卖出回购金融资产款同比 / 券商-结算备付金 / 券商-结算备付金同比 / 券商-拆入资金 / 券商-拆入资金同比 / 券商-代理买卖证券款 / 券商-代理买卖证券款同比 / 保险-应收保费 / 保险-应收保费同比 / 保险-短期借款 / 保险-短期借款同比 / 保险-预收保费 / 保险-预收保费同比。

## 接口示例（领域模型）

```python
from em import balance_sheet_em
from em.domain.queries import BalanceSheetQuery

page = balance_sheet_em(BalanceSheetQuery("20260930"))
print(page.total)
for item in page.items[:2]:
    print(item)
```

## 数据示例（领域模型）

```
5582
BalanceSheet(code='688662', name='富信科技', market='sh', industry='其他电子Ⅱ', report_date='2026-09-30', notice_date='2026-11-14', cash=92057738.91, cash_yoy=-66.1836615427, accounts_receivable=173262282.44, accounts_receivable_yoy=93.0474448331, inventory=203764385.8, inventory_yoy=26.6098660526, fixed_assets=319516616.06, total_assets=1091401853.06, total_assets_yoy=14.6652745859, accounts_payable=109770395.77, accounts_payable_yoy=106.5673784029, advance_receipts=None, advance_receipts_yoy=None, total_liabilities=341643858.23, total_liabilities_yoy=60.1864125555, debt_asset_ratio=31.3032140519, current_ratio=180.2702079776, total_equity=749757994.83, total_equity_yoy=1.5194132657, cash_deposit_pbc=None, cash_deposit_pbc_yoy=None, loans_advances=None, loans_advances_yoy=None, available_for_sale_assets=None, available_for_sale_assets_yoy=None, borrowings_from_pbc=None, borrowings_from_pbc_yoy=None, deposits=None, deposits_yoy=None, repo_sold=None, repo_sold_yoy=None, settlement_reserves=None, settlement_reserves_yoy=None, interbank_borrowings=None, interbank_borrowings_yoy=None, customer_brokerage_deposits=None, customer_brokerage_deposits_yoy=None, premiums_receivable=None, premiums_receivable_yoy=None, short_term_loans=None, short_term_loans_yoy=None, advance_premiums=None, advance_premiums_yoy=None)
BalanceSheet(code='688981', name='中芯国际', market='sh', industry='半导体', report_date='2026-09-30', notice_date='2026-11-13', cash=72892808000.0, cash_yoy=157.0034823353, accounts_receivable=6862111000.0, accounts_receivable_yoy=12.1670330044, inventory=32533349000.0, inventory_yoy=31.1012377778, fixed_assets=158617941000.0, total_assets=398167630000.0, total_assets_yoy=13.3191294006, accounts_payable=6105740000.0, accounts_payable_yoy=16.5329419981, advance_receipts=21325000.0, advance_receipts_yoy=38.3303061754, total_liabilities=137190490000.0, total_liabilities_yoy=18.0317518991, debt_asset_ratio=34.4554603798, current_ratio=206.3040729825, total_equity=260977140000.0, total_equity_yoy=10.9896029994, cash_deposit_pbc=None, cash_deposit_pbc_yoy=None, loans_advances=None, loans_advances_yoy=None, available_for_sale_assets=None, available_for_sale_assets_yoy=None, borrowings_from_pbc=None, borrowings_from_pbc_yoy=None, deposits=None, deposits_yoy=None, repo_sold=None, repo_sold_yoy=None, settlement_reserves=None, settlement_reserves_yoy=None, interbank_borrowings=None, interbank_borrowings_yoy=None, customer_brokerage_deposits=None, customer_brokerage_deposits_yoy=None, premiums_receivable=None, premiums_receivable_yoy=None, short_term_loans=None, short_term_loans_yoy=None, advance_premiums=None, advance_premiums_yoy=None)
```

## 接口示例（`DataFrame`，akshare 风格中文列名）

```python
from em import df_balance_sheet_em
from em.domain.queries import BalanceSheetQuery

df = df_balance_sheet_em(BalanceSheetQuery("20260930"))
```

## 数据示例（`DataFrame`）

```
  股票代码  股票简称 市场    所处行业      报告期    公告日期  资产-货币资金  资产-货币资金同比  资产-应收账款  资产-应收账款同比     资产-存货  资产-存货同比  资产-固定资产
0   688662  富信科技   sh   其他电子Ⅱ  2026-09-30  2026-11-14   9.205774e+07         -66.183662   1.732623e+08          93.047445  2.037644e+08      26.609866   3.195166e+08
1   688981  中芯国际   sh      半导体  2026-09-30  2026-11-13   7.289281e+10         157.003482   6.862111e+09          12.167033  3.253335e+10      31.101238   1.586179e+11
2   688845  傲拓科技   sh  自动化设备  2026-09-30  2026-11-13   2.097072e+08                NaN   2.378231e+08                NaN  7.457611e+07            NaN   1.436297e+08
```

示例只列出前 13 列，实际返回上面的全部列。

# 个股龙虎榜详情接口

> 渠道：[eastmoney](../eastmoney.md) ｜ 源码：`src/em/channels/eastmoney/ashare_billboard/billboard_stock/billboard_stock_em.py`

## 接口名称

`billboard_stock_em` / `df_billboard_stock_em`：个股龙虎榜详情（一只股票某个上榜日的买入或卖出席位）

## 目标地址

- <https://data.eastmoney.com/stock/lhb/000530.html>

## 描述

取一只股票某个上榜日买入金额最大的前 5 家营业部（`side="buy"`）或卖出金额最大的前 5 家营业部（`side="sell"`）。对应 akshare `stock_lhb_stock_detail_em`（`RPT_BILLBOARD_DAILYDETAILSBUY` / `RPT_BILLBOARD_DAILYDETAILSSELL`，两张报表列相同）。走数据中心报表，单页最多 500 条，本接口自动翻完全部页，返回 `ReportPage`。只请求用得到的列、查无数据返回空结果、查询写错抛 `QueryRejectedError`、翻页条数校验等公共处理见 [billboard_detail_em.md](./billboard_detail_em.md)。

## 参数规则

- `code` 必填。含引号或括号时在本地抛 `ValueError`（会改写过滤语法）。
- `date` 为 `YYYYMMDD`，可取自 `billboard_stock_dates_em`。格式或日期不对在本地直接抛 `ValueError`。
- **`date` 留空**：取**这只股票**最近一个上榜日（先在该股范围内查一次最新上榜日，多 1 个请求），不是全市场最近的上榜日。
- `side`：`buy` / `sell`，未知值回退 `buy`。
- 该股当天没有上榜、或代码不存在时返回 `total=0` 的空结果。

## 字段处理

- **同一天因多个原因上榜时，每个原因各有一组席位**（各 5 个），`reason` 区分。实测 000530 在 2026-11-02 因两个原因上榜，买入侧共 10 行。本例两组的 5 个席位完全相同，**不能跨组相加**。
- 每个席位同时给出它当天的买入、卖出与净额：`side` 只决定按哪一侧取前 5 名，不是只返回那一侧的金额。
- `buy_ratio` / `sell_ratio` 上游给比例（`0.0535`），已换算成 %（`5.35`）；分母是该上榜原因统计区间的总成交额（`turnover`）。
- 机构席位的 `branch_name` 是“机构专用”，`branch_code` 是 `"0"`；同一组里可以有多个机构专用席位，金额各不相同，是各自独立的席位。
- 金额单位为元。`market` 由上游 `SECUCODE` 后缀得出，可连同 `code` 直接传给 `stock_kline_em`。
- 排序：先按 `TRADE_ID` 把同一上榜原因的席位排在一起，组内按该侧金额倒序（同东财页面），末尾补营业部代码保证顺序稳定。

## 输入参数 `BillboardStockQuery`

| 名称 | 类型 | 必填 | 默认值 | 描述 |
| --- | --- | --- | --- | --- |
| `code` | `str` | 是 | — | 股票代码（如 000530） |
| `date` | `str \| None` | 否 | `None` | 上榜日 YYYYMMDD（可取自 billboard_stock_dates_em）；留空取该股最近一个上榜日 |
| `side` | `str` | 否 | `"buy"` | buy 买入金额最大的前 5 名 / sell 卖出金额最大的前 5 名，未知回退 buy |

## 输出参数 `ReportPage[BillboardSeat]`

| 名称 | 类型 | 描述 |
| --- | --- | --- |
| `total` | `int` | 上游报告的条数，通常等于 `len(items)` |
| `items` | `tuple[BillboardSeat, ...]` | 全部记录，保持上游排序 |

`BillboardSeat` 字段：

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `code` | `str` | — | 股票代码（`SECURITY_CODE`） |
| `market` | `str \| None` | — | 市场：sh / sz / bj，可连同 code 传给 stock_kline_em（`SECUCODE`） |
| `trade_date` | `str \| None` | — | 上榜日 YYYY-MM-DD（`TRADE_DATE`） |
| `reason` | `str \| None` | — | 上榜原因（同一天多个原因时每个原因各有一组席位）（`EXPLANATION`） |
| `branch_code` | `str \| None` | — | 营业部代码（机构专用为 "0"）（`OPERATEDEPT_CODE`） |
| `branch_name` | `str \| None` | — | 交易营业部名称（`OPERATEDEPT_NAME`） |
| `buy` | `float \| None` | 元 | 买入金额（`BUY`） |
| `buy_ratio` | `float \| None` | % | 买入金额占总成交比例（上游比例，已换算）（`TOTAL_BUYRIO`） |
| `sell` | `float \| None` | 元 | 卖出金额（`SELL`） |
| `sell_ratio` | `float \| None` | % | 卖出金额占总成交比例（上游比例，已换算）（`TOTAL_SELLRIO`） |
| `net_buy` | `float \| None` | 元 | 净额（`NET`） |
| `close` | `float \| None` | 元 | 收盘价（`CLOSE_PRICE`） |
| `change_pct` | `float \| None` | % | 涨跌幅（`CHANGE_RATE`） |
| `turnover` | `float \| None` | 元 | 总成交额（该上榜原因统计区间内）（`ACCUM_AMOUNT`） |

## DataFrame 列

`df_billboard_stock_em` 的列对齐 akshare `stock_lhb_stock_detail_em`，末尾加营业部代码、代码、市场、上榜日、收盘价、涨跌幅、总成交额。akshare 的“序号”列不输出。列顺序：交易营业部名称 / 买入金额 / 买入金额-占总成交比例 / 卖出金额 / 卖出金额-占总成交比例 / 净额 / 类型 / 营业部代码 / 代码 / 市场 / 上榜日 / 收盘价 / 涨跌幅 / 总成交额。

## 接口示例（领域模型）

```python
from em import billboard_stock_em
from em.domain.queries import BillboardStockQuery

page = billboard_stock_em(BillboardStockQuery("000530", "20261102", side="buy"))
print(page.total)
for item in page.items[:2]:
    print(item)
```

## 数据示例（领域模型）

```
10
BillboardSeat(code='000530', market='sz', trade_date='2026-11-02', reason='日涨幅偏离值达到7%的前5只证券', branch_code='10026937', branch_name='国泰海通证券股份有限公司武汉紫阳东路证券营业部', buy=96641108.61, buy_ratio=5.3536779728, sell=251259.0, sell_ratio=0.0139191261, net_buy=96389849.61, close=8.71, change_pct=9.9747, turnover=1805134883.0)
BillboardSeat(code='000530', market='sz', trade_date='2026-11-02', reason='日涨幅偏离值达到7%的前5只证券', branch_code='0', branch_name='机构专用', buy=44938927.19, buy_ratio=2.4895052228, sell=33441581.08, sell_ratio=1.8525807348, net_buy=11497346.11, close=8.71, change_pct=9.9747, turnover=1805134883.0)
```

## 接口示例（`DataFrame`，akshare 风格中文列名）

```python
from em import df_billboard_stock_em
from em.domain.queries import BillboardStockQuery

df = df_billboard_stock_em(BillboardStockQuery("000530", "20261102", side="buy"))
```

## 数据示例（`DataFrame`）

```
                                   交易营业部名称     买入金额  买入金额-占总成交比例     卖出金额  卖出金额-占总成交比例         净额                           类型 营业部代码    代码 市场      上榜日  收盘价  涨跌幅      总成交额
0  国泰海通证券股份有限公司武汉紫阳东路证券营业部  96641108.61               5.353678    251259.00               0.013919  96389849.61  日涨幅偏离值达到7%的前5只证券   10026937  000530   sz  2026-11-02    8.71  9.9747  1.805135e+09
1                                        机构专用  44938927.19               2.489505  33441581.08               1.852581  11497346.11  日涨幅偏离值达到7%的前5只证券          0  000530   sz  2026-11-02    8.71  9.9747  1.805135e+09
2                                        机构专用  40570811.34               2.247522  16387426.36               0.907823  24183384.98  日涨幅偏离值达到7%的前5只证券          0  000530   sz  2026-11-02    8.71  9.9747  1.805135e+09
```

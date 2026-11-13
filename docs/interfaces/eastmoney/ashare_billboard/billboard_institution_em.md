# 机构买卖每日统计接口

> 渠道：[eastmoney](../eastmoney.md) ｜ 源码：`src/em/channels/eastmoney/ashare_billboard/billboard_institution/billboard_institution_em.py`

## 接口名称

`billboard_institution_em` / `df_billboard_institution_em`：机构买卖每日统计（按上榜日期区间取有机构席位参与的上榜记录）

## 目标地址

- <https://data.eastmoney.com/stock/jgmmtj.html>

## 描述

按上榜日期区间取有机构席位参与的上榜记录：买卖机构数、机构买入 / 卖出 / 净买额、上榜后涨跌幅。对应 akshare `stock_lhb_jgmmtj_em`（`RPT_ORGANIZATION_TRADE_DETAILS`）。走数据中心报表，单页最多 500 条，本接口自动翻完全部页，返回 `ReportPage`。只请求用得到的列、查无数据返回空结果、查询写错抛 `QueryRejectedError`、翻页条数校验等公共处理见 [billboard_detail_em.md](./billboard_detail_em.md)。

## 日期规则

- 日期为 `YYYYMMDD`。格式或日期不对在本地直接抛 `ValueError`。
- **都留空**：取最近一个有机构席位上榜的交易日（先查一次最新上榜日，多 1 个请求）。
- **只给 `start_date`**：取到北京时间今天。**只给 `end_date`**：只取那一天。
- 周末、节假日没有龙虎榜，单取这类日期返回 `total=0` 的空结果。

## 字段处理

- **同一只股票同一天可能有多条记录**：因多个原因上榜时，每个原因一条，各按自己的上榜原因统计机构数、金额与统计区间的成交额（`turnover`）。实测 2026-11-11 共 52 条，其中 6 只股票各有多条。**按条直接相加会重复计算。**
- 金额单位为元。`float_market_cap` 上游给亿元，已换算成元。
- `net_buy_ratio` 单位为 %：机构净买额 / 市场总成交额。
- `market` 由上游 `SECUCODE` 后缀得出，可连同 `code` 直接传给 `stock_kline_em`。
- 上榜后 N 日涨跌幅（`change_after_*`）未到期时为 `None`。
- 排序同 akshare：机构净买额、上榜日倒序，代码升序。本报表没有 `TRADE_ID`，末尾补上榜原因（`EXPLANATION`），同股同日多条时翻页顺序也稳定。

## 输入参数 `BillboardInstitutionQuery`

| 名称 | 类型 | 必填 | 默认值 | 描述 |
| --- | --- | --- | --- | --- |
| `start_date` | `str \| None` | 否 | `None` | 起始日期 YYYYMMDD；起止都留空取最近一个有数据的交易日，只给起始取到今天 |
| `end_date` | `str \| None` | 否 | `None` | 结束日期 YYYYMMDD；只给结束日期时只取那一天 |

## 输出参数 `ReportPage[BillboardInstitutionTrade]`

| 名称 | 类型 | 描述 |
| --- | --- | --- |
| `total` | `int` | 上游报告的条数，通常等于 `len(items)` |
| `items` | `tuple[BillboardInstitutionTrade, ...]` | 全部记录，保持上游排序 |

`BillboardInstitutionTrade` 字段：

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `code` | `str` | — | 股票代码（`SECURITY_CODE`） |
| `name` | `str` | — | 股票简称（`SECURITY_NAME_ABBR`） |
| `market` | `str \| None` | — | 市场：sh / sz / bj，可连同 code 传给 stock_kline_em（`SECUCODE`） |
| `trade_date` | `str \| None` | — | 上榜日 YYYY-MM-DD（`TRADE_DATE`） |
| `reason` | `str \| None` | — | 上榜原因（同股同日多个原因时为多条记录，各自统计，不能相加）（`EXPLANATION`） |
| `close` | `float \| None` | 元 | 收盘价（`CLOSE_PRICE`） |
| `change_pct` | `float \| None` | % | 涨跌幅（`CHANGE_RATE`） |
| `buy_institutions` | `int \| None` | 家 | 买方机构数（`BUY_TIMES`） |
| `sell_institutions` | `int \| None` | 家 | 卖方机构数（`SELL_TIMES`） |
| `institution_buy` | `float \| None` | 元 | 机构买入总额（`BUY_AMT`） |
| `institution_sell` | `float \| None` | 元 | 机构卖出总额（`SELL_AMT`） |
| `institution_net_buy` | `float \| None` | 元 | 机构买入净额（`NET_BUY_AMT`） |
| `turnover` | `float \| None` | 元 | 市场总成交额（`ACCUM_AMOUNT`） |
| `net_buy_ratio` | `float \| None` | % | 机构净买额占总成交额比（`RATIO`） |
| `turnover_rate` | `float \| None` | % | 换手率（`TURNOVERRATE`） |
| `float_market_cap` | `float \| None` | 元 | 流通市值（上游亿元，已换算）（`FREECAP`） |
| `change_after_1d` | `float \| None` | % | 上榜后 1 日涨跌幅（未到期为 None）（`D1_CLOSE_ADJCHRATE`） |
| `change_after_2d` | `float \| None` | % | 上榜后 2 日涨跌幅（`D2_CLOSE_ADJCHRATE`） |
| `change_after_3d` | `float \| None` | % | 上榜后 3 日涨跌幅（`D3_CLOSE_ADJCHRATE`） |
| `change_after_5d` | `float \| None` | % | 上榜后 5 日涨跌幅（`D5_CLOSE_ADJCHRATE`） |
| `change_after_10d` | `float \| None` | % | 上榜后 10 日涨跌幅（`D10_CLOSE_ADJCHRATE`） |

## DataFrame 列

`df_billboard_institution_em` 的列对齐 akshare `stock_lhb_jgmmtj_em`，并在“名称”后加“市场”，末尾加上榜后 1 / 2 / 3 / 5 / 10 日涨跌幅。akshare 的“序号”列不输出。列顺序：代码 / 名称 / 市场 / 收盘价 / 涨跌幅 / 买方机构数 / 卖方机构数 / 机构买入总额 / 机构卖出总额 / 机构买入净额 / 市场总成交额 / 机构净买额占总成交额比 / 换手率 / 流通市值 / 上榜原因 / 上榜日期 / 上榜后1日 / 上榜后2日 / 上榜后3日 / 上榜后5日 / 上榜后10日。

## 接口示例（领域模型）

```python
from em import billboard_institution_em
from em.domain.queries import BillboardInstitutionQuery

page = billboard_institution_em(BillboardInstitutionQuery("20261111", "20261111"))
print(page.total)
for item in page.items[:2]:
    print(item)
```

## 数据示例（领域模型）

```
52
BillboardInstitutionTrade(code='002384', name='东山精密', market='sz', trade_date='2026-11-11', reason='日涨幅偏离值达到7%的前5只证券', close=92.06, change_pct=10.0012, buy_institutions=3, sell_institutions=4, institution_buy=1253002378.12, institution_sell=783096486.73, institution_net_buy=469905891.39, turnover=12653578551.0, net_buy_ratio=3.713620534271, turnover_rate=10.3151, float_market_cap=127625000000.0, change_after_1d=1.7705844, change_after_2d=None, change_after_3d=None, change_after_5d=None, change_after_10d=None)
BillboardInstitutionTrade(code='688801', name='燧原科技', market='sh', trade_date='2026-11-11', reason='有价格涨跌幅限制的连续3个交易日内收盘价格涨幅偏离值累计达到30%的证券', close=494.0, change_pct=11.2738, buy_institutions=2, sell_institutions=1, institution_buy=555507051.18, institution_sell=120908315.3, institution_net_buy=434598735.88, turnover=4136849000.0, net_buy_ratio=10.505549897519, turnover_rate=15.3249, float_market_cap=8843000000.0, change_after_1d=13.13360324, change_after_2d=None, change_after_3d=None, change_after_5d=None, change_after_10d=None)
```

## 接口示例（`DataFrame`，akshare 风格中文列名）

```python
from em import df_billboard_institution_em
from em.domain.queries import BillboardInstitutionQuery

df = df_billboard_institution_em(BillboardInstitutionQuery("20261111", "20261111"))
```

## 数据示例（`DataFrame`）

```
     代码      名称 市场  收盘价   涨跌幅  买方机构数  卖方机构数  机构买入总额  机构卖出总额  机构买入净额  市场总成交额  机构净买额占总成交额比   换手率      流通市值                                                              上榜原因    上榜日期  上榜后1日 上榜后2日 上榜后3日 上榜后5日 上榜后10日
0  002384  东山精密   sz   92.06  10.0012           3           4  1.253002e+09  7.830965e+08  4.699059e+08  1.265358e+10                3.713621  10.3151  1.276250e+11                                         日涨幅偏离值达到7%的前5只证券  2026-11-11   1.770584      None      None      None       None
1  688801  燧原科技   sh  494.00  11.2738           2           1  5.555071e+08  1.209083e+08  4.345987e+08  4.136849e+09               10.505550  15.3249  8.843000e+09  有价格涨跌幅限制的连续3个交易日内收盘价格涨幅偏离值累计达到30%的证券  2026-11-11  13.133603      None      None      None       None
2  603920  世运电路   sh   39.42   8.3860           1           0  1.608829e+08  0.000000e+00  1.608829e+08  4.652369e+09                3.458085   6.8102  2.840600e+10            非S证券连续三个交易日内收盘价格涨幅偏离值累计达到20%的证券  2026-11-11   0.456621      None      None      None       None
```

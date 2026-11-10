# 龙虎榜详情接口

> 渠道：[eastmoney](../eastmoney.md) ｜ 源码：`src/em/channels/eastmoney/ashare_billboard/billboard_detail/billboard_detail_em.py`

## 接口名称

`billboard_detail_em` / `df_billboard_detail_em`：龙虎榜详情（按上榜日期区间取全部上榜记录）

## 目标地址

- <https://data.eastmoney.com/stock/tradedetail.html>

## 描述

按上榜日期区间一次取回全部上榜记录。走数据中心（`datacenter-web` 的 `RPT_DAILYBILLBOARD_DETAILSNEW` 报表），对应 akshare `stock_lhb_detail_em`。数据中心单页最多 500 条，本接口自动翻完全部页（首页定总页数，其余页并发取），返回 `ReportPage`。

数据中心报表的公共处理（本批龙虎榜、大宗交易、业绩财报接口都一样）：

- **只请求用得到的列**：本接口 22 列，一页 500 条从全部列的 572KB 降到 347KB。过滤条件用到的列也一并请求：上游对拼错的过滤字段**静默忽略、返回整张表**，而拼错的返回列会报 9501，借此把上游改名暴露出来，不会误取 27 万行。
- **查无数据**（上游 code 9201，如周末、日期区间内没有上榜）返回 `total=0` 的空结果，不当失败重试。
- **查询写错**（9501：报表 / 列名 / 排序列不存在、日期格式不对；200：参数类型不对）抛 `QueryRejectedError`，换 IP 也一样，不重试、不拉黑出口。服务器繁忙（9701）和其他未知返回码按渠道异常换 IP 重试。
- **翻页一致性**：各页报告的总数不一致、或取到的条数与总数不等，说明翻页期间上游有增删，整轮重取一次；仍不一致时记 warning，返回最后一轮的结果。实测按 50 条一页、5 个并发翻 15 页，与一次取 500 条的结果逐条一致。

## 日期规则

- 日期为 `YYYYMMDD`。格式或日期不对在本地直接抛 `ValueError`（上游对 `2026-11-06` 这类写法只回 9501 语法错误）。
- **都留空**：取最近一个有龙虎榜的交易日（先查一次最新上榜日，多 1 个请求）。龙虎榜收盘后发布，北京时间 11-09 晚上已能取到 11-09 的数据。
- **只给 `start_date`**：取到北京时间今天。**只给 `end_date`**：只取那一天。
- 周末、节假日没有龙虎榜，单取这类日期返回空结果。

## 字段处理

- **同一只股票同一天可能有多条记录**：因多个原因上榜时，每个原因一条（上游 `TRADE_ID` 不同）。各条按自己的上榜原因统计金额：单日原因之间金额相同，“连续三个交易日”类原因按三日累计。实测 10-09 到 11-06 共 1677 条中，同股同日多条的有 202 组，其中 120 组金额不同。**按条直接相加会重复计算。**
- 金额单位为元，涨跌幅、换手率、两个占比单位为 %（占比 = 龙虎榜净买额或成交额 / 市场总成交额）。
- `market` 由上游 `SECUCODE` 后缀得出（`000525.SZ` → `sz`），可连同 `code` 直接传给 `stock_kline_em`。
- 上榜后 N 日涨跌幅（`change_after_*`）未到期时为 `None`，如 11-09 抓取时 11-06 上榜的只有 1 日有值。
- 排序同 akshare：代码升序、上榜日倒序；末尾补 `TRADE_ID`，同股同日多条时翻页顺序也稳定。

## 输入参数 `BillboardDetailQuery`

| 名称 | 类型 | 必填 | 默认值 | 描述 |
| --- | --- | --- | --- | --- |
| `start_date` | `str \| None` | 否 | `None` | 起始日期 `YYYYMMDD`，规则见上 |
| `end_date` | `str \| None` | 否 | `None` | 结束日期 `YYYYMMDD`，规则见上 |

## 输出参数 `ReportPage[BillboardEntry]`

| 名称 | 类型 | 描述 |
| --- | --- | --- |
| `total` | `int` | 上游报告的条数，通常等于 `len(items)` |
| `items` | `tuple[BillboardEntry, ...]` | 全部上榜记录 |

`BillboardEntry` 字段：

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `code` | `str` | — | 股票代码（`SECURITY_CODE`） |
| `name` | `str` | — | 股票简称（`SECURITY_NAME_ABBR`） |
| `market` | `str \| None` | — | `sh` / `sz` / `bj`（`SECUCODE` 后缀） |
| `trade_date` | `str \| None` | — | 上榜日 `YYYY-MM-DD`（`TRADE_DATE`） |
| `reason` | `str \| None` | — | 上榜原因（`EXPLANATION`） |
| `interpretation` | `str \| None` | — | 解读，如“2家机构卖出，成功率18.37%”（`EXPLAIN`） |
| `close` | `float \| None` | 元 | 收盘价（`CLOSE_PRICE`） |
| `change_pct` | `float \| None` | % | 涨跌幅（`CHANGE_RATE`） |
| `net_buy` | `float \| None` | 元 | 龙虎榜净买额（`BILLBOARD_NET_AMT`） |
| `buy` | `float \| None` | 元 | 龙虎榜买入额（`BILLBOARD_BUY_AMT`） |
| `sell` | `float \| None` | 元 | 龙虎榜卖出额（`BILLBOARD_SELL_AMT`） |
| `billboard_turnover` | `float \| None` | 元 | 龙虎榜成交额（`BILLBOARD_DEAL_AMT`） |
| `turnover` | `float \| None` | 元 | 市场总成交额，即该股当日成交额（`ACCUM_AMOUNT`） |
| `net_buy_ratio` | `float \| None` | % | 净买额占总成交比（`DEAL_NET_RATIO`） |
| `billboard_turnover_ratio` | `float \| None` | % | 龙虎榜成交额占总成交比（`DEAL_AMOUNT_RATIO`） |
| `turnover_rate` | `float \| None` | % | 换手率（`TURNOVERRATE`） |
| `float_market_cap` | `float \| None` | 元 | 流通市值（`FREE_MARKET_CAP`） |
| `change_after_1d` / `_2d` / `_5d` / `_10d` | `float \| None` | % | 上榜后 1 / 2 / 5 / 10 日涨跌幅（`D*_CLOSE_ADJCHRATE`），未到期为 `None` |

## DataFrame 列

`df_billboard_detail_em` 的列对齐 akshare `stock_lhb_detail_em`，并在“名称”后加“市场”：代码 / 名称 / 市场 / 上榜日 / 解读 / 收盘价 / 涨跌幅 / 龙虎榜净买额 / 龙虎榜买入额 / 龙虎榜卖出额 / 龙虎榜成交额 / 市场总成交额 / 净买额占总成交比 / 成交额占总成交比 / 换手率 / 流通市值 / 上榜原因 / 上榜后1日 / 上榜后2日 / 上榜后5日 / 上榜后10日。akshare 的“序号”列不输出。

## 接口示例（领域模型）

```python
from em import billboard_detail_em
from em.domain.queries import BillboardDetailQuery

page = billboard_detail_em(BillboardDetailQuery("20261106", "20261106"))
print(page.total)
for e in page.items[:2]:
    print(e)
```

## 数据示例（领域模型）

```
79
BillboardEntry(code='000525', name='红太阳', market='sz', trade_date='2026-11-06', reason='日涨幅偏离值达到7%的前5只证券', interpretation='普通席位买入，成功率38.49%', close=5.02, change_pct=10.0877, net_buy=98694262.06, buy=148944265.27, sell=50250003.21, billboard_turnover=199194268.48, turnover=593597267.0, net_buy_ratio=16.626468406567, billboard_turnover_ratio=33.557140430702, turnover_rate=11.3403, float_market_cap=5581035225.1, change_after_1d=9.96015936, change_after_2d=None, change_after_5d=None, change_after_10d=None)
BillboardEntry(code='000530', name='冰山冷热', market='sz', trade_date='2026-11-06', reason='日换手率达到20%的前5只证券', interpretation='2家机构卖出，成功率18.37%', close=8.7, change_pct=-3.7611, net_buy=-27359349.0, buy=126251727.43, sell=153611076.43, billboard_turnover=279862803.86, turnover=1623302557.0, net_buy_ratio=-1.68541279517, billboard_turnover_ratio=17.240335306143, turnover_rate=30.0962, float_market_cap=5629150507.5, change_after_1d=10.0, change_after_2d=None, change_after_5d=None, change_after_10d=None)
```

## 接口示例（`DataFrame`，akshare 风格中文列名）

```python
from em import df_billboard_detail_em
from em.domain.queries import BillboardDetailQuery

df = df_billboard_detail_em(BillboardDetailQuery("20261106", "20261106"))
```

## 数据示例（`DataFrame`）

```
       代码    名称  市场         上榜日                解读    收盘价      涨跌幅       龙虎榜净买额        龙虎榜买入额        龙虎榜卖出额        龙虎榜成交额        市场总成交额   净买额占总成交比   成交额占总成交比      换手率          流通市值                      上榜原因      上榜后1日 上榜后2日 上榜后5日 上榜后10日
0  000525   红太阳  sz  2026-11-06  普通席位买入，成功率38.49%   5.02  10.0877  98694262.06  1.489443e+08  5.025000e+07  1.991943e+08  5.935973e+08  16.626468  33.557140  11.3403  5.581035e+09          日涨幅偏离值达到7%的前5只证券   9.960159  None  None   None
1  000530  冰山冷热  sz  2026-11-06  2家机构卖出，成功率18.37%   8.70  -3.7611 -27359349.00  1.262517e+08  1.536111e+08  2.798628e+08  1.623303e+09  -1.685413  17.240335  30.0962  5.629151e+09           日换手率达到20%的前5只证券  10.000000  None  None   None
2  000603  盛达资源  sz  2026-11-06  4家机构买入，成功率18.11%  26.53   1.8426 -27526649.09  8.978500e+08  9.253766e+08  1.823227e+09  4.474339e+09  -0.615212  40.748516  12.0592  1.768799e+10  连续三个交易日内，涨幅偏离值累计达到20%的证券   4.523181  None  None   None
```

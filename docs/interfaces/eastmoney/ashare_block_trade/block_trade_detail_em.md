# 大宗交易每日明细接口

> 渠道：[eastmoney](../eastmoney.md) ｜ 源码：`src/em/channels/eastmoney/ashare_block_trade/block_trade_detail/block_trade_detail_em.py`

## 接口名称

`block_trade_detail_em` / `df_block_trade_detail_em`：大宗交易每日明细（按证券类型和交易日期区间取全部成交，一笔成交一行）

## 目标地址

- <https://data.eastmoney.com/dzjy/dzjy_mrmx.html>

## 描述

按证券类型和交易日期区间取全部大宗交易成交，一笔成交一行：成交价、折溢率、成交量、成交额、买卖双方营业部。对应 akshare `stock_dzjy_mrmx`（`RPT_DATA_BLOCKTRADE`）。走数据中心报表，本接口按每页 500 条自动翻完全部页，返回 `ReportPage`。只请求用得到的列、查无数据返回空结果、查询写错抛 `QueryRejectedError`、翻页条数校验等公共处理见 [billboard_detail_em.md](../ashare_billboard/billboard_detail_em.md)。

与 akshare 的差别：akshare 不翻页，区间内超过 5000 条时只返回前 5000 条（实测 A 股一年 33115 条），本接口翻完全部页；akshare 对 B 股、基金、债券只输出 9 列（没有涨跌幅、收盘价、折溢率），本接口四种证券类型是同一组字段。

## 参数规则

- `security_type`：`ashare` A 股 / `bshare` B 股 / `fund` 基金 / `bond` 债券，未知值回退 `ashare`。四种类型是上游同一张表（`SECURITY_TYPE_WEB` 为 1 / 2 / 3 / 4）。实测 2026-11-13 总条数：A 股 337441 / B 股 1661 / 基金 12589 / 债券 333728。
- 日期为 `YYYYMMDD`。格式或日期不对在本地直接抛 `ValueError`。
- **日期都留空**：取最近一个有**这类证券**大宗交易的交易日（先在该类型范围内查一次最新交易日，多 1 个请求）。B 股成交很少，实测 2026-11-13 留空取到的是 2026-06-23。
- **只给 `start_date`**：取到北京时间今天。**只给 `end_date`**：只取那一天。
- 周末、节假日没有大宗交易，单取这类日期返回 `total=0` 的空结果。

## 字段处理

- **上游没有成交编号，相同的成交各算一笔，不能去重**：同一只证券同一天可以有几笔买卖双方、成交价、成交量完全相同的成交（实测 300750 宁德时代 2026-11-10 有 3 笔；2026-11-04 至 11-12 四种类型共 658 笔里，各字段完全相同的有 13 组、共 30 笔）。
- 排序：代码升序、交易日期倒序、当日序号（上游 `DAILY_RANK`）升序。（代码, 日期, 当日序号）唯一（实测 2025-11 起 A 股 34678 笔无重复），翻页顺序稳定；只按代码排序（akshare 的排序）按页取会重复和丢行（实测一个月 1794 笔、每页 500 条时重复 7 笔）。
- **成交量单位随证券类型不同**（上游原值，未换算）：A 股、B 股为股，基金为份（成交额 ≈ 成交价 × 成交量）；债券为手，1 手 = 10 张（成交额 = 成交价 × 成交量 × 10）。债券的这个口径抽样看 2015 年起都成立，更早的记录口径不一（深市 2012 年及以前有成交额为 0 的，沪市 2013–2014 年的成交额 = 成交价 × 成交量）。
- **B 股的价格与金额是交易币种**（沪市美元、深市港元）。例外：沪市 B 股 2008–2020 年间的记录（2008、2020 年是其中一部分），成交额 ÷（成交价 × 成交量）在 6.1–7.2 之间，看起来成交额已折算成人民币而成交价仍是美元。
- `premium_rate` 折溢率 = 成交价 ÷ 当日收盘价 − 1，上游给比例（`-0.0192`），已换算成 %（`-1.92`）；正为溢价、负为折价、0 为平价。实测 2026-10-12 至 11-12 的 A 股 1794 笔：溢价 65、平价 635、折价 1094。
- `float_market_cap_ratio` = 成交额 ÷（当日收盘价 × 流通 A 股）× 100，单位 %，只有 A 股有。
- `change_after_*` 只有 A 股有，尚未到期为 `None`；B 股、基金、债券恒为 `None`（实测全部 1661 笔 B 股、2026 年以来 2135 笔基金和 1580 笔债券都为空）。
- 营业部代码：机构专用为 `"0"`；与龙虎榜的营业部代码是同一套（实测 `10126062` 在两边是同一家营业部），可传给 `billboard_branch_trades_em`。买卖双方可以是同一家营业部（实测上述 1794 笔里 109 笔）。早年的个别记录没有营业部代码（`None`）。
- `market` 由上游 `SECUCODE` 后缀得出（`000656.SZ` → `sz`），A 股可连同 `code` 直接传给 `stock_kline_em`。
- **当天的数据收盘后陆续入库**：实测 2026-11-13 当天，16:31 查到 A 股 30 笔、成交总额 2.85 亿元；17:48 再查是 49 笔，19:04 查到成交总额 4.90 亿元，到 20:48 没有再变。当天的数据晚些再取才完整。

## 输入参数 `BlockTradeDetailQuery`

| 名称 | 类型 | 必填 | 默认值 | 描述 |
| --- | --- | --- | --- | --- |
| `start_date` | `str \| None` | 否 | `None` | 起始日期 YYYYMMDD；起止都留空取最近一个有数据的交易日，只给起始取到今天 |
| `end_date` | `str \| None` | 否 | `None` | 结束日期 YYYYMMDD；只给结束日期时只取那一天 |
| `security_type` | `str` | 否 | `"ashare"` | 证券类型：ashare A 股 / bshare B 股 / fund 基金 / bond 债券，未知回退 ashare |

## 输出参数 `ReportPage[BlockTrade]`

| 名称 | 类型 | 描述 |
| --- | --- | --- |
| `total` | `int` | 上游报告的条数，通常等于 `len(items)` |
| `items` | `tuple[BlockTrade, ...]` | 全部记录，保持上游排序 |

`BlockTrade` 字段：

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `code` | `str` | — | 证券代码（`SECURITY_CODE`） |
| `name` | `str` | — | 证券简称（`SECURITY_NAME_ABBR`） |
| `market` | `str \| None` | — | 市场：sh / sz / bj，可连同 code 传给 stock_kline_em（`SECUCODE`） |
| `trade_date` | `str \| None` | — | 交易日期 YYYY-MM-DD（`TRADE_DATE`） |
| `change_pct` | `float \| None` | % | 当日涨跌幅（`CHANGE_RATE`） |
| `close` | `float \| None` | 元 | 当日收盘价（`CLOSE_PRICE`） |
| `price` | `float \| None` | 元 | 成交价（`DEAL_PRICE`） |
| `premium_rate` | `float \| None` | % | 折溢率 = 成交价 / 收盘价 - 1（上游比例，已换算）（`PREMIUM_RATIO`） |
| `volume` | `float \| None` | 股 / 份 / 手 | 成交量，上游原值：A 股、B 股为股，基金为份，债券 2015 年以来为手（1 手 = 10 张）（`DEAL_VOLUME`） |
| `amount` | `float \| None` | 元 | 成交额（B 股为交易币种）（`DEAL_AMT`） |
| `float_market_cap_ratio` | `float \| None` | % | 成交额 / 流通市值（仅 A 股有）（`TURNOVER_RATE`） |
| `buyer_code` | `str \| None` | — | 买方营业部代码（机构专用为 "0"）（`BUYER_CODE`） |
| `buyer_name` | `str \| None` | — | 买方营业部（`BUYER_NAME`） |
| `seller_code` | `str \| None` | — | 卖方营业部代码（机构专用为 "0"）（`SELLER_CODE`） |
| `seller_name` | `str \| None` | — | 卖方营业部（`SELLER_NAME`） |
| `change_after_1d` | `float \| None` | % | 1 日后涨跌幅（仅 A 股有；未到期为 None）（`CHANGE_RATE_1DAYS`） |
| `change_after_5d` | `float \| None` | % | 5 日后涨跌幅（`CHANGE_RATE_5DAYS`） |
| `change_after_10d` | `float \| None` | % | 10 日后涨跌幅（`CHANGE_RATE_10DAYS`） |
| `change_after_20d` | `float \| None` | % | 20 日后涨跌幅（`CHANGE_RATE_20DAYS`） |

## DataFrame 列

`df_block_trade_detail_em` 的列对齐 akshare `stock_dzjy_mrmx` 的 A 股列，并在“证券简称”后加“市场”，末尾加买卖方营业部代码与 1 / 5 / 10 / 20 日后涨跌幅；四种证券类型都是这组列。akshare 的“序号”列不输出。列顺序：交易日期 / 证券代码 / 证券简称 / 市场 / 涨跌幅 / 收盘价 / 成交价 / 折溢率 / 成交量 / 成交额 / 成交额/流通市值 / 买方营业部 / 卖方营业部 / 买方营业部代码 / 卖方营业部代码 / 1日后涨跌幅 / 5日后涨跌幅 / 10日后涨跌幅 / 20日后涨跌幅。

## 接口示例（领域模型）

```python
from em import block_trade_detail_em
from em.domain.queries import BlockTradeDetailQuery

page = block_trade_detail_em(BlockTradeDetailQuery("20261112", "20261112"))
print(page.total)
for item in page.items[:2]:
    print(item)
```

## 数据示例（领域模型）

```
64
BlockTrade(code='000656', name='金科股份', market='sz', trade_date='2026-11-12', change_pct=-1.8868, close=1.04, price=1.02, premium_rate=-1.9230769231, volume=3000000.0, amount=3060000.0, float_market_cap_ratio=0.031349961031, buyer_code='10126062', buyer_name='招商证券股份有限公司温州府东路证券营业部', seller_code='10046604', seller_name='中信证券股份有限公司杭州凤起路证券营业部', change_after_1d=-0.96153846, change_after_5d=None, change_after_10d=None, change_after_20d=None)
BlockTrade(code='000807', name='云铝股份', market='sz', trade_date='2026-11-12', change_pct=-0.4272, close=23.31, price=23.31, premium_rate=0.0, volume=350000.0, amount=8158500.0, float_market_cap_ratio=0.010092504141, buyer_code='0', buyer_name='机构专用', seller_code='0', seller_name='机构专用', change_after_1d=-1.15830116, change_after_5d=None, change_after_10d=None, change_after_20d=None)
```

## 接口示例（`DataFrame`，akshare 风格中文列名）

```python
from em import df_block_trade_detail_em
from em.domain.queries import BlockTradeDetailQuery

df = df_block_trade_detail_em(BlockTradeDetailQuery("20261112", "20261112"))
```

## 数据示例（`DataFrame`）

```
     交易日期 证券代码  证券简称 市场  涨跌幅  收盘价  成交价    折溢率     成交量      成交额  成交额/流通市值                         买方营业部                         卖方营业部 买方营业部代码 卖方营业部代码  1日后涨跌幅 5日后涨跌幅 10日后涨跌幅 20日后涨跌幅
0  2026-11-12   000656  金科股份   sz -1.8868    1.04    1.02 -1.923077  3000000.0   3060000.0         0.031350  招商证券股份有限公司温州府东路证…  中信证券股份有限公司杭州凤起路证…       10126062       10046604    -0.961538        None         None         None
1  2026-11-12   000807  云铝股份   sz -0.4272   23.31   23.31  0.000000   350000.0   8158500.0         0.010093                           机构专用                           机构专用              0              0    -1.158301        None         None         None
2  2026-11-12   002273  水晶光电   sz -2.3819   23.77   21.92 -7.782920  1990700.0  43636100.0         0.134382  广发证券股份有限公司东营北一路证…  广发证券股份有限公司东营北一路证…       10084399       10084399    -1.598654        None         None         None
```

示例里的长文本列为便于阅读做了截断（以 `…` 结尾），实际返回完整内容。

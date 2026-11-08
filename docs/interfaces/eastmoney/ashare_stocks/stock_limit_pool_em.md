# 涨跌停股池接口

> 渠道：[eastmoney](../eastmoney.md) ｜ 源码：`src/em/channels/eastmoney/ashare_stocks/stock_limit_pool/stock_limit_pool_em.py`

## 接口名称

`stock_limit_pool_em` / `df_stock_limit_pool_em`：涨跌停股池（涨停 / 昨日涨停 / 强势 / 次新 / 炸板 / 跌停）

## 目标地址

- <https://quote.eastmoney.com/ztb/detail#type=ztgc>

## 描述

按股池类型和交易日一次取回整池股票。走 `push2ex` 主机（与行情 `push2` 不同的域名，同样经代理路由按 host 独立决策），响应同为 `rc=0` 的 JSON，传输层协议校验无需特判。一个接口用 `pool_type` 覆盖 akshare 的 6 个股池接口：

| `pool_type` | 股池 | 对应 akshare | 上游路径 | 实测数量（2026-11-06） |
| --- | --- | --- | --- | --- |
| `limit_up`（默认） | 涨停股池 | `stock_zt_pool_em` | `/getTopicZTPool` | 32 |
| `prev_limit_up` | 昨日涨停股池 | `stock_zt_pool_previous_em` | `/getYesterdayZTPool` | 84 |
| `strong` | 强势股池 | `stock_zt_pool_strong_em` | `/getTopicQSPool` | 151 |
| `sub_new` | 次新股池 | `stock_zt_pool_sub_new_em` | `/getTopicCXPooll` | 161 |
| `broken` | 炸板股池 | `stock_zt_pool_zbgc_em` | `/getTopicZBPool` | 14 |
| `limit_down` | 跌停股池 | `stock_zt_pool_dtgc_em` | `/getTopicDTPool` | 15 |

次新股池路径末尾的双 `l` 是上游原样拼写。

## 日期规则（实测，与 akshare 的说法不同）

- **只保留最近约 15 个交易日。** 2026-11-07 实测 10-19 到 11-06 有数据，10-16 及更早全部为空，6 个股池都一样。akshare 只对炸板、跌停股池限制 30 天，实际窗口更短，且对所有股池都生效。超出窗口不报错，只返回空池。
- **上游的 `qdate` 不是数据日期。** 无论请求哪天，`qdate` 都返回最近交易日。数据实际属于哪天要按下表判断，本接口已算好放在 `LimitPoolPage.date`：

| 请求日期 | 返回数据 | `page.date` |
| --- | --- | --- |
| 今天或未来（含周末当天） | 最近交易日 | 最近交易日 |
| 过去的交易日（窗口内） | 该日 | 该日 |
| 过去的周末 / 节假日 | 空池 | 该日 |

- **`date` 留空取北京时间今天**，即最近交易日的数据。用的是固定的 UTC+8，不依赖 tzdata。
- **格式必须是 `YYYYMMDD`。** 上游对 `2026-11-06` 这类写法不报错、只返回空数据，容易误判成“当天没有股票”，所以本接口在本地直接抛 `ValueError`；CLI 给出参数错误提示，退出码 2。
- 空池时无法区分“当天确实没有”（如 11-05 跌停股池为 0）和“超出窗口”，需结合日期判断。

## 字段处理

- **价格（`p` / `ztp`）固定除以 1000**，与 clist 的 `f1` 无关，北交所也一样。
- **涨停价哨兵值：** 北交所新股首日不设涨停价，上游 `ztp` 给 1000000000，映射为 `None`，而不是 100 万元。
- 涨跌幅、换手率、振幅、涨速、量比、市盈率为上游原值。上游是单精度浮点，会带尾数（如 `10.10988998413086`），未做取舍。
- 封板时间 `92500` → `09:25:00`；日期 `20261106` → `2026-11-06`。
- `market`：上游 `m` 为 1 是 `sh`，为 0 是 `sz`；北交所也挂在 0 下，按代码段（`4` / `8` / `92` 开头）识别为 `bj`。可连同 `code` 直接传给 `stock_kline_em`：实测 10-30 涨停池第一只 603703 盛洋科技 11.95 元，与当日 K 线收盘价一致。
- 强势股池入选理由 `cc`：1 → `60日新高`、2 → `近期多次涨停`、3 → `60日新高且近期多次涨停`。
- 涨停统计 `zttj` 拆成 `stat_days` / `stat_limit_ups`，如“10 天 6 板”。

## 输入参数 `LimitPoolQuery`

| 名称 | 类型 | 必填 | 默认值 | 描述 |
| --- | --- | --- | --- | --- |
| `pool_type` | `str` | 否 | `"limit_up"` | 股池，见上表，未知回退 `limit_up` |
| `date` | `str \| None` | 否 | `None` | 交易日 `YYYYMMDD`，留空取最近交易日 |

## 输出参数 `LimitPoolPage`

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `pool_type` | `str` | — | 规范化后的股池类型 |
| `date` | `str` | — | 数据实际所属交易日 `YYYY-MM-DD`（规则见上） |
| `total` | `int` | — | 池内股票数（上游 `tc`） |
| `items` | `tuple[LimitPoolStock, ...]` | — | 整池股票，按各股池默认排序（同 akshare） |

`LimitPoolStock` 字段（6 个股池共用；前 10 个各股池都有，其余为专属字段，不适用时为 `None`）：

| 名称 | 类型 | 单位 | 适用股池 | 描述 |
| --- | --- | --- | --- | --- |
| `code` | `str` | — | 全部 | 股票代码（`c`） |
| `name` | `str` | — | 全部 | 股票简称（`n`） |
| `market` | `str \| None` | — | 全部 | `sh` / `sz` / `bj` |
| `price` | `float \| None` | 元 | 全部 | 最新价（`p`） |
| `change_pct` | `float \| None` | % | 全部 | 涨跌幅（`zdp`） |
| `turnover` | `float \| None` | 元 | 全部 | 成交额（`amount`） |
| `float_market_cap` | `float \| None` | 元 | 全部 | 流通市值（`ltsz`） |
| `total_market_cap` | `float \| None` | 元 | 全部 | 总市值（`tshare`） |
| `turnover_rate` | `float \| None` | % | 全部 | 换手率（`hs`） |
| `industry` | `str \| None` | — | 全部 | 所属行业（`hybk`） |
| `stat_days` / `stat_limit_ups` | `int \| None` | 天 / 次 | 除跌停外 | 涨停统计（`zttj.days` / `zttj.ct`） |
| `limit_up_price` | `float \| None` | 元 | 昨日涨停 / 强势 / 次新 / 炸板 | 涨停价（`ztp`） |
| `seal_fund` | `float \| None` | 元 | 涨停 / 跌停 | 封板资金 / 封单资金（`fund`） |
| `first_seal_time` | `str \| None` | — | 涨停 / 炸板 | 首次封板时间（`fbt`） |
| `last_seal_time` | `str \| None` | — | 涨停 / 跌停 | 最后封板时间（`lbt`） |
| `broken_count` | `int \| None` | 次 | 涨停 / 炸板 | 炸板次数（`zbc`） |
| `limit_up_streak` | `int \| None` | 板 | 涨停 | 连板数（`lbc`） |
| `prev_seal_time` | `str \| None` | — | 昨日涨停 | 昨日封板时间（`yfbt`） |
| `prev_limit_up_streak` | `int \| None` | 板 | 昨日涨停 | 昨日连板数（`ylbc`） |
| `amplitude` | `float \| None` | % | 昨日涨停 / 炸板 | 振幅（`zf`） |
| `speed` | `float \| None` | % | 昨日涨停 / 强势 / 炸板 | 涨速（`zs`） |
| `volume_ratio` | `float \| None` | — | 强势 | 量比（`lb`） |
| `new_high` | `bool \| None` | — | 强势 / 次新 | 是否 60 日新高（`nh`） |
| `reason` | `str \| None` | — | 强势 | 入选理由（`cc`） |
| `open_days` | `int \| None` | 天 | 次新 | 开板几日（`ods`） |
| `open_date` | `str \| None` | — | 次新 | 开板日期（`od`） |
| `listing_date` | `str \| None` | — | 次新 | 上市日期（`ipod`） |
| `pe` | `float \| None` | — | 跌停 | 动态市盈率（`pe`） |
| `board_turnover` | `float \| None` | 元 | 跌停 | 板上成交额（`fba`） |
| `limit_down_streak` | `int \| None` | 天 | 跌停 | 连续跌停（`days`） |
| `open_count` | `int \| None` | 次 | 跌停 | 开板次数（`oc`） |

## DataFrame 列

`df_stock_limit_pool_em` 只输出该股池适用的列，列名与顺序对齐 akshare 对应接口，并在“名称”后加“市场”；涨停统计拆成“涨停统计-天数”“涨停统计-板数”两列。跌停股池的 `seal_fund` 列名为“封单资金”，其余股池为“封板资金”。各股池的列见 `src/em/application/dataframe.py` 中的 `LIMIT_POOL_FIELDS_BY_TYPE`。

## 接口示例（领域模型 `LimitPoolPage`）

```python
from em import stock_limit_pool_em
from em.domain.queries import LimitPoolQuery

page = stock_limit_pool_em(LimitPoolQuery(pool_type="limit_up", date="20261106"))
print(page.date, page.total)
for s in page.items[:2]:
    print(s.code, s.name, s.limit_up_streak, s.first_seal_time, s.seal_fund)
```

## 数据示例（领域模型）

```
limit_up 2026-11-06 32
LimitPoolStock(code='002578', name='闽发铝业', market='sz', price=5.01, change_pct=10.10988998413086, turnover=538747056.0, float_market_cap=4314424430.61, total_market_cap=4702537181.76, turnover_rate=12.504834175109863, industry='工业金属', stat_days=10, stat_limit_ups=6, limit_up_price=None, seal_fund=220341804.0, first_seal_time='09:25:00', last_seal_time='09:30:09', broken_count=1, limit_up_streak=5, prev_seal_time=None, prev_limit_up_streak=None, amplitude=None, speed=None, volume_ratio=None, new_high=None, reason=None, open_days=None, open_date=None, listing_date=None, pe=None, board_turnover=None, limit_down_streak=None, open_count=None)
LimitPoolStock(code='601599', name='浙文影业', market='sh', price=5.08, change_pct=9.956709861755371, turnover=1295102704.0, float_market_cap=5895555661.24, total_market_cap=5895555635.84, turnover_rate=21.97380256652832, industry='纺织制造', stat_days=5, stat_limit_ups=5, limit_up_price=None, seal_fund=169470679.0, first_seal_time='09:25:01', last_seal_time='10:07:58', broken_count=1, limit_up_streak=5, prev_seal_time=None, prev_limit_up_streak=None, amplitude=None, speed=None, volume_ratio=None, new_high=None, reason=None, open_days=None, open_date=None, listing_date=None, pe=None, board_turnover=None, limit_down_streak=None, open_count=None)
```

## 接口示例（`DataFrame`，akshare 风格中文列名）

```python
from em import df_stock_limit_pool_em
from em.domain.queries import LimitPoolQuery

df = df_stock_limit_pool_em(LimitPoolQuery(pool_type="limit_up", date="20261106"))
```

## 数据示例（`DataFrame`）

```
       代码    名称  市场        涨跌幅    最新价           成交额          流通市值           总市值        换手率         封板资金    首次封板时间    最后封板时间  炸板次数  涨停统计-天数  涨停统计-板数  连板数  所属行业
0  002578  闽发铝业  sz  10.109890   5.01  5.387471e+08  4.314424e+09  4.702537e+09  12.504834  220341804.0  09:25:00  09:30:09     1       10        6    5  工业金属
1  601599  浙文影业  sh   9.956710   5.08  1.295103e+09  5.895556e+09  5.895556e+09  21.973803  169470679.0  09:25:01  10:07:58     1        5        5    5  纺织制造
2  603381  永臻股份  sh  10.026525  20.74  1.558585e+08  2.947936e+09  4.920696e+09   5.287038  146363714.0  09:25:01  09:25:01     0        4        4    4  光伏设备
```

# 场内基金列表接口

> 渠道：[eastmoney](../eastmoney.md) ｜ 源码：`src/em/channels/eastmoney/fund_market/fund_list/fund_list_em.py`

## 接口名称

`fund_list_em` / `df_fund_list_em`：场内基金列表（ETF / LOF）

## 目标地址

- <https://quote.eastmoney.com/center/gridlist.html#fund_etf>
- <https://quote.eastmoney.com/center/gridlist.html#fund_lof>

## 描述

按基金类型抓取场内基金实时行情列表，返回代码、名称、市场、最新价、IOPV 实时估值、折价率、涨跌额、涨跌幅、成交量、成交额、开盘价、最高价、最低价、昨收、换手率、流通市值、总市值。走 `pushguest` 游客主机的 `clist` 接口。对应 akshare `fund_etf_spot_em` / `fund_lof_spot_em`：

| `fund_type` | 范围 | 上游 `fs` | 实测 total（2026-11-06） |
| --- | --- | --- | --- |
| `etf`（默认） | ETF | `b:MK0021,b:MK0022,b:MK0023,b:MK0024,b:MK0827` | 1666 |
| `lof` | LOF | `b:MK0404,b:MK0405,b:MK0406,b:MK0407` | 389 |
| `all` | ETF + LOF | 两者拼接 | 2055 |

- akshare 的 ETF 走 `push2delay` 主机、LOF 走 `push2`；实测 `pushguest` 返回同样的 total 与数据，本接口统一走游客主机。
- 列取 akshare 两个接口的共有列，再加 ETF 的 IOPV 与折价率。akshare ETF 版另有资金流、委比、内外盘、买一卖一、最新份额等列，本接口未包含。

**字段倍数（实测 `fltt=1` 与 `fltt=2` 逐字段对照确认）：**

| 字段 | 处理 |
| --- | --- |
| 价格、涨跌额（`f2` / `f4` / `f15`–`f18`） | 除以 `10 ** f1`；基金 `f1=3`，即除以 1000，与港股同一套逻辑 |
| 涨跌幅、换手率、折价率（`f3` / `f8` / `f402`） | 除以 100 |
| IOPV（`f441`） | **原值**：`fltt=1` 时也不放大，不能再除 |
| 成交量（手）、成交额、市值（`f5` / `f6` / `f20` / `f21`） | 原值 |

**折价率为负表示溢价。** 上游口径为 `(IOPV − 价格) / IOPV`，如中韩半导体ETF 价格 3.541、IOPV 3.2077，折价率 −10.39%。

**IOPV 不一定有值。** LOF 没有 IOPV；货币 ETF（如 511880 银华日利ETF）也没有。这些情况 `iopv` 为 `None`，但折价率仍可能有值（LOF 按净值计算）。

## 限量

- 单页最多 100 条，ETF 1666 条需翻页。
- 上游对境外 IP 封禁 / 限流，需经国内动态代理访问；本接口已内置代理池 + 自动换 IP 重试。
- `fund_type` 传未知值时回退 `etf`；`sort` 为上游排序字段名（如 `f3` 涨跌幅、`f6` 成交额）。
- 停牌基金（如 160142 南方优势产业LOF）上游返回 `"-"`，对应字段为 `None`，昨收与市值通常仍有值。
- 价格、成交额、市值单位为元，成交量单位为手。

## 与 K 线接口衔接

`code` 连同 `market`（`sh` / `sz`）可直接传给 `stock_kline_em` 取基金 K 线，覆盖 akshare `fund_etf_hist_em` / `fund_lof_hist_em` 的日 / 周 / 月及 5–60 分钟周期：

```python
from em import fund_list_em, stock_kline_em
from em.domain.queries import FundListQuery, KlineQuery

etf = fund_list_em(FundListQuery(fund_type="etf", sort="f6", size=3)).items[-1]
series = stock_kline_em(KlineQuery(code=etf.code, market=etf.market, period="day", adjust="none"))
print(series.name, series.items[-1].close)
```

实测 159915 创业板ETF易方达列表价 2.480，与当日 K 线收盘价一致。注意 `cli --preset kline` 的渲染保留 2 位小数，领域模型本身是完整精度。

## 输入参数 `FundListQuery`

| 名称 | 类型 | 必填 | 默认值 | 描述 |
| --- | --- | --- | --- | --- |
| `fund_type` | `str` | 否 | `"etf"` | 基金类型：`etf` / `lof` / `all`（ETF + LOF），未知回退 `etf` |
| `sort` | `str` | 否 | `"f3"` | 排序字段（上游 `f*` 字段名） |
| `page` | `int` | 否 | `1` | 页码，从 1 起 |
| `size` | `int` | 否 | `20` | 每页条数，上游上限 100 |

## 输出参数 `FundListPage`

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `total` | `int` | — | 该类型基金总数 |
| `items` | `tuple[FundQuote, ...]` | — | 本页基金 |

`FundQuote` 字段：

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `code` | `str` | — | 基金代码 |
| `name` | `str` | — | 基金简称 |
| `market` | `str \| None` | — | 市场：`sh` / `sz`（`f13` 前缀 1 / 0） |
| `price` | `float \| None` | 元 | 最新价（`f2`） |
| `iopv` | `float \| None` | 元 | IOPV 实时估值（`f441`，LOF 与货币 ETF 为 `None`） |
| `discount_rate` | `float \| None` | % | 基金折价率（`f402`，负值表示溢价） |
| `change_pct` | `float \| None` | % | 涨跌幅（`f3`） |
| `change` | `float \| None` | 元 | 涨跌额（`f4`） |
| `volume` | `float \| None` | 手 | 成交量（`f5`） |
| `turnover` | `float \| None` | 元 | 成交额（`f6`） |
| `open` | `float \| None` | 元 | 开盘价（`f17`） |
| `high` | `float \| None` | 元 | 最高价（`f15`） |
| `low` | `float \| None` | 元 | 最低价（`f16`） |
| `pre_close` | `float \| None` | 元 | 昨收（`f18`） |
| `turnover_rate` | `float \| None` | % | 换手率（`f8`） |
| `float_market_cap` | `float \| None` | 元 | 流通市值（`f21`） |
| `total_market_cap` | `float \| None` | 元 | 总市值（`f20`） |

## 接口示例（领域模型 `FundListPage`）

```python
from em import fund_list_em
from em.domain.queries import FundListQuery

page = fund_list_em(FundListQuery(fund_type="etf", sort="f6", size=3))
print(page.total)
for q in page.items:
    print(q.code, q.market, q.name, q.price, q.iopv, q.discount_rate)
```

## 数据示例（领域模型）

```
total: 1666
FundQuote(code='511880', name='银华日利ETF', market='sh', price=100.954, iopv=None, discount_rate=-0.01, change_pct=0.02, change=0.023, volume=3498839.0, turnover=35321084294.0, open=100.948, high=100.954, low=100.945, pre_close=100.931, turnover_rate=29.77, float_market_cap=118649238118.0, total_market_cap=118649238118.0)
FundQuote(code='511990', name='华宝添益ETF', market='sh', price=100.008, iopv=None, discount_rate=-0.01, change_pct=0.01, change=0.012, volume=1769170.0, turnover=17692647355.0, open=100.004, high=100.009, low=100.003, pre_close=99.996, turnover_rate=17.08, float_market_cap=103617989576.0, total_market_cap=103617989576.0)
FundQuote(code='159915', name='创业板ETF易方达', market='sz', price=2.48, iopv=2.4809, discount_rate=0.04, change_pct=-4.02, change=-0.104, volume=55565896.0, turnover=13843109694.811, open=2.485, high=2.524, low=2.465, pre_close=2.584, turnover_rate=12.37, float_market_cap=111387848499.0, total_market_cap=111387848499.0)
```

## 接口示例（`DataFrame`，akshare 风格中文列名）

```python
from em import df_fund_list_em
from em.domain.queries import FundListQuery

df = df_fund_list_em(FundListQuery(fund_type="lof", sort="f6", size=3))
```

## 数据示例（`DataFrame`）

```
       代码        名称  市场    最新价 IOPV实时估值  基金折价率    涨跌额   涨跌幅        成交量           成交额    开盘价    最高价    最低价     昨收    换手率          流通市值           总市值
0  501018   南方原油LOF  sh  2.062     None  -1.74  0.057  2.84  5558582.0  1.159950e+09  2.083  2.120  2.059  2.005  83.86  1.366745e+09  1.366745e+09
1  161129  原油LOF易方达  sz  1.932     None  -0.10  0.069  3.70  2528150.0  4.887952e+08  1.928  1.944  1.921  1.863  58.19  8.393676e+08  8.393676e+08
2  160723   嘉实原油LOF  sz  2.317     None  -0.26  0.086  3.85  1287334.0  2.979785e+08  2.302  2.328  2.302  2.231  26.25  1.136244e+09  1.136244e+09
```

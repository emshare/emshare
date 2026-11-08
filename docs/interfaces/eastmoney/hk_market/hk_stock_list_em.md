# 港股列表接口

> 渠道：[eastmoney](../eastmoney.md) ｜ 源码：`src/em/channels/eastmoney/hk_market/hk_stock_list/hk_stock_list_em.py`

## 接口名称

`hk_stock_list_em` / `df_hk_stock_list_em`：港股列表（主板 / 创业板）

## 目标地址

- <https://quote.eastmoney.com/center/gridlist.html#hk_stocks>

## 描述

按板块范围抓取港股实时行情列表，返回代码、名称、最新价、涨跌额、涨跌幅、今开、最高、最低、昨收、成交量、成交额。走 `pushguest` 游客主机的 `clist` 接口，与 A 股列表同源。对应 akshare `stock_hk_spot_em` / `stock_hk_main_board_spot_em`：

| `scope` | 范围 | 上游 `fs` | 实测 total（2026-11-06） |
| --- | --- | --- | --- |
| `all`（默认） | 主板 + 创业板 | `m:128+t:3,m:128+t:4` | 2933 |
| `main` | 主板 | `m:128+t:3` | 2620 |
| `gem` | 创业板（8 字头代码） | `m:128+t:4` | 313 |

**与 akshare `stock_hk_spot_em` 的口径不同。** akshare 的“全部港股”是 `m:128` 下 `t:1` 到 `t:4` 四段，实测 4743 条，其中 `t:1`（489 条）是 ETF 与基金（如 02800 盈富基金、杠杆反向产品），`t:2`（1321 条）是债券（如国债、政府债）。本接口名为股票列表，只取主板和创业板；ETF 与债券留给基金、债券市场的接口。`main` 与 akshare `stock_hk_main_board_spot_em` 一致。

**价格按 3 位小数还原。** 东财 `fltt=1` 时价格按 `10 ** f1` 放大：A 股与指数 `f1=2`，港股 `f1=3`。所以港股价格要除以 1000，不能套用 A 股的 100 倍（否则腾讯会被算成 4198 港元）。映射层逐行读 `f1`，缺失时按 2 位处理；涨跌幅仍放大 100 倍。0.3 港元左右的仙股正是需要第 3 位小数的场景（如 08299 大唐黄金 0.215）。

## 限量

- 单页最多 100 条，全量 2933 条需翻页。
- 上游对境外 IP 封禁 / 限流，需经国内动态代理访问；本接口已内置代理池 + 自动换 IP 重试。
- `scope` 传未知值时回退 `all`；`sort` 为上游排序字段名（如 `f3` 涨跌幅、`f6` 成交额）。
- 停牌或无成交的股票（如 00007 智富资源投资）上游返回 `"-"`，对应字段为 `None`，昨收通常仍有值。
- 价格与成交额单位为**港元**，成交量单位为**股**（不是手；港股每手股数因股而异）。

## 与 K 线接口衔接

`code` 连同 `market="hk"` 可直接传给 `stock_kline_em` 取港股 K 线（secid 前缀 `116`）：

```python
from em import hk_stock_list_em, stock_kline_em
from em.domain.queries import HkStockListQuery, KlineQuery

q = hk_stock_list_em(HkStockListQuery(scope="main", sort="f6", size=1)).items[0]
series = stock_kline_em(KlineQuery(code=q.code, market="hk", period="day", adjust="qfq"))
```

- 实测腾讯控股 2026-11-06 不复权日 K 收盘价 419.800、成交量 29605485，与本接口一致。
- 港股 K 线的价格单位是港元、成交量单位是股（不是手），与 A 股 K 线不同；`KlineSeries` 本身不带币种，调用方需按 `market` 区分。
- 复权有效：前复权与不复权结果不同（如腾讯 2020-01-02 收盘不复权 382.400、前复权 333.105）。

## 输入参数 `HkStockListQuery`

| 名称 | 类型 | 必填 | 默认值 | 描述 |
| --- | --- | --- | --- | --- |
| `scope` | `str` | 否 | `"all"` | 范围：`all` 主板 + 创业板 / `main` 主板 / `gem` 创业板，未知回退 `all` |
| `sort` | `str` | 否 | `"f3"` | 排序字段（上游 `f*` 字段名） |
| `page` | `int` | 否 | `1` | 页码，从 1 起 |
| `size` | `int` | 否 | `20` | 每页条数，上游上限 100 |

## 输出参数 `HkStockListPage`

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `total` | `int` | — | 该范围港股总数 |
| `items` | `tuple[HkQuote, ...]` | — | 本页港股 |

`HkQuote` 字段：

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `code` | `str` | — | 港股代码（5 位） |
| `name` | `str` | — | 证券简称 |
| `price` | `float \| None` | 港元 | 最新价（`f2`） |
| `change_pct` | `float \| None` | % | 涨跌幅（`f3`） |
| `change` | `float \| None` | 港元 | 涨跌额（`f4`） |
| `open` | `float \| None` | 港元 | 今开（`f17`） |
| `high` | `float \| None` | 港元 | 最高（`f15`） |
| `low` | `float \| None` | 港元 | 最低（`f16`） |
| `pre_close` | `float \| None` | 港元 | 昨收（`f18`） |
| `volume` | `float \| None` | 股 | 成交量（`f5`） |
| `turnover` | `float \| None` | 港元 | 成交额（`f6`） |

## 接口示例（领域模型 `HkStockListPage`）

```python
from em import hk_stock_list_em
from em.domain.queries import HkStockListQuery

page = hk_stock_list_em(HkStockListQuery(scope="main", sort="f6", size=3))
print(page.total)
for q in page.items:
    print(q.code, q.name, q.price, q.change_pct)
```

## 数据示例（领域模型）

```
total: 2620
HkQuote(code='00700', name='腾讯控股', price=419.8, change_pct=-2.46, change=-10.6, open=421.0, high=428.6, low=416.2, pre_close=430.4, volume=29605485.0, turnover=12502715648.0)
HkQuote(code='09988', name='阿里巴巴-W', price=104.9, change_pct=-3.85, change=-4.2, open=105.0, high=107.0, low=103.9, pre_close=109.1, volume=95566833.0, turnover=10063671552.0)
HkQuote(code='01810', name='小米集团-W', price=30.38, change_pct=-2.94, change=-0.92, open=31.0, high=31.74, low=30.22, pre_close=31.3, volume=303884864.0, turnover=9420626688.0)
```

## 接口示例（`DataFrame`，akshare 风格中文列名）

```python
from em import df_hk_stock_list_em
from em.domain.queries import HkStockListQuery

df = df_hk_stock_list_em(HkStockListQuery(scope="main", sort="f6", size=3))
```

## 数据示例（`DataFrame`）

```
      代码      名称     最新价    涨跌额   涨跌幅     今开      最高      最低     昨收          成交量           成交额
0  00700    腾讯控股  419.80 -10.60 -2.46  421.0  428.60  416.20  430.4   29605485.0  1.250272e+10
1  09988  阿里巴巴-W  104.90  -4.20 -3.85  105.0  107.00  103.90  109.1   95566833.0  1.006367e+10
2  01810  小米集团-W   30.38  -0.92 -2.94   31.0   31.74   30.22   31.3  303884864.0  9.420627e+09
```

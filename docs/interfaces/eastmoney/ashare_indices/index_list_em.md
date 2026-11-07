# 指数列表接口

> 渠道：[eastmoney](../eastmoney.md) ｜ 源码：`src/em/channels/eastmoney/ashare_indices/index_list/index_list_em.py`

## 接口名称

`index_list_em` / `df_index_list_em`：指数列表（沪深重要指数 / 上证系列 / 深证系列 / 中证系列）

## 目标地址

- <https://quote.eastmoney.com/center/gridlist.html#index_sz>

## 描述

按指数系列抓取指数实时行情列表，返回代码、名称、市场、最新点位、涨跌幅、涨跌额、成交量、成交额、振幅、最高、最低、今开、昨收、量比。走 `pushguest` 游客主机的 `clist` 接口，与板块列表、个股列表同源。对应 akshare `stock_zh_index_spot_em`：

| `series` | akshare `symbol` | 上游 `fs` | 实测 total（2026-11-06） |
| --- | --- | --- | --- |
| `main`（默认） | 沪深重要指数 | `b:MK0010` | 43 |
| `sh` | 上证系列指数 | `m:1+t:1` | 268 |
| `sz` | 深证系列指数 | `m:0+t:5` | 957 |
| `csi` | 中证系列指数 | `m:2` | 562 |

- akshare 的“指数成份”（`m:1+s:3,m:0+t:5`，实测 1137 条）的 `fs` 包含整个深证系列（`m:0+t:5`），本接口未单独提供。
- 北证指数（如 899050 北证50）只出现在 `main` 里，不在 `sh` / `sz` / `csi` 任一系列中。
- `sh` / `sz` / `csi` 三个系列之间代码互不重复（实测共 1787 条）。

**代码要连同 `market` 一起用。** `000001` 在沪市是上证指数、在深市是平安银行，所以每条指数都带 `market`：上游 `f13` 前缀 `1` 为 `sh`、`2` 为 `csi`、`0` 为 `sz`；北证指数也挂在 `0` 前缀下，按 `899` 代码段识别为 `bj`。akshare 的输出没有这一列，单凭代码无法区分。

## 限量

- 单页最多 100 条，`sz` 系列 957 条需翻页。
- 上游对境外 IP 封禁 / 限流，需经国内动态代理访问；本接口已内置代理池 + 自动换 IP 重试。
- `series` 传未知值时回退 `main`；`sort` 为上游排序字段名（如 `f3` 涨跌幅、`f6` 成交额）。
- 停牌或未开盘的指数（如 988201 湾创100R）上游返回 `"-"`，对应字段为 `None`，昨收通常仍有值。
- 点位类字段单位为**点**，成交额单位为元，成交量单位为手。

## 与 K 线接口衔接

`market` 为 `sh` / `sz` / `bj` 的指数可直接传给 `stock_kline_em` 取 K 线：

```python
from em import index_list_em, stock_kline_em
from em.domain.queries import IndexListQuery, KlineQuery

idx = next(i for i in index_list_em(IndexListQuery(size=100)).items if i.code == "000001")
series = stock_kline_em(KlineQuery(code=idx.code, market=idx.market, period="day"))
print(series.name)  # 上证指数
```

`market="csi"` 的中证指数暂时不行：`stock_kline_em` 只认 `sz` / `sh` / `bj`，传 `csi` 会回退到深市。上游本身支持（实测 `secid=2.932000` 能取到中证2000 的 K 线），需要另行扩展。

## 输入参数 `IndexListQuery`

| 名称 | 类型 | 必填 | 默认值 | 描述 |
| --- | --- | --- | --- | --- |
| `series` | `str` | 否 | `"main"` | 指数系列：`main` 沪深重要指数 / `sh` 上证系列 / `sz` 深证系列 / `csi` 中证系列，未知回退 `main` |
| `sort` | `str` | 否 | `"f3"` | 排序字段（上游 `f*` 字段名） |
| `page` | `int` | 否 | `1` | 页码，从 1 起 |
| `size` | `int` | 否 | `20` | 每页条数，上游上限 100 |

## 输出参数 `IndexListPage`

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `total` | `int` | — | 该系列指数总数 |
| `items` | `tuple[IndexQuote, ...]` | — | 本页指数 |

`IndexQuote` 字段：

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `code` | `str` | — | 指数代码 |
| `name` | `str` | — | 指数名称 |
| `market` | `str \| None` | — | 市场：`sh` / `sz` / `bj` / `csi`（`f13` + 代码段） |
| `price` | `float \| None` | 点 | 最新点位（`f2`） |
| `change_pct` | `float \| None` | % | 涨跌幅（`f3`） |
| `change` | `float \| None` | 点 | 涨跌额（`f4`） |
| `volume` | `float \| None` | 手 | 成交量（`f5`） |
| `turnover` | `float \| None` | 元 | 成交额（`f6`） |
| `amplitude` | `float \| None` | % | 振幅（`f7`） |
| `high` | `float \| None` | 点 | 最高（`f15`） |
| `low` | `float \| None` | 点 | 最低（`f16`） |
| `open` | `float \| None` | 点 | 今开（`f17`） |
| `pre_close` | `float \| None` | 点 | 昨收（`f18`） |
| `volume_ratio` | `float \| None` | — | 量比（`f10`） |

## 接口示例（领域模型 `IndexListPage`）

```python
from em import index_list_em
from em.domain.queries import IndexListQuery

page = index_list_em(IndexListQuery(series="main", sort="f6", size=3))
print(page.total)
for i in page.items:
    print(i.code, i.market, i.name, i.price, i.change_pct)
```

## 数据示例（领域模型）

```
total: 43
IndexQuote(code='000985', name='中证全指', market='sh', price=5115.37, change_pct=-1.85, change=-96.42, volume=1006247073.0, turnover=1597481825555.0, amplitude=1.94, high=5160.75, low=5059.65, open=5059.65, pre_close=5211.79, volume_ratio=0.88)
IndexQuote(code='399001', name='深证成指', market='sz', price=11175.78, change_pct=-2.57, change=-295.31, volume=569400962.0, turnover=885159900792.1285, amplitude=2.25, high=11303.22, low=11044.56, open=11044.56, pre_close=11471.09, volume_ratio=0.9)
IndexQuote(code='399106', name='深证综指', market='sz', price=2134.88, change_pct=-2.25, change=-49.22, volume=569348123.0, turnover=885158726099.4086, amplitude=2.28, high=2158.29, low=2108.43, open=2108.43, pre_close=2184.1, volume_ratio=0.9)
```

## 接口示例（`DataFrame`，akshare 风格中文列名）

```python
from em import df_index_list_em
from em.domain.queries import IndexListQuery

df = df_index_list_em(IndexListQuery(series="main", sort="f6", size=4))
```

## 数据示例（`DataFrame`）

```
       代码    名称  市场       最新价   涨跌幅     涨跌额           成交量           成交额    振幅        最高        最低        今开        昨收    量比
0  000985  中证全指  sh   5115.37 -1.85  -96.42  1.006247e+09  1.597482e+12  1.94   5160.75   5059.65   5059.65   5211.79  0.88
1  399001  深证成指  sz  11175.78 -2.57 -295.31  5.694010e+08  8.851599e+11  2.25  11303.22  11044.56  11044.56  11471.09  0.90
2  399106  深证综指  sz   2134.88 -2.25  -49.22  5.693481e+08  8.851587e+11  2.28   2158.29   2108.43   2108.43   2184.10  0.90
3  399100   新指数  sz  10111.23 -2.23 -230.73  5.554193e+08  8.789047e+11  2.24  10219.13   9987.27   9987.27  10341.96  0.90
```

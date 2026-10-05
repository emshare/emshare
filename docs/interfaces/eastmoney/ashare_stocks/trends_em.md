# 分时行情接口

> 渠道：[eastmoney](../eastmoney.md) ｜ 源码：`src/em/channels/eastmoney/ashare_stocks/trends/trends_em.py`

## 接口名称

`fetch_trends` / `fetch_trends_df`：个股 / 指数分时行情（`trends2`，`ndays` 日分时）

## 目标地址

- <https://quote.eastmoney.com/sz000001.html#fullScreenChart>

## 描述

按证券代码抓取分时（分钟级）行情，返回时间、最新价、均价、最高、最低、成交量、成交额、均价2。走 `push2his` 历史主机。`ndays` 控制分时天数（`1` 当日、`5` 五日）。响应 `data` 含 `preClose`（昨收）、`prePrice`（昨结算 / 盘前价）、`trendsTotal`（分时点总数）。与 `clist` 接口不同，分时价格**不做** 100 倍放大还原，映射层直接按原值读取。

## 限量

- 单次返回所请求 `ndays` 日全部分时点（A 股一日 241 个点，09:30–15:00 每分钟一个）。
- 上游对境外 IP 封禁 / 限流，需经国内动态代理访问；本接口已内置代理池 + 自动换 IP 重试。
- 非交易日请求 `ndays=1` 返回最近一个交易日的分时。
- 价格单位为元，成交量单位为手，成交额单位为元。

## 输入参数 `TrendQuery`

| 名称 | 类型 | 必填 | 默认值 | 描述 |
| --- | --- | --- | --- | --- |
| `code` | `str` | 否 | `"000001"` | 证券代码，如 `000001` |
| `market` | `str` | 否 | `"sz"` | 市场：`sz` 深市 / `sh` 沪市 / `bj` 北交所，未知回退 `sz` |
| `ndays` | `int` | 否 | `1` | 分时天数：`1` 当日 / `5` 五日 |
| `iscr` | `int` | 否 | `0` | 是否含前收盘 |
| `iscca` | `int` | 否 | `0` | 是否含成交额累计 |

## 输出参数 `TrendSeries`

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `code` | `str` | — | 证券代码 |
| `name` | `str` | — | 证券简称 |
| `pre_close` | `float \| None` | 元 | 昨收 |
| `pre_price` | `float \| None` | 元 | 昨结算 / 盘前价 |
| `ndays` | `int` | — | 分时天数 |
| `items` | `tuple[Trend, ...]` | — | 分时点序列，按时间升序 |

`Trend` 字段：

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `time` | `str` | — | 时间 `YYYY-MM-DD HH:MM` |
| `price` | `float \| None` | 元 | 最新价 |
| `avg_price` | `float \| None` | 元 | 均价 |
| `high` | `float \| None` | 元 | 该分钟最高 |
| `low` | `float \| None` | 元 | 该分钟最低 |
| `volume` | `float \| None` | 手 | 成交量 |
| `amount` | `float \| None` | 元 | 成交额 |
| `avg_price2` | `float \| None` | 元 | 均价（3 位精度，f58） |

## 接口示例（领域模型 `TrendSeries`）

```python
from em import fetch_trends
from em.domain.queries import TrendQuery

series = fetch_trends(TrendQuery(code="000001", market="sz", ndays=1))
print(series.code, series.name, series.pre_close, len(series.items))
for t in series.items[:3]:
    print(t.time, t.price, t.avg_price)
```

## 数据示例（领域模型）

```
code=000001 name=平安银行 pre_close=11.35 pre_price=11.35 ndays=1 共 241 个分时点，首 3 条：
Trend(time='2026-09-30 09:30', price=11.36, avg_price=11.36, high=11.36, low=11.36, volume=2625.0, amount=2982000.0, avg_price2=11.36)
Trend(time='2026-09-30 09:31', price=11.34, avg_price=11.39, high=11.41, low=11.33, volume=18271.0, amount=20793150.0, avg_price2=11.378)
Trend(time='2026-09-30 09:32', price=11.39, avg_price=11.38, high=11.4, low=11.38, volume=3409.0, amount=3883010.0, avg_price2=11.38)
```

## 接口示例（`DataFrame`，中文列名）

```python
from em import fetch_trends_df
from em.domain.queries import TrendQuery

df = fetch_trends_df(TrendQuery(code="000001", market="sz", ndays=1))
```

## 数据示例（`DataFrame`）

```
                  时间   最新价    均价    最高    最低    成交量         成交额    均价2
0  2026-09-30 09:30  11.36  11.36  11.36  11.36     2625.0  2.982000e+06  11.360
1  2026-09-30 09:31  11.34  11.39  11.41  11.33    18271.0  2.079315e+07  11.378
2  2026-09-30 09:32  11.39  11.38  11.40  11.38     3409.0  3.883010e+06  11.380
```
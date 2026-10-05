# 历史 K 线接口

> 渠道：[eastmoney](../eastmoney.md) ｜ 源码：`src/em/channels/eastmoney/ashare_stocks/kline/kline_em.py`

## 接口名称

`kline_em` / `df_kline_em`：个股 / 指数历史 K 线（日 / 周 / 月 / 5分 / 15分 / 30分 / 60分，前 / 后 / 不复权）

## 目标地址

- <https://quote.eastmoney.com/sz000001.html#fullScreenChart>

## 描述

按证券代码抓取历史 K 线序列，返回日期、开盘、收盘、最高、最低、成交量、成交额、振幅、涨跌幅、涨跌额、换手率。走 `push2his` 历史行情主机。`period` 决定周期（`day`→`klt=101` 日 K、`week`→`klt=102` 周 K、`month`→`klt=103` 月 K、`5m`→`klt=5` 5 分钟、`15m`→`klt=15` 15 分钟、`30m`→`klt=30` 30 分钟、`60m`→`klt=60` 60 分钟），`adjust` 决定复权（`qfq`→`fqt=1` 前复权、`hfq`→`fqt=2` 后复权、`none`→`fqt=0` 不复权）。与 `clist` 接口不同，K 线价格**不做** 100 倍放大还原，映射层直接按原值读取。

## 限量

- 单次返回所请求区间内的全部 K 线；`beg=0` 且 `end=20500101` 可取全历史（如平安银行日 K 共 8490 条）。
- 上游对境外 IP 封禁 / 限流，需经国内动态代理访问；本接口已内置代理池 + 自动换 IP 重试。
- `period` / `adjust` 传未知值时回退 `day` / `qfq`；分钟级周期（`5m`/`15m`/`30m`/`60m`）的 `date` 字段为 `YYYY-MM-DD HH:MM` 时间戳，数据量远大于日级，建议用 `beg`/`end` 限定区间。
- 价格单位为元，成交量单位为手，成交额单位为元。

## 输入参数 `KlineQuery`

| 名称 | 类型 | 必填 | 默认值 | 描述 |
| --- | --- | --- | --- | --- |
| `code` | `str` | 否 | `"000001"` | 证券代码，如 `000001` |
| `market` | `str` | 否 | `"sz"` | 市场：`sz` 深市 / `sh` 沪市 / `bj` 北交所，未知回退 `sz` |
| `period` | `str` | 否 | `"day"` | 周期：`day` 日 K / `week` 周 K / `month` 月 K / `5m` / `15m` / `30m` / `60m` 分钟 K，未知回退 `day` |
| `adjust` | `str` | 否 | `"qfq"` | 复权：`qfq` 前复权 / `hfq` 后复权 / `none` 不复权，未知回退 `qfq` |
| `beg` | `str` | 否 | `"0"` | 起始日期 `YYYYMMDD`，`0` 表示不限 |
| `end` | `str` | 否 | `"20500101"` | 结束日期 `YYYYMMDD` |

## 输出参数 `KlineSeries`

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `code` | `str` | — | 证券代码 |
| `name` | `str` | — | 证券简称 |
| `period` | `str` | — | 实际生效周期（规范化后） |
| `adjust` | `str` | — | 实际生效复权方式（规范化后） |
| `items` | `tuple[Kline, ...]` | — | K 线序列，按日期升序 |

`Kline` 字段：

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `date` | `str` | — | 交易日期/时间（日/周/月为 `YYYY-MM-DD`；分钟级为 `YYYY-MM-DD HH:MM`） |
| `open` | `float \| None` | 元 | 开盘价 |
| `close` | `float \| None` | 元 | 收盘价 |
| `high` | `float \| None` | 元 | 最高价 |
| `low` | `float \| None` | 元 | 最低价 |
| `volume` | `float \| None` | 手 | 成交量 |
| `amount` | `float \| None` | 元 | 成交额 |
| `amplitude` | `float \| None` | % | 振幅 |
| `change_pct` | `float \| None` | % | 涨跌幅 |
| `change` | `float \| None` | 元 | 涨跌额 |
| `turnover_rate` | `float \| None` | % | 换手率 |

## 接口示例（领域模型 `KlineSeries`）

```python
from em import kline_em
from em.domain.queries import KlineQuery

series = kline_em(KlineQuery(code="000001", market="sz", period="day", adjust="qfq"))
print(series.code, series.name, len(series.items))
for k in series.items[-3:]:
    print(k.date, k.open, k.close, k.change_pct)
```

## 数据示例（领域模型）

```
code=000001 name=平安银行 period=day adjust=qfq 共 8490 条，末 3 条：
Kline(date='2026-09-28', open=11.28, close=11.3, high=11.41, low=11.27, volume=715341.0, amount=810575796.4, amplitude=1.24, change_pct=0.0, change=0.0, turnover_rate=0.37)
Kline(date='2026-09-29', open=11.3, close=11.35, high=11.41, low=11.28, volume=690979.0, amount=784632823.03, amplitude=1.15, change_pct=0.44, change=0.05, turnover_rate=0.36)
Kline(date='2026-09-30', open=11.36, close=11.57, high=11.65, low=11.33, volume=1045357.0, amount=1205814857.64, amplitude=2.82, change_pct=1.94, change=0.22, turnover_rate=0.54)
```

## 接口示例（`DataFrame`，akshare 风格中文列名）

```python
from em import df_kline_em
from em.domain.queries import KlineQuery

df = df_kline_em(KlineQuery(code="000001", market="sz", period="day", adjust="qfq"))
```

## 数据示例（`DataFrame`）

```
          日期     开盘     收盘     最高     最低      成交量           成交额    振幅    涨跌幅   涨跌额    换手率
0  2026-09-28  11.28  11.30  11.41  11.27   715341.0  8.105758e+08  1.24   0.00  0.00   0.37
1  2026-09-29  11.30  11.35  11.41  11.28   690979.0  7.846328e+08  1.15   0.44  0.05   0.36
2  2026-09-30  11.36  11.57  11.65  11.33  1045357.0  1.205815e+09  2.82   1.94  0.22   0.54
```
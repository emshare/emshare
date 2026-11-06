# 板块（行业 / 概念 / 地域）历史 K 线接口

> 渠道：[eastmoney](../eastmoney.md) ｜ 源码：`src/em/channels/eastmoney/ashare_boards/board_kline/board_kline_em.py`

## 接口名称

`board_kline_em` / `df_board_kline_em`：板块历史 K 线（日 / 周 / 月 / 5分 / 15分 / 30分 / 60分）

## 目标地址

- <https://quote.eastmoney.com/bk/90.BK0438.html>

## 描述

按板块代码抓取板块指数的历史 K 线，返回日期、开盘、收盘、最高、最低、成交量、成交额、振幅、涨跌幅、涨跌额、换手率。与个股 K 线共用上游端点 `push2his` 的 `kline/get`，参数仅 `secid` 不同：板块统一用 `90.` 前缀（如 `90.BK0438`），与 `board_fund_flow_em` 一致。`period` 决定周期，映射与 `stock_kline_em` 相同（`day`→`klt=101`、`week`→`102`、`month`→`103`、`5m`/`15m`/`30m`/`60m`→`5`/`15`/`30`/`60`）。

板块是指数，复权对其无意义：实测 `fqt=0` 与 `fqt=1` 返回完全一致，因此本接口不提供 `adjust` 参数，固定按不复权（`fqt=0`）请求，返回的 `KlineSeries.adjust` 恒为 `none`。

对应 akshare：`stock_board_industry_hist_em` / `stock_board_concept_hist_em`（日 / 周 / 月）与 `stock_board_industry_hist_min_em` / `stock_board_concept_hist_min_em` 的 5 到 60 分钟周期；1 分钟周期 akshare 走 `trends2`，本接口不含。

## 限量

- 单次返回所请求区间内的全部 K 线；`beg=0` 且 `end=20500101` 可取全历史（如 BK0438 食品饮料日 K 共 6502 条）。
- 上游对境外 IP 封禁 / 限流，需经国内动态代理访问；本接口已内置代理池 + 自动换 IP 重试。
- `period` 传未知值时回退 `day`；分钟级周期的 `date` 为 `YYYY-MM-DD HH:MM`，数据量远大于日级，建议用 `beg` / `end` 限定区间。
- 开盘 / 收盘 / 最高 / 最低 / 涨跌额单位为**点**（板块指数点位），成交额单位为元。

## 输入参数 `BoardKlineQuery`

| 名称 | 类型 | 必填 | 默认值 | 描述 |
| --- | --- | --- | --- | --- |
| `board` | `str` | 否 | `"BK0438"` | 板块代码，如 `BK0438` 食品饮料（可从 `board_industry_list_em` 取） |
| `period` | `str` | 否 | `"day"` | 周期：`day` 日 K / `week` 周 K / `month` 月 K / `5m` / `15m` / `30m` / `60m` 分钟 K，未知回退 `day` |
| `beg` | `str` | 否 | `"0"` | 起始日期 `YYYYMMDD`，`0` 表示不限 |
| `end` | `str` | 否 | `"20500101"` | 结束日期 `YYYYMMDD` |

## 输出参数 `KlineSeries`

与 `stock_kline_em` 共用领域模型：

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `code` | `str` | — | 板块代码 |
| `name` | `str` | — | 板块名称 |
| `period` | `str` | — | 实际生效周期（规范化后） |
| `adjust` | `str` | — | 恒为 `none` |
| `items` | `tuple[Kline, ...]` | — | K 线序列，按日期升序 |

`Kline` 字段：

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `date` | `str` | — | 交易日期/时间（日/周/月为 `YYYY-MM-DD`；分钟级为 `YYYY-MM-DD HH:MM`） |
| `open` | `float \| None` | 点 | 开盘点位 |
| `close` | `float \| None` | 点 | 收盘点位 |
| `high` | `float \| None` | 点 | 最高点位 |
| `low` | `float \| None` | 点 | 最低点位 |
| `volume` | `float \| None` | 手 | 成交量 |
| `amount` | `float \| None` | 元 | 成交额 |
| `amplitude` | `float \| None` | % | 振幅 |
| `change_pct` | `float \| None` | % | 涨跌幅 |
| `change` | `float \| None` | 点 | 涨跌额 |
| `turnover_rate` | `float \| None` | % | 换手率 |

## 接口示例（领域模型 `KlineSeries`）

```python
from em import board_kline_em
from em.domain.queries import BoardKlineQuery

series = board_kline_em(BoardKlineQuery(board="BK0438", period="day"))
print(series.code, series.name, len(series.items))
for k in series.items[-3:]:
    print(k.date, k.open, k.close, k.change_pct)
```

## 数据示例（领域模型）

```
code=BK0438 name=食品饮料 period=day adjust=none，beg=20261102 end=20261104 共 3 条：
Kline(date='2026-11-02', open=25296.91, close=26071.4, high=26089.85, low=25069.29, volume=26989569.0, amount=57630504816.0, amplitude=4.04, change_pct=3.09, change=781.61, turnover_rate=2.87)
Kline(date='2026-11-03', open=26004.69, close=26262.51, high=26458.25, low=26004.69, volume=23504140.0, amount=49129373892.0, amplitude=1.74, change_pct=0.73, change=191.11, turnover_rate=2.5)
Kline(date='2026-11-04', open=26215.58, close=25992.65, high=26280.32, low=25831.6, volume=24280978.0, amount=49053755462.0, amplitude=1.71, change_pct=-1.03, change=-269.86, turnover_rate=2.58)
```

## 接口示例（`DataFrame`，akshare 风格中文列名）

```python
from em import df_board_kline_em
from em.domain.queries import BoardKlineQuery

df = df_board_kline_em(BoardKlineQuery(board="BK0438", beg="20261102", end="20261104"))
```

## 数据示例（`DataFrame`）

```
           日期        开盘        收盘        最高        最低         成交量           成交额    振幅   涨跌幅     涨跌额   换手率
0  2026-11-02  25296.91  26071.40  26089.85  25069.29  26989569.0  5.763050e+10  4.04  3.09  781.61  2.87
1  2026-11-03  26004.69  26262.51  26458.25  26004.69  23504140.0  4.912937e+10  1.74  0.73  191.11  2.50
2  2026-11-04  26215.58  25992.65  26280.32  25831.60  24280978.0  4.905376e+10  1.71 -1.03 -269.86  2.58
```

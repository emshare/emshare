# 板块（行业 / 概念 / 地域）历史资金流接口

> 渠道：[eastmoney](./eastmoney.md) ｜ 源码：`src/em/channels/eastmoney/board_fund_flow/board_fund_flow_em.py`

## 接口名称

`fetch_board_fund_flow` / `fetch_board_fund_flow_df`：板块历史资金流（`fflow/daykline`，日线）

## 目标地址

- <https://data.eastmoney.com/bkzj/BK0438.html>

## 描述

按板块代码抓取历史资金流日线，返回日期，以及主力 / 小单 / 中单 / 大单 / 超大单的净流入净额与净占比。板块（行业 / 概念 / 地域）与个股共用同一上游端点 `push2his` 的 `fflow/daykline`，参数仅 `secid` 不同：板块统一用 `90.` 前缀（如 `90.BK0438`），走 `push2his` 历史主机，固定 `klt=101`（日线）、`lmt=0`（取全部）。金额**不做** 100 倍放大还原，映射层直接按原值读取。上游字段顺序为 `f51`–`f65`：日期、主力净额、小单净额、中单净额、大单净额、超大单净额、主力占比、小单占比、中单占比、大单占比、超大单占比、收盘价、涨跌幅、…；板块口径只取前 11 个（`f51`–`f61`），`f62`/`f63`（板块指数点位 / 涨跌幅）东财页面与 akshare `stock_sector_fund_flow_hist` 均不展示，映射层忽略。主力净流入 = 大单净流入 + 超大单净流入（上游 `f52 = f55 + f56`）。

## 限量

- 单次返回全部历史资金流（`lmt=0`，如板块 BK0438 共 120 条）。
- 上游对境外 IP 封禁 / 限流，需经国内动态代理访问；本接口已内置代理池 + 自动换 IP 重试。
- 净额单位为元，占比单位为 %。

## 输入参数 `BoardFundFlowQuery`

| 名称 | 类型 | 必填 | 默认值 | 描述 |
| --- | --- | --- | --- | --- |
| `board` | `str` | 否 | `"BK0438"` | 板块代码，如 `BK0438` 食品饮料 |

## 输出参数 `BoardFundFlowSeries`

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `code` | `str` | — | 板块代码 |
| `name` | `str` | — | 板块名称 |
| `items` | `tuple[BoardFundFlow, ...]` | — | 资金流序列，按日期升序 |

`BoardFundFlow` 字段（11 个，不含收盘价 / 涨跌幅）：

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `date` | `str` | — | 交易日期 `YYYY-MM-DD` |
| `main_net_inflow` | `float \| None` | 元 | 主力净流入-净额（`f52 = 大单 + 超大单`） |
| `small_net_inflow` | `float \| None` | 元 | 小单净流入-净额（`f53`） |
| `medium_net_inflow` | `float \| None` | 元 | 中单净流入-净额（`f54`） |
| `large_net_inflow` | `float \| None` | 元 | 大单净流入-净额（`f55`） |
| `xlarge_net_inflow` | `float \| None` | 元 | 超大单净流入-净额（`f56`） |
| `main_net_pct` | `float \| None` | % | 主力净流入-净占比（`f57`） |
| `small_net_pct` | `float \| None` | % | 小单净流入-净占比（`f58`） |
| `medium_net_pct` | `float \| None` | % | 中单净流入-净占比（`f59`） |
| `large_net_pct` | `float \| None` | % | 大单净流入-净占比（`f60`） |
| `xlarge_net_pct` | `float \| None` | % | 超大单净流入-净占比（`f61`） |

## 接口示例（领域模型 `BoardFundFlowSeries`）

```python
from em import fetch_board_fund_flow
from em.domain.queries import BoardFundFlowQuery

series = fetch_board_fund_flow(BoardFundFlowQuery(board="BK0438"))
print(series.code, series.name, len(series.items))
for f in series.items[-3:]:
    print(f.date, f.main_net_inflow, f.main_net_pct)
```

## 数据示例（领域模型）

```
code=BK0438 name=食品饮料 共 120 条，前 3 条：
BoardFundFlow(date='2026-04-09', main_net_inflow=-1435059744.0, small_net_inflow=890112768.0, medium_net_inflow=525396736.0, large_net_inflow=-877367504.0, xlarge_net_inflow=-557692240.0, main_net_pct=-6.8, small_net_pct=4.21, medium_net_pct=2.49, large_net_pct=-4.15, xlarge_net_pct=-2.64)
BoardFundFlow(date='2026-04-10', main_net_inflow=-22437264.0, small_net_inflow=294418432.0, medium_net_inflow=-250164224.0, large_net_inflow=-64300288.0, xlarge_net_inflow=41863024.0, main_net_pct=-0.1, small_net_pct=1.28, medium_net_pct=-1.09, large_net_pct=-0.28, xlarge_net_pct=0.18)
BoardFundFlow(date='2026-04-13', main_net_inflow=-684540208.0, small_net_inflow=480337152.0, medium_net_inflow=191266560.0, large_net_inflow=-510654208.0, xlarge_net_inflow=-173886000.0, main_net_pct=-3.01, small_net_pct=2.11, medium_net_pct=0.84, large_net_pct=-2.24, xlarge_net_pct=-0.76)
```

## 接口示例（`DataFrame`，akshare 风格中文列名）

```python
from em import fetch_board_fund_flow_df
from em.domain.queries import BoardFundFlowQuery

df = fetch_board_fund_flow_df(BoardFundFlowQuery(board="BK0438"))
```

## 数据示例（`DataFrame`）

```
           日期    主力净流入-净额  主力净流入-净占比   超大单净流入-净额  超大单净流入-净占比   大单净流入-净额  大单净流入-净占比   中单净流入-净额  中单净流入-净占比   小单净流入-净额  小单净流入-净占比
0  2026-04-09 -1435059744.0       -6.80    -557692240.0        -2.64   -877367504.0       -4.15    525396736.0        2.49    890112768.0        4.21
1  2026-04-10   -22437264.0       -0.10      41863024.0         0.18    -64300288.0       -0.28   -250164224.0       -1.09    294418432.0        1.28
2  2026-04-13  -684540208.0       -3.01    -173886000.0        -0.76   -510654208.0       -2.24    191266560.0        0.84    480337152.0        2.11
```
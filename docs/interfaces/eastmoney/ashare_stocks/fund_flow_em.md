# 个股历史资金流接口

> 渠道：[eastmoney](../eastmoney.md) ｜ 源码：`src/em/channels/eastmoney/ashare_stocks/fund_flow/fund_flow_em.py`

## 接口名称

`fetch_fund_flow` / `fetch_fund_flow_df`：个股历史资金流（`fflow/daykline`，日线）

## 目标地址

- <https://data.eastmoney.com/zjlx/000001.html>

## 描述

按证券代码抓取历史资金流日线，返回日期、收盘价、涨跌幅，以及主力 / 小单 / 中单 / 大单 / 超大单的净流入净额与净占比。走 `push2his` 历史主机，固定 `klt=101`（日线）、`lmt=0`（取全部）。与 `clist` 接口不同，资金流金额**不做** 100 倍放大还原，映射层直接按原值读取。上游字段顺序为 `f51`–`f63`：日期、主力净额、小单净额、中单净额、大单净额、超大单净额、主力占比、小单占比、中单占比、大单占比、超大单占比、收盘价、涨跌幅；`f64`/`f65` 语义未确认，映射层忽略。主力净流入 = 大单净流入 + 超大单净流入（上游 `f52 = f55 + f56`）。

## 限量

- 单次返回全部历史资金流（`lmt=0`，如平安银行共 120 条）。
- 上游对境外 IP 封禁 / 限流，需经国内动态代理访问；本接口已内置代理池 + 自动换 IP 重试。
- 净额单位为元，占比单位为 %，价格单位为元。

## 输入参数 `FundFlowQuery`

| 名称 | 类型 | 必填 | 默认值 | 描述 |
| --- | --- | --- | --- | --- |
| `code` | `str` | 否 | `"000001"` | 证券代码，如 `000001` |
| `market` | `str` | 否 | `"sz"` | 市场：`sz` 深市 / `sh` 沪市 / `bj` 北交所，未知回退 `sz` |

## 输出参数 `FundFlowSeries`

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `code` | `str` | — | 证券代码 |
| `name` | `str` | — | 证券简称 |
| `market` | `str` | — | 实际生效市场（规范化后） |
| `items` | `tuple[FundFlow, ...]` | — | 资金流序列，按日期升序 |

`FundFlow` 字段：

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
| `close` | `float \| None` | 元 | 收盘价（`f62`） |
| `change_pct` | `float \| None` | % | 涨跌幅（`f63`） |

## 接口示例（领域模型 `FundFlowSeries`）

```python
from em import fetch_fund_flow
from em.domain.queries import FundFlowQuery

series = fetch_fund_flow(FundFlowQuery(code="000001", market="sz"))
print(series.code, series.name, series.market, len(series.items))
for f in series.items[-3:]:
    print(f.date, f.main_net_inflow, f.main_net_pct, f.close)
```

## 数据示例（领域模型）

```
code=000001 name=平安银行 market=sz 共 120 条，末 3 条：
FundFlow(date='2026-09-28', main_net_inflow=-31666602.0, small_net_inflow=11438227.0, medium_net_inflow=20228375.0, large_net_inflow=16474822.0, xlarge_net_inflow=-48141424.0, main_net_pct=-3.91, small_net_pct=1.41, medium_net_pct=2.5, large_net_pct=2.03, xlarge_net_pct=-5.94, close=11.3, change_pct=0.0)
FundFlow(date='2026-09-29', main_net_inflow=-43303644.0, small_net_inflow=3643147.0, medium_net_inflow=39660497.0, large_net_inflow=17593356.0, xlarge_net_inflow=-60897000.0, main_net_pct=-5.52, small_net_pct=0.46, medium_net_pct=5.05, large_net_pct=2.24, xlarge_net_pct=-7.76, close=11.35, change_pct=0.44)
FundFlow(date='2026-09-30', main_net_inflow=125061199.0, small_net_inflow=-71487229.0, medium_net_inflow=-53573968.0, large_net_inflow=151634160.0, xlarge_net_inflow=-26572961.0, main_net_pct=10.37, small_net_pct=-5.93, medium_net_pct=-4.44, large_net_pct=12.58, xlarge_net_pct=-2.2, close=11.57, change_pct=1.94)
```

## 接口示例（`DataFrame`，akshare 风格中文列名）

```python
from em import fetch_fund_flow_df
from em.domain.queries import FundFlowQuery

df = fetch_fund_flow_df(FundFlowQuery(code="000001", market="sz"))
```

## 数据示例（`DataFrame`）

```
           日期   收盘价   涨跌幅  主力净流入-净额  主力净流入-净占比  超大单净流入-净额  超大单净流入-净占比  大单净流入-净额  大单净流入-净占比  中单净流入-净额  中单净流入-净占比  小单净流入-净额  小单净流入-净占比
0  2026-09-28  11.30  0.00  -31666602.0       -3.91    -48141424.0        -5.94   16474822.0        2.03   20228375.0        2.50   11438227.0        1.41
1  2026-09-29  11.35  0.44  -43303644.0       -5.52    -60897000.0        -7.76   17593356.0        2.24   39660497.0        5.05    3643147.0        0.46
2  2026-09-30  11.57  1.94  125061199.0       10.37    -26572961.0        -2.20  151634160.0       12.58  -53573968.0       -4.44  -71487229.0       -5.93
```
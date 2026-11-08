# 个股基本信息接口

> 渠道：[eastmoney](../eastmoney.md) ｜ 源码：`src/em/channels/eastmoney/ashare_stocks/stock_info/stock_info_em.py`

## 接口名称

`stock_info_em` / `df_stock_info_em`：个股基本信息（行业 / 上市时间 / 股本 / 市值 / 最新价）

## 目标地址

- <https://quote.eastmoney.com/concept/sh603777.html?from=classic>

## 描述

按代码与市场查询单只股票的基本信息，对应 akshare `stock_individual_info_em` 的 9 项（股票代码、股票简称、总股本、流通股、行业、总市值、流通市值、上市时间、最新），另加 `market`。走 `pushguest` 游客主机的 `stock/get`，显式指定字段集 `f57,f58,f59,f43,f84,f85,f116,f117,f127,f189`。

- 最新价按 `10 ** f59` 还原（A 股 `f59=2`）；股本单位为股、市值单位为元，均为原值。
- 上市日期 `20010827` → `2001-08-27`。
- akshare 按代码首位是否为 `6` 判断沪深；本接口与 K 线等接口一致，显式传 `market`，北交所用 `bj`。

## 查无此券

不存在的代码上游返回 `rc=100`（代码含非数字时 `rc=102`），`data` 为 `null`。这是正常协议，不是代理劫持页：本接口在传输层放行这两种情况，随后抛出 `SecurityNotFoundError`，**不换 IP 重试**。若按通用的 `rc != 0` 处理，会把好 IP 拉黑、重试到耗尽才报错。实测查 999999 在 0.03 秒内直接报“证券不存在”。`SecurityNotFoundError` 不是渠道异常，CLI 显示“抓取失败”且不给 IP 封禁提示。

## 限量

- 单次只查一只股票；`market` 支持 `sz` / `sh` / `bj`，未知回退 `sz`。CLI 对 `stockinfo` 预设传 `csi` / `hk` 会直接报错。
- 上游对境外 IP 封禁 / 限流，需经国内动态代理访问；本接口已内置代理池 + 自动换 IP 重试。

## 输入参数 `StockInfoQuery`

| 名称 | 类型 | 必填 | 默认值 | 描述 |
| --- | --- | --- | --- | --- |
| `code` | `str` | 否 | `"000001"` | 股票代码 |
| `market` | `str` | 否 | `"sz"` | 市场：`sz` 深市 / `sh` 沪市 / `bj` 北交所，未知回退 `sz` |

## 输出参数 `StockInfo`

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `code` | `str` | — | 股票代码（`f57`） |
| `name` | `str` | — | 股票简称（`f58`） |
| `market` | `str \| None` | — | 市场（规范化后的查询值） |
| `industry` | `str \| None` | — | 所属行业（`f127`） |
| `listing_date` | `str \| None` | — | 上市日期 `YYYY-MM-DD`（`f189`） |
| `price` | `float \| None` | 元 | 最新价（`f43`） |
| `total_shares` | `float \| None` | 股 | 总股本（`f84`） |
| `float_shares` | `float \| None` | 股 | 流通股（`f85`） |
| `total_market_cap` | `float \| None` | 元 | 总市值（`f116`） |
| `float_market_cap` | `float \| None` | 元 | 流通市值（`f117`） |

## 接口示例

```python
from em import stock_info_em, df_stock_info_em
from em.domain.queries import StockInfoQuery

info = stock_info_em(StockInfoQuery(code="600519", market="sh"))
print(info.name, info.industry, info.listing_date, info.total_market_cap)
df = df_stock_info_em(StockInfoQuery(code="920085", market="bj"))  # item / value 纵表
```

## 数据示例

```
StockInfo(code='600519', name='贵州茅台', market='sh', industry='白酒Ⅱ', listing_date='2001-08-27', price=1453.0, total_shares=1250081601.0, float_shares=1250081601.0, total_market_cap=1816368566253.0, float_market_cap=1816368566253.0)

   item         value
0  股票代码        920085
1  股票简称           N森峰
2    市场            bj
3    最新         39.25
4   总股本    76000000.0
5   流通股    18623829.0
6   总市值  2983000000.0
7  流通市值  730985288.25
8    行业         自动化设备
9  上市时间    2026-11-06
```

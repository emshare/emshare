# 沪深京 A 股全市场列表接口

> 渠道：[eastmoney](../eastmoney.md) ｜ 源码：`src/em/channels/eastmoney/ashare_stocks/stock_list/stock_list_em.py`

## 接口名称

`stock_list_em` / `df_stock_list_em`：沪深京 A 股全市场列表（游客接口，不含资金流）

## 目标地址

- <https://quote.eastmoney.com/center/gridlist.html#hs_a_board>

## 描述

抓取沪深京三市全 A 股列表（沪市主板 / 沪市 B 股剔除 / 深市主板 / 深市创业板 / 北交所），返回最新价、涨跌幅、涨跌额、成交额、换手率。走 `pushguest` 游客主机，无需登录。`main_net_inflow` 恒为 `None`（全市场接口不返回资金流字段）。

## 限量

- 单页最多 50 条，全量约 5500+ 条需翻页。
- 上游对境外 IP 封禁，需经国内动态代理访问；本接口已内置代理池 + 自动换 IP 重试。
- `sort` 为上游排序字段名（如 `f3` 涨跌幅、`f6` 成交额），传非法值上游按默认排序。

## 输入参数 `MarketQuery`

| 名称 | 类型 | 必填 | 默认值 | 描述 |
| --- | --- | --- | --- | --- |
| `sort` | `str` | 否 | `"f3"` | 排序字段（上游 `f*` 字段名） |
| `page` | `int` | 否 | `1` | 页码，从 1 起 |
| `size` | `int` | 否 | `20` | 每页条数，上游上限 50 |

## 输出参数 `QuotePage`

同 `board_constituent_em`，但 `main_net_inflow` 恒为 `None`。

## 接口示例（领域模型 `QuotePage`）

```python
from em import stock_list_em
from em.domain.queries import MarketQuery

page = stock_list_em(MarketQuery(sort="f3", size=3))
print(page.total)
for q in page.items:
    print(q.code, q.name, q.price, q.change_pct)
```

## 数据示例（领域模型）

```
total: 5579
Quote(code='001246', name='N力勤', price=65.09, change_pct=206.59, change=43.86, main_net_inflow=None, turnover=8345390508.96, turnover_rate=74.93)
Quote(code='301190', name='善水科技', price=35.93, change_pct=20.01, change=5.99, main_net_inflow=None, turnover=510373313.64, turnover_rate=7.95)
Quote(code='688185', name='康希诺', price=102.64, change_pct=20.0, change=17.11, main_net_inflow=None, turnover=1065144349.0, turnover_rate=9.32)
```

## 接口示例（`DataFrame`，主力净流入列恒为 `None`）

```python
from em import df_stock_list_em
from em.domain.queries import MarketQuery

df = df_stock_list_em(MarketQuery(sort="f3", size=3))
```

## 数据示例（`DataFrame`）

```
       代码    名称     最新价     涨跌幅    涨跌额 主力净流入           成交额    换手率
0  001246   N力勤   65.09  206.59  43.86  None  8.345391e+09  74.93
1  301190  善水科技   35.93   20.01   5.99  None  5.103733e+08   7.95
2  688185   康希诺  102.64   20.00  17.11  None  1.065144e+09   9.32
```
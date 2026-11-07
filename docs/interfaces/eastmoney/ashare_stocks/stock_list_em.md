# 沪深京 A 股全市场列表接口

> 渠道：[eastmoney](../eastmoney.md) ｜ 源码：`src/em/channels/eastmoney/ashare_stocks/stock_list/stock_list_em.py`

## 接口名称

`stock_list_em` / `df_stock_list_em`：沪深京 A 股全市场列表（游客接口，不含资金流，可按市场 / 板块筛选）

## 目标地址

- <https://quote.eastmoney.com/center/gridlist.html#hs_a_board>

## 描述

抓取沪深京三市全 A 股列表（沪市主板 / 沪市 B 股剔除 / 深市主板 / 深市创业板 / 北交所），返回最新价、涨跌幅、涨跌额、成交额、换手率。走 `pushguest` 游客主机，无需登录。`main_net_inflow` 恒为 `None`（全市场接口不返回资金流字段）。

`scope` 用上游 `fs` 筛选范围，对应 akshare `stock_zh_a_spot_em` / `stock_sh_a_spot_em` / `stock_sz_a_spot_em` / `stock_bj_a_spot_em` / `stock_kc_a_spot_em` / `stock_cy_a_spot_em` / `stock_new_a_spot_em` / `stock_zh_a_st_em`：

| `scope` | 范围 | 上游 `fs` | 实测 total（2026-11-06） |
| --- | --- | --- | --- |
| `all` | 沪深京全部 A 股（默认） | `m:0+t:6+f:!2,m:0+t:80+f:!2,m:1+t:2+f:!2,m:1+t:23+f:!2,m:0+t:81+s:262144+f:!2` | 5581 |
| `sh` | 沪市（主板 + 科创板） | `m:1+t:2+f:!2,m:1+t:23+f:!2` | 2319 |
| `sz` | 深市（主板 + 创业板） | `m:0+t:6+f:!2,m:0+t:80+f:!2` | 2906 |
| `bj` | 北交所 | `m:0+t:81+s:262144+f:!2` | 356 |
| `kc` | 科创板 | `m:1+t:23+f:!2` | 619 |
| `cy` | 创业板 | `m:0+t:80+f:!2` | 1411 |
| `new` | 新股 | A 股各段 `+f:8`（`m:0+t:6+f:8,…,m:0+t:81+s:262144+f:8`） | 83 |
| `st` | 风险警示 | A 股各段 `+f:4`（`m:0+t:6+f:4,…,m:0+t:81+s:262144+f:4`） | 197 |

- `sh` + `sz` + `bj` 的分段拼起来正好是 `all`，三者 total 之和也等于 `all`；其余范围都是 `all` 的子集。
- `bj` 沿用全量口径的 `s:262144`；akshare 用 `s:2048`，实测多 8 条（364）。
- `new` / `st` 是在 A 股各段上加标志筛选，不带 `f:!2`：实测标志与 `f:!2` 叠加会让筛选失效（返回 5.8 万条）。
- `st` 与 akshare `stock_zh_a_st_em` 口径不同：akshare 用 `m:0+f:4,m:1+f:4`，实测 386 条，混入了 B 股（如 900915 ST中路B）和三板代码（如 873841、831516）；本接口按 A 股各段限定，只留 197 条 A 股。
- `new` 与 akshare 结果一致（83 条）；上游没有给北交所新股打 `f:8` 标志，所以不含北交所新股（如 920085 N森峰）。

## 限量

- 单页最多 50 条，全量约 5500+ 条需翻页（`stock_list_all_em` 并发翻页，同样支持 `scope`）。
- 上游对境外 IP 封禁，需经国内动态代理访问；本接口已内置代理池 + 自动换 IP 重试。
- `sort` 为上游排序字段名（如 `f3` 涨跌幅、`f6` 成交额），传非法值上游按默认排序。
- `scope` 传未知值时回退 `all`。

## 输入参数 `MarketQuery`

| 名称 | 类型 | 必填 | 默认值 | 描述 |
| --- | --- | --- | --- | --- |
| `sort` | `str` | 否 | `"f3"` | 排序字段（上游 `f*` 字段名） |
| `page` | `int` | 否 | `1` | 页码，从 1 起 |
| `size` | `int` | 否 | `20` | 每页条数，上游上限 50 |
| `scope` | `str` | 否 | `"all"` | 范围：`all` / `sh` / `sz` / `bj` / `kc` / `cy` / `new` / `st`，见上表，未知回退 `all` |

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

kc = stock_list_em(MarketQuery(scope="kc", size=3))  # 只看科创板
```

## 数据示例（领域模型）

```
total: 5579
Quote(code='001246', name='N力勤', price=65.09, change_pct=206.59, change=43.86, main_net_inflow=None, turnover=8345390508.96, turnover_rate=74.93)
Quote(code='301190', name='善水科技', price=35.93, change_pct=20.01, change=5.99, main_net_inflow=None, turnover=510373313.64, turnover_rate=7.95)
Quote(code='688185', name='康希诺', price=102.64, change_pct=20.0, change=17.11, main_net_inflow=None, turnover=1065144349.0, turnover_rate=9.32)
```

`scope="kc"`（2026-11-06）：

```
total: 619
Quote(code='688429', name='时创能源', price=12.36, change_pct=15.62, change=1.67, main_net_inflow=None, turnover=188398544.0, turnover_rate=4.02)
Quote(code='688203', name='海正生材', price=15.69, change_pct=10.65, change=1.51, main_net_inflow=None, turnover=350046970.0, turnover_rate=11.2)
Quote(code='688228', name='开普云', price=78.19, change_pct=8.01, change=5.8, main_net_inflow=None, turnover=381186228.0, turnover_rate=7.5)
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
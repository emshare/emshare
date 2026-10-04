# 板块成分股资金流接口

> 渠道：[eastmoney](./eastmoney.md) ｜ 源码：`src/em/channels/eastmoney/board_constituent/board_constituent_em.py`

## 接口名称

`fetch_board` / `fetch_board_df`：板块成分股（含主力净流入，可按当日 / 5 日 / 10 日资金流排序）

## 目标地址

- <https://quote.eastmoney.com/center/gridlist.html#industry_board_1>

## 描述

按板块代码抓取成分股列表，返回最新价、涨跌幅、涨跌额、主力净流入（按所选周期）、成交额、换手率。`period` 决定排序字段与 `main_net_inflow` 取值周期：`day`→`f62`（当日）、`5d`→`f164`（5 日）、`10d`→`f174`（10 日）。价格 / 涨跌幅 / 换手率在上游为放大 100 倍的整数（`fltt=1`），映射层已还原为浮点。

## 限量

- 单页最多 50 条（上游 `pz` 上限），全量需翻页。
- 上游对境外 IP 封禁，需经国内动态代理访问；本接口已内置代理池 + 自动换 IP 重试。
- 主力净流入单位为元，数值可能为负（净流出）。

## 输入参数 `BoardQuery`

| 名称 | 类型 | 必填 | 默认值 | 描述 |
| --- | --- | --- | --- | --- |
| `board` | `str` | 否 | `"BK0438"` | 板块代码（如 `BK0438` 白酒） |
| `period` | `str` | 否 | `"10d"` | 资金流周期：`day` / `5d` / `10d`，未知值回退 `10d` |
| `page` | `int` | 否 | `1` | 页码，从 1 起 |
| `size` | `int` | 否 | `8` | 每页条数，上游上限 50 |

## 输出参数 `QuotePage`

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `total` | `int` | — | 全量条数 |
| `items` | `tuple[Quote, ...]` | — | 本页记录 |

`Quote` 字段：

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `code` | `str` | — | 证券代码 |
| `name` | `str` | — | 证券简称 |
| `price` | `float \| None` | 元 | 最新价 |
| `change_pct` | `float \| None` | % | 涨跌幅 |
| `change` | `float \| None` | 元 | 涨跌额 |
| `main_net_inflow` | `float \| None` | 元 | 主力净流入（按 `period` 周期） |
| `turnover` | `float \| None` | 元 | 成交额 |
| `turnover_rate` | `float \| None` | % | 换手率 |

## 接口示例（领域模型 `QuotePage`）

```python
from em import fetch_board
from em.domain.queries import BoardQuery

page = fetch_board(BoardQuery(board="BK0438", period="10d", size=3))
print(page.total)
for q in page.items:
    print(q.code, q.name, q.price, q.main_net_inflow)
```

## 数据示例（领域模型）

```
total: 131
Quote(code='600887', name='伊利股份', price=27.3, change_pct=0.22, change=0.06, main_net_inflow=695959104.0, turnover=827638790.0, turnover_rate=0.48)
Quote(code='600059', name='古越龙山', price=12.27, change_pct=10.04, change=1.12, main_net_inflow=611398864.0, turnover=1093331572.0, turnover_rate=9.87)
Quote(code='000895', name='双汇发展', price=23.66, change_pct=1.07, change=0.25, main_net_inflow=165793489.0, turnover=168466694.07, turnover_rate=0.21)
```

## 接口示例（`DataFrame`，akshare 风格中文列名）

```python
from em import fetch_board_df
from em.domain.queries import BoardQuery

df = fetch_board_df(BoardQuery(board="BK0438", period="10d", size=3))
```

## 数据示例（`DataFrame`）

```
       代码    名称    最新价    涨跌幅   涨跌额        主力净流入           成交额   换手率
0  600887  伊利股份  27.30   0.22  0.06  695959104.0  8.276388e+08  0.48
1  600059  古越龙山  12.27  10.04  1.12  611398864.0  1.093332e+09  9.87
2  000895  双汇发展  23.66   1.07  0.25  165793489.0  1.684667e+08  0.21
```
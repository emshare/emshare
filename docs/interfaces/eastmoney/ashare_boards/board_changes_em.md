# 板块异动接口

> 渠道：[eastmoney](../eastmoney.md) ｜ 源码：`src/em/channels/eastmoney/ashare_boards/board_changes/board_changes_em.py`

## 接口名称

`board_changes_em` / `df_board_changes_em`：板块异动（当日有异动的板块：异动总次数、异动最频繁个股、各类异动次数、主力净流入）

## 目标地址

- <https://quote.eastmoney.com/changes/>（当日异动板块监控）
- <https://quote.eastmoney.com/changes/boardlist.html>

## 描述

一次取回最近一个交易日全部有异动的板块（行业 / 概念 / 地域等，2026-11-06 共 1052 个），按异动总次数倒序；每个板块的各类异动次数也按次数倒序。走 `push2ex` 主机的 `getAllBKChanges`（与盘口异动、涨跌停股池同主机、同 `ut`），响应同为 `rc=0` 的 JSON，传输层协议校验无需特判。对应 akshare `stock_board_change_em`，无参数。

## 数据范围（实测）

- **只有最近一个交易日。** 上游 `dt` 是数据时间（`20261106150000`），本接口拆成 `date` / `time` 放在 `BoardChangesPage`。2026-11-08（周日）实测返回 `2026-11-06 15:00:00`。
- **一次取全量**：上游不限 `pagesize`，本接口与盘口异动同取 50000。响应体约 435KB，与全量 K 线同量级，读预算与 K 线相同。

## 字段处理

- **主力净流入 `zjl` 单位是万元**（东财页面表头即“主力净流入(万元)”），本接口乘以 10000 换算成元。实测 BK1036 / BK0477 / BK0596 三个板块与 `board_fund_flow_em` 当日主力净额的比值都正好是 10000。akshare 原样输出万元。
- 涨跌幅 `u` 是字符串（`"-1.99"`），单位 %，转成 float。
- **异动最频繁个股 `ms`**：`c` 代码、`n` 名称、`m` 市场前缀、`t` 该股所属异动类型。`m` 为 1 是 `sh`，为 0 是 `sz`；北交所按代码段识别为 `bj`。
- **东财未公开的 6 种类型（8217–8222）**：上游的各类异动次数 `ydl` 与最频繁个股的类型里都会出现，但东财页面与 akshare 都没有名字，页面直接过滤掉。11-06 实测：
  - 未公开类型占全部异动次数的 23.4%；
  - 1052 个板块中有 174 个的最频繁个股是未公开类型，`top_stock_change_type` 为 `None`；
  - 10 个板块只有未公开类型的异动，`type_counts` 为空（东财页面把这些板块整行隐藏，本接口保留，`total` 与条数一致）。
- `change_count` 是上游 `ct` 原值，等于全部类型（含未公开）次数之和；`type_counts` 只列 22 种已知类型，所以两者之和可能对不上。

## 与 akshare 的差异

- **akshare 的“买卖方向”列是错的**：它把 `ms.m`（市场前缀）当成买卖方向（0 大笔买入 / 1 大笔卖出）。如 BK0596 的最频繁个股 N森峰 实际类型是大笔卖出（`t=8194`），akshare 因 `m=0` 显示成“大笔买入”。本接口改为输出该股的异动类型与市场。
- akshare 主力净流入是万元，本接口是元。
- akshare 不输出板块代码；本接口保留 `code`，可直接传给 `board_kline_em` / `board_fund_flow_em` 等板块接口。
- akshare 的“板块具体异动类型列表及出现次数”是上游原始的 `[{'t': 8202, 'ct': 1903}, ...]`；本接口领域模型为 `ChangeTypeCount`（英文类型），DataFrame 为 `{中文类型: 次数}` 字典。

## 输入参数 `BoardChangesQuery`

无参数（上游没有可选参数，保留查询句柄是为了与其他 `*_em(query, settings)` 签名一致）。

## 输出参数 `BoardChangesPage`

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `date` | `str` | — | 数据日期 `YYYY-MM-DD`（`dt`） |
| `time` | `str` | — | 数据时间 `HH:MM:SS`（`dt`） |
| `total` | `int` | — | 有异动的板块数（`tc`） |
| `items` | `tuple[BoardChange, ...]` | — | 全部板块，按异动总次数倒序 |

`BoardChange` 字段：

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `code` | `str` | — | 板块代码（`c`） |
| `name` | `str` | — | 板块名称（`n`） |
| `change_pct` | `float \| None` | % | 板块涨跌幅（`u`） |
| `main_net_inflow` | `float \| None` | 元 | 主力净流入（`zjl` × 10000） |
| `change_count` | `int \| None` | 次 | 板块异动总次数（`ct`，含未公开类型） |
| `top_stock_code` | `str \| None` | — | 异动最频繁个股：代码（`ms.c`） |
| `top_stock_name` | `str \| None` | — | 异动最频繁个股：名称（`ms.n`） |
| `top_stock_market` | `str \| None` | — | 异动最频繁个股：`sh` / `sz` / `bj`（`ms.m`） |
| `top_stock_change_type` | `str \| None` | — | 异动最频繁个股：所属异动类型（`ms.t`，未公开类型为 `None`） |
| `type_counts` | `tuple[ChangeTypeCount, ...]` | — | 各类异动次数（`ydl`），只含 22 种已知类型，按次数倒序 |

`ChangeTypeCount` 字段：`change_type`（`str`，英文类型，取值见 [stock_changes_em.md](../ashare_stocks/stock_changes_em.md)）、`count`（`int`，次数）。

## DataFrame 列

`df_board_changes_em` 的列为 板块代码 / 板块名称 / 涨跌幅 / 主力净流入 / 板块异动总次数 / 板块异动最频繁个股及所属类型-股票代码 / -股票名称 / -市场 / -异动类型 / 板块具体异动类型列表及出现次数。列名沿用 akshare，“-买卖方向”换成“-市场”与“-异动类型”两列（见上）；最后一列是 `{中文类型: 次数}` 字典，顺序同上游。

## 接口示例（领域模型 `BoardChangesPage`）

```python
from em import board_changes_em

page = board_changes_em()
print(page.date, page.time, page.total)
for b in page.items[:1]:
    print(b)
```

## 数据示例（领域模型）

```
2026-11-06 15:00:00 1052
BoardChange(code='BK0596', name='融资融券', change_pct=-1.99, main_net_inflow=-50364710912.0, change_count=10998, top_stock_code='920085', top_stock_name='N森峰', top_stock_market='bj', top_stock_change_type='big_sell', type_counts=(ChangeTypeCount(change_type='quick_rebound', count=1903), ChangeTypeCount(change_type='open_below_ma5', count=1565), ChangeTypeCount(change_type='big_buy', count=984), ...))
```

## 接口示例（`DataFrame`，akshare 风格中文列名）

```python
from em import df_board_changes_em

df = df_board_changes_em()
```

## 数据示例（`DataFrame`）

```
     板块代码   板块名称   涨跌幅         主力净流入  板块异动总次数 板块异动最频繁个股及所属类型-股票代码 板块异动最频繁个股及所属类型-股票名称 板块异动最频繁个股及所属类型-市场 板块异动最频繁个股及所属类型-异动类型
0  BK0596   融资融券 -1.99 -5.036471e+10    10998              920085                 N森峰                bj                大笔卖出
1  BK0804    深股通 -2.04 -3.034726e+10     5779              301697                 贝特利                sz                大笔买入
2  BK1633  昨日高振幅 -2.73 -1.977184e+10     4962              002086                东方海洋                sz                大笔买入
```

第一行的“板块具体异动类型列表及出现次数”：

```
{'快速反弹': 1903, '低开5日线': 1565, '大笔买入': 984, '大笔卖出': 866, '有大买盘': 619, '高台跳水': 527, '火箭发射': 454, '竞价下跌': 374, '加速下跌': 339, '有大卖盘': 277, '向下缺口': 128, '60日大幅下跌': 113, '60日新高': 95, '60日大幅上涨': 87, '封跌停板': 70, '打开跌停板': 65, '60日新低': 60, '封涨停板': 40, '打开涨停板': 31, '向上缺口': 8, '竞价上涨': 2, '高开5日线': 1}
```

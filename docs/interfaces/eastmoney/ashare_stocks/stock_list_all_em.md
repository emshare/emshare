# 沪深京 A 股全市场快照接口（全量翻页）

> 渠道：[eastmoney](../eastmoney.md) ｜ 源码：`src/em/application/market_data.py`（`stock_list_all_em`）

## 接口名称

`stock_list_all_em` / `df_stock_list_all_em`：沪深京 A 股**全市场快照**——单次调用返回全部约 5580 只，无需调用方翻页。

## 目标地址

- 同 [`stock_list_em`](stock_list_em.md)：`pushguest` 游客 clist 接口

## 描述

在 `stock_list_em` 单页能力之上的应用层组合：首页确定 `total` 后按 5 线程并发翻页拉取全部约 56 页，去重合并。内置多项可靠性机制：

- **固定按代码（f12）排序**：行情字段（f3 等）盘中实时跳动，按其排序会使并发分页跨页大面积重复；代码序几乎不变，1:1 无重复。需要特定行情顺序请取完后在本地排序。
- **定向补漏**：东财多后端节点分页快照不一致表现为"替换型漂移"（相邻页码集合重叠、非末页短页），按可疑页精准重抓，不做整轮全量重试；可疑页清零仍缺码时才做一次全量兜底轮（至多 `max_rounds` 轮）。
- **旧快照定点淘汰**：某页"满页零新增"视为代理节点旧快照，淘汰该出口 IP 后重试，避免同节点反复返回旧数据。
- **输出按代码升序**：并发抓取的合并结果按 `code` 排序，保证调用方拿到稳定顺序。
- **耗时统计日志**：结束时输出直连/代理分桶请求次数与耗时、代理获取等待、失败尝试数（INFO 级，logger `em.application.market_data`）。

链路层能力（动态代理路由、最少在飞 IP 分发、P95 动态读超时、换 IP 重试）见 [overview](../overview.md) 与 `.env.example` 配置说明。

## 限量

- 上游单页 `pz` 上限 100，本接口内部按 100 翻页，调用方无需关心分页。
- 结果以证券代码去重；极端情况下（代理资源枯竭）仍可能缺码，此时输出 WARNING 日志且 `len(items) < total`，调用方可据此校验。
- `workers` 过高易触发代理源限频与上游封禁，默认 5 已实测均衡。

## 输入参数

| 名称 | 类型 | 必填 | 默认值 | 描述 |
| --- | --- | --- | --- | --- |
| `query` | `MarketQuery` | 否 | `None` | 仅 `sort` 被忽略（内部固定 `f12`）；`page`/`size` 亦由内部接管 |
| `settings` | `Settings` | 否 | `None` | 留空从环境变量读取 |
| `max_rounds` | `int` | 否 | `5` | 补漏轮上限（定向重抓轮数） |
| `workers` | `int` | 否 | `5` | 翻页并发线程数（≥1） |

## 输出参数 `QuotePage`

同 [`stock_list_em`](stock_list_em.md)，但 `items` 为全市场并集且按 `code` 升序；`total` 为上游快照总数。

## 接口示例（领域模型 `QuotePage`）

```python
from em import stock_list_all_em

page = stock_list_all_em()          # 默认 5 并发、至多 5 轮补漏
print(page.total, len(page.items))  # 5580 5580
assert [q.code for q in page.items] == sorted(q.code for q in page.items)
```

## 数据示例（领域模型）

```
total: 5580
Quote(code='000001', name='平安银行', price=12.10, change_pct=0.83, change=0.10, main_net_inflow=None, turnover=...)
Quote(code='000002', name='万科A', price=7.85, ...)
...
Quote(code='920000', name='...', ...)   # 末条为北交所（代码升序）
```

## 接口示例（`DataFrame`，主力净流入列恒为 `None`）

```python
from em import df_stock_list_all_em

df = df_stock_list_all_em()
```

## 数据示例（`DataFrame`）

```
       代码    名称     最新价     涨跌幅    涨跌额 主力净流入           成交额    换手率
0  000001  平安银行   12.10    0.83   0.10  None  ...
1  000002   万科A    7.85   -1.13  -0.09  None  ...
...  （全市场 5580 行，按代码升序）
```

## 命令行

```bash
python -m em --preset market-all            # 默认展示末 20 条
python -m em --preset market-all --head 10  # 前 10 条
python -m em --preset market-all --head 5 --tail 5  # 前 5 + 末 5
```

## 实测参考

代理正常时全量拉取约 4~5 秒；代理源质量差的时段约 25~40 秒（失败重试成本），`timing_stats` 与结束日志可定位耗时构成。

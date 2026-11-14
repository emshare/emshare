# 大宗交易活跃营业部统计接口

> 渠道：[eastmoney](../eastmoney.md) ｜ 源码：`src/em/channels/eastmoney/ashare_block_trade/block_trade_branch_active/block_trade_branch_active_em.py`

## 接口名称

`block_trade_branch_active_em` / `df_block_trade_branch_active_em`：大宗交易活跃营业部统计（最近 N 个交易日各营业部的买卖笔数、金额与买入的股票）

## 目标地址

- <https://data.eastmoney.com/dzjy/dzjy_hyyybtj.html>

## 描述

按最近 N 个交易日取各营业部的大宗交易买卖汇总，一家营业部一行：买入 / 卖出笔数与金额、净买入额、买入的股票。对应 akshare `stock_dzjy_hyyybtj`（`RPT_BLOCKTRADE_OPERATEDEPTSTATISTICS`）。走数据中心报表，本接口按每页 500 条自动翻完全部页，返回 `ReportPage`。只请求用得到的列、查无数据返回空结果、查询写错抛 `QueryRejectedError`、翻页条数校验等公共处理见 [billboard_detail_em.md](../ashare_billboard/billboard_detail_em.md)。

## 统计周期

- `period` 取 `1d` / `3d` / `5d` / `10d` / `30d`，即最近 1 / 3 / 5 / 10 / 30 个**交易日**（上游 `N_DATE` 为 0 / -3 / -5 / -10 / -30）。未知值回退 `1d`。默认 `1d`（akshare 默认近 3 日）。
- 实测 2026-11-13：各周期的买卖笔数与每日明细按交易日窗口逐家一致；按自然日窗口算，`10d`、`30d` 对不上。
- **`1d` 用的是上游的“最新”（`N_DATE=0`）**，即最近一个交易日。akshare 的“当前交易日”传 `N_DATE=-1`，实测查不到任何行。
- 当天的数据收盘后陆续入库：实测 2026-11-13 的 `1d`，16:31 是 18 家，当晚再查是 35 家。
- 实测 2026-11-13：`1d` 35 家，`3d` 121 家，`5d` 185 家，`10d` 319 家，`30d` 691 家。

## 字段处理

- **只统计 A 股**：实测 `3d`（当时 113 家）的买卖笔数、金额与每日明细的 A 股部分逐家一致；把基金、债券的成交算进去就对不上。
- **`buy_stocks` / `buy_stock_codes` 确实只含买入的股票**（龙虎榜 `billboard_branch_active_em` 的 `stocks` 则含只卖出的，两者不同）：实测各周期逐家与明细里的买入股票集合一致。只卖出的营业部这两个字段为 `None` / 空元组（实测 2026-11-13 `3d` 的 121 家里 44 家，`30d` 的 691 家里 274 家）。
- 上游 `STOCK_DETAILS` 是逗号分隔的“代码|简称”，拆成简称（空格分隔，写法同龙虎榜）和代码元组，两者一一对应、按代码升序；同一只股票买入多笔只列一次。
- 金额上游给万元，统一成元；`net_buy` = `buy` − `sell`。`buy_times` / `sell_times` 是成交笔数。
- `latest_date` 是周期内该营业部最后一次买入或卖出的交易日。
- `branch_code`：机构专用为 `"0"`，是所有机构席位的合计；与每日明细的买卖方营业部代码、龙虎榜的营业部代码是同一套。
- `branch_name` 是简称（如“平安证券深圳金田路证券营业部”），每日明细里是全称（“平安证券股份有限公司…”）：两边关联请用营业部代码。
- 排序同 akshare：买入笔数、买入金额倒序；只卖出的营业部两项都是 0、大量并列（实测 `30d` 691 家里 288 家），末尾补营业部代码保证翻页顺序稳定。周期内一家营业部一行。

## 输入参数 `BlockTradeBranchActiveQuery`

| 名称 | 类型 | 必填 | 默认值 | 描述 |
| --- | --- | --- | --- | --- |
| `period` | `str` | 否 | `"1d"` | 最近 N 个交易日：1d 最近一个交易日 / 3d / 5d / 10d / 30d，未知回退 1d |

## 输出参数 `ReportPage[BlockTradeBranchActive]`

| 名称 | 类型 | 描述 |
| --- | --- | --- |
| `total` | `int` | 上游报告的条数，通常等于 `len(items)` |
| `items` | `tuple[BlockTradeBranchActive, ...]` | 全部记录，保持上游排序 |

`BlockTradeBranchActive` 字段：

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `branch_code` | `str` | — | 营业部代码（机构专用为 "0"）（`OPERATEDEPT_CODE`） |
| `branch_name` | `str` | — | 营业部名称（`OPERATEDEPT_NAME`） |
| `latest_date` | `str \| None` | — | 最近上榜日 YYYY-MM-DD（周期内最后一次买入或卖出的交易日）（`ONLIST_DATE`） |
| `buy_times` | `int \| None` | 笔 | 买入笔数（`BUYER_NUM`） |
| `sell_times` | `int \| None` | 笔 | 卖出笔数（`SELLER_NUM`） |
| `buy` | `float \| None` | 元 | 买入金额（上游万元，已换算）（`TOTAL_BUYAMT`） |
| `sell` | `float \| None` | 元 | 卖出金额（上游万元，已换算）（`TOTAL_SELLAMT`） |
| `net_buy` | `float \| None` | 元 | 净买入额 = 买入 - 卖出（`TOTAL_NETAMT`） |
| `buy_stocks` | `str \| None` | — | 买入股票的简称，空格分隔；只卖出的营业部为 None（`STOCK_DETAILS`） |
| `buy_stock_codes` | `tuple[str, ...]` | — | 买入股票的代码，与 buy_stocks 一一对应（`STOCK_DETAILS`） |

## DataFrame 列

`df_block_trade_branch_active_em` 的列对齐 akshare `stock_dzjy_hyyybtj`，末尾加“营业部代码”“买入股票代码”。akshare 的“序号”列不输出。列顺序：最近上榜日 / 营业部名称 / 次数总计-买入 / 次数总计-卖出 / 成交金额统计-买入 / 成交金额统计-卖出 / 成交金额统计-净买入额 / 买入的股票 / 营业部代码 / 买入股票代码。

## 接口示例（领域模型）

```python
from em import block_trade_branch_active_em
from em.domain.queries import BlockTradeBranchActiveQuery

page = block_trade_branch_active_em(BlockTradeBranchActiveQuery(period="3d"))
print(page.total)
for item in page.items[:2]:
    print(item)
```

## 数据示例（领域模型）

```
121
BlockTradeBranchActive(branch_code='0', branch_name='机构专用', latest_date='2026-11-13', buy_times=77, sell_times=63, buy=1836215300.0, sell=1341741100.0, net_buy=494474200.0, buy_stocks='潍柴动力 京东方A 云铝股份 紫光股份 悍高集团 银轮股份 蔚蓝锂芯 杰瑞股份 北方华创 东山精密 杭氧股份 兴森科技 荣盛石化 奋达科技 广东宏大 东易日盛 中矿资源 凯莱英 裕同科技 深南电路 鼎龙股份 中际旭创 苏大维格 泰格医药 芒果超媒 江丰电子 宁德时代 康龙化成 石药创新 锦盛新材 江天化学 尤安设计 凯淳股份 信濠光电 力诺药包 贵州茅台 山东黄金 国泰海通 中科曙光 安孚科技 中重科技 景旺电子 药明康德 永杰新材 龙旗科技 瑞芯微 博敏电子 圣泉集团 华依科技 埃夫特 思特威 翱捷科技 寒武纪 奥浦迈 奕瑞科技 日联科技 思瑞浦 芯碁微装 屹唐股份 中控技术 联讯仪器', buy_stock_codes=('000338', '000725', '000807', '000938', '001221', '002126', '002245', '002353', '002371', '002384', '002430', '002436', '002493', '002681', '002683', '002713', '002738', '002821', '002831', '002916', '300054', '300308', '300331', '300347', '300413', '300666', '300750', '300759', '300765', '300849', '300927', '300983', '301001', '301051', '301188', '600519', '600547', '601211', '603019', '603031', '603135', '603228', '603259', '603271', '603341', '603893', '603936', '605589', '688071', '688165', '688213', '688220', '688256', '688293', '688301', '688531', '688536', '688630', '688729', '688777', '688808'))
BlockTradeBranchActive(branch_code='10388201', branch_name='平安证券深圳金田路证券营业部', latest_date='2026-11-13', buy_times=6, sell_times=1, buy=87884700.0, sell=9414700.0, net_buy=78470000.0, buy_stocks='中际旭创 中国化学 仙鹤股份 道通科技', buy_stock_codes=('300308', '601117', '603733', '688208'))
```

## 接口示例（`DataFrame`，akshare 风格中文列名）

```python
from em import df_block_trade_branch_active_em
from em.domain.queries import BlockTradeBranchActiveQuery

df = df_block_trade_branch_active_em(BlockTradeBranchActiveQuery(period="3d"))
```

## 数据示例（`DataFrame`）

```
   最近上榜日                    营业部名称  次数总计-买入  次数总计-卖出  成交金额统计-买入  成交金额统计-卖出  成交金额统计-净买入额                                    买入的股票 营业部代码               买入股票代码
0  2026-11-13                      机构专用             77             63       1.836215e+09       1.341741e+09            494474200.0  潍柴动力 京东方A 云铝股份 紫光股份 悍高集团…          0  ('000338', '000725', '00…
1  2026-11-13  平安证券深圳金田路证券营业部              6              1       8.788470e+07       9.414700e+06             78470000.0           中际旭创 中国化学 仙鹤股份 道通科技   10388201  ('300308', '601117', '60…
2  2026-11-13            中信证券上海分公司              6              0       3.788690e+07       0.000000e+00             37886900.0  兴森科技 长川科技 西部矿业 中科曙光 华友钴业   10135341  ('002436', '300604', '60…
```

示例里的长文本列为便于阅读做了截断（以 `…` 结尾），实际返回完整内容。

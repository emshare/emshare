# eastmoney 渠道接口预览

> 目录结构：[directory_tree.md](./directory_tree.md)

## 行情接口一览表

### `板块成分股`
接口：`board_constituent_em`, `df_board_constituent_em`->（DataFrame版）
描述：板块成分股（含主力净流入，可按当日/5日/10日资金流排序）。

- 详情：[board_constituent_em.md](./ashare_boards/board_constituent_em.md)
- 源码：`src/em/channels/eastmoney/ashare_boards/board_constituent/board_constituent_em.py`


### `沪深京 A 股全市场列表`
接口：`stock_list_em`, `df_stock_list_em`->（DataFrame版）
描述：沪深京 A 股全市场列表（游客接口，不含资金流，`scope` 可筛沪 / 深 / 北 / 科创 / 创业 / 新股 / ST）。

- 详情：[stock_list_em.md](./ashare_stocks/stock_list_em.md)
- 源码：`src/em/channels/eastmoney/ashare_stocks/stock_list/stock_list_em.py`


### `历史 K 线`
接口：`stock_kline_em`, `df_stock_kline_em`->（DataFrame版）
描述：个股 / 指数 / 基金 / 港股历史 K 线（日 / 周 / 月 / 5分 / 15分 / 30分 / 60分，前 / 后 / 不复权；`market` 支持 sz / sh / bj / csi / hk）。

- 详情：[stock_kline_em.md](./ashare_stocks/stock_kline_em.md)
- 源码：`src/em/channels/eastmoney/ashare_stocks/stock_kline/stock_kline_em.py`


### `分时行情`
接口：`stock_trends_em`, `df_stock_trends_em`->（DataFrame版）
描述：个股 / 指数分时行情（trends2，ndays 日分时）。

- 详情：[stock_trends_em.md](./ashare_stocks/stock_trends_em.md)
- 源码：`src/em/channels/eastmoney/ashare_stocks/stock_trends/stock_trends_em.py`


### `个股历史资金流`
接口：`stock_fund_flow_em`, `df_stock_fund_flow_em`->（DataFrame版）
描述：个股历史资金流（fflow/daykline，日线，主力/超大单/大单/中单/小单净流入）。

- 详情：[stock_fund_flow_em.md](./ashare_stocks/stock_fund_flow_em.md)
- 源码：`src/em/channels/eastmoney/ashare_stocks/stock_fund_flow/stock_fund_flow_em.py`


### `板块（行业 / 概念 / 地域）历史资金流`
接口：`board_fund_flow_em`, `df_board_fund_flow_em`->（DataFrame版）
描述：板块历史资金流（fflow/daykline，日线，secid 前缀 90，主力/超大单/大单/中单/小单净流入，不含收盘价/涨跌幅）。

- 详情：[board_fund_flow_em.md](./ashare_boards/board_fund_flow_em.md)
- 源码：`src/em/channels/eastmoney/ashare_boards/board_fund_flow/board_fund_flow_em.py`


### `板块（行业 / 概念 / 地域）历史 K 线`
接口：`board_kline_em`, `df_board_kline_em`->（DataFrame版）
描述：板块历史 K 线（push2his kline，secid 前缀 90，日 / 周 / 月 / 5分 / 15分 / 30分 / 60分，价格为指数点位，不复权）。

- 详情：[board_kline_em.md](./ashare_boards/board_kline_em.md)
- 源码：`src/em/channels/eastmoney/ashare_boards/board_kline/board_kline_em.py`


### `指数列表`
接口：`index_list_em`, `df_index_list_em`->（DataFrame版）
描述：指数列表（clist 游客接口，沪深重要指数 / 上证 / 深证 / 中证系列，带 `market` 消歧 `000001` 这类重名代码）。

- 详情：[index_list_em.md](./ashare_indices/index_list_em.md)
- 源码：`src/em/channels/eastmoney/ashare_indices/index_list/index_list_em.py`


### `港股列表`
接口：`hk_stock_list_em`, `df_hk_stock_list_em`->（DataFrame版）
描述：港股列表（clist 游客接口，主板 / 创业板，价格按 3 位小数还原，单位港元，不含 ETF 与债券）。

- 详情：[hk_stock_list_em.md](./hk_market/hk_stock_list_em.md)
- 源码：`src/em/channels/eastmoney/hk_market/hk_stock_list/hk_stock_list_em.py`


### `场内基金列表`
接口：`fund_list_em`, `df_fund_list_em`->（DataFrame版）
描述：场内基金列表（clist 游客接口，ETF / LOF，含 IOPV 实时估值与折价率，带 `market` 可直接接 `stock_kline_em` 取基金 K 线）。

- 详情：[fund_list_em.md](./fund_market/fund_list_em.md)
- 源码：`src/em/channels/eastmoney/fund_market/fund_list/fund_list_em.py`


### `涨跌停股池`
接口：`stock_limit_pool_em`, `df_stock_limit_pool_em`->（DataFrame版）
描述：涨跌停股池（push2ex，涨停 / 昨日涨停 / 强势 / 次新 / 炸板 / 跌停，按交易日取整池；上游只保留约 15 个交易日）。

- 详情：[stock_limit_pool_em.md](./ashare_stocks/stock_limit_pool_em.md)
- 源码：`src/em/channels/eastmoney/ashare_stocks/stock_limit_pool/stock_limit_pool_em.py`


### `个股基本信息`
接口：`stock_info_em`, `df_stock_info_em`->（DataFrame版）
描述：个股基本信息（push2 stock/get，行业 / 上市时间 / 股本 / 市值 / 最新价；查无此券抛 `SecurityNotFoundError`，不换 IP 重试）。

- 详情：[stock_info_em.md](./ashare_stocks/stock_info_em.md)
- 源码：`src/em/channels/eastmoney/ashare_stocks/stock_info/stock_info_em.py`


### `个股五档盘口`
接口：`stock_bid_ask_em`, `df_stock_bid_ask_em`->（DataFrame版）
描述：个股买卖五档与当日行情快照（push2 stock/get 默认字段集，挂单量单位手）。

- 详情：[stock_bid_ask_em.md](./ashare_stocks/stock_bid_ask_em.md)
- 源码：`src/em/channels/eastmoney/ashare_stocks/stock_bid_ask/stock_bid_ask_em.py`


### `盘口异动`
接口：`stock_changes_em`, `df_stock_changes_em`->（DataFrame版）
描述：盘口异动（push2ex，大笔买入 / 大笔卖出、火箭发射、封涨停板等 22 种，按 `change_type` 一次取最近交易日该类全部记录；上游不认日期，只有最近一个交易日）。

- 详情：[stock_changes_em.md](./ashare_stocks/stock_changes_em.md)
- 源码：`src/em/channels/eastmoney/ashare_stocks/stock_changes/stock_changes_em.py`


### `板块异动`
接口：`board_changes_em`, `df_board_changes_em`->（DataFrame版）
描述：板块异动（push2ex，最近交易日全部有异动的板块：异动总次数、异动最频繁个股、各类异动次数、主力净流入，主力净流入已从万元换算成元）。

- 详情：[board_changes_em.md](./ashare_boards/board_changes_em.md)
- 源码：`src/em/channels/eastmoney/ashare_boards/board_changes/board_changes_em.py`


### `龙虎榜详情`
接口：`billboard_detail_em`, `df_billboard_detail_em`->（DataFrame版）
描述：龙虎榜详情（数据中心，按上榜日期区间取全部上榜记录，自动翻页；日期留空取最近一个有龙虎榜的交易日）。同股同日多个上榜原因为多条记录，金额不能直接相加。

- 详情：[billboard_detail_em.md](./ashare_billboard/billboard_detail_em.md)
- 源码：`src/em/channels/eastmoney/ashare_billboard/billboard_detail/billboard_detail_em.py`


### `个股上榜统计`
接口：`billboard_stock_stats_em`, `df_billboard_stock_stats_em`->（DataFrame版）
描述：个股上榜统计（数据中心，按统计周期 `1mo` / `3mo` / `6mo` / `1y` 取全部上过榜的股票：上榜次数与龙虎榜、机构买卖合计）。

- 详情：[billboard_stock_stats_em.md](./ashare_billboard/billboard_stock_stats_em.md)
- 源码：`src/em/channels/eastmoney/ashare_billboard/billboard_stock_stats/billboard_stock_stats_em.py`


### `机构买卖每日统计`
接口：`billboard_institution_em`, `df_billboard_institution_em`->（DataFrame版）
描述：机构买卖每日统计（数据中心，按上榜日期区间取有机构席位参与的上榜记录；日期留空取最近一个有机构席位上榜的交易日）。同股同日多个上榜原因为多条记录，金额不能直接相加。

- 详情：[billboard_institution_em.md](./ashare_billboard/billboard_institution_em.md)
- 源码：`src/em/channels/eastmoney/ashare_billboard/billboard_institution/billboard_institution_em.py`


### `机构席位追踪`
接口：`billboard_institution_stats_em`, `df_billboard_institution_stats_em`->（DataFrame版）
描述：机构席位追踪（数据中心，按统计周期取各股上榜时机构席位的买卖次数与金额合计）。

- 详情：[billboard_institution_stats_em.md](./ashare_billboard/billboard_institution_stats_em.md)
- 源码：`src/em/channels/eastmoney/ashare_billboard/billboard_institution_stats/billboard_institution_stats_em.py`


### `每日活跃营业部`
接口：`billboard_branch_active_em`, `df_billboard_branch_active_em`->（DataFrame版）
描述：每日活跃营业部（数据中心，按上榜日期区间取各营业部的买卖个股数、买卖合计与当日交易的上榜股票；日期留空取最近一个有龙虎榜的交易日）。`stocks` / `stock_codes`（DataFrame 列“买入股票”）是当日买入或卖出过的全部上榜股票，含只卖出的。

- 详情：[billboard_branch_active_em.md](./ashare_billboard/billboard_branch_active_em.md)
- 源码：`src/em/channels/eastmoney/ashare_billboard/billboard_branch_active/billboard_branch_active_em.py`


### `营业部排行`
接口：`billboard_branch_rank_em`, `df_billboard_branch_rank_em`->（DataFrame版）
描述：营业部排行（数据中心，按统计周期取各营业部买入上榜后 1 / 2 / 3 / 5 / 10 天的买入次数、平均涨幅与上涨概率）。

- 详情：[billboard_branch_rank_em.md](./ashare_billboard/billboard_branch_rank_em.md)
- 源码：`src/em/channels/eastmoney/ashare_billboard/billboard_branch_rank/billboard_branch_rank_em.py`


### `营业部统计`
接口：`billboard_branch_stats_em`, `df_billboard_branch_stats_em`->（DataFrame版）
描述：营业部统计（数据中心，按统计周期取各营业部的上榜次数与买卖次数、金额合计）。

- 详情：[billboard_branch_stats_em.md](./ashare_billboard/billboard_branch_stats_em.md)
- 源码：`src/em/channels/eastmoney/ashare_billboard/billboard_branch_stats/billboard_branch_stats_em.py`


### `营业部详情`
接口：`billboard_branch_trades_em`, `df_billboard_branch_trades_em`->（DataFrame版）
描述：营业部详情（数据中心，取一家营业部的上榜买卖记录，可按日期区间筛选；日期留空取全部历史）。只买入或只卖出时另一侧为 `None`。

- 详情：[billboard_branch_trades_em.md](./ashare_billboard/billboard_branch_trades_em.md)
- 源码：`src/em/channels/eastmoney/ashare_billboard/billboard_branch_trades/billboard_branch_trades_em.py`


### `个股上榜日期`
接口：`billboard_stock_dates_em`, `df_billboard_stock_dates_em`->（DataFrame版）
描述：个股上榜日期（数据中心，取一只股票历次上榜的日期，倒序）。

- 详情：[billboard_stock_dates_em.md](./ashare_billboard/billboard_stock_dates_em.md)
- 源码：`src/em/channels/eastmoney/ashare_billboard/billboard_stock_dates/billboard_stock_dates_em.py`


### `个股龙虎榜详情`
接口：`billboard_stock_em`, `df_billboard_stock_em`->（DataFrame版）
描述：个股龙虎榜详情（数据中心，取一只股票某个上榜日买入或卖出金额最大的前 5 家营业部；日期留空取该股最近一个上榜日）。同一天多个上榜原因时每个原因各有一组席位。

- 详情：[billboard_stock_em.md](./ashare_billboard/billboard_stock_em.md)
- 源码：`src/em/channels/eastmoney/ashare_billboard/billboard_stock/billboard_stock_em.py`


### `通用转换`
接口：`to_dataframe`
描述：任意 `QuotePage` → `DataFrame`，默认中文列名，可传 `columns` 覆盖。

- 详情：[eastmoney.md](./eastmoney.md)

```python
from em import to_dataframe

df = to_dataframe(page, columns=None)
```

## 接口检索（离线，不触网，对齐 akshare）

核心函数返回 `list[dict]` / `dict`，不依赖 pandas；`*_df` 为 DataFrame 包装。

### `关键词检索`
接口：`search`
描述：按关键词检索接口，精确名置顶，2-gram 降级召回。

```python
import em

em.search("板块 资金流")  # -> list[dict]
```

### `接口详情`
接口：`interface_info`
描述：查看单个接口的输入参数、输出字段与调用示例；未知接口抛 `InterfaceNotFoundError` 并给最接近候选。

```python
em.interface_info("board_constituent_em")  # -> dict
```

### `类目列表`
接口：`list_categories`
描述：列出全部类目及其接口数量。

```python
em.list_categories()  # -> [{"类目": "board", "接口数": 1}, ...]
```

### `检索 / 详情 / 类目（DataFrame）`
接口：`search_df` / `interface_info_df` / `list_categories_df`
描述：DataFrame 包装（需 pandas）。`interface_info_df` 返回 `{"inputs": 参数表, "outputs": 字段表}`，中文列名。

```python
em.search_df("板块 资金流")
em.interface_info_df("board_constituent_em")  # -> {"inputs": df, "outputs": df}
em.list_categories_df()
```

## 相关

- 渠道总览（公共面 / 配置 / 异常）：[eastmoney.md](./eastmoney.md)
- 检索实现：`src/em/application/catalog.py`
# emshare

行情数据的 Python 接口：A 股 / 港股 / 指数 / 场内基金的行情列表、K 线、分时、资金流、板块、涨跌停股池、盘口异动、龙虎榜、大宗交易、业绩与财务报表。

- 返回带类型标注的数据对象；装上 pandas 后，每个接口都有返回 `DataFrame`（中文列名）的 `df_` 版本
- 核心功能只依赖 `requests`
- 直连被封时可自动切换到你配置的动态代理

## 安装

```bash
pip install emshare                # 核心功能
pip install "emshare[pandas]"      # 需要 DataFrame 时
```

要求 Python >= 3.10。**安装名是 `emshare`，导入名是 `em`。**

## 快速开始

```python
from em import stock_kline_em, df_stock_kline_em
from em.domain.queries import KlineQuery

# 平安银行日 K（默认前复权）
series = stock_kline_em(KlineQuery(code="000001", market="sz", period="day"))
print(series.name, len(series.items))
last = series.items[-1]
print(last.date, last.open, last.close, last.change_pct)

# 同一个查询，直接拿 DataFrame（列：日期 / 开盘 / 收盘 / 最高 / 最低 / 成交量 / ...）
df = df_stock_kline_em(KlineQuery(code="000001", market="sz", period="day"))
```

每个接口都是「一个查询对象进，一个结果出」；查询对象在 `em.domain.queries` 里，参数都有默认值：

```python
from em import df_billboard_detail_em, df_stock_list_em, kline_by_name
from em.domain.queries import MarketQuery

df_stock_list_em(MarketQuery(sort="f3", size=20))  # A 股按涨跌幅排序的前 20 只
df_billboard_detail_em()  # 最近一个交易日的龙虎榜
kline_by_name("贵州茅台")  # 不知道代码时按名称取 K 线
```

## 有哪些接口

| 类别 | 接口 |
| --- | --- |
| 行情列表 | `stock_list_em` A 股、`stock_list_all_em` A 股全市场快照、`index_list_em` 指数、`hk_stock_list_em` 港股、`fund_list_em` ETF / LOF |
| K 线与分时 | `stock_kline_em`（个股 / 指数 / 基金 / 港股）、`board_kline_em`、`stock_trends_em` |
| 资金流 | `stock_fund_flow_em`、`board_fund_flow_em` |
| 板块 | `board_industry_list_em`（行业 / 概念 / 地域）、`board_constituent_em` 成分股 |
| 个股 | `stock_info_em` 基本信息、`stock_bid_ask_em` 五档盘口 |
| 盘中 | `stock_limit_pool_em` 涨跌停股池、`stock_changes_em` 盘口异动、`board_changes_em` 板块异动 |
| 龙虎榜 | `billboard_detail_em` 等 10 个 |
| 大宗交易 | `block_trade_detail_em` 等 6 个 |
| 业绩与财报 | `earnings_report_em` / `earnings_express_em` / `earnings_forecast_em` / `earnings_schedule_em`、`balance_sheet_em` / `income_statement_em` / `cash_flow_statement_em` |

共 40 个接口，各有对应的 `df_` 版本。不必记名字，包内自带离线检索：

```python
import em

em.search("资金流")  # 按关键词找接口
em.interface_info("stock_kline_em")  # 参数、返回字段、调用示例
em.list_categories()  # 全部类目
```

## 命令行

```bash
emshare --preset kline --code 600519 --market sh --tail 5    # 贵州茅台最近 5 根日 K
emshare --preset market --sort f3 --pz 20                    # A 股涨幅榜
emshare --preset limitpool --head 20                         # 涨停股池
emshare --help                                               # 全部预设与参数
```

## 被封 IP 时：配置代理

不配置也能用，默认直连。如果请求持续失败（连接被断开，或返回 403 / 429），多半是出口 IP 被封，这时需要你自己提供一个动态代理的提取接口：

```bash
emshare --init-env      # 在当前目录生成带注释的 .env 模板
```

至少改两项：

```
EM_PROXY_API=<代理提取接口地址，需返回纯文本，每行一个 ip:port>
EM_PROXY_NUM=<该接口每次返回的 IP 数>
```

`import em` 和 `emshare` 命令都会自动读取运行目录下的 `.env`（只取 `EM_` 开头的变量，已设置的环境变量优先）。配好后直连正常时不走代理，失败后才自动切换。没配代理而请求全部失败时，报错信息里会直接写明该配什么。

## 说明

- 数据取自公开的网页接口，仅供学习与研究；字段含义与可用性以上游为准，上游调整时接口可能失效。
- 许可证：MIT。

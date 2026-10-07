# 板块列表接口（行业 / 概念 / 地域）

> 渠道：[eastmoney](../eastmoney.md) ｜ 源码：`src/em/channels/eastmoney/ashare_boards/board_industry_list/board_industry_list_em.py`

## 接口名称

`board_industry_list_em` / `df_board_industry_list_em`：板块列表（行业 / 概念 / 地域，行业支持一 / 二 / 三级）

## 目标地址

- <https://quote.eastmoney.com/center/gridlist.html#industry_board>

## 描述

抓取东方财富板块列表，返回板块代码、板块名称、板块指数点位、涨跌幅、涨跌额、成交额、换手率、上涨家数、下跌家数、领涨股与领跌股。走 `pushguest` 游客主机，无需登录。

`board_type` 区分三类板块：

| `board_type` | fs 编码 | 说明 | 数量 |
| --- | --- | --- | --- |
| `industry` | `m:90+s:{s}+f:!50` | 行业板块，`level` 控制分级（s:2 一级 / s:4 二级 / s:8 三级） | 一级 31 / 二级 128 / 三级 337 |
| `industry` | `m:90+t:2+f:!50` | 行业板块全级别（`level="all"`，含一/二/三级） | 496 |
| `concept` | `m:90+t:3+f:!50` | 概念板块（无分级，`level` 被忽略） | 504 |
| `region` | `m:90+t:1+f:!50` | 地域板块（无分级，`level` 被忽略） | 31 |

## 限量

- 单页最多 100 条，二级行业（128）/ 三级行业（337）/ 概念板块（504）需翻页。
- 上游对境外 IP 封禁，需经国内动态代理访问；本接口已内置代理池 + 自动换 IP 重试。
- `sort` 为上游排序字段名（如 `f3` 涨跌幅、`f20` 成交额），传非法值上游按默认排序。

## 输入参数 `BoardListQuery`

| 名称 | 类型 | 必填 | 默认值 | 描述 |
| --- | --- | --- | --- | --- |
| `board_type` | `str` | 否 | `"industry"` | 板块类型：`industry` 行业 / `concept` 概念 / `region` 地域，未知回退 `industry` |
| `level` | `str` | 否 | `"1"` | 行业分级：`1` 一级 / `2` 二级 / `3` 三级 / `all` 全级别，仅 `industry` 有效，未知回退 `1` |
| `sort` | `str` | 否 | `"f3"` | 排序字段（上游 `f*` 字段名） |
| `page` | `int` | 否 | `1` | 页码，从 1 起 |
| `size` | `int` | 否 | `20` | 每页条数，上游上限 100 |

## 输出参数 `BoardListPage`

| 名称 | 类型 | 单位 | 描述 |
| --- | --- | --- | --- |
| `code` | `str` | — | 板块代码 |
| `name` | `str` | — | 板块名称 |
| `price` | `float \| None` | 元 | 板块指数最新点位 |
| `change_pct` | `float \| None` | % | 涨跌幅 |
| `change` | `float \| None` | 元 | 涨跌额 |
| `turnover` | `float \| None` | 元 | 成交额 |
| `turnover_rate` | `float \| None` | % | 换手率 |
| `up_count` | `int \| None` | — | 上涨家数 |
| `down_count` | `int \| None` | — | 下跌家数 |
| `leader_code` | `str \| None` | — | 领涨股代码 |
| `leader_name` | `str \| None` | — | 领涨股名称 |
| `leader_change_pct` | `float \| None` | % | 领涨股涨跌幅 |
| `laggard_code` | `str \| None` | — | 领跌股代码 |
| `laggard_name` | `str \| None` | — | 领跌股名称 |
| `laggard_change_pct` | `float \| None` | % | 领跌股涨跌幅 |

## 接口示例（领域模型 `BoardListPage`）

```python
from em import board_industry_list_em
from em.domain.queries import BoardListQuery

page = board_industry_list_em(BoardListQuery(board_type="industry", level="1", size=5))
print(page.total)
for b in page.items:
    print(b.code, b.name, b.change_pct, b.up_count, b.down_count, b.leader_name)
```

## 数据示例（领域模型）

```
total: 31
Board(code='BK1216', name='医药生物', price=4767.98, change_pct=2.03, change=95.04, turnover=6901833728000.0, turnover_rate=2.54, up_count=429, down_count=70, leader_code='000710', leader_name='贝瑞基因', leader_change_pct=10.02, laggard_code='920201', laggard_name='百瑞吉', laggard_change_pct=-8.58)
Board(code='BK0438', name='食品饮料', price=1234.56, change_pct=-1.50, change=-20.00, turnover=5000000000.0, turnover_rate=1.20, up_count=30, down_count=50, leader_code='600887', leader_name='伊利股份', leader_change_pct=5.00, laggard_code='600059', laggard_name='古越龙山', laggard_change_pct=-3.00)
```

## 接口示例（`DataFrame`）

```python
from em import df_board_industry_list_em
from em.domain.queries import BoardListQuery

df = df_board_industry_list_em(BoardListQuery(board_type="concept", size=5))
```

## 数据示例（`DataFrame`）

```
    板块代码   板块名称      最新价   涨跌幅    涨跌额           成交额  换手率  上涨家数  下跌家数  领涨股票代码  领涨股票  领涨股票-涨跌幅  领跌股票代码  领跌股票  领跌股票-涨跌幅
0  BK1063  重组蛋白  1135.45   4.33   47.16  5.093861e+11   3.84      33       2       688806  泰诺麦博-U       19.99       688179   阿拉丁        -0.04
```
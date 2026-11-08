"""命令行入口：解析参数、调用应用层服务、渲染领域模型。"""

import argparse
import logging
import sys
from pathlib import Path
from typing import TypeVar

from em.application.dataframe import CHANGE_TYPE_LABELS_ZH
from em.application.market_data import (
    board_changes_em,
    board_constituent_em,
    board_fund_flow_em,
    board_industry_list_em,
    board_kline_em,
    fund_list_em,
    hk_stock_list_em,
    index_list_em,
    stock_bid_ask_em,
    stock_changes_em,
    stock_fund_flow_em,
    stock_info_em,
    stock_kline_em,
    stock_limit_pool_em,
    stock_list_all_em,
    stock_list_em,
    stock_trends_em,
)
from em.channels.eastmoney.ashare_indices.index_list import INDEX_SERIES_FS
from em.channels.eastmoney.ashare_stocks.stock_changes import STOCK_CHANGE_TYPES
from em.channels.eastmoney.ashare_stocks.stock_limit_pool import (
    LIMIT_POOL_ENDPOINTS,
    resolve_date,
)
from em.channels.eastmoney.ashare_stocks.stock_list import MARKET_SCOPE_FS
from em.channels.eastmoney.config import (
    FQT_ADJUSTS,
    FUND_FLOW_FIELDS,
    KLINE_MARKET_IDS,
    KLT_PERIODS,
    MARKET_IDS,
)
from em.channels.eastmoney.fund_market.fund_list import FUND_TYPE_FS
from em.channels.eastmoney.hk_market.hk_stock_list import HK_SCOPE_FS
from em.core.env import load_dotenv
from em.core.errors import EmError, EmptyResponseError, HttpStatusError, NetworkError
from em.core.settings import Settings
from em.domain.models import (
    BoardChangesPage,
    BoardFundFlowSeries,
    BoardListPage,
    FundFlowSeries,
    FundListPage,
    HkStockListPage,
    IndexListPage,
    Kline,
    KlineSeries,
    LimitPoolPage,
    LimitPoolStock,
    Quote,
    QuotePage,
    StockBidAsk,
    StockChangesPage,
    StockInfo,
    TrendSeries,
)
from em.domain.queries import (
    BoardChangesQuery,
    BoardFundFlowQuery,
    BoardKlineQuery,
    BoardListQuery,
    BoardQuery,
    FundFlowQuery,
    FundListQuery,
    HkStockListQuery,
    IndexListQuery,
    KlineQuery,
    LimitPoolQuery,
    MarketQuery,
    StockBidAskQuery,
    StockChangesQuery,
    StockInfoQuery,
    TrendQuery,
)


def _fmt(value: float | int | None, pattern: str) -> str:
    return "-" if value is None else format(value, pattern)


def _fmt_amount(value: float | None) -> str:
    """把金额（元）格式化为 亿/万 友好字符串；``None`` 显示 ``-``。"""
    if value is None:
        return "-"
    if abs(value) >= 1e8:
        return f"{value / 1e8:.2f}亿"
    if abs(value) >= 1e4:
        return f"{value / 1e4:.2f}万"
    return f"{value:.2f}"


def _quote_line(quote: Quote) -> str:
    cols = [
        f"{quote.code:<8}",
        f"{quote.name:<10}",
        f"最新价:{_fmt(quote.price, '>8.2f')}",
        f"涨跌幅:{_fmt(quote.change_pct, '>6.2f')}%",
    ]
    if quote.main_net_inflow is not None:
        cols.append(f"主力净流入:{quote.main_net_inflow:>16.0f}")
    if quote.turnover is not None:
        cols.append(f"成交额:{quote.turnover:>16.0f}")
    return "  " + "  ".join(cols)


def _render(page: QuotePage) -> None:
    print(f"\n✅ 共 {page.total} 条，本次返回 {len(page.items)} 条")
    print("-" * 90)
    for quote in page.items:
        print(_quote_line(quote))
    print("-" * 90)


def _render_quotes(page: QuotePage, head: int | None = None, tail: int | None = None) -> None:
    """全市场快照渲染：5580 条不全打，按 head/tail 切片展示（默认末 20 条）。"""
    parts = _select_slices(page.items, head, tail)
    print(f"\n✅ 共 {page.total} 条，本次返回 {len(page.items)} 条")
    print("-" * 90)
    for label, shown in parts:
        print(f"—— {label} ——")
        for quote in shown:
            print(_quote_line(quote))
    print("-" * 90)


_T = TypeVar("_T")


def _select_slices(
    items: tuple[_T, ...],
    head: int | None,
    tail: int | None,
) -> list[tuple[str, tuple[_T, ...]]]:
    """选择要展示的片段（``--head`` 与 ``--tail`` 可同时生效）。

    - 都未指定：末 20 条
    - 仅 ``head``：前 head 条（0=全部）
    - 仅 ``tail``：末 tail 条（0=全部）
    - 同时指定：前 head 条 + 末 tail 条（两段，数据少时可能重叠）
    """
    parts: list[tuple[str, tuple[_T, ...]]] = []
    if head is not None:
        shown = items[:head] if head > 0 else items
        parts.append((f"前 {len(shown)} 条", shown))
    if tail is not None:
        shown = items[-tail:] if tail and tail > 0 else items
        parts.append((f"末 {len(shown)} 条", shown))
    if not parts:
        parts.append(("末 20 条", items[-20:]))
    return parts


def _select_klines(
    items: tuple[Kline, ...],
    head: int | None,
    tail: int | None,
) -> list[tuple[str, tuple[Kline, ...]]]:
    """K 线展示选择（保留旧签名，委托 ``_select_slices``）。"""
    return _select_slices(items, head, tail)


def _render_kline(series: KlineSeries, head: int | None = None, tail: int | None = None) -> None:
    parts = _select_klines(series.items, head, tail)
    print(
        f"\n✅ {series.code} {series.name}  {series.period}/{series.adjust} 共 {len(series.items)} 条："
    )
    print("-" * 90)
    for label, shown in parts:
        print(f"—— {label} ——")
        for k in shown:
            print(
                f"  {k.date}  开:{_fmt(k.open, '>8.2f')}  收:{_fmt(k.close, '>8.2f')}"
                f"  高:{_fmt(k.high, '>8.2f')}  低:{_fmt(k.low, '>8.2f')}"
                f"  量:{_fmt(k.volume, '>12.0f')}  涨跌幅:{_fmt(k.change_pct, '>6.2f')}%"
            )
    print("-" * 90)


def _render_trend(series: TrendSeries, tail: int | None = None) -> None:
    shown = series.items if (tail is None or tail <= 0) else series.items[-tail:]
    label = "全部" if (tail is None or tail <= 0) else f"末 {len(shown)} 条"
    print(
        f"\n✅ {series.code} {series.name}  ndays={series.ndays}"
        f"  昨收:{_fmt(series.pre_close, '>8.2f')}  共 {len(series.items)} 个分时点，{label}："
    )
    print("-" * 90)
    for t in shown:
        print(
            f"  {t.time}  价:{_fmt(t.price, '>8.2f')}  均价:{_fmt(t.avg_price, '>8.2f')}"
            f"  高:{_fmt(t.high, '>8.2f')}  低:{_fmt(t.low, '>8.2f')}"
            f"  量:{_fmt(t.volume, '>10.0f')}  额:{_fmt(t.amount, '>14.0f')}"
        )
    print("-" * 90)


def _render_fund_flow(
    series: FundFlowSeries, head: int | None = None, tail: int | None = None
) -> None:
    parts = _select_slices(series.items, head, tail)
    print(f"\n✅ {series.code} {series.name}  资金流（{series.market}）共 {len(series.items)} 条：")
    print("-" * 90)
    for label, shown in parts:
        print(f"—— {label} ——")
        for f in shown:
            print(
                f"  {f.date}  收盘价:{_fmt(f.close, '>8.2f')}"
                f"  涨跌幅:{_fmt(f.change_pct, '>6.2f')}%"
                f"  主力净流入(净额:{_fmt_amount(f.main_net_inflow):>12}"
                f" 净占比:{_fmt(f.main_net_pct, '>6.2f')}%)"
                f"  超大单净流入(净额:{_fmt_amount(f.xlarge_net_inflow):>12}"
                f" 净占比:{_fmt(f.xlarge_net_pct, '>6.2f')}%)"
                f"  大单净流入(净额:{_fmt_amount(f.large_net_inflow):>12}"
                f" 净占比:{_fmt(f.large_net_pct, '>6.2f')}%)"
                f"  中单净流入(净额:{_fmt_amount(f.medium_net_inflow):>12}"
                f" 净占比:{_fmt(f.medium_net_pct, '>6.2f')}%)"
                f"  小单净流入(净额:{_fmt_amount(f.small_net_inflow):>12}"
                f" 净占比:{_fmt(f.small_net_pct, '>6.2f')}%)"
            )
    print("-" * 90)


def _render_board_fund_flow(
    series: BoardFundFlowSeries, head: int | None = None, tail: int | None = None
) -> None:
    parts = _select_slices(series.items, head, tail)
    print(f"\n✅ {series.code} {series.name}  板块资金流 共 {len(series.items)} 条：")
    print("-" * 90)
    for label, shown in parts:
        print(f"—— {label} ——")
        for f in shown:
            print(
                f"  {f.date}"
                f"  主力净流入(净额:{_fmt_amount(f.main_net_inflow):>12}"
                f" 净占比:{_fmt(f.main_net_pct, '>6.2f')}%)"
                f"  超大单净流入(净额:{_fmt_amount(f.xlarge_net_inflow):>12}"
                f" 净占比:{_fmt(f.xlarge_net_pct, '>6.2f')}%)"
                f"  大单净流入(净额:{_fmt_amount(f.large_net_inflow):>12}"
                f" 净占比:{_fmt(f.large_net_pct, '>6.2f')}%)"
                f"  中单净流入(净额:{_fmt_amount(f.medium_net_inflow):>12}"
                f" 净占比:{_fmt(f.medium_net_pct, '>6.2f')}%)"
                f"  小单净流入(净额:{_fmt_amount(f.small_net_inflow):>12}"
                f" 净占比:{_fmt(f.small_net_pct, '>6.2f')}%)"
            )
    print("-" * 90)


def _render_board_list(page: BoardListPage) -> None:
    print(f"\n✅ 共 {page.total} 条，本次返回 {len(page.items)} 条")
    print("-" * 100)
    for b in page.items:
        print(
            f"  {b.code:<8} {b.name:<10}"
            f"  最新价:{_fmt(b.price, '>10.2f')}"
            f"  涨跌幅:{_fmt(b.change_pct, '>6.2f')}%"
            f"  上涨:{_fmt(b.up_count, '>4')}"
            f"  下跌:{_fmt(b.down_count, '>4')}"
            f"  领涨:{b.leader_name or '-'}({_fmt(b.leader_change_pct, '>6.2f')}%)"
            f"  领跌:{b.laggard_name or '-'}({_fmt(b.laggard_change_pct, '>6.2f')}%)"
        )
    print("-" * 100)


def _render_index_list(page: IndexListPage) -> None:
    print(f"\n✅ 共 {page.total} 条，本次返回 {len(page.items)} 条")
    print("-" * 100)
    for i in page.items:
        print(
            f"  {i.code:<8} {i.market or '-':<4} {i.name:<10}"
            f"  最新:{_fmt(i.price, '>10.2f')}"
            f"  涨跌幅:{_fmt(i.change_pct, '>6.2f')}%"
            f"  成交额:{_fmt_amount(i.turnover):>10}"
            f"  量比:{_fmt(i.volume_ratio, '>5.2f')}"
        )
    print("-" * 100)


def _render_hk_stock_list(page: HkStockListPage) -> None:
    print(f"\n✅ 共 {page.total} 条，本次返回 {len(page.items)} 条（价格 / 成交额单位：港元）")
    print("-" * 90)
    for q in page.items:
        print(
            f"  {q.code:<6} {q.name:<10}"
            f"  最新价:{_fmt(q.price, '>9.3f')}"
            f"  涨跌幅:{_fmt(q.change_pct, '>6.2f')}%"
            f"  成交额:{_fmt_amount(q.turnover):>10}"
        )
    print("-" * 90)


def _render_fund_list(page: FundListPage) -> None:
    print(f"\n✅ 共 {page.total} 条，本次返回 {len(page.items)} 条")
    print("-" * 100)
    for q in page.items:
        print(
            f"  {q.code:<8} {q.market or '-':<3} {q.name:<12}"
            f"  最新价:{_fmt(q.price, '>7.3f')}"
            f"  IOPV:{_fmt(q.iopv, '>7.4f')}"
            f"  折价率:{_fmt(q.discount_rate, '>6.2f')}%"
            f"  涨跌幅:{_fmt(q.change_pct, '>6.2f')}%"
            f"  成交额:{_fmt_amount(q.turnover):>10}"
        )
    print("-" * 100)


_POOL_LABELS = {
    "limit_up": "涨停股池",
    "prev_limit_up": "昨日涨停股池",
    "strong": "强势股池",
    "sub_new": "次新股池",
    "broken": "炸板股池",
    "limit_down": "跌停股池",
}


def _pool_extra(s: LimitPoolStock, pool_type: str) -> str:
    """各股池最有用的一两个专属字段。"""
    if pool_type == "limit_up":
        return (
            f"  连板:{_fmt(s.limit_up_streak, '>2')}  首封:{s.first_seal_time or '-'}"
            f"  封板资金:{_fmt_amount(s.seal_fund):>10}"
        )
    if pool_type == "prev_limit_up":
        return (
            f"  昨日连板:{_fmt(s.prev_limit_up_streak, '>2')}  昨日封板:{s.prev_seal_time or '-'}"
        )
    if pool_type == "strong":
        return f"  量比:{_fmt(s.volume_ratio, '>5.2f')}  理由:{s.reason or '-'}"
    if pool_type == "sub_new":
        return f"  上市:{s.listing_date or '-'}  开板几日:{_fmt(s.open_days, '>3')}"
    if pool_type == "broken":
        return f"  炸板:{_fmt(s.broken_count, '>2')}次  首封:{s.first_seal_time or '-'}"
    return f"  连续跌停:{_fmt(s.limit_down_streak, '>2')}  封单资金:{_fmt_amount(s.seal_fund):>10}"


def _render_limit_pool(page: LimitPoolPage, head: int | None = None) -> None:
    label = _POOL_LABELS.get(page.pool_type, page.pool_type)
    shown = page.items if (head is None or head <= 0) else page.items[:head]
    print(f"\n✅ {page.date} {label} 共 {page.total} 只，展示 {len(shown)} 只")
    print("-" * 100)
    for s in shown:
        print(
            f"  {s.code:<7} {s.market or '-':<3} {s.name:<8}"
            f"  最新价:{_fmt(s.price, '>8.2f')}"
            f"  涨跌幅:{_fmt(s.change_pct, '>6.2f')}%" + _pool_extra(s, page.pool_type)
        )
    print("-" * 100)


def _render_stock_info(info: StockInfo) -> None:
    print(f"\n✅ {info.code} {info.name}（{info.market or '-'}）")
    print("-" * 60)
    print(f"  行业:{info.industry or '-'}  上市时间:{info.listing_date or '-'}")
    print(f"  最新价:{_fmt(info.price, '.2f')}")
    print(f"  总股本:{_fmt_amount(info.total_shares)}股  流通股:{_fmt_amount(info.float_shares)}股")
    print(
        f"  总市值:{_fmt_amount(info.total_market_cap)}  流通市值:{_fmt_amount(info.float_market_cap)}"
    )
    print("-" * 60)


def _render_bid_ask(book: StockBidAsk) -> None:
    print(
        f"\n✅ {book.code} {book.name}（{book.market or '-'}）"
        f"  最新:{_fmt(book.price, '.2f')}  均价:{_fmt(book.avg_price, '.2f')}"
        f"  昨收:{_fmt(book.pre_close, '.2f')}"
    )
    print("-" * 60)
    for i in range(len(book.asks), 0, -1):
        a = book.asks[i - 1]
        print(f"  卖{i}  {_fmt(a.price, '>9.2f')}  {_fmt(a.volume, '>10.0f')} 手")
    print("  " + "-" * 30)
    for i, b in enumerate(book.bids, start=1):
        print(f"  买{i}  {_fmt(b.price, '>9.2f')}  {_fmt(b.volume, '>10.0f')} 手")
    print("-" * 60)
    print(
        f"  今开:{_fmt(book.open, '.2f')}  最高:{_fmt(book.high, '.2f')}  最低:{_fmt(book.low, '.2f')}"
        f"  涨停:{_fmt(book.limit_up, '.2f')}  跌停:{_fmt(book.limit_down, '.2f')}"
    )
    print(
        f"  总手:{_fmt(book.volume, '.0f')}  金额:{_fmt_amount(book.turnover)}"
        f"  外盘:{_fmt(book.outer_volume, '.0f')}  量比:{_fmt(book.volume_ratio, '.2f')}"
    )


# 异动列表动辄上千条：不指定 --head 时只展示前 20 条（0=全部）
_CHANGES_DEFAULT_HEAD = 20


def _head_slice(items: tuple[_T, ...], head: int | None) -> tuple[_T, ...]:
    if head is not None and head <= 0:
        return items
    return items[: head or _CHANGES_DEFAULT_HEAD]


def _change_label(change_type: str | None) -> str:
    return CHANGE_TYPE_LABELS_ZH.get(change_type, change_type) if change_type else "-"


def _render_stock_changes(page: StockChangesPage, head: int | None = None) -> None:
    shown = _head_slice(page.items, head)
    print(
        f"\n✅ {_change_label(page.change_type)} 共 {page.total} 条，展示 {len(shown)} 条"
        "（最近一个交易日，按时间倒序）"
    )
    print("-" * 100)
    for c in shown:
        extra = ""
        if c.volume is not None or c.amount is not None:
            extra = f"  数量:{_fmt(c.volume, '>10.0f')}股  金额:{_fmt_amount(c.amount):>10}"
        print(
            f"  {c.time}  {c.code:<7} {c.market or '-':<3} {c.name:<8}"
            f"  价格:{_fmt(c.price, '>8.2f')}  涨跌幅:{_fmt(c.change_pct, '>7.2f')}%" + extra
        )
    print("-" * 100)


def _render_board_changes(page: BoardChangesPage, head: int | None = None) -> None:
    shown = _head_slice(page.items, head)
    print(f"\n✅ {page.date} {page.time} 板块异动 共 {page.total} 个板块，展示 {len(shown)} 个")
    print("-" * 110)
    for b in shown:
        top = f"{b.top_stock_name or '-'}({_change_label(b.top_stock_change_type)})"
        kinds = " / ".join(f"{_change_label(t.change_type)}{t.count}" for t in b.type_counts[:3])
        print(
            f"  {b.code:<7} {b.name:<8}  涨跌幅:{_fmt(b.change_pct, '>6.2f')}%"
            f"  主力净流入:{_fmt_amount(b.main_net_inflow):>10}"
            f"  异动:{_fmt(b.change_count, '>5')}次  最频繁:{top}  前三类:{kinds or '-'}"
        )
    print("-" * 110)


# 这些预设的 secid 只认沪深京（csi / hk 仅 K 线支持）
_SZ_SH_BJ_PRESETS = ("trends", "fundflow", "stockinfo", "bidask")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="东方财富行情抓取（动态代理 + 自动重试）")
    ap.add_argument(
        "--preset",
        choices=[
            "board",
            "market",
            "market-all",
            "kline",
            "trends",
            "fundflow",
            "boardflow",
            "boardlist",
            "boardkline",
            "indexlist",
            "hklist",
            "fundlist",
            "limitpool",
            "stockinfo",
            "bidask",
            "changes",
            "boardchanges",
        ],
        default="board",
        help="接口预设",
    )
    ap.add_argument(
        "--pool-type",
        choices=list(LIMIT_POOL_ENDPOINTS),
        default="limit_up",
        help="股池（limitpool 预设）：limit_up / prev_limit_up / strong / sub_new / broken / limit_down",
    )
    ap.add_argument(
        "--change-type",
        choices=list(STOCK_CHANGE_TYPES),
        default="big_buy",
        help="盘口异动类型（changes 预设），如 big_buy 大笔买入 / rocket_launch 火箭发射，共 22 种",
    )
    ap.add_argument(
        "--date", default=None, help="交易日 YYYYMMDD（limitpool 预设，留空取最近交易日）"
    )
    ap.add_argument(
        "--fund-type",
        choices=list(FUND_TYPE_FS),
        default="etf",
        help="基金类型（fundlist 预设）：etf / lof / all",
    )
    ap.add_argument(
        "--hk-scope",
        choices=list(HK_SCOPE_FS),
        default="all",
        help="港股范围（hklist 预设）：all 主板 + 创业板 / main 主板 / gem 创业板",
    )
    ap.add_argument(
        "--series",
        choices=list(INDEX_SERIES_FS),
        default="main",
        help="指数系列（indexlist 预设）：main 沪深重要 / sh 上证 / sz 深证 / csi 中证",
    )
    ap.add_argument("--board", default="BK0438", help="板块代码（board/boardflow/boardkline 预设）")
    ap.add_argument(
        "--board-type",
        choices=["industry", "concept", "region"],
        default="industry",
        help="板块类型（boardlist 预设）",
    )
    ap.add_argument(
        "--level", choices=["1", "2", "3", "all"], default="1", help="行业分级（boardlist 预设）"
    )
    ap.add_argument("--rank", choices=list(FUND_FLOW_FIELDS), default="10d", help="资金流周期")
    ap.add_argument(
        "--sort", default="f3", help="排序字段（market/boardlist/indexlist/hklist/fundlist 预设）"
    )
    ap.add_argument(
        "--scope",
        choices=list(MARKET_SCOPE_FS),
        default="all",
        help="A 股范围（market/market-all 预设）：沪/深/北/科创/创业/新股/ST",
    )
    ap.add_argument(
        "--code", default="000001", help="证券代码（kline/trends/fundflow/stockinfo/bidask 预设）"
    )
    ap.add_argument(
        "--market",
        choices=list(KLINE_MARKET_IDS),
        default="sz",
        help="市场（kline/trends/fundflow/stockinfo/bidask 预设；csi 中证指数 / hk 港股仅 kline 支持）",
    )
    ap.add_argument(
        "--period",
        choices=list(KLT_PERIODS),
        default="day",
        help="K 线周期（kline/boardkline 预设）",
    )
    ap.add_argument(
        "--adjust", choices=list(FQT_ADJUSTS), default="qfq", help="复权方式（kline 预设）"
    )
    ap.add_argument("--ndays", type=int, default=1, help="分时天数（trends 预设，1 当日 / 5 五日）")
    ap.add_argument(
        "--head",
        type=int,
        default=None,
        help=(
            "展示前 N 条（kline/boardkline/fundflow/market-all/limitpool/changes/boardchanges 预设，"
            "0=全部；changes/boardchanges 不指定时展示前 20 条；可与 --tail 同时使用）"
        ),
    )
    ap.add_argument(
        "--tail",
        type=int,
        default=None,
        help="展示末 N 条（kline/boardkline/fundflow/market-all 预设，0=全部，可与 --head 同时使用）",
    )
    ap.add_argument("--pn", type=int, default=1, help="页码")
    ap.add_argument("--pz", type=int, default=None, help="每页条数")
    args = ap.parse_args(argv)
    # 分时 / 资金流 / 个股信息 / 盘口的 secid 映射只认沪深京：放行 csi / hk 会被静默当成深市代码去查
    if args.preset in _SZ_SH_BJ_PRESETS and args.market not in MARKET_IDS:
        ap.error(f"--market {args.market} 仅 kline 预设支持，{args.preset} 只支持 sz / sh / bj")
    if args.date:
        try:
            resolve_date(args.date)
        except ValueError as exc:
            ap.error(str(exc))
    return args


def _is_network_failure(exc: EmError) -> bool:
    """判断是否为网络/封禁类错误（连接断开、空响应、403/429）。"""
    if isinstance(exc, (NetworkError, EmptyResponseError)):
        return True
    return isinstance(exc, HttpStatusError) and exc.status_code in (403, 429)


def _hint_ip_blocked(exc: EmError) -> str | None:
    """网络/封禁错误时，根据代理配置状态返回友好提示。"""
    if not _is_network_failure(exc):
        return None
    s = Settings.from_env()
    if not s.proxy_enabled or s.proxy_mode == "never":
        return (
            "💡 本机 IP 可能被东方财富封禁。建议在 .env 中配置动态代理解决：\n"
            "   EM_PROXY_API=<代理API地址>\n"
            "   配置示例见 .env.example"
        )
    api = s.proxy_api or ""
    if not api or "YOUR_" in api:
        return (
            "💡 代理已启用但 EM_PROXY_API 未正确配置。\n"
            "   请在 .env 中填入真实的代理 API 地址，配置示例见 .env.example"
        )
    return None


def main(argv: list[str] | None = None) -> int:
    # CWD/.env 优先，找不到则回退到项目根（src/em 的上两级），支持从任意目录调用
    project_root = Path(__file__).resolve().parents[2]
    for candidate in (Path(".env"), project_root / ".env"):
        load_dotenv(candidate)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = _parse_args(argv)
    try:
        if args.preset == "market":
            page = stock_list_em(
                MarketQuery(sort=args.sort, page=args.pn, size=args.pz or 20, scope=args.scope)
            )
            _render(page)
        elif args.preset == "market-all":
            # 全市场快照（约 56 页并发翻页），结果按代码升序，切片展示
            _render_quotes(
                stock_list_all_em(MarketQuery(scope=args.scope)), head=args.head, tail=args.tail
            )
        elif args.preset == "kline":
            series = stock_kline_em(
                KlineQuery(
                    code=args.code, market=args.market, period=args.period, adjust=args.adjust
                )
            )
            _render_kline(series, head=args.head, tail=args.tail)
        elif args.preset == "trends":
            trend_series = stock_trends_em(
                TrendQuery(code=args.code, market=args.market, ndays=args.ndays)
            )
            _render_trend(trend_series, tail=args.tail)
        elif args.preset == "fundflow":
            flow_series = stock_fund_flow_em(FundFlowQuery(code=args.code, market=args.market))
            _render_fund_flow(flow_series, head=args.head, tail=args.tail)
        elif args.preset == "boardflow":
            board_flow = board_fund_flow_em(BoardFundFlowQuery(board=args.board))
            _render_board_fund_flow(board_flow, head=args.head, tail=args.tail)
        elif args.preset == "boardkline":
            board_series = board_kline_em(BoardKlineQuery(board=args.board, period=args.period))
            _render_kline(board_series, head=args.head, tail=args.tail)
        elif args.preset == "boardlist":
            board_page = board_industry_list_em(
                BoardListQuery(
                    board_type=args.board_type,
                    level=args.level,
                    sort=args.sort,
                    page=args.pn,
                    size=args.pz or 20,
                )
            )
            _render_board_list(board_page)
        elif args.preset == "indexlist":
            index_page = index_list_em(
                IndexListQuery(series=args.series, sort=args.sort, page=args.pn, size=args.pz or 20)
            )
            _render_index_list(index_page)
        elif args.preset == "hklist":
            hk_page = hk_stock_list_em(
                HkStockListQuery(
                    scope=args.hk_scope, sort=args.sort, page=args.pn, size=args.pz or 20
                )
            )
            _render_hk_stock_list(hk_page)
        elif args.preset == "fundlist":
            fund_page = fund_list_em(
                FundListQuery(
                    fund_type=args.fund_type, sort=args.sort, page=args.pn, size=args.pz or 20
                )
            )
            _render_fund_list(fund_page)
        elif args.preset == "limitpool":
            pool_page = stock_limit_pool_em(
                LimitPoolQuery(pool_type=args.pool_type, date=args.date)
            )
            _render_limit_pool(pool_page, head=args.head)
        elif args.preset == "stockinfo":
            _render_stock_info(stock_info_em(StockInfoQuery(code=args.code, market=args.market)))
        elif args.preset == "bidask":
            _render_bid_ask(stock_bid_ask_em(StockBidAskQuery(code=args.code, market=args.market)))
        elif args.preset == "changes":
            changes_page = stock_changes_em(StockChangesQuery(change_type=args.change_type))
            _render_stock_changes(changes_page, head=args.head)
        elif args.preset == "boardchanges":
            _render_board_changes(board_changes_em(BoardChangesQuery()), head=args.head)
        else:
            page = board_constituent_em(
                BoardQuery(board=args.board, period=args.rank, page=args.pn, size=args.pz or 8)
            )
            _render(page)
    except KeyboardInterrupt:
        return 130
    except EmError as exc:
        print(f"❌ 抓取失败：{exc}", file=sys.stderr)
        hint = _hint_ip_blocked(exc)
        if hint:
            print(hint, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""命令行入口：解析参数、调用应用层服务、渲染领域模型。"""

import argparse
import logging
import sys
from pathlib import Path
from typing import TypeVar

from em.application.market_data import (
    board_constituent_em,
    board_fund_flow_em,
    stock_fund_flow_em,
    stock_kline_em,
    stock_list_em,
    stock_trends_em,
)
from em.channels.eastmoney.config import FQT_ADJUSTS, FUND_FLOW_FIELDS, KLT_PERIODS
from em.core.env import load_dotenv
from em.core.errors import EmError, EmptyResponseError, HttpStatusError, NetworkError
from em.core.settings import Settings
from em.domain.models import (
    BoardFundFlowSeries,
    FundFlowSeries,
    Kline,
    KlineSeries,
    QuotePage,
    TrendSeries,
)
from em.domain.queries import (
    BoardFundFlowQuery,
    BoardQuery,
    FundFlowQuery,
    KlineQuery,
    MarketQuery,
    TrendQuery,
)


def _fmt(value: float | None, pattern: str) -> str:
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


def _render(page: QuotePage) -> None:
    print(f"\n✅ 共 {page.total} 条，本次返回 {len(page.items)} 条")
    print("-" * 90)
    for quote in page.items:
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
        print("  " + "  ".join(cols))
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


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="东方财富行情抓取（动态代理 + 自动重试）")
    ap.add_argument(
        "--preset",
        choices=["board", "market", "kline", "trends", "fundflow", "boardflow"],
        default="board",
        help="接口预设",
    )
    ap.add_argument("--board", default="BK0438", help="板块代码（board 预设）")
    ap.add_argument("--rank", choices=list(FUND_FLOW_FIELDS), default="10d", help="资金流周期")
    ap.add_argument("--sort", default="f3", help="排序字段（market 预设）")
    ap.add_argument("--code", default="000001", help="证券代码（kline/trends/fundflow 预设）")
    ap.add_argument(
        "--market",
        choices=["sz", "sh", "bj"],
        default="sz",
        help="市场（kline/trends/fundflow 预设）",
    )
    ap.add_argument(
        "--period", choices=list(KLT_PERIODS), default="day", help="K 线周期（kline 预设）"
    )
    ap.add_argument(
        "--adjust", choices=list(FQT_ADJUSTS), default="qfq", help="复权方式（kline 预设）"
    )
    ap.add_argument("--ndays", type=int, default=1, help="分时天数（trends 预设，1 当日 / 5 五日）")
    ap.add_argument(
        "--head",
        type=int,
        default=None,
        help="展示前 N 条（kline/fundflow 预设，0=全部，可与 --tail 同时使用）",
    )
    ap.add_argument(
        "--tail",
        type=int,
        default=None,
        help="展示末 N 条（kline/fundflow 预设，0=全部，可与 --head 同时使用）",
    )
    ap.add_argument("--pn", type=int, default=1, help="页码")
    ap.add_argument("--pz", type=int, default=None, help="每页条数")
    return ap.parse_args(argv)


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
            page = stock_list_em(MarketQuery(sort=args.sort, page=args.pn, size=args.pz or 20))
            _render(page)
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

"""CLI K 线展示选择的行为锁（不触网）。"""

from em.cli import (
    _fmt_amount,
    _render_board_fund_flow,
    _render_fund_flow,
    _select_klines,
    main,
)
from em.core.errors import NetworkError
from em.domain.models import BoardFundFlow, BoardFundFlowSeries, FundFlow, FundFlowSeries, Kline


def _items(n: int) -> tuple[Kline, ...]:
    return tuple(Kline(date=f"2020-{i:02d}-01") for i in range(1, n + 1))


def test_fmt_amount_uses_yi_and_wan() -> None:
    assert _fmt_amount(125061199.0) == "1.25亿"
    assert _fmt_amount(-26572961.0) == "-2657.30万"
    assert _fmt_amount(1250.0) == "1250.00"
    assert _fmt_amount(None) == "-"


def test_fmt_amount_boundaries() -> None:
    assert _fmt_amount(1e8) == "1.00亿"
    assert _fmt_amount(1e4) == "1.00万"
    assert _fmt_amount(99999999.0) == "10000.00万"


def test_render_fund_flow_uses_full_field_names(capsys) -> None:
    series = FundFlowSeries(
        code="000001",
        name="平安银行",
        market="sz",
        items=(
            FundFlow(
                date="2026-09-30",
                close=11.57,
                change_pct=1.94,
                main_net_inflow=125061199.0,
                main_net_pct=10.37,
                xlarge_net_inflow=-26572961.0,
                xlarge_net_pct=-2.2,
                large_net_inflow=151634160.0,
                large_net_pct=12.58,
                medium_net_inflow=-53573968.0,
                medium_net_pct=-4.44,
                small_net_inflow=-71487229.0,
                small_net_pct=-5.93,
            ),
        ),
    )
    _render_fund_flow(series, tail=1)
    out = capsys.readouterr().out
    for label in (
        "收盘价:",
        "涨跌幅:",
        "主力净流入(净额:",
        "超大单净流入(净额:",
        "大单净流入(净额:",
        "中单净流入(净额:",
        "小单净流入(净额:",
        "净占比:",
    ):
        assert label in out
    assert "净占比: 10.37%" in out
    assert "-2657.30万" in out


def test_render_board_fund_flow_omits_close_and_change_pct(capsys) -> None:
    series = BoardFundFlowSeries(
        code="BK0438",
        name="食品饮料",
        items=(
            BoardFundFlow(
                date="2026-04-09",
                main_net_inflow=-1435059744.0,
                main_net_pct=-6.80,
                xlarge_net_inflow=-557692240.0,
                xlarge_net_pct=-2.64,
                large_net_inflow=-877367504.0,
                large_net_pct=-4.15,
                medium_net_inflow=525396736.0,
                medium_net_pct=2.49,
                small_net_inflow=890112768.0,
                small_net_pct=4.21,
            ),
        ),
    )
    _render_board_fund_flow(series, tail=1)
    out = capsys.readouterr().out
    assert "板块资金流" in out
    for label in (
        "主力净流入(净额:",
        "超大单净流入(净额:",
        "大单净流入(净额:",
        "中单净流入(净额:",
        "小单净流入(净额:",
        "净占比:",
    ):
        assert label in out
    assert "净占比: -6.80%" in out
    assert "-14.35亿" in out
    assert "收盘价" not in out
    assert "涨跌幅" not in out


def test_default_last_20() -> None:
    items = _items(5)
    parts = _select_klines(items, head=None, tail=None)
    assert parts == [("末 20 条", items)]
    assert [k.date for k in parts[0][1]] == [
        "2020-01-01",
        "2020-02-01",
        "2020-03-01",
        "2020-04-01",
        "2020-05-01",
    ]


def test_head_only() -> None:
    items = _items(5)
    parts = _select_klines(items, head=3, tail=None)
    assert parts == [("前 3 条", items[:3])]
    assert [k.date for k in parts[0][1]] == ["2020-01-01", "2020-02-01", "2020-03-01"]


def test_tail_only() -> None:
    items = _items(5)
    parts = _select_klines(items, head=None, tail=2)
    assert parts == [("末 2 条", items[-2:])]
    assert [k.date for k in parts[0][1]] == ["2020-04-01", "2020-05-01"]


def test_head_and_tail_both_shown() -> None:
    items = _items(5)
    parts = _select_klines(items, head=2, tail=2)
    assert [label for label, _ in parts] == ["前 2 条", "末 2 条"]
    assert [k.date for k in parts[0][1]] == ["2020-01-01", "2020-02-01"]
    assert [k.date for k in parts[1][1]] == ["2020-04-01", "2020-05-01"]


def test_head_zero_means_all() -> None:
    items = _items(5)
    parts = _select_klines(items, head=0, tail=None)
    assert parts == [("前 5 条", items)]


def test_tail_zero_means_all() -> None:
    items = _items(5)
    parts = _select_klines(items, head=None, tail=0)
    assert parts == [("末 5 条", items)]


def test_empty_items_default() -> None:
    parts = _select_klines((), head=None, tail=None)
    assert parts == [("末 20 条", ())]


def test_main_em_error_returns_1_without_traceback(monkeypatch, capsys) -> None:
    def boom(_query):
        raise NetworkError("连接被断开")

    monkeypatch.setattr("em.cli.fetch_kline", boom)
    rc = main(["--preset", "kline", "--code", "000001"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "抓取失败" in err
    assert "Traceback" not in err


def test_main_keyboard_interrupt_returns_130(monkeypatch) -> None:
    def boom(_query):
        raise KeyboardInterrupt

    monkeypatch.setattr("em.cli.fetch_kline", boom)
    assert main(["--preset", "kline", "--code", "000001"]) == 130

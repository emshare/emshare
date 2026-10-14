"""CLI 行为锁：渲染字段、展示切片、退出码与提示（不触网）。"""

from em.cli import (
    _fmt_amount,
    _hint_ip_blocked,
    _is_network_failure,
    _render_board_fund_flow,
    _render_fund_flow,
    _render_quotes,
    _select_klines,
    main,
)
from em.core.errors import (
    ConfigError,
    EmptyResponseError,
    HttpStatusError,
    NetworkError,
)
from em.domain.models import (
    BoardFundFlow,
    BoardFundFlowSeries,
    FundFlow,
    FundFlowSeries,
    Kline,
    Quote,
    QuotePage,
)


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

    monkeypatch.setattr("em.cli.stock_kline_em", boom)
    rc = main(["--preset", "kline", "--code", "000001"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "抓取失败" in err
    assert "Traceback" not in err


def test_main_keyboard_interrupt_returns_130(monkeypatch) -> None:
    def boom(_query):
        raise KeyboardInterrupt

    monkeypatch.setattr("em.cli.stock_kline_em", boom)
    assert main(["--preset", "kline", "--code", "000001"]) == 130


class _FakeSettings:
    def __init__(
        self,
        proxy_enabled: bool,
        proxy_mode: str,
        proxy_api: str = "http://api.example.com/get?uid=real&vkey=real",
    ) -> None:
        self.proxy_enabled = proxy_enabled
        self.proxy_mode = proxy_mode
        self.proxy_api = proxy_api


def test_is_network_failure_classifies_correctly() -> None:
    assert _is_network_failure(NetworkError("conn")) is True
    assert _is_network_failure(EmptyResponseError("empty")) is True
    assert _is_network_failure(HttpStatusError(403)) is True
    assert _is_network_failure(HttpStatusError(429)) is True
    assert _is_network_failure(HttpStatusError(500)) is False
    assert _is_network_failure(HttpStatusError(404)) is False
    assert _is_network_failure(ConfigError("bad")) is False


def test_hint_ip_blocked_no_proxy(monkeypatch) -> None:
    monkeypatch.setattr("em.cli.Settings.from_env", lambda: _FakeSettings(False, "never"))
    hint = _hint_ip_blocked(NetworkError("连接断开"))
    assert hint is not None
    assert "封禁" in hint
    assert "EM_PROXY_API" in hint
    assert ".env.example" in hint


def test_hint_ip_blocked_with_proxy_returns_none(monkeypatch) -> None:
    monkeypatch.setattr("em.cli.Settings.from_env", lambda: _FakeSettings(True, "auto"))
    assert _hint_ip_blocked(NetworkError("连接断开")) is None


def test_hint_proxy_api_placeholder(monkeypatch) -> None:
    monkeypatch.setattr(
        "em.cli.Settings.from_env",
        lambda: _FakeSettings(True, "auto", "http://api.xiequ.cn?uid=YOUR_UID&vkey=YOUR_VKEY"),
    )
    hint = _hint_ip_blocked(NetworkError("连接断开"))
    assert hint is not None
    assert "EM_PROXY_API" in hint
    assert "未正确配置" in hint


def test_hint_proxy_api_empty(monkeypatch) -> None:
    monkeypatch.setattr("em.cli.Settings.from_env", lambda: _FakeSettings(True, "auto", ""))
    hint = _hint_ip_blocked(NetworkError("连接断开"))
    assert hint is not None
    assert "未正确配置" in hint


def test_hint_ip_blocked_non_network_error_returns_none(monkeypatch) -> None:
    monkeypatch.setattr("em.cli.Settings.from_env", lambda: _FakeSettings(False, "never"))
    assert _hint_ip_blocked(ConfigError("bad config")) is None


def test_main_shows_ip_blocked_hint_when_no_proxy(monkeypatch, capsys) -> None:
    def boom(_query):
        raise NetworkError("连接被断开")

    monkeypatch.setattr("em.cli.stock_kline_em", boom)
    monkeypatch.setattr("em.cli.Settings.from_env", lambda: _FakeSettings(False, "never"))
    rc = main(["--preset", "kline", "--code", "000001"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "封禁" in err
    assert "EM_PROXY_API" in err


def test_main_no_hint_when_proxy_configured(monkeypatch, capsys) -> None:
    def boom(_query):
        raise NetworkError("连接被断开")

    monkeypatch.setattr("em.cli.stock_kline_em", boom)
    monkeypatch.setattr("em.cli.Settings.from_env", lambda: _FakeSettings(True, "auto"))
    rc = main(["--preset", "kline", "--code", "000001"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "封禁" not in err


# --- market-all 全市场快照预设 ---


def _quotes(n: int) -> tuple[Quote, ...]:
    return tuple(
        Quote(code=f"{600000 + i}", name=f"股{i}", price=10.0 + i, change_pct=1.0 * i)
        for i in range(n)
    )


def test_render_quotes_slices_and_total(capsys) -> None:
    page = QuotePage(total=5580, items=_quotes(30))
    _render_quotes(page, head=2, tail=2)
    out = capsys.readouterr().out
    assert "共 5580 条，本次返回 30 条" in out
    assert "前 2 条" in out
    assert "末 2 条" in out
    assert "600000" in out and "600029" in out  # 首条与末条
    assert out.count("最新价:") == 4  # 只渲染切片，不全打


def test_render_quotes_default_last_20(capsys) -> None:
    page = QuotePage(total=100, items=_quotes(30))
    _render_quotes(page)
    out = capsys.readouterr().out
    assert "末 20 条" in out
    assert out.count("最新价:") == 20


def test_main_market_all_renders_without_paging(monkeypatch, capsys) -> None:
    page = QuotePage(total=5580, items=_quotes(3))
    monkeypatch.setattr("em.cli.stock_list_all_em", lambda: page)
    rc = main(["--preset", "market-all", "--tail", "2"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "共 5580 条" in out
    assert "末 2 条" in out


def test_main_market_all_error_returns_1(monkeypatch, capsys) -> None:
    def boom():
        raise NetworkError("连接被断开")

    monkeypatch.setattr("em.cli.stock_list_all_em", boom)
    monkeypatch.setattr("em.cli.Settings.from_env", lambda: _FakeSettings(True, "auto"))
    rc = main(["--preset", "market-all"])
    assert rc == 1
    assert "抓取失败" in capsys.readouterr().err

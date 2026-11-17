"""CLI 行为锁：渲染字段、展示切片、退出码与提示（不触网）。"""

import pytest

from em.application.hints import is_egress_failure
from em.cli import (
    _fmt_amount,
    _hint_ip_blocked,
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
from em.domain.queries import MarketQuery


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


def test_main_kline_accepts_csi_and_hk(monkeypatch) -> None:
    from em.domain.models import KlineSeries
    from em.domain.queries import KlineQuery

    seen: list[KlineQuery] = []

    def fake_kline(query: KlineQuery) -> KlineSeries:
        seen.append(query)
        return KlineSeries(code=query.code, name="x", period="day", adjust="qfq", items=())

    monkeypatch.setattr("em.cli.stock_kline_em", fake_kline)
    assert main(["--preset", "kline", "--code", "932000", "--market", "csi"]) == 0
    assert main(["--preset", "kline", "--code", "00700", "--market", "hk"]) == 0
    assert [(q.code, q.market) for q in seen] == [("932000", "csi"), ("00700", "hk")]


@pytest.mark.parametrize("preset", ["trends", "fundflow"])
@pytest.mark.parametrize("market", ["csi", "hk"])
def test_main_rejects_kline_only_markets(preset: str, market: str, capsys) -> None:
    # 分时 / 资金流的 secid 只认沪深京：放行会被静默当成深市代码去查
    with pytest.raises(SystemExit) as exc:
        main(["--preset", preset, "--code", "00700", "--market", market])
    assert exc.value.code == 2
    assert "仅 kline 预设支持" in capsys.readouterr().err


def test_main_limitpool_rejects_malformed_date(capsys) -> None:
    # 上游对 2026-11-06 这类写法只返回空数据，CLI 要给友好提示而不是异常栈
    with pytest.raises(SystemExit) as exc:
        main(["--preset", "limitpool", "--date", "2026-11-06"])
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "YYYYMMDD" in err
    assert "Traceback" not in err


def test_main_limitpool_passes_query(monkeypatch, capsys) -> None:
    from em.domain.models import LimitPoolPage
    from em.domain.queries import LimitPoolQuery

    seen: list[LimitPoolQuery] = []

    def fake_pool(query: LimitPoolQuery) -> LimitPoolPage:
        seen.append(query)
        return LimitPoolPage(pool_type=query.pool_type, date="2026-11-06", total=0, items=())

    monkeypatch.setattr("em.cli.stock_limit_pool_em", fake_pool)
    assert main(["--preset", "limitpool", "--pool-type", "broken", "--date", "20261106"]) == 0
    assert [(q.pool_type, q.date) for q in seen] == [("broken", "20261106")]
    assert "2026-11-06 炸板股池 共 0 只" in capsys.readouterr().out


def _change_items(n: int):
    from em.domain.models import StockChange

    return tuple(
        StockChange(time="14:55:04", code=f"{i:06d}", name="x", market="sz", change_type="big_buy")
        for i in range(n)
    )


def test_main_changes_passes_type_and_shows_first_20(monkeypatch, capsys) -> None:
    from em.domain.models import StockChangesPage
    from em.domain.queries import StockChangesQuery

    seen: list[StockChangesQuery] = []

    def fake_changes(query: StockChangesQuery) -> StockChangesPage:
        seen.append(query)
        return StockChangesPage(change_type=query.change_type, total=30, items=_change_items(30))

    monkeypatch.setattr("em.cli.stock_changes_em", fake_changes)
    assert main(["--preset", "changes", "--change-type", "high_dive"]) == 0
    assert [q.change_type for q in seen] == ["high_dive"]
    out = capsys.readouterr().out
    assert "高台跳水 共 30 条，展示 20 条" in out
    assert main(["--preset", "changes", "--head", "0"]) == 0
    assert "大笔买入 共 30 条，展示 30 条" in capsys.readouterr().out


def test_main_changes_rejects_unknown_type(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--preset", "changes", "--change-type", "大笔买入"])
    assert exc.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


def test_main_boardchanges_renders_time_and_top_types(monkeypatch, capsys) -> None:
    from em.domain.models import BoardChange, BoardChangesPage, ChangeTypeCount

    board = BoardChange(
        code="BK0596",
        name="融资融券",
        change_pct=-1.99,
        main_net_inflow=-50364710912.0,
        change_count=10998,
        top_stock_name="N森峰",
        top_stock_change_type=None,  # 未公开类型
        type_counts=(ChangeTypeCount("quick_rebound", 1903), ChangeTypeCount("big_buy", 984)),
    )
    page = BoardChangesPage(date="2026-11-06", time="15:00:00", total=1052, items=(board,))
    monkeypatch.setattr("em.cli.board_changes_em", lambda query: page)
    assert main(["--preset", "boardchanges"]) == 0
    out = capsys.readouterr().out
    assert "2026-11-06 15:00:00 板块异动 共 1052 个板块，展示 1 个" in out
    assert "-503.65亿" in out
    assert "最频繁:N森峰(-)" in out
    assert "前三类:快速反弹1903 / 大笔买入984" in out


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
        self.fixed_proxy = None


def test_is_egress_failure_classifies_correctly() -> None:
    assert is_egress_failure(NetworkError("conn")) is True
    assert is_egress_failure(EmptyResponseError("empty")) is True
    assert is_egress_failure(HttpStatusError(403)) is True
    assert is_egress_failure(HttpStatusError(429)) is True
    assert is_egress_failure(HttpStatusError(500)) is False
    assert is_egress_failure(HttpStatusError(404)) is False
    assert is_egress_failure(ConfigError("bad")) is False


def test_hint_ip_blocked_no_proxy(monkeypatch) -> None:
    monkeypatch.setattr("em.cli.Settings.from_env", lambda: _FakeSettings(False, "never"))
    hint = _hint_ip_blocked(NetworkError("连接断开"))
    assert hint is not None
    assert "封禁" in hint
    assert "EM_PROXY_API" in hint
    assert "EM_PROXY_ENABLED" in hint  # 说明代理是关着的
    assert ".env.example" not in hint  # 装完包后拿不到的文件不该出现在提示里


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
    assert "占位符" in hint


def test_hint_proxy_api_empty(monkeypatch) -> None:
    monkeypatch.setattr("em.cli.Settings.from_env", lambda: _FakeSettings(True, "auto", ""))
    hint = _hint_ip_blocked(NetworkError("连接断开"))
    assert hint is not None
    # 全新安装就是这个状态：必须说到封禁、最少配置项与生成模板的命令
    assert "封禁" in hint
    assert "EM_PROXY_API" in hint
    assert "EM_PROXY_NUM" in hint
    assert "--init-env" in hint


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
    queries: list[MarketQuery] = []

    def fake_all(query: MarketQuery) -> QuotePage:
        queries.append(query)
        return page

    monkeypatch.setattr("em.cli.stock_list_all_em", fake_all)
    rc = main(["--preset", "market-all", "--tail", "2"])
    assert rc == 0
    assert [q.scope for q in queries] == ["all"]
    out = capsys.readouterr().out
    assert "共 5580 条" in out
    assert "末 2 条" in out


def test_main_market_scope_is_passed_through(monkeypatch) -> None:
    seen: list[MarketQuery] = []

    def fake_list(query: MarketQuery) -> QuotePage:
        seen.append(query)
        return QuotePage(total=0, items=())

    monkeypatch.setattr("em.cli.stock_list_em", fake_list)
    monkeypatch.setattr("em.cli.stock_list_all_em", fake_list)
    assert main(["--preset", "market", "--scope", "kc", "--pz", "5"]) == 0
    assert main(["--preset", "market-all", "--scope", "st"]) == 0
    assert [(q.scope, q.size) for q in seen] == [("kc", 5), ("st", 20)]


def test_main_market_all_error_returns_1(monkeypatch, capsys) -> None:
    def boom(query: MarketQuery):
        raise NetworkError("连接被断开")

    monkeypatch.setattr("em.cli.stock_list_all_em", boom)
    monkeypatch.setattr("em.cli.Settings.from_env", lambda: _FakeSettings(True, "auto"))
    rc = main(["--preset", "market-all"])
    assert rc == 1
    assert "抓取失败" in capsys.readouterr().err


def test_main_billboard_passes_dates_and_renders(monkeypatch, capsys) -> None:
    from em.domain.models import BillboardEntry, ReportPage
    from em.domain.queries import BillboardDetailQuery

    seen: list[BillboardDetailQuery] = []
    entry = BillboardEntry(
        code="000525",
        name="红太阳",
        trade_date="2026-11-06",
        change_pct=10.0877,
        net_buy=98694262.06,
        billboard_turnover=199194268.48,
        reason="日涨幅偏离值达到7%的前5只证券",
    )

    def fake(query: BillboardDetailQuery) -> ReportPage[BillboardEntry]:
        seen.append(query)
        return ReportPage(total=79, items=(entry,))

    monkeypatch.setattr("em.cli.billboard_detail_em", fake)
    assert (
        main(["--preset", "billboard", "--start-date", "20261106", "--end-date", "20261106"]) == 0
    )
    assert [(q.start_date, q.end_date) for q in seen] == [("20261106", "20261106")]
    out = capsys.readouterr().out
    assert "龙虎榜详情 共 79 条，展示 1 条" in out
    assert "净买额:9869.43万" in out and "上榜原因:日涨幅偏离值达到7%的前5只证券" in out


def test_main_billboard_rejects_bad_dates(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--preset", "billboard", "--start-date", "20261106", "--end-date", "20261101"])
    assert exc.value.code == 2
    assert "晚于" in capsys.readouterr().err


# --- 库抛出的异常自带建议时：命令行只打印一遍 ---


def test_main_prints_library_hint_once(monkeypatch, capsys) -> None:
    def boom(_query):
        exc = NetworkError("连接被断开")
        exc.hint = "💡 来自库的建议"
        raise exc

    monkeypatch.setattr("em.cli.stock_kline_em", boom)
    # 配置看起来没问题：若命令行另算一遍就不会有建议，以此确认用的是异常自带的那条
    monkeypatch.setattr("em.cli.Settings.from_env", lambda: _FakeSettings(True, "auto"))
    assert main(["--preset", "kline", "--code", "000001"]) == 1
    err = capsys.readouterr().err
    assert "❌ 抓取失败：连接被断开\n" in err
    assert err.count("💡 来自库的建议") == 1


# --- --init-env：生成 .env 模板 ---


@pytest.fixture
def empty_cwd(tmp_path, monkeypatch, clean_em_env):
    from em.core import env

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(env, "_checkout_root", lambda: None)
    return tmp_path


def test_init_env_writes_the_packaged_template(empty_cwd, capsys) -> None:
    from em.core import env

    assert main(["--init-env"]) == 0
    target = empty_cwd / ".env"
    assert target.read_text(encoding="utf-8") == env.template_text()
    out = capsys.readouterr().out
    assert str(target) in out
    assert "EM_PROXY_API" in out
    assert "EM_PROXY_NUM" in out


@pytest.mark.skipif(not hasattr(__import__("os"), "getuid"), reason="POSIX 权限位")
def test_init_env_file_is_private_to_the_user(empty_cwd) -> None:
    # 文件里要填代理凭证：不给同机其他用户读
    assert main(["--init-env"]) == 0
    assert (empty_cwd / ".env").stat().st_mode & 0o077 == 0


def test_init_env_never_overwrites(empty_cwd, capsys) -> None:
    target = empty_cwd / ".env"
    target.write_text("EM_PROXY_API=http://real/credentials\n", encoding="utf-8")
    assert main(["--init-env"]) == 1
    assert target.read_text(encoding="utf-8") == "EM_PROXY_API=http://real/credentials\n"
    assert "已存在" in capsys.readouterr().err


def test_init_env_does_not_fetch_anything(empty_cwd, monkeypatch) -> None:
    def boom(*_a, **_k):
        raise AssertionError("--init-env 不应发起取数")

    monkeypatch.setattr("em.cli.board_constituent_em", boom)
    assert main(["--init-env"]) == 0


def test_init_env_honours_env_file_location(empty_cwd, monkeypatch) -> None:
    # 指定了 EM_ENV_FILE：模板写到自动加载会去读的那个位置，而不是运行目录
    target = empty_cwd / "conf.env"
    monkeypatch.setenv("EM_ENV_FILE", str(target))
    assert main(["--init-env"]) == 0
    assert target.is_file()
    assert not (empty_cwd / ".env").exists()


def test_init_env_warns_when_autoload_is_off(empty_cwd, monkeypatch, capsys) -> None:
    monkeypatch.setenv("EM_ENV_FILE", "none")
    assert main(["--init-env"]) == 0
    assert (empty_cwd / ".env").is_file()
    assert "不会被读取" in capsys.readouterr().err


def test_generated_env_is_loaded_by_the_next_run(empty_cwd) -> None:
    # 生成 → 下一次进程启动时自动加载：两头用的是同一个位置
    from em.core import env
    from em.core.settings import Settings

    assert main(["--init-env"]) == 0
    assert env.autoload() == empty_cwd / ".env"
    s = Settings.from_env()
    assert "YOUR_UID" in s.proxy_api
    assert s.proxy_num == 5

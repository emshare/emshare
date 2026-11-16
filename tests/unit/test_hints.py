"""出口失败提示的行为锁：什么时候给、给什么、库调用是否也能看到（不触网）。"""

from unittest.mock import MagicMock

import pytest
import requests

from em.application import market_data
from em.application.hints import egress_hint, is_egress_failure
from em.core import env
from em.core.errors import (
    ConfigError,
    EmError,
    EmptyResponseError,
    HttpStatusError,
    InvalidContentError,
    NetworkError,
    QueryRejectedError,
)
from em.core.proxy import ProxyPool, ProxyRouter, ProxySettings
from em.core.resilience import RetryPolicy
from em.core.settings import Settings
from em.core.transport import HttpClient
from em.domain.queries import KlineQuery

_REAL_API = "http://api.example.com/get?uid=real&vkey=real&num=5"
_PLACEHOLDER_API = "http://api.xiequ.cn/VAD/GetIp.aspx?uid=YOUR_UID&vkey=YOUR_VKEY&num=5"


@pytest.fixture(autouse=True)
def _isolated(clean_em_env, tmp_path, monkeypatch):
    """提示里会写 .env 的查找位置 / 已加载文件：固定在空目录里，不受开发机现状影响。"""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(env, "_checkout_root", lambda: None)


# --- 何时给提示 ---


@pytest.mark.parametrize(
    "exc",
    [NetworkError("断开"), EmptyResponseError("空"), HttpStatusError(403), HttpStatusError(429)],
)
def test_hint_for_egress_failures_without_proxy_source(exc: EmError) -> None:
    assert is_egress_failure(exc)
    assert egress_hint(exc, Settings()) is not None


@pytest.mark.parametrize(
    "exc",
    [
        HttpStatusError(500),
        HttpStatusError(404),
        InvalidContentError("劫持页"),
        QueryRejectedError("报表不存在"),
        ConfigError("bad"),
        ValueError("x"),
    ],
)
def test_no_hint_for_other_failures(exc: Exception) -> None:
    assert egress_hint(exc, Settings()) is None


def test_no_hint_when_a_real_proxy_source_is_configured() -> None:
    # 代理配好了仍失败（代理全死、额度用尽）不是"缺配置"，不能误导去改配置
    assert egress_hint(NetworkError("断开"), Settings(proxy_api=_REAL_API)) is None


def test_no_hint_when_backup_source_is_real() -> None:
    # 主源还是占位符、备用源是真的：代理能用，不提示
    settings = Settings(proxy_api=f"{_PLACEHOLDER_API},{_REAL_API}")
    assert egress_hint(NetworkError("断开"), settings) is None


# --- 提示内容：三种"代理用不上"的原因各说各的 ---


def test_missing_source_says_what_to_configure() -> None:
    hint = egress_hint(HttpStatusError(403), Settings(), host="push2his.eastmoney.com")
    assert hint is not None
    assert "push2his.eastmoney.com" in hint
    assert "封禁" in hint
    assert "全部走直连" in hint
    assert "EM_PROXY_API=" in hint
    assert "ip:port" in hint  # 接口返回格式
    assert "EM_PROXY_NUM=" in hint
    assert "emshare --init-env" in hint
    assert "import em" in hint  # 说明库调用也会读 .env
    assert ".env.example" not in hint  # 装完包后拿不到的文件


def test_placeholder_source_is_called_out() -> None:
    hint = egress_hint(NetworkError("断开"), Settings(proxy_api=_PLACEHOLDER_API))
    assert hint is not None
    assert "占位符" in hint
    assert "YOUR_UID" in hint
    assert "--init-env" not in hint  # 文件已经有了，不该再叫人生成
    assert "直连" not in hint  # 占位符源仍会被拿去回源，不能断言全程直连


@pytest.mark.parametrize(
    "settings",
    [
        Settings(proxy_api=_REAL_API, proxy_enabled=False),
        Settings(proxy_api=_REAL_API, proxy_mode="never"),
    ],
)
def test_disabled_proxy_is_called_out(settings: Settings) -> None:
    hint = egress_hint(NetworkError("断开"), settings)
    assert hint is not None
    assert "关闭" in hint
    assert "EM_PROXY_ENABLED=1" in hint
    assert "EM_PROXY_MODE=auto" in hint


# --- 提示里对 .env 现状的说明 ---


def test_hint_lists_where_env_was_looked_for(tmp_path) -> None:
    hint = egress_hint(NetworkError("断开"), Settings())
    assert hint is not None
    assert "未找到 .env" in hint
    assert str(tmp_path / ".env") in hint


def test_hint_names_the_loaded_env_file(tmp_path) -> None:
    (tmp_path / ".env").write_text("EM_PROXY_ENABLED=0\n", encoding="utf-8")
    env.autoload()
    hint = egress_hint(NetworkError("断开"), Settings.from_env())
    assert hint is not None
    assert f"当前已加载：{tmp_path / '.env'}" in hint
    assert "未找到" not in hint


def test_hint_flags_env_file_without_em_keys(tmp_path) -> None:
    # 运行目录下的 .env 是别的项目的：文件读到了，但里面没有本库的配置
    (tmp_path / ".env").write_text("DATABASE_URL_7F3A=postgres://x\n", encoding="utf-8")
    env.autoload()
    hint = egress_hint(NetworkError("断开"), Settings.from_env())
    assert hint is not None
    assert "没有 EM_ 开头的配置项" in hint


def test_hint_says_when_autoload_is_switched_off(monkeypatch) -> None:
    monkeypatch.setenv("EM_ENV_FILE", "none")
    hint = egress_hint(NetworkError("断开"), Settings())
    assert hint is not None
    assert "EM_ENV_FILE" in hint
    assert "未找到" not in hint


# --- 异常自带提示：str() 能看到，args 不变 ---


def test_hint_is_appended_to_str_but_not_to_args() -> None:
    exc = HttpStatusError(403)
    assert str(exc) == "HTTP 403"
    exc.hint = "💡 建议"
    assert str(exc) == "HTTP 403\n💡 建议"
    assert exc.args == ("HTTP 403",)
    assert exc.status_code == 403


def test_errors_have_no_hint_by_default() -> None:
    assert NetworkError("x").hint is None
    assert str(ConfigError("bad")) == "bad"


# --- 传输层：重试耗尽时才要提示 ---


def _client(session: MagicMock, hint, max_retries: int = 2) -> HttpClient:
    ps = ProxySettings(api="", mode="auto")
    router = ProxyRouter(ProxyPool(ps, MagicMock(spec=requests.Session)), ps)
    policy = RetryPolicy(max_retries=max_retries, backoff_sec=0.0, connect_backoff_sec=0.0)
    return HttpClient(session, router, policy, exhausted_hint=hint)


def test_transport_attaches_hint_once_retries_are_exhausted() -> None:
    session = MagicMock(spec=requests.Session)
    session.get.side_effect = requests.ConnectionError("boom")
    seen: list[tuple[str, str]] = []

    def hint(host: str, exc: Exception) -> str:
        seen.append((host, type(exc).__name__))
        return "💡 配代理"

    with pytest.raises(NetworkError) as info:
        _client(session, hint).get_text("https://push2his.eastmoney.com/api", {}, {})
    assert info.value.hint == "💡 配代理"
    assert str(info.value).endswith("\n💡 配代理")
    assert seen == [("push2his.eastmoney.com", "ProxyConnectError")]  # 只在最后问一次
    assert session.get.call_count == 3


def test_transport_does_not_ask_for_hint_on_success_or_non_retryable() -> None:
    hint = MagicMock(return_value="💡")
    ok = MagicMock(spec=requests.Session)
    ok.get.return_value = MagicMock(status_code=200, text='{"rc":0}')
    assert _client(ok, hint).get_text("https://h/x", {}, {}) == '{"rc":0}'
    not_found = MagicMock(spec=requests.Session)
    not_found.get.return_value = MagicMock(status_code=404, text="")
    with pytest.raises(HttpStatusError) as info:
        _client(not_found, hint).get_text("https://h/x", {}, {})
    assert info.value.hint is None
    hint.assert_not_called()


def test_transport_without_hint_callback_behaves_as_before() -> None:
    session = MagicMock(spec=requests.Session)
    session.get.side_effect = requests.ConnectionError("boom")
    with pytest.raises(NetworkError) as info:
        _client(session, None).get_text("https://h/x", {}, {})
    assert info.value.hint is None
    assert str(info.value) == "boom"


# --- 端到端：库调用（不经过命令行）在全新配置下被封，异常里就有指引 ---


def _blocked(monkeypatch: pytest.MonkeyPatch, response) -> None:
    def fake_get(self, url, **kwargs):
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(requests.Session, "get", fake_get)
    monkeypatch.setattr("em.core.budget.time.sleep", lambda _s: None)
    market_data._reset_client_cache()


@pytest.mark.parametrize(
    "response",
    [requests.ConnectionError("Connection aborted."), MagicMock(status_code=403, text="")],
    ids=["disconnect", "http403"],
)
def test_library_call_error_carries_the_hint(monkeypatch, caplog, response) -> None:
    _blocked(monkeypatch, response)
    try:
        with caplog.at_level("WARNING"), pytest.raises(EmError) as info:
            market_data.stock_kline_em(KlineQuery(code="000001", market="sz"), Settings())
    finally:
        market_data._reset_client_cache()
    text = str(info.value)
    assert "push2his.eastmoney.com" in text
    assert "封禁" in text
    assert "EM_PROXY_API=" in text
    assert "EM_PROXY_NUM=" in text
    assert "emshare --init-env" in text
    # 没有代理可换时，重试日志不能再说"换 IP"
    retry_logs = [r.getMessage() for r in caplog.records if "请求失败" in r.getMessage()]
    assert retry_logs
    assert all("换 IP" not in m for m in retry_logs)


def test_library_call_error_has_no_hint_when_proxy_source_is_configured(monkeypatch) -> None:
    # 配了代理源：直连失败后切代理，代理也全失败——这时不该再提示"去配代理"
    def fake_get(self, url, **kwargs):
        if "eastmoney.com" in url:
            raise requests.ConnectionError("Connection aborted.")
        return MagicMock(status_code=200, text="10.0.0.1:8080\n10.0.0.2:8080")

    monkeypatch.setattr(requests.Session, "get", fake_get)
    monkeypatch.setattr("em.core.budget.time.sleep", lambda _s: None)
    monkeypatch.setattr("em.core.proxy.time.sleep", lambda _s: None)
    monkeypatch.setenv("EM_LEDGER_PATH", "none")
    settings = Settings(proxy_api=_REAL_API, proxy_prefilter=False, max_retries=3)
    market_data._reset_client_cache()
    try:
        with pytest.raises(EmError) as info:
            market_data.stock_kline_em(KlineQuery(code="000001", market="sz"), settings)
    finally:
        market_data._reset_client_cache()
    assert info.value.hint is None
    assert "EM_PROXY_API" not in str(info.value)

"""Settings.from_env 行为锁：退避参数可从环境变量读取并校验。"""

import os

import pytest

from em.core.errors import ConfigError
from em.core.settings import Settings


def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in list(os.environ):
        if k.startswith("EM_"):
            monkeypatch.delenv(k, raising=False)


def test_defaults_apply_when_env_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    s = Settings.from_env()
    assert s.backoff_sec == pytest.approx(0.2)
    assert s.backoff_cap_sec == pytest.approx(2.0)


def test_backoff_cap_read_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("EM_BACKOFF_SEC", "0.5")
    monkeypatch.setenv("EM_BACKOFF_CAP_SEC", "1.5")
    s = Settings.from_env()
    assert s.backoff_sec == pytest.approx(0.5)
    assert s.backoff_cap_sec == pytest.approx(1.5)


def test_backoff_cap_none_disables_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("EM_BACKOFF_CAP_SEC", "none")
    s = Settings.from_env()
    assert s.backoff_cap_sec is None


def test_invalid_backoff_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("EM_BACKOFF_SEC", "abc")
    with pytest.raises(ConfigError):
        Settings.from_env()


def test_negative_cap_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("EM_BACKOFF_CAP_SEC", "-1")
    with pytest.raises(ConfigError):
        Settings.from_env()


def test_multi_source_apis_joined_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    # 多源代理：EM_PROXY_API 为主源，EM_PROXY_API_* 后缀 KEY 按名排序拼接为备用源
    _clear_env(monkeypatch)
    monkeypatch.setenv("EM_PROXY_API", "http://primary/get")
    monkeypatch.setenv("EM_PROXY_API_BACKUP", "http://backup/get")
    monkeypatch.setenv("EM_PROXY_API_BACKUP2", "http://backup2/get")
    s = Settings.from_env()
    assert s.proxy_api == "http://primary/get,http://backup/get,http://backup2/get"


def test_multi_source_apis_blank_parts_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    # 主源未设/备用为空串时被过滤，不产生空源；仅备用也可独立生效
    _clear_env(monkeypatch)
    monkeypatch.setenv("EM_PROXY_API_BACKUP", " http://backup/get ")
    s = Settings.from_env()
    assert s.proxy_api == "http://backup/get"


def test_multi_source_apis_absent_keeps_default(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    s = Settings.from_env()
    assert s.proxy_api == ""

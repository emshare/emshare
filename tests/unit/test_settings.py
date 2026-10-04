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

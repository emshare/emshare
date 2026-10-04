"""配置：从环境变量读取，集中默认值；构造期做 fail-fast 校验。"""

import os
from dataclasses import dataclass
from typing import Literal

from em.core import defaults
from em.core.errors import ConfigError

ProxyMode = Literal["auto", "always", "never"]
_VALID_MODES = ("auto", "always", "never")


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} 必须是整数，实际为 {raw!r}") from exc


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} 必须是数值，实际为 {raw!r}") from exc


def _float_env_or_none(name: str, default: float | None) -> float | None:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    if raw.strip().lower() in ("none", "null"):
        return None
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} 必须是数值，实际为 {raw!r}") from exc


def _mode_env(name: str, default: ProxyMode) -> ProxyMode:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    val = raw.strip().lower()
    if val not in _VALID_MODES:
        raise ConfigError(f"{name} 必须是 {','.join(_VALID_MODES)}，实际为 {raw!r}")
    return val  # type: ignore[return-value]


@dataclass(frozen=True)
class Settings:
    """运行期配置。优先级：环境变量 > 代码默认值。"""

    proxy_api: str = defaults.DEFAULT_PROXY_API
    proxy_enabled: bool = True
    proxy_num: int = 1
    proxy_ttl_sec: int = 30
    proxy_safety_margin_sec: int = 3
    proxy_timeout_sec: int = 8
    proxy_mode: ProxyMode = "auto"
    proxy_direct_fails: int = 3
    proxy_proxy_successes: int = 5
    proxy_cooldown_sec: int = 300
    request_timeout_sec: int = defaults.DEFAULT_TIMEOUT_SEC
    max_retries: int = defaults.DEFAULT_MAX_RETRIES
    backoff_sec: float = defaults.DEFAULT_BACKOFF_SEC
    backoff_cap_sec: float | None = defaults.DEFAULT_BACKOFF_CAP_SEC

    def __post_init__(self) -> None:
        if self.proxy_num < 1:
            raise ConfigError("proxy_num 必须 >= 1")
        if self.proxy_ttl_sec <= self.proxy_safety_margin_sec:
            raise ConfigError("proxy_ttl_sec 必须大于 proxy_safety_margin_sec")
        if self.proxy_mode not in _VALID_MODES:
            raise ConfigError(f"proxy_mode 必须是 {','.join(_VALID_MODES)}")
        if self.proxy_direct_fails < 1:
            raise ConfigError("proxy_direct_fails 必须 >= 1")
        if self.proxy_proxy_successes < 1:
            raise ConfigError("proxy_proxy_successes 必须 >= 1")
        if self.proxy_cooldown_sec < 0:
            raise ConfigError("proxy_cooldown_sec 不能为负")
        if self.max_retries < 0:
            raise ConfigError("max_retries 不能为负")
        if self.backoff_sec < 0:
            raise ConfigError("backoff_sec 不能为负")
        if self.backoff_cap_sec is not None and self.backoff_cap_sec < 0:
            raise ConfigError("backoff_cap_sec 不能为负")

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            proxy_api=os.getenv("EM_PROXY_API", defaults.DEFAULT_PROXY_API),
            proxy_enabled=_bool_env("EM_PROXY_ENABLED", True),
            proxy_num=_int_env("EM_PROXY_NUM", 1),
            proxy_ttl_sec=_int_env("EM_PROXY_TTL_SEC", 30),
            proxy_safety_margin_sec=_int_env("EM_PROXY_SAFETY_MARGIN_SEC", 3),
            proxy_timeout_sec=_int_env("EM_PROXY_TIMEOUT_SEC", 8),
            proxy_mode=_mode_env("EM_PROXY_MODE", "auto"),
            proxy_direct_fails=_int_env("EM_PROXY_DIRECT_FAILS", 3),
            proxy_proxy_successes=_int_env("EM_PROXY_PROXY_SUCCESSES", 5),
            proxy_cooldown_sec=_int_env("EM_PROXY_COOLDOWN_SEC", 300),
            request_timeout_sec=_int_env("EM_REQUEST_TIMEOUT_SEC", defaults.DEFAULT_TIMEOUT_SEC),
            max_retries=_int_env("EM_MAX_RETRIES", defaults.DEFAULT_MAX_RETRIES),
            backoff_sec=_float_env("EM_BACKOFF_SEC", defaults.DEFAULT_BACKOFF_SEC),
            backoff_cap_sec=_float_env_or_none(
                "EM_BACKOFF_CAP_SEC", defaults.DEFAULT_BACKOFF_CAP_SEC
            ),
        )

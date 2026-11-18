"""配置：从环境变量读取，集中默认值；构造期做 fail-fast 校验。"""

import math
import os
from dataclasses import dataclass, field
from typing import Literal

from em.core import defaults
from em.core.errors import ConfigError
from em.core.fixed_proxy import validate_proxy_url

ProxyMode = Literal["auto", "always", "never"]
_VALID_MODES = ("auto", "always", "never")
DegradedMode = Literal["adopt", "lenient"]
_VALID_DEGRADED = ("adopt", "lenient")


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


def _degraded_env(name: str, default: DegradedMode) -> DegradedMode:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    val = raw.strip().lower()
    if val not in _VALID_DEGRADED:
        raise ConfigError(f"{name} 必须是 {','.join(_VALID_DEGRADED)}，实际为 {raw!r}")
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
    proxy_prefilter: bool = defaults.DEFAULT_PROXY_PREFILTER
    proxy_prefilter_sources: int = 1
    # 预筛探到这么多个活 IP 就停，其余留作预留按需再探；0 = 整批全探
    proxy_prefilter_target: int = 1
    proxy_degraded_mode: DegradedMode = "lenient"
    proxy_direct_fails: int = 1
    proxy_proxy_successes: int = 5
    proxy_cooldown_sec: int = 300
    request_timeout_sec: int = defaults.DEFAULT_TIMEOUT_SEC
    request_connect_timeout_sec: int = defaults.DEFAULT_CONNECT_TIMEOUT_SEC
    request_dynamic_timeout: bool = defaults.DEFAULT_REQUEST_DYNAMIC_TIMEOUT
    max_retries: int = defaults.DEFAULT_MAX_RETRIES
    backoff_sec: float = defaults.DEFAULT_BACKOFF_SEC
    backoff_cap_sec: float | None = defaults.DEFAULT_BACKOFF_CAP_SEC
    backoff_jitter_sec: float = defaults.DEFAULT_BACKOFF_JITTER_SEC
    proxy_url: str = field(default="", repr=False)

    def __post_init__(self) -> None:
        validate_proxy_url(self.proxy_url)
        if self.proxy_url and self.proxy_api.strip():
            raise ConfigError("proxy_url 与 proxy_api（含备用源）不能同时配置")
        if self.request_timeout_sec <= 0 or self.proxy_timeout_sec <= 0:
            raise ConfigError("请求与代理超时必须为正")
        if self.proxy_safety_margin_sec < 0:
            raise ConfigError("proxy_safety_margin_sec 不能为负")
        for value in (self.backoff_sec, self.backoff_cap_sec, self.backoff_jitter_sec):
            if value is not None and not math.isfinite(value):
                raise ConfigError("退避参数必须是有限数值")
        if self.proxy_num < 1:
            raise ConfigError("proxy_num 必须 >= 1")
        if self.proxy_ttl_sec <= self.proxy_safety_margin_sec:
            raise ConfigError("proxy_ttl_sec 必须大于 proxy_safety_margin_sec")
        if self.proxy_mode not in _VALID_MODES:
            raise ConfigError(f"proxy_mode 必须是 {','.join(_VALID_MODES)}")
        if self.proxy_prefilter_sources < 0:
            raise ConfigError("proxy_prefilter_sources 不能为负")
        if self.proxy_prefilter_target < 0:
            raise ConfigError("proxy_prefilter_target 不能为负")
        if self.proxy_degraded_mode not in _VALID_DEGRADED:
            raise ConfigError(f"proxy_degraded_mode 必须是 {','.join(_VALID_DEGRADED)}")
        if self.proxy_direct_fails < 1:
            raise ConfigError("proxy_direct_fails 必须 >= 1")
        if self.proxy_proxy_successes < 1:
            raise ConfigError("proxy_proxy_successes 必须 >= 1")
        if self.proxy_cooldown_sec < 0:
            raise ConfigError("proxy_cooldown_sec 不能为负")
        if self.request_connect_timeout_sec <= 0:
            raise ConfigError("request_connect_timeout_sec 必须为正")
        if self.max_retries < 0:
            raise ConfigError("max_retries 不能为负")
        if self.backoff_sec < 0:
            raise ConfigError("backoff_sec 不能为负")
        if self.backoff_cap_sec is not None and self.backoff_cap_sec < 0:
            raise ConfigError("backoff_cap_sec 不能为负")
        if self.backoff_jitter_sec < 0:
            raise ConfigError("backoff_jitter_sec 不能为负")

    @property
    def fixed_proxy(self) -> str | None:
        """实际启用的固定出口；never 和总开关优先。"""
        return (
            self.proxy_url
            if self.proxy_url and self.proxy_enabled and self.proxy_mode != "never"
            else None
        )

    @classmethod
    def from_env(cls) -> "Settings":
        # 多源代理：EM_PROXY_API 为主源，EM_PROXY_API_* 后缀 KEY（如 _BACKUP）按名拼接为备用源，
        # 逗号分隔传给代理池；每个源独立一行便于维护，注释掉某行即可停用该源
        apis = [os.getenv("EM_PROXY_API", defaults.DEFAULT_PROXY_API)]
        apis += [v for k, v in sorted(os.environ.items()) if k.startswith("EM_PROXY_API_")]
        return cls(
            proxy_url=os.getenv("EM_PROXY_URL", "").strip(),
            proxy_api=",".join(p.strip() for p in apis if p.strip()),
            proxy_enabled=_bool_env("EM_PROXY_ENABLED", True),
            proxy_num=_int_env("EM_PROXY_NUM", 1),
            proxy_ttl_sec=_int_env("EM_PROXY_TTL_SEC", 30),
            proxy_safety_margin_sec=_int_env("EM_PROXY_SAFETY_MARGIN_SEC", 3),
            proxy_timeout_sec=_int_env("EM_PROXY_TIMEOUT_SEC", 8),
            proxy_mode=_mode_env("EM_PROXY_MODE", "auto"),
            proxy_prefilter=_bool_env("EM_PROXY_PREFILTER", defaults.DEFAULT_PROXY_PREFILTER),
            proxy_prefilter_sources=_int_env("EM_PROXY_PREFILTER_SOURCES", 1),
            proxy_prefilter_target=_int_env("EM_PROXY_PREFILTER_TARGET", 1),
            proxy_degraded_mode=_degraded_env("EM_PROXY_DEGRADED_MODE", "lenient"),
            proxy_direct_fails=_int_env("EM_PROXY_DIRECT_FAILS", 1),
            proxy_proxy_successes=_int_env("EM_PROXY_PROXY_SUCCESSES", 5),
            proxy_cooldown_sec=_int_env("EM_PROXY_COOLDOWN_SEC", 300),
            request_timeout_sec=_int_env("EM_REQUEST_TIMEOUT_SEC", defaults.DEFAULT_TIMEOUT_SEC),
            request_connect_timeout_sec=_int_env(
                "EM_REQUEST_CONNECT_TIMEOUT_SEC", defaults.DEFAULT_CONNECT_TIMEOUT_SEC
            ),
            request_dynamic_timeout=_bool_env(
                "EM_REQUEST_DYNAMIC_TIMEOUT", defaults.DEFAULT_REQUEST_DYNAMIC_TIMEOUT
            ),
            max_retries=_int_env("EM_MAX_RETRIES", defaults.DEFAULT_MAX_RETRIES),
            backoff_sec=_float_env("EM_BACKOFF_SEC", defaults.DEFAULT_BACKOFF_SEC),
            backoff_cap_sec=_float_env_or_none(
                "EM_BACKOFF_CAP_SEC", defaults.DEFAULT_BACKOFF_CAP_SEC
            ),
            backoff_jitter_sec=_float_env(
                "EM_BACKOFF_JITTER_SEC", defaults.DEFAULT_BACKOFF_JITTER_SEC
            ),
        )

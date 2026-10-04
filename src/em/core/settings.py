"""配置：从环境变量读取，集中默认值；构造期做 fail-fast 校验。"""

import os
from dataclasses import dataclass

from em.core import defaults
from em.core.errors import ConfigError


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


@dataclass(frozen=True)
class Settings:
    """运行期配置。优先级：环境变量 > 代码默认值。"""

    proxy_api: str = defaults.DEFAULT_PROXY_API
    proxy_enabled: bool = True
    proxy_num: int = 1
    proxy_ttl_sec: int = 30
    proxy_safety_margin_sec: int = 3
    proxy_timeout_sec: int = 8
    request_timeout_sec: int = defaults.DEFAULT_TIMEOUT_SEC
    max_retries: int = defaults.DEFAULT_MAX_RETRIES
    backoff_sec: float = defaults.DEFAULT_BACKOFF_SEC

    def __post_init__(self) -> None:
        if self.proxy_num < 1:
            raise ConfigError("proxy_num 必须 >= 1")
        if self.proxy_ttl_sec <= self.proxy_safety_margin_sec:
            raise ConfigError("proxy_ttl_sec 必须大于 proxy_safety_margin_sec")
        if self.max_retries < 0:
            raise ConfigError("max_retries 不能为负")

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            proxy_api=os.getenv("EM_PROXY_API", defaults.DEFAULT_PROXY_API),
            proxy_enabled=_bool_env("EM_PROXY_ENABLED", True),
            proxy_num=_int_env("EM_PROXY_NUM", 1),
            proxy_ttl_sec=_int_env("EM_PROXY_TTL_SEC", 30),
            proxy_safety_margin_sec=_int_env("EM_PROXY_SAFETY_MARGIN_SEC", 3),
            request_timeout_sec=_int_env("EM_REQUEST_TIMEOUT_SEC", defaults.DEFAULT_TIMEOUT_SEC),
            max_retries=_int_env("EM_MAX_RETRIES", defaults.DEFAULT_MAX_RETRIES),
        )

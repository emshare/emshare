"""动态代理池：TTL 内复用、失败即淘汰换 IP、池内备选。

与 LoongSoar 的 ProxyPool 同构，但只保留抓取所需的判据（不引入连接层跨 origin 启发式）。
"""

import logging
import re
import time
from dataclasses import dataclass

import requests

from em.core.errors import ConfigError

log = logging.getLogger(__name__)

_PROXY_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}:\d+$")


@dataclass(frozen=True)
class ProxySettings:
    api: str
    enabled: bool = True
    num: int = 1
    ttl_sec: int = 30
    safety_margin_sec: int = 3
    timeout_sec: int = 8

    def __post_init__(self) -> None:
        if self.num < 1:
            raise ConfigError("num 必须 >= 1")
        if self.ttl_sec <= self.safety_margin_sec:
            raise ConfigError("ttl_sec 必须大于 safety_margin_sec")


def fetch_proxies(settings: ProxySettings, session: requests.Session) -> list[str]:
    """从代理源取一批 'ip:port'；失败返回空列表（退化直连，不抛异常）。"""
    try:
        text = session.get(settings.api, timeout=settings.timeout_sec).text.strip()
    except requests.RequestException as exc:
        log.debug("获取代理失败: %s", exc)
        return []
    lines = [ln.strip() for ln in text.splitlines() if _PROXY_RE.match(ln.strip())]
    return lines[: settings.num]


class ProxyPool:
    """短效动态代理池。``enabled=False`` 时 ``acquire`` 返回 None（走直连）。"""

    def __init__(self, settings: ProxySettings, session: requests.Session) -> None:
        self._settings = settings
        self._session = session
        self._current: str | None = None
        self._fetched_at = 0.0
        self._standby: list[str] = []

    @property
    def enabled(self) -> bool:
        return self._settings.enabled

    def acquire(self) -> str | None:
        """取一个可用代理 'ip:port'；不可用或关闭时返回 None。"""
        if not self._settings.enabled:
            return None
        if self._is_live(self._current):
            return self._current
        return self._refill() or self._take_standby()

    def report_failure(self, proxy: str | None) -> None:
        """上报失败：淘汰当前与备用中的同 IP，下次请求换新 IP。"""
        if proxy is not None and proxy == self._current:
            self._current = None
        if proxy is not None:
            self._standby = [p for p in self._standby if p != proxy]

    def _is_live(self, proxy: str | None) -> bool:
        if not proxy:
            return False
        expire_at = self._fetched_at + self._settings.ttl_sec - self._settings.safety_margin_sec
        return time.monotonic() < expire_at

    def _refill(self) -> str | None:
        fetched = fetch_proxies(self._settings, self._session)
        if not fetched:
            return None
        self._current = fetched[0]
        self._standby = fetched[1:]
        self._fetched_at = time.monotonic()
        return self._current

    def _take_standby(self) -> str | None:
        if self._standby:
            self._current = self._standby.pop(0)
            return self._current
        return None

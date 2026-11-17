"""固定出口路由：没有采购、TTL、淘汰或自动换 IP；与动态池共用传输层。"""

from typing import Any
from urllib.parse import urlsplit

from em.core.errors import ConfigError


def validate_proxy_url(value: str) -> None:
    """仅接受 HTTP(S) 代理服务器 URL；报错不回显可能含认证信息的输入。"""
    if not value:
        return
    try:
        parsed = urlsplit(value)
        valid = (
            parsed.scheme in ("http", "https")
            and bool(parsed.hostname)
            and parsed.port is not None
            and 0 < parsed.port <= 65535
            and parsed.path in ("", "/")
            and not parsed.query
            and not parsed.fragment
            and not any(c.isspace() for c in value)
            and (parsed.username is None or bool(parsed.username))
        )
    except ValueError:
        valid = False
    if not valid:
        raise ConfigError("proxy_url 必须是 http(s)://[用户:密码@]主机:端口，不允许查询参数或路径")


class FixedProxyRouter:
    """显式固定出口；proxy=None 用于总开关关闭或 never，不回退采购。"""

    can_rotate = False

    def __init__(self, proxy: str | None) -> None:
        self._proxy = proxy

    def acquire(self, host: str, min_lifetime: float = 0.0) -> str | None:
        return self._proxy

    def available(self, host: str) -> int:
        return int(self._proxy is not None)

    def hold(self, proxy: str | None, min_lifetime: float = 0.0) -> bool:
        return proxy is not None and proxy == self._proxy

    def remaining_lifetime(self, proxy: str) -> float:
        return float("inf")

    def lifetime_requirement(self, requested: float) -> float:
        return requested

    def report_result(
        self, host: str, proxy: str | None, success: bool, banned: bool = False, soft: bool = False
    ) -> None:
        pass

    def abandon(self, host: str, proxy: str | None) -> None:
        pass

    def release(self, proxy: str | None) -> None:
        pass

    def report_proxy_failure(self, proxy: str | None) -> None:
        # 固定地址不能淘汰后采购替代者；业务端仍可报告旧快照并按页级上限退出。
        pass

    def close(self) -> None:
        pass

    def stats(self) -> dict[str, Any]:
        # 不输出地址/认证信息，也不冒充动态池采购或供应商计费。
        return {"pool": {"route_kind": "fixed" if self._proxy else "direct"}}

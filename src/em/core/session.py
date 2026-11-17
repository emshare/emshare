"""统一网络会话策略与有界代理连接管理器。"""

import os
import threading
from collections import OrderedDict
from typing import Any

import requests


class ExplicitProxySession(requests.Session):  # noqa: TID251 -- 唯一受控的底层会话继承点
    """只使用显式代理，直连及重定向不读取环境/系统代理。

    trust_env 同时关闭隐式 netrc 认证；单独保留 requests 的环境 CA 规则：
    请求未指定 verify 或为 True 时，REQUESTS_CA_BUNDLE 优先于 CURL_CA_BUNDLE，
    每次请求读取。显式 verify 路径/False 与 Session 设置继续由 requests 合并。
    """

    def __init__(self) -> None:
        super().__init__()
        self.trust_env = False

    def merge_environment_settings(
        self,
        url: str,
        proxies: dict[str, str] | None,
        stream: bool | None,
        verify: Any,
        cert: Any,
    ) -> dict[str, Any]:
        if verify is True or verify is None:
            verify = (
                os.environ.get("REQUESTS_CA_BUNDLE") or os.environ.get("CURL_CA_BUNDLE") or verify
            )
        return super().merge_environment_settings(url, proxies, stream, verify, cert)


class BoundedProxyAdapter(requests.adapters.HTTPAdapter):
    def __init__(self, proxy_limit: int = 32, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._proxy_limit = proxy_limit
        self._manager_lock = threading.RLock()
        self._recent: OrderedDict[str, None] = OrderedDict()
        self._active: dict[str, int] = {}

    def proxy_manager_for(self, proxy: str, **proxy_kwargs: Any) -> Any:
        with self._manager_lock:
            manager = super().proxy_manager_for(proxy, **proxy_kwargs)
            self._recent[proxy] = None
            self._recent.move_to_end(proxy)
            self._trim()
            return manager

    def _trim(self) -> None:
        for proxy in list(self._recent):
            if len(self.proxy_manager) <= self._proxy_limit:
                break
            if self._active.get(proxy, 0):
                continue
            self._recent.pop(proxy, None)
            manager = self.proxy_manager.pop(proxy, None)
            if manager is not None:
                manager.clear()

    def send(
        self,
        request: requests.PreparedRequest,
        stream: bool = False,
        timeout: Any = None,
        verify: Any = True,
        cert: Any = None,
        proxies: Any = None,
    ) -> requests.Response:
        proxy = requests.utils.select_proxy(request.url or "", proxies)
        with self._manager_lock:
            if proxy:
                self._active[proxy] = self._active.get(proxy, 0) + 1
        try:
            response = super().send(request, stream, timeout, verify, cert, proxies)
            if not stream:
                try:
                    _ = response.content
                except Exception:
                    response.close()
                    raise
            return response
        finally:
            with self._manager_lock:
                if proxy:
                    count = self._active[proxy] - 1
                    if count:
                        self._active[proxy] = count
                    else:
                        self._active.pop(proxy)
                self._trim()

    def close(self) -> None:
        with self._manager_lock:
            super().close()
            self.proxy_manager.clear()
            self._recent.clear()

"""限制短效代理连接管理器数量，并保留仍在使用的连接。"""

import threading
from collections import OrderedDict
from typing import Any

import requests


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

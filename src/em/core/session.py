"""统一网络会话策略与有界代理连接管理器。"""

import os
import threading
from collections import OrderedDict
from collections.abc import Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar

import requests
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool

_P = ParamSpec("_P")
_T = TypeVar("_T")
_PHASES = frozenset(
    {
        "tcp",
        "proxy_connect",
        "proxy_tls",
        "tls",
        "request_send",
        "response_headers",
        "response_body",
    }
)


def network_failure_phase(error: BaseException) -> str:
    """沿实际异常链读取受控连接标记，不解析异常文案或用耗时猜阶段。"""
    pending = [error]
    visited: set[int] = set()
    while pending:
        cause = pending.pop()
        if id(cause) in visited:
            continue
        visited.add(id(cause))
        phase = getattr(cause, "_em_network_phase", None)
        if isinstance(phase, str) and phase in _PHASES:
            return phase
        pending.extend(value for value in cause.args if isinstance(value, BaseException))
        if cause.__context__ is not None:
            pending.append(cause.__context__)
        if cause.__cause__ is not None:
            pending.append(cause.__cause__)
    return "unknown"


def _at_phase(phase: str) -> Callable[[Callable[_P, _T]], Callable[_P, _T]]:
    def decorate(method: Callable[_P, _T]) -> Callable[_P, _T]:
        @wraps(method)
        def tracked(*args: _P.args, **kwargs: _P.kwargs) -> _T:
            try:
                return method(*args, **kwargs)
            except Exception as error:
                # 内层 TCP/CONNECT 标记比外层 connect/request/getresponse 更准确。
                observed = getattr(error, "_em_network_phase", None)
                if not isinstance(observed, str) or observed not in _PHASES:
                    error.__dict__["_em_network_phase"] = phase
                raise

        return tracked

    return decorate


class _PhaseHTTPConnection(HTTPConnection):
    _new_conn = _at_phase("tcp")(HTTPConnection._new_conn)
    request = _at_phase("request_send")(HTTPConnection.request)
    getresponse = _at_phase("response_headers")(HTTPConnection.getresponse)

    @_at_phase("proxy_connect")
    def _tunnel(self) -> None:
        super()._tunnel()


class _PhaseHTTPSConnection(_PhaseHTTPConnection, HTTPSConnection):
    @_at_phase("proxy_tls")
    def _connect_tls_proxy(self, hostname: str, sock: Any) -> Any:
        return super()._connect_tls_proxy(hostname, sock)

    @_at_phase("tls")
    def connect(self) -> None:
        super().connect()


class _PhaseHTTPPool(HTTPConnectionPool):
    ConnectionCls = _PhaseHTTPConnection


class _PhaseHTTPSPool(HTTPSConnectionPool):
    ConnectionCls = _PhaseHTTPSConnection


def _instrument_manager(manager: Any) -> None:
    # 每个 manager 独立映射；禁止修改 urllib3 全局连接池或会话间共享状态。
    manager.pool_classes_by_scheme = {"http": _PhaseHTTPPool, "https": _PhaseHTTPSPool}


def _close_manager(manager: Any) -> None:
    # clear() 只移除引用时，异常 traceback 仍可能延长空闲 socket 的存活期。
    # 显式关闭池：在途连接不在空闲队列中，归还到关闭池时再释放。
    with manager.pools.lock:
        for key in list(manager.pools.keys()):
            pool = manager.pools.get(key)
            if pool is not None:
                pool.close()
        manager.clear()


class ExplicitProxySession(requests.Session):  # noqa: TID251 -- 唯一受控的底层会话继承点
    """只使用显式代理，直连及重定向不读取环境/系统代理。

    trust_env 同时关闭隐式 netrc 认证；单独保留 requests 的环境 CA 规则：
    请求未指定 verify 或为 True 时，REQUESTS_CA_BUNDLE 优先于 CURL_CA_BUNDLE，
    每次请求读取。显式 verify 路径/False 与 Session 设置继续由 requests 合并。
    """

    def __init__(self) -> None:
        super().__init__()
        self.trust_env = False
        self.mount("http://", BoundedProxyAdapter())
        self.mount("https://", BoundedProxyAdapter())

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

    def init_poolmanager(self, *args: Any, **kwargs: Any) -> None:
        super().init_poolmanager(*args, **kwargs)
        _instrument_manager(self.poolmanager)

    def proxy_manager_for(self, proxy: str, **proxy_kwargs: Any) -> Any:
        with self._manager_lock:
            manager = super().proxy_manager_for(proxy, **proxy_kwargs)
            if proxy.lower().startswith(("http://", "https://")):
                _instrument_manager(manager)
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
                _close_manager(manager)

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
                except Exception as error:
                    error.__dict__["_em_network_phase"] = "response_body"
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
            _close_manager(self.poolmanager)
            for manager in self.proxy_manager.values():
                _close_manager(manager)
            super().close()
            self.proxy_manager.clear()
            self._recent.clear()

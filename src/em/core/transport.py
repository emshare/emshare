"""传输层：封装 HTTP 请求，接入重试与动态代理，并把失败归类为 ``core.errors``。"""

import logging
from collections.abc import Mapping
from typing import Any

import requests

from em.core.errors import EmptyResponseError, HttpStatusError, NetworkError
from em.core.proxy import ProxyPool
from em.core.resilience import RetryPolicy, should_retry, sleep_backoff

log = logging.getLogger(__name__)


class HttpClient:
    """带换 IP 重试的 HTTP 客户端；耗尽重试则抛出最后一次异常。"""

    def __init__(
        self,
        session: requests.Session,
        proxy_pool: ProxyPool,
        policy: RetryPolicy,
        timeout_sec: int = 15,
    ) -> None:
        self._session = session
        self._proxy_pool = proxy_pool
        self._policy = policy
        self._timeout = timeout_sec

    def get_text(
        self,
        url: str,
        params: Mapping[str, Any],
        headers: Mapping[str, str],
    ) -> str:
        last_exc: Exception | None = None
        for attempt in range(self._policy.max_retries + 1):
            proxy = self._proxy_pool.acquire()
            try:
                return self._attempt(url, params, headers, proxy)
            except Exception as exc:
                last_exc = exc
                if not should_retry(exc):
                    raise
                self._proxy_pool.report_failure(proxy)
                log.warning(
                    "请求失败(%s): %s，换 IP 重试 [%d/%d]",
                    type(exc).__name__,
                    str(exc)[:120],
                    attempt + 1,
                    self._policy.max_retries,
                )
                sleep_backoff(self._policy, attempt)
        assert last_exc is not None
        raise last_exc

    def _attempt(
        self,
        url: str,
        params: Mapping[str, Any],
        headers: Mapping[str, str],
        proxy: str | None,
    ) -> str:
        proxies = {"http": f"http://{proxy}", "https": f"http://{proxy}"} if proxy else None
        try:
            resp = self._session.get(
                url, params=params, headers=headers, proxies=proxies, timeout=self._timeout
            )
        except requests.RequestException as exc:
            raise NetworkError(str(exc)) from exc
        if resp.status_code != 200:
            raise HttpStatusError(resp.status_code)
        if not resp.text:
            raise EmptyResponseError("空响应(Empty reply)")
        return resp.text

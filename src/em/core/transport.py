"""传输层：封装 HTTP 请求，接入重试与动态代理路由，并把失败归类为 ``core.errors``。"""

import logging
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

import requests

from em.core.errors import ChannelError, EmptyResponseError, HttpStatusError, NetworkError
from em.core.proxy import ProxyRouter
from em.core.resilience import RetryPolicy, should_retry, sleep_backoff

log = logging.getLogger(__name__)


def _is_banned(exc: Exception) -> bool:
    """确定封禁信号* 403/429 视为出口 IP 被目标封禁。"""
    if isinstance(exc, HttpStatusError):
        return exc.status_code in (403, 429)
    return False


class HttpClient:
    """带换 IP 重试的 HTTP 客户端；耗尽重试则抛出最后一次异常。"""

    def __init__(
        self,
        session: requests.Session,
        router: ProxyRouter,
        policy: RetryPolicy,
        timeout_sec: int = 15,
    ) -> None:
        self._session = session
        self._router = router
        self._policy = policy
        self._timeout = timeout_sec

    def get_text(
        self,
        url: str,
        params: Mapping[str, Any],
        headers: Mapping[str, str],
    ) -> str:
        host = urlparse(url).hostname or ""
        last_exc: Exception | None = None
        for attempt in range(self._policy.max_retries + 1):
            proxy = self._router.acquire(host)
            try:
                text = self._attempt(url, params, headers, proxy)
                self._router.report_result(host, proxy, success=True)
                return text
            except ChannelError as exc:
                self._router.report_result(host, proxy, success=False, banned=_is_banned(exc))
                last_exc = exc
                if not should_retry(exc):
                    raise
                if attempt >= self._policy.max_retries:
                    break
                log.warning(
                    "请求失败(%s): %s，换 IP 重试 [%d/%d]",
                    type(exc).__name__,
                    str(exc)[:120],
                    attempt + 1,
                    self._policy.max_retries,
                )
                sleep_backoff(self._policy, attempt)
        if last_exc is None:
            raise RuntimeError("未执行请求（max_retries < 0）")
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

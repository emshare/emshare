"""分页任务内共享的重试终止信号；不跨任务保留冷却或封禁状态。"""

import threading
from collections.abc import Iterator
from contextlib import contextmanager

from em.core.errors import EgressRetryStopped


class PageRetryGuard:
    """一页确认不能继续重试后，其他页不再启动新尝试；在途请求自然结束。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._error: EgressRetryStopped | None = None

    @contextmanager
    def attempt(self) -> Iterator[None]:
        with self._lock:
            previous = self._error
        if previous is not None:
            # 每个 worker 抛自己的异常，避免并发改写同一异常的 traceback。
            stopped = EgressRetryStopped(*previous.args)
            stopped.hint = previous.hint
            raise stopped from previous
        try:
            yield
        except EgressRetryStopped as exc:
            with self._lock:
                if self._error is None:
                    self._error = exc
            raise

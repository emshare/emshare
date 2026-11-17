"""共享绝对时间预算，限制锁等待、新请求与重试。"""

import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from em.core.errors import PageDeadlineExceeded

_deadline: ContextVar[float | None] = ContextVar("em_deadline", default=None)


def remaining() -> float | None:
    deadline = _deadline.get()
    if deadline is None:
        return None
    value = deadline - time.monotonic()
    if value <= 0:
        raise PageDeadlineExceeded("请求已超过时间预算")
    return value


@contextmanager
def request_budget(deadline: float) -> Iterator[None]:
    outer = _deadline.get()
    token = _deadline.set(min(deadline, outer) if outer is not None else deadline)
    try:
        remaining()
        yield
        remaining()
    finally:
        _deadline.reset(token)


def deadline() -> float | None:
    """当前上下文的绝对截止时刻；无预算返回 None。"""
    return _deadline.get()


@contextmanager
def detached() -> Iterator[None]:
    """暂时脱离调用方预算：用于结果会写入共享状态的操作（如代理回源与预筛）。

    这类操作若继承某个调用方所剩无几的预算，会用被压短的超时得出错误结论
    （把健康 IP 判死、熔断代理源），并让所有其他调用方一起承担。
    """
    token = _deadline.set(None)
    try:
        yield
    finally:
        _deadline.reset(token)


def timeouts(connect: float, read: float) -> tuple[float, float]:
    available = remaining()
    if available is None:
        return connect, read
    return min(connect, available / 2), min(read, available / 2)


def pause(delay: float) -> float:
    available = remaining()
    duration = min(delay, available) if available is not None else delay
    if duration > 0:
        time.sleep(duration)
    remaining()
    return duration


@contextmanager
def acquire_lock(lock: threading.Lock) -> Iterator[None]:
    available = remaining()
    acquired = lock.acquire() if available is None else lock.acquire(timeout=available)
    if not acquired:
        raise PageDeadlineExceeded("等待代理回源超过时间预算")
    try:
        remaining()
        yield
    finally:
        lock.release()

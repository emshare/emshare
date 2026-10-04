"""弹性策略：重试参数数据化 + 退避计算 + 是否重试判定。"""

import time
from dataclasses import dataclass

from em.core.errors import ChannelError


@dataclass(frozen=True)
class RetryPolicy:
    """重试策略是一份不可变数据，便于集中调整与测试。

    换 IP 重试场景下每次都是全新出口 IP，不该被指数退避越罚越重；
    用 ``backoff_cap_sec`` 给退避封顶，避免代理 IP（TTL 仅数十秒）在长退避里过期。
    """

    max_retries: int = 10
    backoff_sec: float = 0.2
    backoff_cap_sec: float | None = None
    jitter_sec: float = 0.0

    def backoff_for(self, attempt: int) -> float:
        """第 ``attempt`` 次（从 0 起）失败后的等待秒数，指数退避并封顶。"""
        delay = self.backoff_sec * (2.0**attempt) + self.jitter_sec
        if self.backoff_cap_sec is not None:
            delay = min(delay, self.backoff_cap_sec)
        return delay


def should_retry(exc: Exception) -> bool:
    """仅渠道异常且标记 ``retryable`` 时才重试。"""
    return isinstance(exc, ChannelError) and exc.retryable


def sleep_backoff(policy: RetryPolicy, attempt: int) -> None:
    delay = policy.backoff_for(attempt)
    if delay > 0:
        time.sleep(delay)

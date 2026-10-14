"""弹性策略：重试参数数据化 + 退避计算 + 是否重试判定。"""

import time
from dataclasses import dataclass

from em.core.errors import ChannelError, HttpStatusError


@dataclass(frozen=True)
class RetryPolicy:
    """重试策略是一份不可变数据，便于集中调整与测试。

    退避按失败类型分两档：
    - 封禁信号（403/429）：服务端在限流，指数退避并封顶，避免顶风请求；
    - 其余（连接失败/超时/空响应/坏内容）：换的是全新出口 IP，固定极短等待即可，
      不做指数惩罚，避免把代理 IP（TTL 仅数十秒）在长退避里拖过期。
    """

    max_retries: int = 10
    backoff_sec: float = 0.2
    backoff_cap_sec: float | None = None
    jitter_sec: float = 0.0
    # 连接/内容类失败（每次都是新 IP）的固定退避
    connect_backoff_sec: float = 0.1

    def backoff_for(self, attempt: int, exc: Exception | None = None) -> float:
        """第 ``attempt`` 次（从 0 起）失败后的等待秒数。

        传 ``exc`` 时按失败类型选档；不传（旧调用/测试）保持指数退避口径。
        """
        if exc is not None and not _is_rate_limited(exc):
            return self.connect_backoff_sec + self.jitter_sec
        delay = self.backoff_sec * (2.0**attempt) + self.jitter_sec
        if self.backoff_cap_sec is not None:
            delay = min(delay, self.backoff_cap_sec)
        return delay


def _is_rate_limited(exc: Exception) -> bool:
    """403/429 视为服务端限流，值得指数退避；其余连接类错误立即换 IP。"""
    return isinstance(exc, HttpStatusError) and exc.status_code in (403, 429)


def should_retry(exc: Exception) -> bool:
    """仅渠道异常且标记 ``retryable`` 时才重试。"""
    return isinstance(exc, ChannelError) and exc.retryable


def sleep_backoff(policy: RetryPolicy, attempt: int, exc: Exception | None = None) -> None:
    delay = policy.backoff_for(attempt, exc)
    if delay > 0:
        time.sleep(delay)

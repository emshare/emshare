"""异常分层：按处置策略划分，统一携带 ``retryable`` 供上层决定是否换 IP 重试。"""


class EmError(Exception):
    """em 库异常基类。"""


class ConfigError(EmError):
    """配置非法：重试无法恢复，立即上抛。"""


class InterfaceNotFoundError(EmError):
    """接口检索未命中：接口名未知。"""


class ChannelError(EmError):
    """上游渠道异常基类。"""

    retryable: bool = False


class NetworkError(ChannelError):
    """连接失败 / 超时等传输层错误：可换 IP 重试。"""

    retryable = True


class EmptyResponseError(ChannelError):
    """空响应（出口被封时服务端常直接断开）：可换 IP 重试。"""

    retryable = True


class HttpStatusError(ChannelError):
    """上游返回非预期状态码：5xx 与 403/429 可重试，其余 4xx 不可。"""

    def __init__(self, status_code: int, message: str = "") -> None:
        super().__init__(f"HTTP {status_code} {message}".strip())
        self.status_code = status_code
        self.retryable = status_code >= 500 or status_code in (403, 429)

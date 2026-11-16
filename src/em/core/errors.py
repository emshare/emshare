"""异常分层：按处置策略划分，统一携带 ``retryable`` 供上层决定是否换 IP 重试。"""


class EmError(Exception):
    """em 库异常基类。

    ``hint`` 是可选的处置建议（如"出口疑似被封，需要配置代理源"）：有则跟在错误信息后面
    一并显示，``print(exc)`` 与回溯末尾都能看到；``args`` 保持不变。
    """

    hint: str | None = None

    def __str__(self) -> str:
        base = super().__str__()
        return f"{base}\n{self.hint}" if self.hint else base


class ConfigError(EmError):
    """配置非法：重试无法恢复，立即上抛。"""


class InterfaceNotFoundError(EmError):
    """接口检索未命中：接口名未知。"""


class SecurityNotFoundError(EmError):
    """上游明确回复证券不存在（如 stock/get 的 rc=100 / 102）：换 IP 也查不到，不重试。

    不是渠道异常：响应本身是正常协议，只是查无此券；归为 ``ChannelError`` 会被当成劫持页反复换 IP。
    """


class QueryRejectedError(EmError):
    """上游明确拒绝了查询：查询本身写错了，换 IP 也一样，不重试。

    如数据中心的 code=9501（报表 / 列名 / 排序列不存在、日期格式不对）。不是渠道异常：
    响应是正常协议，归为 ``ChannelError`` 会被当成劫持页、拉黑好 IP 并重试到耗尽。
    """


class PageDeadlineExceeded(EmError):
    """单页超过时间预算：标记为失败页，交给定向补漏，不阻塞整轮。

    不是渠道异常——预算耗尽只说明"这一页不值得我们继续等"，重试与否由补漏轮决定。
    """


class ChannelError(EmError):
    """上游渠道异常基类。"""

    retryable: bool = False


class NetworkError(ChannelError):
    """连接失败 / 超时等传输层错误：可换 IP 重试。"""

    retryable = True


class ProxyUnavailableError(NetworkError):
    """代理路由暂时没有可用出口；允许重试，但不能隐式改走直连。"""


class ProxyConnectError(NetworkError):
    """出口连接不可用（connect 超时 / 被重置 / 远端断链）：换 IP 立刻见效，判死该出口。

    与 ``UpstreamReadTimeout`` 分开是为了让代理池能把"出口坏了"和"这一页慢了"
    区别对待：前者应立即淘汰，后者换 IP 只是再付一次握手成本。
    """


class UpstreamReadTimeout(NetworkError):
    """连接已建立但读取超时：多为慢页或瞬时抖动，按软失败处理（同 IP 重试一次）。

    代理池据此把 IP 的淘汰推迟到连续两次软失败，避免把好出口在 TTL 内误杀。
    """


class EmptyResponseError(ChannelError):
    """空响应（出口被封时服务端常直接断开）：可换 IP 重试。"""

    retryable = True


class InvalidContentError(ChannelError):
    """HTTP 200 但响应体不是预期协议（多为代理劫持/错误页）：可换 IP 重试。"""

    retryable = True


class HttpStatusError(ChannelError):
    """上游返回非预期状态码：5xx 与 403/429 可重试，其余 4xx 不可。"""

    def __init__(self, status_code: int, message: str = "") -> None:
        super().__init__(f"HTTP {status_code} {message}".strip())
        self.status_code = status_code
        self.retryable = status_code >= 500 or status_code in (403, 429)

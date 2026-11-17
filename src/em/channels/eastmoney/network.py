"""东财的网络故障判据，由应用层注入通用传输层。"""

import re
from urllib.parse import urlsplit

from em.channels.eastmoney import config

_PUSH2_HOST = re.compile(r"^(?:\d+\.)?push2(?:his|ex|delay)?\.eastmoney\.com$")


def disconnect_may_be_limited(host: str) -> bool:
    """行情主机连续断连按疑似限流止损；不认定所有东财主机均如此。

    pushguest 是本项目全市场入口，也采用有界重试策略；不是对其封禁原因的确认。
    """
    return host == urlsplit(config.GUEST_HOST).hostname or _PUSH2_HOST.fullmatch(host) is not None

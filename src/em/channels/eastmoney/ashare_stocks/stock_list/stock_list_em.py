"""沪深京 A 股全市场列表（clist 游客接口，pushguest），可按市场 / 板块范围筛选。"""

from em.channels.eastmoney import config
from em.channels.eastmoney.request import ClistRequest
from em.domain.queries import MarketQuery

# 各市场分段（f:!2 与现有全量口径一致）
_SZ_FS = "m:0+t:6+f:!2,m:0+t:80+f:!2"  # 深市主板 + 创业板
_SH_FS = "m:1+t:2+f:!2,m:1+t:23+f:!2"  # 沪市主板 + 科创板
_BJ_FS = "m:0+t:81+s:262144+f:!2"  # 北交所

# 全量口径保持原字符串不变：stock_list_all_em 与预筛探测都依赖它
MARKET_FS = "m:0+t:6+f:!2,m:0+t:80+f:!2,m:1+t:2+f:!2,m:1+t:23+f:!2,m:0+t:81+s:262144+f:!2"

# A 股各段（不带 f:!2），供 new / st 这类标志筛选按段限定
_A_SEGMENTS = ("m:0+t:6", "m:0+t:80", "m:1+t:2", "m:1+t:23", "m:0+t:81+s:262144")


def _flagged(flag: str) -> str:
    """按 A 股各段加标志筛选。

    实测标志与 f:!2 叠加会让筛选失效（返回 5.8 万条），故不带 f:!2；
    按段限定是为了只留 A 股：akshare 的 ``m:0+f:4,m:1+f:4`` 会混入 B 股与三板代码（386 条 vs 197 条）。
    """
    return ",".join(f"{seg}+f:{flag}" for seg in _A_SEGMENTS)


# scope -> fs。实测 sh + sz + bj 的 total 之和等于 all，其余范围都是 all 的子集
MARKET_SCOPE_FS = {
    "all": MARKET_FS,
    "sh": _SH_FS,
    "sz": _SZ_FS,
    "bj": _BJ_FS,
    "kc": "m:1+t:23+f:!2",
    "cy": "m:0+t:80+f:!2",
    "new": _flagged("8"),
    "st": _flagged("4"),
}


def normalize_scope(scope: str) -> str:
    """把范围规范为已知值；未知范围回退全量。"""
    return scope if scope in MARKET_SCOPE_FS else "all"


def stock_list_request(query: MarketQuery) -> ClistRequest:
    return ClistRequest(
        host=config.GUEST_HOST,
        fs=MARKET_SCOPE_FS[normalize_scope(query.scope)],
        fields=config.MARKET_FIELDS,
        fid=query.sort,
        page=query.page,
        page_size=query.size,
    )

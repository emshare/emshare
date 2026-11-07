"""港股列表（clist 游客接口，pushguest），按板块范围筛选。"""

from em.channels.eastmoney import config
from em.channels.eastmoney.request import ClistRequest
from em.domain.queries import HkStockListQuery

# 港股市场 m:128 下的分段（实测 2026-11-06）：t:3 主板 2620 / t:4 创业板 313；
# t:1 是 ETF 与基金（如 02800 盈富基金），t:2 是债券（如国债），都不是股票，不纳入
_MAIN_FS = "m:128+t:3"
_GEM_FS = "m:128+t:4"

HK_SCOPE_FS = {
    "all": f"{_MAIN_FS},{_GEM_FS}",
    "main": _MAIN_FS,
    "gem": _GEM_FS,
}


def normalize_scope(scope: str) -> str:
    """把范围规范为已知值；未知范围回退主板 + 创业板。"""
    return scope if scope in HK_SCOPE_FS else "all"


def hk_stock_list_request(query: HkStockListQuery) -> ClistRequest:
    return ClistRequest(
        host=config.GUEST_HOST,
        fs=HK_SCOPE_FS[normalize_scope(query.scope)],
        fields=config.HK_STOCK_LIST_FIELDS,
        fid=query.sort,
        page=query.page,
        page_size=query.size,
    )

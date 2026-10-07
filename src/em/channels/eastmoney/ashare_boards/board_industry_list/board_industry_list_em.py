"""板块列表（clist 游客接口，行业 / 概念 / 地域板块）。

fs 编码：
  - 行业分级：``m:90+s:{s}+f:!50``，``s`` 由 ``level`` 映射（1→2 / 2→4 / 3→8，未知回退 1 级）
  - 行业全级别：``m:90+t:2+f:!50``（``level="all"``，含一/二/三级共 496 个）
  - 概念：``m:90+t:3+f:!50``（无分级）
  - 地域：``m:90+t:1+f:!50``（无分级）
"""

from em.channels.eastmoney import config
from em.channels.eastmoney.request import ClistRequest
from em.domain.queries import BoardListQuery


def industry_level_s(level: str) -> str:
    """把行业分级映射为 fs 中的 s 值；未知级别回退一级（s=2）。"""
    return config.BOARD_INDUSTRY_LEVEL_S.get(level, "2")


def fs_of(query: BoardListQuery) -> str:
    """把板块类型与级别映射为 clist 的 fs 参数；未知类型回退行业一级。"""
    if query.board_type == "concept":
        return config.BOARD_CONCEPT_FS
    if query.board_type == "region":
        return config.BOARD_REGION_FS
    # industry 或未知类型：走行业分级
    if query.level == "all":
        return config.BOARD_INDUSTRY_ALL_FS
    return f"m:90+s:{industry_level_s(query.level)}+f:!50"


def board_industry_list_request(query: BoardListQuery) -> ClistRequest:
    return ClistRequest(
        host=config.GUEST_HOST,
        fs=fs_of(query),
        fields=config.BOARD_LIST_FIELDS,
        fid=query.sort,
        page=query.page,
        page_size=query.size,
    )

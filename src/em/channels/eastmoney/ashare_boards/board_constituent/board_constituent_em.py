"""板块成分股（clist，支持按当日/5日/10日资金流排序）。"""

from em.channels.eastmoney import config
from em.channels.eastmoney.request import ClistRequest
from em.domain.queries import BoardQuery


def flow_field(query: BoardQuery) -> str:
    """把资金流周期映射为字段名；未知周期回退 10 日。"""
    return config.FUND_FLOW_FIELDS.get(query.period, "f174")


def board_constituent_request(query: BoardQuery) -> ClistRequest:
    return ClistRequest(
        host=config.QUOTE_HOST,
        fs=f"b:{query.board}",
        fields=config.BOARD_FIELDS,
        fid=flow_field(query),
        page=query.page,
        page_size=query.size,
    )

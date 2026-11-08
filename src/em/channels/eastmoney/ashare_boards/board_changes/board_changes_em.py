"""板块异动（push2ex getAllBKChanges），一次取最近交易日全部有异动的板块。"""

from em.channels.eastmoney import config
from em.channels.eastmoney.request import BoardChangesRequest
from em.domain.queries import BoardChangesQuery


def board_changes_request(query: BoardChangesQuery) -> BoardChangesRequest:
    # 上游无可选参数；query 保留统一的 *_em(query, settings) 签名
    return BoardChangesRequest(host=config.PUSH2EX_HOST)

"""盘口异动（push2ex getAllStockChanges），按异动类型一次取最近交易日的全部记录。"""

from em.channels.eastmoney import config
from em.channels.eastmoney.request import StockChangesRequest
from em.domain.queries import StockChangesQuery

# 英文 change_type -> 上游 type（22 种，顺序同东财页面与 akshare）
STOCK_CHANGE_TYPES = config.CHANGE_TYPE_CODES


def normalize_change_type(change_type: str) -> str:
    """把异动类型规范为已知值；未知类型回退大笔买入（akshare 默认值）。"""
    return change_type if change_type in STOCK_CHANGE_TYPES else "big_buy"


def stock_changes_request(query: StockChangesQuery) -> StockChangesRequest:
    change_type = normalize_change_type(query.change_type)
    return StockChangesRequest(
        host=config.PUSH2EX_HOST,
        type_code=STOCK_CHANGE_TYPES[change_type],
        change_type=change_type,
    )

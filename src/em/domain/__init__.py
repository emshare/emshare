"""领域模型层：与渠道无关的强类型对象与查询句柄，不依赖 core/channels/application。"""

from em.domain.models import Quote, QuotePage
from em.domain.queries import BoardQuery, MarketQuery

__all__ = ["BoardQuery", "MarketQuery", "Quote", "QuotePage"]

"""现金流量表接口族。"""

from em.channels.eastmoney.ashare_financial_statements.cash_flow_statement.cash_flow_statement_em import (
    CASH_FLOW_STATEMENT,
    cash_flow_statement_request,
)

__all__ = ["CASH_FLOW_STATEMENT", "cash_flow_statement_request"]

"""利润表接口族。"""

from em.channels.eastmoney.ashare_financial_statements.income_statement.income_statement_em import (
    INCOME_STATEMENT,
    income_statement_request,
)

__all__ = ["INCOME_STATEMENT", "income_statement_request"]

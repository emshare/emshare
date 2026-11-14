"""利润表（数据中心 RPT_DMSK_FN_INCOME），按报告期取各公司的数据，一家公司一行。"""

from em.channels.eastmoney.datacenter import (
    Column,
    ReportSpec,
    day,
    market_of,
    number,
    report_period_filter,
    required_text,
)
from em.channels.eastmoney.request import DatacenterRequest
from em.domain.models import IncomeStatement
from em.domain.queries import IncomeStatementQuery

# 排序对齐 akshare（公告日期、代码倒序）；报告期内一家公司一行，代码即唯一键
INCOME_STATEMENT = ReportSpec(
    report="RPT_DMSK_FN_INCOME",
    model=IncomeStatement,
    columns=(
        Column("code", "SECURITY_CODE", required_text),
        Column("name", "SECURITY_NAME_ABBR", required_text),
        Column("market", "SECUCODE", market_of),
        Column("industry", "INDUSTRY_NAME"),
        Column("report_date", "REPORT_DATE", day),
        Column("notice_date", "NOTICE_DATE", day),
        Column("net_profit", "PARENT_NETPROFIT", number),
        Column("net_profit_yoy", "PARENT_NETPROFIT_RATIO", number),
        Column("deducted_net_profit", "DEDUCT_PARENT_NETPROFIT", number),
        Column("deducted_net_profit_yoy", "DPN_RATIO", number),
        Column("revenue", "TOTAL_OPERATE_INCOME", number),
        Column("revenue_yoy", "TOI_RATIO", number),
        Column("operating_expense", "OPERATE_EXPENSE", number),
        Column("operating_expense_yoy", "OPERATE_EXPENSE_RATIO", number),
        Column("operating_cost", "OPERATE_COST", number),
        Column("selling_expense", "SALE_EXPENSE", number),
        Column("admin_expense", "MANAGE_EXPENSE", number),
        Column("finance_expense", "FINANCE_EXPENSE", number),
        Column("taxes_and_surcharges", "OPERATE_TAX_ADD", number),
        Column("total_operating_cost", "TOTAL_OPERATE_COST", number),
        Column("total_operating_cost_yoy", "TOE_RATIO", number),
        Column("operating_profit", "OPERATE_PROFIT", number),
        Column("operating_profit_yoy", "OPERATE_PROFIT_RATIO", number),
        Column("total_profit", "TOTAL_PROFIT", number),
        Column("income_tax", "INCOME_TAX", number),
        Column("operating_income", "OPERATE_INCOME", number),
        Column("net_interest_income", "INTEREST_NI", number),
        Column("net_interest_income_yoy", "INTEREST_NI_RATIO", number),
        Column("net_fee_income", "FEE_COMMISSION_NI", number),
        Column("net_fee_income_yoy", "FCN_RATIO", number),
        Column("business_admin_expense", "MANAGE_EXPENSE_BANK", number),
        Column("earned_premiums", "EARNED_PREMIUM", number),
        Column("earned_premiums_yoy", "EARNED_PREMIUM_RATIO", number),
        Column("investment_income", "INVEST_INCOME", number),
        Column("surrenders", "SURRENDER_VALUE", number),
        Column("claims_expense", "COMPENSATE_EXPENSE", number),
    ),
    sort=(("NOTICE_DATE", -1), ("SECURITY_CODE", -1)),
)

__all__ = ["INCOME_STATEMENT", "income_statement_request"]


def income_statement_request(query: IncomeStatementQuery) -> DatacenterRequest[IncomeStatement]:
    """报告期留空时取今天之前最近的季末；``scope`` 未知回退 all。只取 A 股与存托凭证。"""
    return INCOME_STATEMENT.request(
        report_period_filter("REPORT_DATE", query.report_date, query.scope)
    )

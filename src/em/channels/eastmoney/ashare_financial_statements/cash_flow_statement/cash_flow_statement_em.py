"""现金流量表（数据中心 RPT_DMSK_FN_CASHFLOW），按报告期取各公司的数据，一家公司一行。"""

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
from em.domain.models import CashFlowStatement
from em.domain.queries import CashFlowStatementQuery

# 排序对齐 akshare（公告日期、代码倒序）；报告期内一家公司一行，代码即唯一键
CASH_FLOW_STATEMENT = ReportSpec(
    report="RPT_DMSK_FN_CASHFLOW",
    model=CashFlowStatement,
    columns=(
        Column("code", "SECURITY_CODE", required_text),
        Column("name", "SECURITY_NAME_ABBR", required_text),
        Column("market", "SECUCODE", market_of),
        Column("industry", "INDUSTRY_NAME"),
        Column("report_date", "REPORT_DATE", day),
        Column("notice_date", "NOTICE_DATE", day),
        Column("net_cash_flow", "CCE_ADD", number),
        Column("net_cash_flow_yoy", "CCE_ADD_RATIO", number),
        Column("operating_net", "NETCASH_OPERATE", number),
        Column("operating_net_share", "NETCASH_OPERATE_RATIO", number),
        Column("sales_cash", "SALES_SERVICES", number),
        Column("sales_cash_share", "SALES_SERVICES_RATIO", number),
        Column("staff_cash_paid", "PAY_STAFF_CASH", number),
        Column("staff_cash_paid_share", "PSC_RATIO", number),
        Column("investing_net", "NETCASH_INVEST", number),
        Column("investing_net_share", "NETCASH_INVEST_RATIO", number),
        Column("investment_income_cash", "RECEIVE_INVEST_INCOME", number),
        Column("investment_income_cash_share", "RII_RATIO", number),
        Column("capex", "CONSTRUCT_LONG_ASSET", number),
        Column("capex_share", "CLA_RATIO", number),
        Column("financing_net", "NETCASH_FINANCE", number),
        Column("financing_net_share", "NETCASH_FINANCE_RATIO", number),
        Column("customer_deposits_increase", "CUSTOMER_DEPOSIT_ADD", number),
        Column("customer_deposits_increase_share", "CDA_RATIO", number),
        Column("interbank_deposits_increase", "DEPOSIT_IOFI_OTHER", number),
        Column("interbank_deposits_increase_share", "DIO_RATIO", number),
        Column("loans_increase", "LOAN_ADVANCE_ADD", number),
        Column("loans_increase_share", "LAA_RATIO", number),
        Column("interest_commission_cash", "RECEIVE_INTEREST_COMMISSION", number),
        Column("interest_commission_cash_share", "RIC_RATIO", number),
        Column("investment_cash_paid", "INVEST_PAY_CASH", number),
        Column("investment_cash_paid_share", "IPC_RATIO", number),
        Column("begin_cash", "BEGIN_CCE", number),
        Column("begin_cash_share", "BEGIN_CCE_RATIO", number),
        Column("end_cash", "END_CCE", number),
        Column("end_cash_share", "END_CCE_RATIO", number),
        Column("premiums_cash", "RECEIVE_ORIGIC_PREMIUM", number),
        Column("premiums_cash_share", "ROP_RATIO", number),
        Column("claims_cash_paid", "PAY_ORIGIC_COMPENSATE", number),
        Column("claims_cash_paid_share", "POC_RATIO", number),
    ),
    sort=(("NOTICE_DATE", -1), ("SECURITY_CODE", -1)),
)

__all__ = ["CASH_FLOW_STATEMENT", "cash_flow_statement_request"]


def cash_flow_statement_request(
    query: CashFlowStatementQuery,
) -> DatacenterRequest[CashFlowStatement]:
    """报告期留空时取今天之前最近的季末；``scope`` 未知回退 all。只取 A 股与存托凭证。"""
    return CASH_FLOW_STATEMENT.request(
        report_period_filter("REPORT_DATE", query.report_date, query.scope)
    )

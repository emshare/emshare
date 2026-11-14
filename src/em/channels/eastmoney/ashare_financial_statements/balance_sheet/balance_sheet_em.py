"""资产负债表（数据中心 RPT_DMSK_FN_BALANCE），按报告期取各公司的数据，一家公司一行。"""

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
from em.domain.models import BalanceSheet
from em.domain.queries import BalanceSheetQuery

# 排序对齐 akshare（公告日期、代码倒序）；报告期内一家公司一行，代码即唯一键
BALANCE_SHEET = ReportSpec(
    report="RPT_DMSK_FN_BALANCE",
    model=BalanceSheet,
    columns=(
        Column("code", "SECURITY_CODE", required_text),
        Column("name", "SECURITY_NAME_ABBR", required_text),
        Column("market", "SECUCODE", market_of),
        Column("industry", "INDUSTRY_NAME"),
        Column("report_date", "REPORT_DATE", day),
        Column("notice_date", "NOTICE_DATE", day),
        Column("cash", "MONETARYFUNDS", number),
        Column("cash_yoy", "MONETARYFUNDS_RATIO", number),
        Column("accounts_receivable", "ACCOUNTS_RECE", number),
        Column("accounts_receivable_yoy", "ACCOUNTS_RECE_RATIO", number),
        Column("inventory", "INVENTORY", number),
        Column("inventory_yoy", "INVENTORY_RATIO", number),
        Column("fixed_assets", "FIXED_ASSET", number),
        Column("total_assets", "TOTAL_ASSETS", number),
        Column("total_assets_yoy", "TOTAL_ASSETS_RATIO", number),
        Column("accounts_payable", "ACCOUNTS_PAYABLE", number),
        Column("accounts_payable_yoy", "ACCOUNTS_PAYABLE_RATIO", number),
        Column("advance_receipts", "ADVANCE_RECEIVABLES", number),
        Column("advance_receipts_yoy", "ADVANCE_RECEIVABLES_RATIO", number),
        Column("total_liabilities", "TOTAL_LIABILITIES", number),
        Column("total_liabilities_yoy", "TOTAL_LIAB_RATIO", number),
        Column("debt_asset_ratio", "DEBT_ASSET_RATIO", number),
        Column("current_ratio", "CURRENT_RATIO", number),
        Column("total_equity", "TOTAL_EQUITY", number),
        Column("total_equity_yoy", "TOTAL_EQUITY_RATIO", number),
        Column("cash_deposit_pbc", "CASH_DEPOSIT_PBC", number),
        Column("cash_deposit_pbc_yoy", "CDP_RATIO", number),
        Column("loans_advances", "LOAN_ADVANCE", number),
        Column("loans_advances_yoy", "LOAN_ADVANCE_RATIO", number),
        Column("available_for_sale_assets", "AVAILABLE_SALE_FINASSET", number),
        Column("available_for_sale_assets_yoy", "ASF_RATIO", number),
        Column("borrowings_from_pbc", "LOAN_PBC", number),
        Column("borrowings_from_pbc_yoy", "LOAN_PBC_RATIO", number),
        Column("deposits", "ACCEPT_DEPOSIT", number),
        Column("deposits_yoy", "ACCEPT_DEPOSIT_RATIO", number),
        Column("repo_sold", "SELL_REPO_FINASSET", number),
        Column("repo_sold_yoy", "SRF_RATIO", number),
        Column("settlement_reserves", "SETTLE_EXCESS_RESERVE", number),
        Column("settlement_reserves_yoy", "SER_RATIO", number),
        Column("interbank_borrowings", "BORROW_FUND", number),
        Column("interbank_borrowings_yoy", "BORROW_FUND_RATIO", number),
        Column("customer_brokerage_deposits", "AGENT_TRADE_SECURITY", number),
        Column("customer_brokerage_deposits_yoy", "ATS_RATIO", number),
        Column("premiums_receivable", "PREMIUM_RECE", number),
        Column("premiums_receivable_yoy", "PREMIUM_RECE_RATIO", number),
        Column("short_term_loans", "SHORT_LOAN", number),
        Column("short_term_loans_yoy", "SHORT_LOAN_RATIO", number),
        Column("advance_premiums", "ADVANCE_PREMIUM", number),
        Column("advance_premiums_yoy", "ADVANCE_PREMIUM_RATIO", number),
    ),
    sort=(("NOTICE_DATE", -1), ("SECURITY_CODE", -1)),
)

__all__ = ["BALANCE_SHEET", "balance_sheet_request"]


def balance_sheet_request(query: BalanceSheetQuery) -> DatacenterRequest[BalanceSheet]:
    """报告期留空时取今天之前最近的季末；``scope`` 未知回退 all。只取 A 股与存托凭证。"""
    return BALANCE_SHEET.request(
        report_period_filter("REPORT_DATE", query.report_date, query.scope)
    )

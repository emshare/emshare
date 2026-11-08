"""场内基金列表（clist 游客接口，pushguest），按 ETF / LOF 筛选。"""

from em.channels.eastmoney import config
from em.channels.eastmoney.request import ClistRequest
from em.domain.queries import FundListQuery

# 东财板块编码（对齐 akshare fund_etf_spot_em / fund_lof_spot_em）。
# akshare 的 ETF 走 push2delay 主机；实测 pushguest 返回同样的 total（ETF 1666 / LOF 389）
_ETF_FS = "b:MK0021,b:MK0022,b:MK0023,b:MK0024,b:MK0827"
_LOF_FS = "b:MK0404,b:MK0405,b:MK0406,b:MK0407"

FUND_TYPE_FS = {
    "etf": _ETF_FS,
    "lof": _LOF_FS,
    "all": f"{_ETF_FS},{_LOF_FS}",
}


def normalize_fund_type(fund_type: str) -> str:
    """把基金类型规范为已知值；未知类型回退 ETF。"""
    return fund_type if fund_type in FUND_TYPE_FS else "etf"


def fund_list_request(query: FundListQuery) -> ClistRequest:
    return ClistRequest(
        host=config.GUEST_HOST,
        fs=FUND_TYPE_FS[normalize_fund_type(query.fund_type)],
        fields=config.FUND_LIST_FIELDS,
        fid=query.sort,
        page=query.page,
        page_size=query.size,
    )

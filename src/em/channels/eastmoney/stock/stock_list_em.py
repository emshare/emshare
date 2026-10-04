"""沪深京 A 股全市场列表（clist 游客接口，pushguest）。"""

from em.channels.eastmoney import config
from em.channels.eastmoney.request import ClistRequest
from em.domain.queries import MarketQuery

MARKET_FS = "m:0+t:6+f:!2,m:0+t:80+f:!2,m:1+t:2+f:!2,m:1+t:23+f:!2,m:0+t:81+s:262144+f:!2"


def stock_list_request(query: MarketQuery) -> ClistRequest:
    return ClistRequest(
        host=config.GUEST_HOST,
        fs=MARKET_FS,
        fields=config.MARKET_FIELDS,
        fid=query.sort,
        page=query.page,
        page_size=query.size,
    )

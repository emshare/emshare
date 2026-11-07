"""指数列表（clist 游客接口，pushguest），按指数系列筛选。"""

from em.channels.eastmoney import config
from em.channels.eastmoney.request import ClistRequest
from em.domain.queries import IndexListQuery

# series -> fs（对齐 akshare stock_zh_index_spot_em 的 symbol）。
# 北证指数（如 899050 北证50）只出现在 main 里，不在 sh / sz / csi 任一系列中
INDEX_SERIES_FS = {
    "main": "b:MK0010",  # 沪深重要指数
    "sh": "m:1+t:1",  # 上证系列指数
    "sz": "m:0+t:5",  # 深证系列指数
    "csi": "m:2",  # 中证系列指数
}


def normalize_series(series: str) -> str:
    """把指数系列规范为已知值；未知系列回退沪深重要指数。"""
    return series if series in INDEX_SERIES_FS else "main"


def index_list_request(query: IndexListQuery) -> ClistRequest:
    return ClistRequest(
        host=config.GUEST_HOST,
        fs=INDEX_SERIES_FS[normalize_series(query.series)],
        fields=config.INDEX_LIST_FIELDS,
        fid=query.sort,
        page=query.page,
        page_size=query.size,
    )

"""涨跌停股池（push2ex），按股池类型与交易日取整池。"""

import re
from datetime import datetime, timedelta, timezone

from em.channels.eastmoney import config
from em.channels.eastmoney.request import LimitPoolRequest
from em.domain.queries import LimitPoolQuery

# pool_type -> (上游路径, 排序)，对齐 akshare stock_zt_pool_*_em。
# 次新股池路径 getTopicCXPooll 末尾的双 l 是上游原样拼写，不是笔误
LIMIT_POOL_ENDPOINTS = {
    "limit_up": ("/getTopicZTPool", "fbt:asc"),  # 涨停股池
    "prev_limit_up": ("/getYesterdayZTPool", "zs:desc"),  # 昨日涨停股池
    "strong": ("/getTopicQSPool", "zdp:desc"),  # 强势股池
    "sub_new": ("/getTopicCXPooll", "ods:asc"),  # 次新股池
    "broken": ("/getTopicZBPool", "fbt:asc"),  # 炸板股池
    "limit_down": ("/getTopicDTPool", "fund:asc"),  # 跌停股池
}

_BEIJING = timezone(timedelta(hours=8))
_DATE_RE = re.compile(r"^\d{8}$")


def normalize_pool_type(pool_type: str) -> str:
    """把股池类型规范为已知值；未知类型回退涨停股池。"""
    return pool_type if pool_type in LIMIT_POOL_ENDPOINTS else "limit_up"


def resolve_date(date: str | None, now: datetime | None = None) -> str:
    """把查询日期规范为 ``YYYYMMDD``；留空取北京时间今天。

    格式不对时直接报错：上游对 ``2026-11-06`` 这类写法不报错，只返回空数据，容易误判成“当天没有股票”。
    """
    if not date:
        return (now or datetime.now(_BEIJING)).astimezone(_BEIJING).strftime("%Y%m%d")
    if not _DATE_RE.match(date):
        raise ValueError(f"date 必须是 YYYYMMDD 格式，收到 {date!r}")
    return date


def stock_limit_pool_request(
    query: LimitPoolQuery, now: datetime | None = None
) -> LimitPoolRequest:
    pool_type = normalize_pool_type(query.pool_type)
    path, sort = LIMIT_POOL_ENDPOINTS[pool_type]
    return LimitPoolRequest(
        host=config.PUSH2EX_HOST,
        path=path,
        sort=sort,
        date=resolve_date(query.date, now),
        pool_type=pool_type,
    )

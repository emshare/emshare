"""定向补漏的可疑页定位：邻页重叠与短页信号。"""

from em.application.market_data import _suspicious_pages


def _full_page(seed: int) -> set[str]:
    return {f"{seed + i:06d}" for i in range(100)}


def test_clean_pages_no_suspicious():
    # 各页 100 条且相邻无交集（首尾衔接但不重叠）→ 无可疑页
    pages = {1: _full_page(0), 2: _full_page(100), 3: _full_page(200)}
    assert _suspicious_pages(pages, total_pages=3) == set()


def test_adjacent_overlap_marks_both_pages():
    # 页 2 混入页 3 的一个码（替换型漂移）→ 2、3 两页都要重抓
    pages = {1: _full_page(0), 2: _full_page(100), 3: _full_page(200)}
    pages[2] = set(list(pages[2])[:99]) | {"000200"}  # 与页3首码重叠
    assert _suspicious_pages(pages, total_pages=3) == {2, 3}


def test_short_non_last_page_flagged():
    # 非末页只有 97 条（真码被挤出）→ 标记该页；末页短不算异常
    pages = {1: _full_page(0), 2: set(list(_full_page(100))[:97]), 3: set(list(_full_page(200))[:80])}
    assert _suspicious_pages(pages, total_pages=3) == {2}


def test_missing_page_not_flagged():
    # 缺失页（拉取失败）不产生重叠/短页信号；由 failed 集合另行重试
    pages = {1: _full_page(0), 3: _full_page(200)}
    assert _suspicious_pages(pages, total_pages=3) == set()

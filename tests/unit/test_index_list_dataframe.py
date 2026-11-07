"""指数列表 DataFrame 适配的行为锁（用固定 IndexListPage，不触网）。"""

import pytest

from em.application.dataframe import INDEX_LIST_COLUMNS_ZH, to_index_list_dataframe
from em.domain.models import IndexListPage, IndexQuote

pd = pytest.importorskip("pandas")


def _sample() -> IndexListPage:
    return IndexListPage(
        total=2,
        items=(
            IndexQuote(code="000001", name="上证指数", market="sh", price=3649.18, change_pct=-1.1),
            IndexQuote(code="399001", name="深证成指", market="sz", price=11175.78),
        ),
    )


def test_default_chinese_columns() -> None:
    df = to_index_list_dataframe(_sample())
    assert list(df.columns) == [
        "代码",
        "名称",
        "市场",
        "最新价",
        "涨跌幅",
        "涨跌额",
        "成交量",
        "成交额",
        "振幅",
        "最高",
        "最低",
        "今开",
        "昨收",
        "量比",
    ]
    assert len(df) == 2
    assert df.iloc[0]["市场"] == "sh"
    assert df.iloc[0]["最新价"] == pytest.approx(3649.18)
    assert pd.isna(df.iloc[1]["涨跌幅"])


def test_empty_page_keeps_header() -> None:
    df = to_index_list_dataframe(IndexListPage(total=0, items=()))
    assert list(df.columns) == list(INDEX_LIST_COLUMNS_ZH.values())
    assert df.empty


def test_custom_columns_override() -> None:
    custom = {k: k for k in INDEX_LIST_COLUMNS_ZH}
    df = to_index_list_dataframe(_sample(), columns=custom)
    assert list(df.columns) == list(INDEX_LIST_COLUMNS_ZH)

"""港股列表 DataFrame 适配的行为锁（用固定 HkStockListPage，不触网）。"""

import pytest

from em.application.dataframe import HK_STOCK_LIST_COLUMNS_ZH, to_hk_stock_list_dataframe
from em.domain.models import HkQuote, HkStockListPage

pd = pytest.importorskip("pandas")


def _sample() -> HkStockListPage:
    return HkStockListPage(
        total=2,
        items=(
            HkQuote(code="00700", name="腾讯控股", price=419.8, change_pct=-2.46),
            HkQuote(code="08646", name="中国宏光", price=0.37),
        ),
    )


def test_default_chinese_columns_match_akshare_order() -> None:
    df = to_hk_stock_list_dataframe(_sample())
    assert list(df.columns) == [
        "代码",
        "名称",
        "最新价",
        "涨跌额",
        "涨跌幅",
        "今开",
        "最高",
        "最低",
        "昨收",
        "成交量",
        "成交额",
    ]
    assert len(df) == 2
    assert df.iloc[0]["最新价"] == pytest.approx(419.8)
    assert df.iloc[1]["最新价"] == pytest.approx(0.37)
    assert pd.isna(df.iloc[1]["涨跌幅"])


def test_empty_page_keeps_header() -> None:
    df = to_hk_stock_list_dataframe(HkStockListPage(total=0, items=()))
    assert list(df.columns) == list(HK_STOCK_LIST_COLUMNS_ZH.values())
    assert df.empty

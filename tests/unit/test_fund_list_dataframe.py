"""场内基金列表 DataFrame 适配的行为锁（用固定 FundListPage，不触网）。"""

import pytest

from em.application.dataframe import FUND_LIST_COLUMNS_ZH, to_fund_list_dataframe
from em.domain.models import FundListPage, FundQuote

pd = pytest.importorskip("pandas")


def _sample() -> FundListPage:
    return FundListPage(
        total=2,
        items=(
            FundQuote(code="159915", name="创业板ETF易方达", market="sz", price=2.48, iopv=2.4809),
            FundQuote(code="501018", name="南方原油LOF", market="sh", price=2.062),
        ),
    )


def test_default_chinese_columns() -> None:
    df = to_fund_list_dataframe(_sample())
    assert list(df.columns) == [
        "代码",
        "名称",
        "市场",
        "最新价",
        "IOPV实时估值",
        "基金折价率",
        "涨跌额",
        "涨跌幅",
        "成交量",
        "成交额",
        "开盘价",
        "最高价",
        "最低价",
        "昨收",
        "换手率",
        "流通市值",
        "总市值",
    ]
    assert len(df) == 2
    assert df.iloc[0]["IOPV实时估值"] == pytest.approx(2.4809)
    assert pd.isna(df.iloc[1]["IOPV实时估值"])  # LOF 无 IOPV


def test_empty_page_keeps_header() -> None:
    df = to_fund_list_dataframe(FundListPage(total=0, items=()))
    assert list(df.columns) == list(FUND_LIST_COLUMNS_ZH.values())
    assert df.empty

"""板块 K 线 DataFrame 版的行为锁：复用个股 K 线的中文列名（不触网）。"""

import pytest

from em.application import market_data
from em.domain.models import Kline, KlineSeries
from em.domain.queries import BoardKlineQuery

pd = pytest.importorskip("pandas")


def _sample() -> KlineSeries:
    return KlineSeries(
        code="BK0438",
        name="食品饮料",
        period="day",
        adjust="none",
        items=(
            Kline(date="2026-11-02", open=25296.91, close=26071.40, change_pct=3.09),
            Kline(date="2026-11-03", open=26004.69, close=26262.51, change_pct=0.73),
        ),
    )


def test_df_board_kline_uses_kline_columns(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[BoardKlineQuery | None] = []

    def fake_board_kline_em(
        query: BoardKlineQuery | None = None, settings: object = None
    ) -> KlineSeries:
        seen.append(query)
        return _sample()

    monkeypatch.setattr(market_data, "board_kline_em", fake_board_kline_em)
    query = BoardKlineQuery(board="BK0438")
    df = market_data.df_board_kline_em(query)
    assert seen == [query]
    assert list(df.columns) == [
        "日期",
        "开盘",
        "收盘",
        "最高",
        "最低",
        "成交量",
        "成交额",
        "振幅",
        "涨跌幅",
        "涨跌额",
        "换手率",
    ]
    assert len(df) == 2
    assert df.iloc[0]["收盘"] == pytest.approx(26071.40)
    assert pd.isna(df.iloc[1]["最高"])

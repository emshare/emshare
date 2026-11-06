"""板块（行业 / 概念 / 地域）历史 K 线的映射与请求构建行为锁（用固定报文，不触网）。"""

import json
from pathlib import Path

import pytest

from em.application import registry
from em.channels.eastmoney import config
from em.channels.eastmoney.ashare_boards.board_kline.board_kline_em import (
    board_kline_request,
    normalize_period,
    secid_of,
)
from em.channels.eastmoney.mapping import to_kline_series
from em.domain.models import Kline
from em.domain.queries import BoardKlineQuery

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "eastmoney" / "board_kline_daily.json"


def _load() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_board_kline_maps_meta() -> None:
    request = board_kline_request(BoardKlineQuery())
    series = to_kline_series(_load(), request.period, request.adjust)
    assert series.code == "BK0438"
    assert series.name == "食品饮料"
    assert series.period == "day"
    assert series.adjust == "none"
    assert len(series.items) == 3
    assert all(isinstance(k, Kline) for k in series.items)


def test_board_kline_first_item_fields() -> None:
    first = to_kline_series(_load()).items[0]
    assert first.date == "2026-11-02"
    assert first.open == pytest.approx(25296.91)
    assert first.close == pytest.approx(26071.40)
    assert first.high == pytest.approx(26089.85)
    assert first.low == pytest.approx(25069.29)
    assert first.volume == pytest.approx(26989569.0)
    assert first.amount == pytest.approx(57630504816.0)
    assert first.amplitude == pytest.approx(4.04)
    assert first.change_pct == pytest.approx(3.09)
    assert first.change == pytest.approx(781.61)
    assert first.turnover_rate == pytest.approx(2.87)


def test_secid_of_uses_board_market_prefix() -> None:
    assert secid_of(BoardKlineQuery(board="BK0438")) == "90.BK0438"
    assert secid_of(BoardKlineQuery(board="BK0475")) == "90.BK0475"


@pytest.mark.parametrize(
    ("period", "klt"),
    [("day", 101), ("week", 102), ("month", 103), ("5m", 5), ("60m", 60)],
)
def test_board_kline_request_period_to_klt(period: str, klt: int) -> None:
    request = board_kline_request(BoardKlineQuery(period=period))
    assert request.klt == klt
    assert request.period == period


def test_unknown_period_falls_back_to_day() -> None:
    assert normalize_period("1m") == "day"
    assert board_kline_request(BoardKlineQuery(period="1m")).klt == 101


def test_board_kline_request_params() -> None:
    request = board_kline_request(BoardKlineQuery(board="BK0438", beg="20260101", end="20261106"))
    assert request.url() == f"{config.KLINE_HOST}{config.KLINE_PATH}"
    params = request.params()
    assert params["secid"] == "90.BK0438"
    assert params["klt"] == "101"
    # 板块是指数，固定不复权（实测 fqt=0 / fqt=1 返回一致）
    assert params["fqt"] == "0"
    assert params["beg"] == "20260101"
    assert params["end"] == "20261106"
    assert params["fields1"] == config.KLINE_FIELDS1
    assert params["fields2"] == config.KLINE_FIELDS2


def test_registry_exposes_board_kline_request() -> None:
    assert registry.board_kline_request is board_kline_request

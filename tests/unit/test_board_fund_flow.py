"""板块（行业 / 概念 / 地域）历史资金流的映射与请求构建行为锁（不触网）。"""

import json
from pathlib import Path

import pytest

from em.channels.eastmoney import config
from em.channels.eastmoney.board_fund_flow.board_fund_flow_em import (
    board_fund_flow_request,
    secid_of,
)
from em.channels.eastmoney.mapping import to_board_fund_flow_series
from em.domain.models import BoardFundFlow
from em.domain.queries import BoardFundFlowQuery

FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "eastmoney" / "board_fund_flow_daily.json"
)


def _load() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_to_board_fund_flow_series_maps_meta() -> None:
    series = to_board_fund_flow_series(_load())
    assert series.code == "BK0438"
    assert series.name == "食品饮料"
    assert len(series.items) == 3
    assert all(isinstance(f, BoardFundFlow) for f in series.items)


def test_board_first_item_fields() -> None:
    first = to_board_fund_flow_series(_load()).items[0]
    assert first.date == "2026-04-09"
    assert first.main_net_inflow == pytest.approx(-1435059744.0)
    assert first.small_net_inflow == pytest.approx(890112768.0)
    assert first.medium_net_inflow == pytest.approx(525396736.0)
    assert first.large_net_inflow == pytest.approx(-877367504.0)
    assert first.xlarge_net_inflow == pytest.approx(-557692240.0)
    assert first.main_net_pct == pytest.approx(-6.80)
    assert first.small_net_pct == pytest.approx(4.21)
    assert first.medium_net_pct == pytest.approx(2.49)
    assert first.large_net_pct == pytest.approx(-4.15)
    assert first.xlarge_net_pct == pytest.approx(-2.64)


def test_board_item_has_no_close_or_change_pct() -> None:
    first = to_board_fund_flow_series(_load()).items[0]
    assert not hasattr(first, "close")
    assert not hasattr(first, "change_pct")


def test_board_series_has_no_market() -> None:
    series = to_board_fund_flow_series(_load())
    assert not hasattr(series, "market")


def test_board_main_flow_equals_large_plus_xlarge() -> None:
    first = to_board_fund_flow_series(_load()).items[0]
    assert first.main_net_inflow == pytest.approx(first.large_net_inflow + first.xlarge_net_inflow)


def test_short_board_fund_flow_line_pads_with_none() -> None:
    data = {"rc": 0, "data": {"code": "x", "name": "y", "klines": ["2026-01-02,100.0"]}}
    flow = to_board_fund_flow_series(data).items[0]
    assert flow.main_net_inflow == pytest.approx(100.0)
    assert flow.xlarge_net_inflow is None
    assert flow.xlarge_net_pct is None


def test_empty_board_fund_flow() -> None:
    series = to_board_fund_flow_series({"rc": 0, "data": {}})
    assert series.code == ""
    assert series.items == ()


def test_secid_of_uses_board_market_prefix() -> None:
    assert secid_of(BoardFundFlowQuery(board="BK0438")) == "90.BK0438"
    assert secid_of(BoardFundFlowQuery(board="BK0475")) == "90.BK0475"


def test_board_fund_flow_request_params() -> None:
    request = board_fund_flow_request(BoardFundFlowQuery(board="BK0438"))
    assert request.url() == f"{config.KLINE_HOST}{config.FFLOW_PATH}"
    assert request.market == "bk"
    params = request.params()
    assert params["secid"] == "90.BK0438"
    assert params["lmt"] == "0"
    assert params["klt"] == "101"
    assert params["fields1"] == config.FFLOW_FIELDS1
    assert params["fields2"] == config.FFLOW_FIELDS2
    assert params["ut"] == config.FFLOW_UT

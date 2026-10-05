"""资金流映射与请求构建的行为锁（用固定报文，不触网）。"""

import json
from pathlib import Path

import pytest

from em.channels.eastmoney import config
from em.channels.eastmoney.ashare_stocks.stock_fund_flow.stock_fund_flow_em import (
    fund_flow_request,
    secid_of,
)
from em.channels.eastmoney.mapping import to_fund_flow_series
from em.domain.queries import FundFlowQuery

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "eastmoney" / "fund_flow_daily.json"


def _load() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_to_fund_flow_series_maps_meta_and_items() -> None:
    series = to_fund_flow_series(_load(), market="sz")
    assert series.code == "000001"
    assert series.name == "平安银行"
    assert series.market == "sz"
    assert len(series.items) == 3


def test_to_fund_flow_maps_all_fields() -> None:
    first = to_fund_flow_series(_load()).items[0]
    assert first.date == "2026-04-09"
    assert first.main_net_inflow == pytest.approx(-30314508.0)
    assert first.small_net_inflow == pytest.approx(-37481557.0)
    assert first.medium_net_inflow == pytest.approx(67796066.0)
    assert first.large_net_inflow == pytest.approx(20898638.0)
    assert first.xlarge_net_inflow == pytest.approx(-51213146.0)
    assert first.main_net_pct == pytest.approx(-4.53)
    assert first.small_net_pct == pytest.approx(-5.60)
    assert first.medium_net_pct == pytest.approx(10.13)
    assert first.large_net_pct == pytest.approx(3.12)
    assert first.xlarge_net_pct == pytest.approx(-7.65)
    assert first.close == pytest.approx(10.49)
    assert first.change_pct == pytest.approx(-1.13)


def test_main_flow_equals_large_plus_xlarge() -> None:
    first = to_fund_flow_series(_load()).items[0]
    assert first.main_net_inflow == pytest.approx(first.large_net_inflow + first.xlarge_net_inflow)


def test_short_fund_flow_line_pads_with_none() -> None:
    data = {"rc": 0, "data": {"code": "x", "name": "y", "klines": ["2026-01-02,100.0"]}}
    flow = to_fund_flow_series(data).items[0]
    assert flow.main_net_inflow == pytest.approx(100.0)
    assert flow.xlarge_net_inflow is None
    assert flow.change_pct is None


def test_empty_fund_flow() -> None:
    series = to_fund_flow_series({"rc": 0, "data": {}})
    assert series.code == ""
    assert series.items == ()


def test_secid_of_by_market() -> None:
    assert secid_of(FundFlowQuery(code="000001", market="sz")) == "0.000001"
    assert secid_of(FundFlowQuery(code="600887", market="sh")) == "1.600887"
    assert secid_of(FundFlowQuery(code="830799", market="bj")) == "0.830799"
    assert secid_of(FundFlowQuery(code="000001", market="nope")) == "0.000001"


def test_fund_flow_request_params() -> None:
    request = fund_flow_request(FundFlowQuery(code="000001", market="sz"))
    assert request.url() == f"{config.KLINE_HOST}{config.FFLOW_PATH}"
    params = request.params()
    assert params["secid"] == "0.000001"
    assert params["lmt"] == "0"
    assert params["klt"] == "101"
    assert params["fields1"] == config.FFLOW_FIELDS1
    assert params["fields2"] == config.FFLOW_FIELDS2
    assert params["ut"] == config.FFLOW_UT

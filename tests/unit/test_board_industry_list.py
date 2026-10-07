"""板块列表（行业 / 概念 / 地域）的映射与请求构建行为锁（不触网）。"""

import json
from pathlib import Path

import pytest

from em.channels.eastmoney import config
from em.channels.eastmoney.ashare_boards.board_industry_list.board_industry_list_em import (
    board_industry_list_request,
    fs_of,
    industry_level_s,
)
from em.channels.eastmoney.mapping import to_board_list_page
from em.domain.models import Board, BoardListPage
from em.domain.queries import BoardListQuery

FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "eastmoney" / "clist_board_industry.json"
)


def _load() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_to_board_list_page_maps_meta() -> None:
    page = to_board_list_page(_load())
    assert isinstance(page, BoardListPage)
    assert page.total == 31
    assert len(page.items) == 2
    assert all(isinstance(b, Board) for b in page.items)


def test_board_first_item_fields() -> None:
    first = to_board_list_page(_load()).items[0]
    assert first.code == "BK1216"
    assert first.name == "医药生物"
    assert first.price == pytest.approx(4767.98)
    assert first.change_pct == pytest.approx(2.03)
    assert first.change == pytest.approx(95.04)
    assert first.turnover_rate == pytest.approx(2.54)
    assert first.turnover == pytest.approx(6901833728000.0)
    assert first.up_count == 429
    assert first.down_count == 70
    assert first.leader_code == "000710"
    assert first.leader_name == "贝瑞基因"
    assert first.leader_change_pct == pytest.approx(10.02)
    assert first.laggard_code == "920201"
    assert first.laggard_name == "百瑞吉"
    assert first.laggard_change_pct == pytest.approx(-8.58)


def test_board_second_item_negative_change() -> None:
    second = to_board_list_page(_load()).items[1]
    assert second.code == "BK0438"
    assert second.change_pct == pytest.approx(-1.50)
    assert second.change == pytest.approx(-20.00)
    assert second.up_count == 30
    assert second.down_count == 50
    assert second.leader_change_pct == pytest.approx(5.00)
    assert second.laggard_change_pct == pytest.approx(-3.00)


def test_empty_board_list() -> None:
    page = to_board_list_page({"rc": 0, "data": {}})
    assert page.total == 0
    assert page.items == ()


def test_board_missing_leader_becomes_none() -> None:
    page = to_board_list_page(
        {"rc": 0, "data": {"total": 1, "diff": [{"f12": "BK0001", "f14": "测试"}]}}
    )
    board = page.items[0]
    assert board.code == "BK0001"
    assert board.price is None
    assert board.up_count is None
    assert board.leader_code is None
    assert board.leader_name is None
    assert board.laggard_change_pct is None


def test_industry_level_s_maps_levels() -> None:
    assert industry_level_s("1") == "2"
    assert industry_level_s("2") == "4"
    assert industry_level_s("3") == "8"


def test_industry_level_s_unknown_fallback() -> None:
    assert industry_level_s("9") == "2"
    assert industry_level_s("x") == "2"


def test_fs_of_industry_levels() -> None:
    assert fs_of(BoardListQuery(board_type="industry", level="1")) == "m:90+s:2+f:!50"
    assert fs_of(BoardListQuery(board_type="industry", level="2")) == "m:90+s:4+f:!50"
    assert fs_of(BoardListQuery(board_type="industry", level="3")) == "m:90+s:8+f:!50"


def test_fs_of_industry_all() -> None:
    assert fs_of(BoardListQuery(board_type="industry", level="all")) == config.BOARD_INDUSTRY_ALL_FS
    assert fs_of(BoardListQuery(board_type="industry", level="all")) == "m:90+t:2+f:!50"


def test_fs_of_concept_and_region() -> None:
    assert fs_of(BoardListQuery(board_type="concept")) == config.BOARD_CONCEPT_FS
    assert fs_of(BoardListQuery(board_type="region")) == config.BOARD_REGION_FS


def test_fs_of_concept_ignores_level() -> None:
    assert fs_of(BoardListQuery(board_type="concept", level="3")) == config.BOARD_CONCEPT_FS


def test_fs_of_unknown_type_fallback_industry() -> None:
    assert fs_of(BoardListQuery(board_type="nope", level="2")) == "m:90+s:4+f:!50"


def test_board_industry_list_request_params() -> None:
    request = board_industry_list_request(BoardListQuery(board_type="industry", level="1"))
    assert request.url() == f"{config.GUEST_HOST}{config.CLIST_PATH}"
    assert request.fs == "m:90+s:2+f:!50"
    assert request.fields == config.BOARD_LIST_FIELDS
    assert request.fid == "f3"
    params = request.params()
    assert params["fs"] == "m:90+s:2+f:!50"
    assert params["fields"] == config.BOARD_LIST_FIELDS
    assert params["fid"] == "f3"
    assert params["pn"] == "1"
    assert params["pz"] == "20"
    assert params["ut"] == config.UT


def test_board_industry_list_request_concept_params() -> None:
    request = board_industry_list_request(
        BoardListQuery(board_type="concept", sort="f6", page=2, size=50)
    )
    assert request.fs == config.BOARD_CONCEPT_FS
    assert request.fid == "f6"
    params = request.params()
    assert params["pn"] == "2"
    assert params["pz"] == "50"

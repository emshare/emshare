"""接口检索的行为锁（纯本地，不触网）。"""

import pytest

from em import interface_info, list_categories, search
from em.core.errors import InterfaceNotFoundError


def test_search_exact_name_top() -> None:
    rows = search("board_constituent_em")
    assert rows[0]["接口名"] == "board_constituent_em"
    assert rows[0]["匹配分"] >= 100.0


def test_search_by_keyword() -> None:
    rows = search("板块")
    assert rows and rows[0]["接口名"] == "board_constituent_em"


def test_search_market_by_keyword() -> None:
    rows = search("全市场 A股")
    assert rows and rows[0]["接口名"] == "stock_list_em"


def test_search_kline_by_keyword() -> None:
    # 个股与板块 K 线对“K线”同分，同分按接口名排序；加“个股”即可区分
    names = [r["接口名"] for r in search("K线")[:2]]
    assert set(names) == {"stock_kline_em", "board_kline_em"}
    assert search("个股 K线")[0]["接口名"] == "stock_kline_em"


def test_search_trends_by_keyword() -> None:
    rows = search("分时")
    assert rows and rows[0]["接口名"] == "stock_trends_em"


def test_search_fund_flow_by_keyword() -> None:
    names = [r["接口名"] for r in search("fund_flow")]
    assert "stock_fund_flow_em" in names
    assert "board_fund_flow_em" in names
    assert search("stock_fund_flow_em")[0]["接口名"] == "stock_fund_flow_em"


def test_search_board_fund_flow_by_keyword() -> None:
    rows = search("板块历史资金流")
    assert rows and rows[0]["接口名"] == "board_fund_flow_em"


def test_search_empty_query() -> None:
    assert search("") == []
    assert search("   ") == []


def test_search_negative_limit_raises() -> None:
    with pytest.raises(ValueError):
        search("board", limit=-1)


def test_search_category_filter() -> None:
    rows = search("股", category="market")
    assert all(r["类目"] == "market" for r in rows)
    assert search("股", category="nope") == []


def test_search_documented_only() -> None:
    rows = search("fetch", documented_only=True)
    assert all(r["有无文档"] for r in rows)


def test_interface_info_returns_full_record() -> None:
    info = interface_info("board_constituent_em")
    assert info["name"] == "board_constituent_em"
    assert info["category"] == "board"
    assert info["dataframe_variant"] == "df_board_constituent_em"
    assert len(info["inputs"]) == 4
    assert any(f["name"] == "main_net_inflow" for f in info["outputs"])
    assert "board_constituent_em(" in info["example"]


def test_interface_info_unknown_raises_with_hint() -> None:
    with pytest.raises(InterfaceNotFoundError) as exc:
        interface_info("fetch_nope")
    assert "候选" in str(exc.value)


def test_interface_info_kline() -> None:
    info = interface_info("stock_kline_em")
    assert info["category"] == "kline"
    assert info["dataframe_variant"] == "df_stock_kline_em"
    assert len(info["inputs"]) == 6
    assert any(f["name"] == "close" for f in info["outputs"])
    assert "stock_kline_em(" in info["example"]


def test_interface_info_trends() -> None:
    info = interface_info("stock_trends_em")
    assert info["category"] == "trends"
    assert info["dataframe_variant"] == "df_stock_trends_em"
    assert len(info["inputs"]) == 5
    assert any(f["name"] == "avg_price" for f in info["outputs"])
    assert "stock_trends_em(" in info["example"]


def test_interface_info_fund_flow() -> None:
    info = interface_info("stock_fund_flow_em")
    assert info["category"] == "fund_flow"
    assert info["dataframe_variant"] == "df_stock_fund_flow_em"
    assert len(info["inputs"]) == 2
    assert any(f["name"] == "xlarge_net_inflow" for f in info["outputs"])
    assert "stock_fund_flow_em(" in info["example"]


def test_interface_info_board_fund_flow() -> None:
    info = interface_info("board_fund_flow_em")
    assert info["category"] == "fund_flow"
    assert info["dataframe_variant"] == "df_board_fund_flow_em"
    assert len(info["inputs"]) == 1
    assert info["inputs"][0]["name"] == "board"
    names = [f["name"] for f in info["outputs"]]
    assert len(names) == 11
    assert "main_net_inflow" in names
    assert "close" not in names
    assert "change_pct" not in names
    assert "board_fund_flow_em(" in info["example"]


def test_search_board_industry_list_by_keyword() -> None:
    rows = search("板块列表")
    assert rows and rows[0]["接口名"] == "board_industry_list_em"


def test_interface_info_board_industry_list() -> None:
    info = interface_info("board_industry_list_em")
    assert info["category"] == "board"
    assert info["dataframe_variant"] == "df_board_industry_list_em"
    assert len(info["inputs"]) == 5
    input_names = [p["name"] for p in info["inputs"]]
    assert input_names == ["board_type", "level", "sort", "page", "size"]
    out_names = [f["name"] for f in info["outputs"]]
    assert "up_count" in out_names
    assert "leader_name" in out_names
    assert "laggard_change_pct" in out_names
    assert "board_industry_list_em(" in info["example"]


def test_list_categories() -> None:
    cats = list_categories()
    assert cats == [
        {"类目": "board", "接口数": 2},
        {"类目": "fund_flow", "接口数": 2},
        {"类目": "hk", "接口数": 1},
        {"类目": "index", "接口数": 1},
        {"类目": "kline", "接口数": 2},
        {"类目": "market", "接口数": 1},
        {"类目": "trends", "接口数": 1},
    ]


def test_search_index_list_by_keyword() -> None:
    rows = search("指数列表")
    assert rows and rows[0]["接口名"] == "index_list_em"


def test_interface_info_index_list() -> None:
    info = interface_info("index_list_em")
    assert info["category"] == "index"
    assert info["dataframe_variant"] == "df_index_list_em"
    assert [p["name"] for p in info["inputs"]] == ["series", "sort", "page", "size"]
    units = {f["name"]: f["unit"] for f in info["outputs"]}
    assert len(units) == 14
    assert units["price"] == "点"
    assert units["turnover"] == "元"
    assert "market" in units
    assert "index_list_em(" in info["example"]


def test_search_hk_stock_list_by_keyword() -> None:
    rows = search("港股")
    assert rows and rows[0]["接口名"] == "hk_stock_list_em"


def test_interface_info_hk_stock_list() -> None:
    info = interface_info("hk_stock_list_em")
    assert info["category"] == "hk"
    assert info["dataframe_variant"] == "df_hk_stock_list_em"
    assert [p["name"] for p in info["inputs"]] == ["scope", "sort", "page", "size"]
    units = {f["name"]: f["unit"] for f in info["outputs"]}
    assert len(units) == 11
    assert units["price"] == "港元"
    assert units["turnover"] == "港元"
    assert units["volume"] == "股"
    assert "hk_stock_list_em(" in info["example"]


def test_search_board_kline_by_keyword() -> None:
    rows = search("板块 K线")
    assert rows and rows[0]["接口名"] == "board_kline_em"


def test_interface_info_board_kline() -> None:
    info = interface_info("board_kline_em")
    assert info["category"] == "kline"
    assert info["dataframe_variant"] == "df_board_kline_em"
    assert [p["name"] for p in info["inputs"]] == ["board", "period", "beg", "end"]
    units = {f["name"]: f["unit"] for f in info["outputs"]}
    assert len(units) == 11
    # 板块是指数：价格类字段单位为点，成交额仍为元
    assert units["close"] == "点"
    assert units["change"] == "点"
    assert units["amount"] == "元"
    assert "board_kline_em(" in info["example"]


# -- DataFrame 包装（需 pandas，缺失则跳过）--

pd = pytest.importorskip("pandas")


def test_search_df_returns_dataframe() -> None:
    from em import search_df

    df = search_df("board_constituent_em")
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["接口名", "类目", "描述", "有无文档", "匹配分"]
    assert df.iloc[0]["接口名"] == "board_constituent_em"


def test_list_categories_df_returns_dataframe() -> None:
    from em import list_categories_df

    df = list_categories_df()
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["类目", "接口数"]
    assert len(df) == 7


def test_interface_info_df_returns_param_and_field_tables() -> None:
    from em import interface_info_df

    tables = interface_info_df("board_constituent_em")
    assert set(tables) == {"inputs", "outputs"}
    assert isinstance(tables["inputs"], pd.DataFrame)
    assert isinstance(tables["outputs"], pd.DataFrame)
    assert list(tables["inputs"].columns) == ["名称", "类型", "必填", "默认值", "描述"]
    assert list(tables["outputs"].columns) == ["名称", "类型", "单位", "描述"]
    assert len(tables["inputs"]) == 4
    assert tables["inputs"].iloc[0]["名称"] == "board"
    assert any(tables["outputs"]["名称"] == "main_net_inflow")

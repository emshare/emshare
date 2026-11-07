"""沪深京 A 股列表 scope 筛选的请求构建行为锁（不触网）。"""

import pytest

from em.channels.eastmoney import config
from em.channels.eastmoney.ashare_stocks.stock_list.stock_list_em import (
    MARKET_FS,
    MARKET_SCOPE_FS,
    normalize_scope,
    stock_list_request,
)
from em.domain.queries import MarketQuery


def test_default_scope_keeps_original_full_market_fs() -> None:
    # 全量口径不得漂移：stock_list_all_em 与预筛探测都按它请求
    assert MarketQuery().scope == "all"
    expected = "m:0+t:6+f:!2,m:0+t:80+f:!2,m:1+t:2+f:!2,m:1+t:23+f:!2,m:0+t:81+s:262144+f:!2"
    assert expected == MARKET_FS
    assert stock_list_request(MarketQuery()).fs == MARKET_FS


def test_sh_sz_bj_partition_the_full_market() -> None:
    # 三市分段拼起来正好是全量的各段（实测 total 2319 + 2906 + 356 = 5581）
    parts = ",".join(MARKET_SCOPE_FS[s] for s in ("sh", "sz", "bj")).split(",")
    assert sorted(parts) == sorted(MARKET_FS.split(","))


def test_boards_are_subsets_of_their_market() -> None:
    assert MARKET_SCOPE_FS["kc"] in MARKET_SCOPE_FS["sh"].split(",")
    assert MARKET_SCOPE_FS["cy"] in MARKET_SCOPE_FS["sz"].split(",")


@pytest.mark.parametrize(("scope", "flag"), [("new", "8"), ("st", "4")])
def test_flag_scopes_are_limited_to_a_share_segments(scope: str, flag: str) -> None:
    # 实测 f:8 / f:4 与 f:!2 叠加会让筛选失效（返回 5.8 万条），所以不能带 f:!2；
    # 又必须按 A 股各段限定，否则 st 会混入 B 股与三板代码（386 条 vs 197 条）
    parts = MARKET_SCOPE_FS[scope].split(",")
    assert all("f:!2" not in p for p in parts)
    segments = [p.removesuffix("+f:!2") for p in MARKET_FS.split(",")]
    assert parts == [f"{seg}+f:{flag}" for seg in segments]


@pytest.mark.parametrize("scope", sorted(MARKET_SCOPE_FS))
def test_stock_list_request_uses_scope_fs(scope: str) -> None:
    request = stock_list_request(MarketQuery(scope=scope, sort="f6", page=2, size=50))
    assert request.host == config.GUEST_HOST
    assert request.fs == MARKET_SCOPE_FS[scope]
    params = request.params()
    assert params["fs"] == MARKET_SCOPE_FS[scope]
    assert params["fid"] == "f6"
    assert params["pn"] == "2"
    assert params["pz"] == "50"


def test_unknown_scope_falls_back_to_all() -> None:
    assert normalize_scope("hk") == "all"
    assert stock_list_request(MarketQuery(scope="hk")).fs == MARKET_FS

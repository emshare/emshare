"""采购账本落盘：字段口径、追加写入、写盘失败不影响取数、按源聚合。"""

import json
from pathlib import Path

import pytest

from em.application import ledger


def _pool(**extra: object) -> dict[str, object]:
    base: dict[str, object] = {
        "fetch_calls": 2,
        "ips_returned": 10,
        "ips_unique": 10,
        "prefilter_rejected": 6,
        "ips_adopted": 4,
        "ips_served": 4,
        "ips_productive": 3,
        "soft_failures": 1,
        "degraded_adopted": 0,
        "degraded_events": 1,
        "source_breaker_trips": 0,
        "refill_sec": 0.5,
        "prefilter_sec": 1.5,
        "source_stats": {
            "src0:x#1": {"calls": 2, "returned": 10, "rejected": 6, "adopted": 4}
        },
    }
    base.update(extra)
    return base


_TIMING = {
    "proxy_requests": 58,
    "proxy_sec": 24.5,
    "proxy_wait_sec": 2.1,
    "backoff_sec": 0.0,
    "failed_attempts": 2,
}

# 这些字段是跨版本合并历史数据的最小集合：改名/删除会让旧账本断档，新增则安全
_REQUIRED_KEYS = {
    "ts",
    "pages",
    "items",
    "wall",
    "ips_returned",
    "prefilter_rejected",
    "ips_adopted",
    "ips_productive",
    "source_breaker_trips",
    "proxy_requests",
    "failed_attempts",
    "prefiltered",
    "sources",
}


def test_build_row_has_stable_schema() -> None:
    row = ledger.build_row(_pool(), _TIMING, pages=56, items=5580, wall=8.66)
    assert set(row) >= _REQUIRED_KEYS
    assert row["pages"] == 56
    assert row["ips_returned"] == 10
    assert row["ips_productive"] == 3
    assert row["failed_attempts"] == 2
    assert row["sources"]["src0:x#1"]["rejected"] == 6  # type: ignore[index]
    assert "T" in str(row["ts"])  # ISO 时间戳
    json.dumps(row)  # 必须可序列化


def test_record_appends_jsonl(tmp_path, monkeypatch) -> None:
    path = tmp_path / "sub" / "ledger.jsonl"
    monkeypatch.setenv("EM_LEDGER_PATH", str(path))
    ledger.record(_pool(), _TIMING, 56, 5580, 8.0)
    ledger.record(_pool(ips_productive=1), _TIMING, 56, 5580, 9.0)

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["pages"] == 56
    assert json.loads(lines[1])["ips_productive"] == 1


def test_record_is_best_effort(tmp_path, monkeypatch, caplog) -> None:
    # 账本是旁路观测：父路径不可写时只告警，绝不让取数失败
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setenv("EM_LEDGER_PATH", str(blocker / "ledger.jsonl"))
    caplog.set_level("WARNING", logger="em.application.ledger")

    ledger.record(_pool(), _TIMING, 56, 5580, 8.0)

    assert any("账本写入失败" in r.message for r in caplog.records)


def test_ledger_path_defaults_and_disable(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("EM_LEDGER_PATH", raising=False)
    assert ledger.ledger_path() == Path(ledger.DEFAULT_LEDGER_PATH)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EM_LEDGER_PATH", "none")
    assert ledger.ledger_path() is None
    ledger.record(_pool(), _TIMING, 56, 5580, 8.0)
    assert not (tmp_path / ".em_ledger.jsonl").exists()


def test_load_skips_broken_lines(tmp_path) -> None:
    path = tmp_path / "ledger.jsonl"
    path.write_text('{"pages": 1}\n\n{bad json}\n{"pages": 2}\n', encoding="utf-8")

    assert [r["pages"] for r in ledger.load(path)] == [1, 2]
    assert ledger.load(tmp_path / "missing.jsonl") == []


def test_build_row_records_prefiltered_sources() -> None:
    # 未预筛的源"淘汰率恒为 0"是构造出来的，必须在账本里标出，否则报表会把它排到第一
    row = ledger.build_row(_pool(prefiltered=["src0:x#1"]), _TIMING, 56, 5580, 8.0)
    assert row["prefiltered"] == ["src0:x#1"]


def test_aggregate_marks_unprefiltered_sources() -> None:
    rows = [
        {
            "prefiltered": ["good#1"],
            "sources": {
                "good#1": {"calls": 1, "returned": 5, "rejected": 3, "adopted": 2},
                "backup#2": {"calls": 1, "returned": 5, "rejected": 0, "adopted": 5},
            },
        }
    ]
    agg = ledger.aggregate_sources(rows)

    assert agg["good#1"]["pref"] == 1.0
    assert agg["good#1"]["tagged"] == 1.0
    assert agg["backup#2"]["pref"] == 0.0  # 未预筛
    assert agg["backup#2"]["tagged"] == 1.0  # 但账本有标记，可以确定


def test_aggregate_marks_legacy_rows_as_untagged() -> None:
    # 旧账本没有 prefiltered 字段：只能标"未知"，不能当成"未预筛"
    rows = [{"sources": {"x#1": {"calls": 1, "returned": 5, "rejected": 0, "adopted": 5}}}]
    assert ledger.aggregate_sources(rows)["x#1"]["tagged"] == 0.0


def test_aggregate_sources_ranks_by_yield() -> None:
    rows = [
        {"sources": {"good#1": {"calls": 2, "returned": 10, "rejected": 1, "adopted": 9}}},
        {
            "sources": {
                "good#1": {"calls": 1, "returned": 5, "rejected": 0, "adopted": 5},
                "bad#2": {"calls": 2, "returned": 10, "rejected": 9, "adopted": 1},
            }
        },
    ]
    agg = ledger.aggregate_sources(rows)

    assert agg["good#1"]["calls"] == 3
    assert agg["good#1"]["adopted"] == 14
    assert agg["good#1"]["reject_rate"] == pytest.approx(1 / 15)
    assert agg["bad#2"]["adopted_per_call"] == pytest.approx(0.5)
    assert agg["good#1"]["adopted_per_call"] > agg["bad#2"]["adopted_per_call"]

#!/usr/bin/env python3
"""采购账本报表：按源汇总跨天数据，决定主备顺序与是否换源。

用法：
    python3 tools/ledger_report.py                 # 默认读 EM_LEDGER_PATH / XDG 数据目录
    python3 tools/ledger_report.py --limit 10      # 只看最近 10 次
    python3 tools/ledger_report.py --path /tmp/x.jsonl

判读：`每次进池` 越高、`淘汰率` 越低，说明该源买到的 IP 越值钱；
只有当两个源的出现次数都足够（≥3 次）时，比较才有意义。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from em.application.ledger import aggregate_sources, ledger_path, load


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="采购账本报表（按源汇总）")
    ap.add_argument("--path", default=None, help="账本文件；缺省取 EM_LEDGER_PATH / XDG 数据目录")
    ap.add_argument("--limit", type=int, default=20, help="只看最近 N 次运行（默认 20）")
    args = ap.parse_args(argv)

    path = Path(args.path).expanduser() if args.path else ledger_path()
    if path is None:
        print("账本已关闭（EM_LEDGER_PATH=none）")
        return 1
    rows = load(path)
    if not rows:
        print(f"没有账本数据：{path}")
        return 1
    rows = rows[-max(args.limit, 1) :]

    pages = sum(int(r.get("pages", 0) or 0) for r in rows)
    returned = sum(int(r.get("ips_returned", 0) or 0) for r in rows)
    adopted = sum(int(r.get("ips_adopted", 0) or 0) for r in rows)
    productive = sum(int(r.get("ips_productive", 0) or 0) for r in rows)
    failed = sum(int(r.get("failed_attempts", 0) or 0) for r in rows)
    trips = sum(int(r.get("source_breaker_trips", 0) or 0) for r in rows)
    degraded = sum(int(r.get("degraded_adopted", 0) or 0) for r in rows)

    print(f"账本：{path}｜最近 {len(rows)} 次运行")
    print(
        f"总页数 {pages}｜采购 {returned}｜进池 {adopted}｜有产出 {productive}"
        f"｜单有效 IP {pages / max(productive, 1):.1f} 页"
        f"｜失败 {failed}｜熔断 {trips}｜降级放行 {degraded}"
    )
    ranked: list[tuple[str, dict[str, float], str]] = []
    for name, stat in aggregate_sources(rows).items():
        if stat["pref"] >= 1.0:
            tag = "是"
        elif stat["tagged"] >= 1.0:
            tag = "否"
        else:
            tag = "?"  # 旧账本没有 prefiltered 字段
        ranked.append((name, stat, tag))
    # 预筛源优先排名：未预筛的"淘汰率恒为 0"是构造出来的，不能混在同一列里比
    ranked.sort(key=lambda x: (x[2] != "是", -x[1]["adopted_per_call"]))

    print()
    print(
        f"{'源':<32}{'预筛':>4}{'次数':>5}{'回源':>6}{'交付':>6}"
        f"{'淘汰':>6}{'淘汰率':>8}{'进池':>6}{'每次进池':>10}"
    )
    flagged = False
    for name, stat, tag in ranked:
        comparable = tag == "是"
        flagged = flagged or not comparable
        rate = f"{stat['reject_rate']:>7.0%}" if comparable else f"{'-':>7}"
        per = f"{stat['adopted_per_call']:>9.2f}" + (" " if comparable else "*")
        print(
            f"{name:<32}{tag:>4}{int(stat['runs']):>5}{int(stat['calls']):>6}"
            f"{int(stat['returned']):>6}{int(stat['rejected']):>6}{rate}"
            f"{int(stat['adopted']):>6}{per}"
        )
    if flagged:
        print()
        print("  * 未参与预筛（或旧账本无标记）：淘汰率与每次进池不可与预筛源比较——")
        print("    未经筛选的 IP 全部进池，死 IP 由业务侧淘汰，数字天然好看。")
    print()
    print("提示：出现次数 <3 的源先不下结论；`每次进池` 是同一批里能用的 IP 数，越高越好。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

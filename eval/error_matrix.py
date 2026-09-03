"""Матрица ошибок: вариант × класс дефекта (по кодам MATRIX.md), из сырого JSON бенча.

    python eval/bench.py --variants ... --json eval/night/raw.json
    python eval/error_matrix.py eval/night/raw.json [--out eval/error_matrix.md]

Выход: recall по группам A–F и по кодам; систематические слепые зоны (не ловит
ни один вариант); уникальные вклады (ловит ровно один вариант); шум по вариантам.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("raw", nargs="+")
    ap.add_argument("--out", default="eval/error_matrix.md")
    args = ap.parse_args()

    records = []
    for p in args.raw:
        records += json.loads((ROOT / p).read_text(encoding="utf-8"))

    variants = sorted({r["variant"] for r in records})
    # (variant, code) -> [hit, total]; (variant, group) -> [hit, total]
    by_code = defaultdict(lambda: [0, 0])
    by_group = defaultdict(lambda: [0, 0])
    by_diff = defaultdict(lambda: [0, 0])
    # defect key -> {variant: hit}
    defect_hits: dict[tuple, dict] = defaultdict(dict)
    defect_meta: dict[tuple, dict] = {}
    noise = defaultdict(list)

    for r in records:
        v = r["variant"]
        for did, d in r.get("defects", {}).items():
            key = (r["target"], did)
            defect_hits[key][v] = d["hit"]
            defect_meta[key] = d
            by_code[(v, d["code"])][1] += 1
            by_group[(v, d["code"][:1])][1] += 1
            by_diff[(v, d["difficulty"])][1] += 1
            if d["hit"]:
                by_code[(v, d["code"])][0] += 1
                by_group[(v, d["code"][:1])][0] += 1
                by_diff[(v, d["difficulty"])][0] += 1
        for f in r.get("noise", []):
            noise[v].append(f)

    groups = sorted({g for (_, g) in by_group})
    codes = sorted({c for (_, c) in by_code})
    diffs = [d for d in ("easy", "medium", "hard", "expert") if any((v, d) in by_diff for v in variants)]

    def cell(table, v, k):
        h, t = table.get((v, k), (0, 0))
        return f"{h}/{t}" if t else "·"

    lines = ["# Матрица ошибок (вариант × класс дефекта)", ""]
    lines.append("## По группам матрицы")
    lines.append("| Вариант | " + " | ".join(groups) + " | easy | medium | hard | expert |")
    lines.append("|" + "---|" * (len(groups) + 5))
    for v in variants:
        row = [cell(by_group, v, g) for g in groups] + [cell(by_diff, v, d) for d in ("easy", "medium", "hard", "expert")]
        lines.append(f"| {v} | " + " | ".join(row) + " |")

    lines.append("\n## По кодам (полные коды MATRIX.md)")
    lines.append("| Вариант | " + " | ".join(codes) + " |")
    lines.append("|" + "---|" * (len(codes) + 1))
    for v in variants:
        lines.append(f"| {v} | " + " | ".join(cell(by_code, v, c) for c in codes) + " |")

    blind = [(k, m) for k, m in defect_meta.items()
             if defect_hits[k] and not any(defect_hits[k].values())]
    lines.append(f"\n## Систематические слепые зоны (не пойманы НИ ОДНИМ из {len(variants)} вариантов): {len(blind)}")
    for (target, did), m in sorted(blind):
        lines.append(f"- **[{m['code']}/{m['difficulty']}] {did}** ({target}): {m['description']}")

    lines.append("\n## Уникальные вклады (дефект пойман ровно одним вариантом)")
    for (target, did), hits in sorted(defect_hits.items()):
        winners = [v for v, h in hits.items() if h]
        if len(winners) == 1 and len(hits) > 1:
            m = defect_meta[(target, did)]
            lines.append(f"- {winners[0]} ← [{m['code']}] {did} ({target}): {m['description'][:90]}")

    lines.append("\n## Шум на чистом документе (medium+)")
    for v in variants:
        items = noise.get(v, [])
        lines.append(f"- **{v}: {len(items)}**")
        for f in items[:6]:
            lines.append(f"    - {f['severity']} {f['category']}: {f['why'][:100]}")

    out = ROOT / args.out
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:20]))
    print(f"...\nПолная матрица: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Точность по «лишним» находкам бенча (raw JSON) — заготовка разметки и подсчёт.

    python eval/bench_precision.py skeleton eval/night/raw_exp19_oss_a.json [...] > eval/labels/exp19_skeleton.yaml
    python eval/bench_precision.py score eval/labels/exp19_labels.yaml eval/night/raw_exp19_oss_a.json [...]

skeleton: все extras (не совпавшие с голдом) и noise (clean-документ) → YAML со строками
  {variant, target, idx, category, severity, why, verdict: ?, cls: ?}; verdict ∈ TP / FP / NA, cls — класс мусора
  (na-slot / placeholder-name / generic-whatif / rule-threshold / gold-dup / new).
score: precision по вариантам = (совпавшие с голдом + TP среди лишних) / все находки; шум@clean отдельно.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import yaml


def load_raw(paths: list[str]) -> list[dict]:
    recs: list[dict] = []
    for p in paths:
        recs.extend(json.loads(Path(p).read_text(encoding="utf-8")))
    return recs


def skeleton(paths: list[str]) -> None:
    rows = []
    for r in load_raw(paths):
        items = r.get("extras") or r.get("noise") or []
        for i, f in enumerate(items):
            rows.append({"variant": r["variant"], "target": r["target"], "idx": i,
                         "category": f["category"], "severity": f["severity"],
                         "why": f["why"], "verdict": "?", "cls": "?"})
    print(yaml.safe_dump({"labels": rows}, allow_unicode=True, sort_keys=False, width=200))


def score(labels_path: str, paths: list[str]) -> None:
    labels = yaml.safe_load(Path(labels_path).read_text(encoding="utf-8"))["labels"]
    lab = {(x["variant"], x["target"], x["idx"]): x for x in labels}
    per_variant: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    cls_count: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in load_raw(paths):
        v = r["variant"]
        hits = sum(1 for d in r.get("defects", {}).values() if d.get("hit"))
        items = r.get("extras") or r.get("noise") or []
        is_clean = not r.get("defects")
        per_variant[v]["hit"] += hits
        per_variant[v]["gold"] += len(r.get("defects", {}))
        for i, _ in enumerate(items):
            x = lab.get((v, r["target"], i))
            verdict = (x or {}).get("verdict", "?")
            key = "clean_" if is_clean else ""
            per_variant[v][key + verdict] += 1
            if verdict in ("FP", "NA"):
                cls_count[v][(x or {}).get("cls", "?")] += 1
    print("| Вариант | recall | находок | TP среди лишних | FP | NA | ? | precision | шум@clean (не-TP) |")
    print("|---|---|---|---|---|---|---|---|---|")
    for v, c in per_variant.items():
        total = c["hit"] + c["TP"] + c["FP"] + c["NA"] + c["?"]
        tp = c["hit"] + c["TP"]
        prec = f"{tp / total:.0%}" if total else "—"
        clean_bad = c["clean_FP"] + c["clean_NA"] + c["clean_?"]
        print(f"| {v} | {c['hit']}/{c['gold']} | {total} | {c['TP']} | {c['FP']} | {c['NA']} | {c['?']} | {prec} | {clean_bad} |")
    print("\nКлассы мусора (FP+NA) по вариантам:")
    for v, cc in cls_count.items():
        print(f"- {v}: " + ", ".join(f"{k} {n}" for k, n in sorted(cc.items(), key=lambda x: -x[1])))


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__); return 2
    if sys.argv[1] == "skeleton":
        skeleton(sys.argv[2:])
    elif sys.argv[1] == "score":
        score(sys.argv[2], sys.argv[3:])
    else:
        print(__doc__); return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

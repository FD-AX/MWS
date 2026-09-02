"""Бенч: варианты × цели → сводная таблица + разбор промахов («где ошибается»).

Использование:
    python eval/bench.py                     # только v1 (без LLM)
    python eval/bench.py --variants v1,v0b,v2,v2e
    python eval/bench.py --out eval/bench_report.md

Варианты: v1 = детерминированный слой; v0b = бейзлайн одним промптом;
v2 = полный конвейер; v2e = конвейер + semantic entropy. LLM-варианты требуют .env.
"""
from __future__ import annotations

import argparse
import datetime
import sys
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_eval import finding_matches  # noqa: E402
from tz_review.pipeline import review  # noqa: E402
from tz_review.rubric import load_rubric  # noqa: E402

VARIANTS = {
    "v1":  {"llm": False, "baseline": False, "entropy": False, "graph": False},
    "v1g": {"llm": False, "baseline": False, "entropy": False, "graph": True},
    "v0b": {"llm": True,  "baseline": True,  "entropy": False, "graph": False},
    "v2":  {"llm": True,  "baseline": False, "entropy": False, "graph": False},
    "v2g": {"llm": True,  "baseline": False, "entropy": False, "graph": True},
    "v2e": {"llm": True,  "baseline": False, "entropy": True,  "graph": True},
    # h5 = граф + только «компиляция ТЗ» (изолированный вклад гипотезы H5)
    "h5":  {"llm": True,  "baseline": False, "entropy": False, "graph": True,
            "passes": ["compile"]},
    # v3 = полный конвейер + граф + компиляция
    "v3":  {"llm": True,  "baseline": False, "entropy": False, "graph": True,
            "passes": ["checklist", "document_level", "developer_sim", "compile"]},
}


def evaluate(result, gold_defects):
    findings = [f.model_dump() for f in result.findings]
    hits, matched_fids = {}, set()
    for d in gold_defects:
        found = [f for f in findings if finding_matches(d, f)]
        hits[d["id"]] = found
        matched_fids.update(f["fid"] for f in found)
    extras = [f for f in findings if f["fid"] not in matched_fids]
    by_group = defaultdict(lambda: [0, 0])
    by_diff = defaultdict(lambda: [0, 0])
    for d in gold_defects:
        g = str(d.get("code", "?"))[:1]
        by_group[g][1] += 1
        by_diff[str(d.get("difficulty", "?"))][1] += 1
        if hits[d["id"]]:
            by_group[g][0] += 1
            by_diff[str(d.get("difficulty", "?"))][0] += 1
    return hits, extras, dict(by_group), dict(by_diff)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", default="v1")
    ap.add_argument("--targets", default="eval/targets.yaml")
    ap.add_argument("--out", default="eval/bench_report.md")
    args = ap.parse_args()

    variants = [v.strip() for v in args.variants.split(",")]
    unknown = [v for v in variants if v not in VARIANTS]
    if unknown:
        raise SystemExit(f"Неизвестные варианты: {unknown}. Доступны: {list(VARIANTS)}")

    targets = yaml.safe_load((ROOT / args.targets).read_text(encoding="utf-8"))["targets"]
    rubric = load_rubric()

    llm = None
    if any(VARIANTS[v]["llm"] for v in variants):
        try:
            from tz_review.config import settings_or_die
            from tz_review.llm import LLM
            llm = LLM(settings_or_die())
        except SystemExit as e:
            print(f"! LLM недоступна ({e}); LLM-варианты пропущены.")
            variants = [v for v in variants if not VARIANTS[v]["llm"]]

    lines = [f"# Bench report — {datetime.date.today()}",
             f"Варианты: {', '.join(variants)}", "",
             "## Сводка", "",
             "| Вариант | Цель | Recall | По группам | По сложности | Находок | Лишних | Anchoring |",
             "|---|---|---|---|---|---|---|---|"]
    details = []

    for vname in variants:
        spec = VARIANTS[vname]
        for t in targets:
            text = (ROOT / t["doc"]).read_text(encoding="utf-8")
            result = review(text, rubric, llm if spec["llm"] else None,
                            use_baseline=spec["baseline"], use_entropy=spec["entropy"],
                            use_graph=spec["graph"],
                            llm_passes=frozenset(spec["passes"]) if spec.get("passes") else None)
            n_findings = len(result.findings)
            if t.get("gold"):
                gold = yaml.safe_load((ROOT / t["gold"]).read_text(encoding="utf-8"))["defects"]
                hits, extras, by_group, by_diff = evaluate(result, gold)
                n_hit = sum(1 for v in hits.values() if v)
                groups = " ".join(f"{g} {a}/{b}" for g, (a, b) in sorted(by_group.items()))
                diffs = " ".join(f"{d[:3]} {a}/{b}" for d, (a, b) in
                                 sorted(by_diff.items(),
                                        key=lambda x: {"easy": 0, "medium": 1, "hard": 2}.get(x[0], 9)))
                lines.append(f"| {vname} | {t['label']} | **{n_hit}/{len(gold)}** | {groups} "
                             f"| {diffs} | {n_findings} | {len(extras)} | {result.anchoring:.0%} |")
                det = [f"### {vname} · {t['label']}", "", "Пропущено:"]
                det += [f"- **[{d.get('code', '?')}] {d['id']}**: {d['description']}"
                        for d in gold if not hits[d["id"]]] or ["- (ничего)"]
                if extras:
                    det.append("\nЛишние находки (разметить: FP или новый TP):")
                    det += [f"- `{f['fid']}` {f['category']} ({f['severity']}): "
                            f"{(f['why'] or '')[:110]}" for f in extras]
                details.append("\n".join(det))
            else:
                lines.append(f"| {vname} | {t['label']} | — | — | {n_findings} "
                             f"| noise={n_findings} | {result.anchoring:.0%} |")

    report = "\n".join(lines) + "\n\n## Промахи и лишние\n\n" + "\n\n".join(details) + "\n"
    out = ROOT / args.out
    out.write_text(report, encoding="utf-8")
    print("\n".join(lines))
    print(f"\nОтчёт: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

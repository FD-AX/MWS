"""Офлайн-симуляция правил точности на сохранённых ревью (без вызовов модели).

    python eval/simulate_rules.py eval/labels/unmatched_2026-09-05.yaml

Для каждой находки из истории применяем: (1) детерминированную применимость слота (NA),
(2) фильтр вопросов о заглушках, (3) severity из score критика, (4) новые правила
пустых/обязательных разделов (детерминированный слой перегоняется на тексте документа).
Считаем, сколько не-TP срезано и сколько TP задето — «ожидаемый выигрыш» до живого прогона.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))
from run_eval import finding_matches  # noqa: E402
from tz_review import document  # noqa: E402
from tz_review.passes import checklist, critic, deterministic, filters  # noqa: E402
from tz_review.rubric import load_rubric  # noqa: E402
from tz_review.schema import Finding  # noqa: E402

GOLD = {"doc1": "eval/gold_doc1.yaml", "doc2": "eval/gold_doc2.yaml", "doc3": "eval/gold_doc3.yaml"}
SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "advisory": 4}


def get(path):
    return json.loads(urllib.request.urlopen("http://localhost:18080" + path, timeout=30).read())


def main() -> int:
    labels = {(x["review"], x["fid"]): x for x in yaml.safe_load(Path(sys.argv[1]).read_text(encoding="utf-8"))["labels"]}
    rubric = load_rubric()
    rows = [r for r in get("/reviews?limit=30") if r["status"] == "done" and not r.get("cached_from")]
    before, after = Counter(), Counter()
    cut_by = Counter()
    top_before, top_after = Counter(), Counter()
    recall_before = recall_after = recall_total = 0
    for r in rows:
        key = next((k for k in GOLD if k in (r.get("filename") or "")), None)
        if not key:
            continue
        gold = yaml.safe_load((ROOT / GOLD[key]).read_text(encoding="utf-8"))["defects"]
        job = get(f"/reviews/{r['job_id']}")
        fs = (job.get("result") or {}).get("findings", [])
        text = get(f"/documents/{job['doc_hash']}/text")["markdown"]
        matched = {f["fid"] for d in gold for f in fs if finding_matches(d, f)}

        def verdict(f):
            if f["fid"] in matched:
                return "TP"
            lab = labels.get((r["job_id"], f["fid"]))
            return lab["verdict"] if lab else "?"

        # 4) детерминированный слой заново на тексте: какие template-находки остаются
        det_now = deterministic.run(document.parse(text), rubric)
        det_keys = {(f.category, (f.section or "")[:30]) for f in det_now}

        _, na_slots = checklist.split_applicable(rubric["checklist"], text)
        survivors = []
        kept_raw = []
        for f in fs:
            v = verdict(f)
            before[v] += 1
            cat = f["category"]
            if cat.startswith("checklist:") and cat.split(":")[1] in na_slots:
                cut_by[("na-rule", v)] += 1
                continue
            fo = Finding(**{k: val for k, val in f.items() if k in Finding.model_fields})
            if filters.is_placeholder_question(fo):
                cut_by[("placeholder-filter", v)] += 1
                continue
            if cat.startswith("template:") and (cat, (f.get("section") or "")[:30]) not in det_keys:
                cut_by[("template-rule", v)] += 1
                continue
            sev = f["severity"]
            if f.get("source_pass") not in ("deterministic", "doc_graph") and f.get("score") is not None \
                    and not (cat.startswith("checklist:") and any(q.get("official") and q["id"] == cat.split(":")[1] for q in rubric["checklist"])):
                sev = critic.severity_from_score(float(f["score"]))
            survivors.append((sev, f.get("score") or 0, v))
            kept_raw.append(f)
            after[v] += 1
        # recall по голду до/после правил — правила не должны съедать размеченные дефекты
        recall_total += len(gold)
        recall_before += sum(1 for d in gold if any(finding_matches(d, f) for f in fs))
        recall_after += sum(1 for d in gold if any(finding_matches(d, f) for f in kept_raw))
        ordered_b = sorted(((SEV_ORDER.get(f["severity"], 9), -(f.get("score") or 0), verdict(f)) for f in fs))[:10]
        ordered_a = sorted(((SEV_ORDER.get(s, 9), -sc, v) for s, sc, v in survivors))[:10]
        for *_, v in ordered_b: top_before[v] += 1
        for *_, v in ordered_a: top_after[v] += 1

    def prec(c):
        n = sum(c[v] for v in ("TP", "FP", "NA"))
        return c["TP"], n, (c["TP"] / n if n else float("nan"))
    tb, nb, pb = prec(before); ta, na_, pa = prec(after)
    print(f"# Офлайн-симуляция правил точности (те же находки, без новых вызовов)\n")
    print(f"| | TP | всего | precision |\n|---|---|---|---|\n| до правил | {tb} | {nb} | {pb:.0%} |\n| после правил | {ta} | {na_} | {pa:.0%} |")
    print(f"\nСрезано правилами (правило → вердикт срезанной находки):")
    for (rule, v), n in sorted(cut_by.items()):
        print(f"- {rule}: {v} × {n}")
    tp_lost = sum(n for (rule, v), n in cut_by.items() if v == "TP")
    junk_cut = sum(n for (rule, v), n in cut_by.items() if v in ("FP", "NA"))
    print(f"\nИтого: срезано мусора {junk_cut}, задето TP {tp_lost}")
    tb, nb, pb = prec(top_before); ta, na_, pa = prec(top_after)
    print(f"\nPrecision@top-10 (сумма по ревью): до {tb}/{nb} = {pb:.0%}, после {ta}/{na_} = {pa:.0%}")
    print(f"Recall по голду (сумма по ревью): до {recall_before}/{recall_total}, после {recall_after}/{recall_total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

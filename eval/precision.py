"""Точность по сохранённым ревью: голд-совпадения + ручная разметка «лишних» (TP / FP / NA).

    python eval/precision.py eval/labels/unmatched_2026-09-05.yaml [--api http://localhost:18080]

Разметка: список {review, fid, verdict: TP|FP|NA, reason}. NA = «слот должен был быть „не применимо“»
(считается ложным срабатыванием в precision, но выделяется отдельно как класс ошибки).
Выход: precision по моделям, по проходам (category до ':'), по критичности; precision@top-10
(в порядке критичности и score — то, что аналитик читает первым); печать в markdown.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))
from run_eval import finding_matches  # noqa: E402

GOLD = {"doc1": "eval/gold_doc1.yaml", "doc2": "eval/gold_doc2.yaml", "doc3": "eval/gold_doc3.yaml"}
SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "advisory": 4}


def get(api: str, path: str):
    return json.loads(urllib.request.urlopen(api + path, timeout=30).read())


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    labels_path = Path(sys.argv[1])
    api = sys.argv[sys.argv.index("--api") + 1] if "--api" in sys.argv else "http://localhost:18080"
    labels = {(x["review"], x["fid"]): x for x in yaml.safe_load(labels_path.read_text(encoding="utf-8"))["labels"]}

    rows = [r for r in get(api, "/reviews?limit=30") if r["status"] == "done" and not r.get("cached_from")]
    records = []  # (model, doc, pass, severity, score, verdict)
    for r in rows:
        key = next((k for k in GOLD if k in (r.get("filename") or "")), None)
        if not key:
            continue
        gold = yaml.safe_load((ROOT / GOLD[key]).read_text(encoding="utf-8"))["defects"]
        fs = (get(api, f"/reviews/{r['job_id']}").get("result") or {}).get("findings", [])
        matched = {f["fid"] for d in gold for f in fs if finding_matches(d, f)}
        model = "gpt-5.5" if "gpt-5" in (r.get("model") or "") else "gpt-oss-120b"
        ordered = sorted(fs, key=lambda f: (SEV_ORDER.get(f["severity"], 9), -(f.get("score") or 0)))
        for rank, f in enumerate(ordered, 1):
            if f["fid"] in matched:
                verdict = "TP"
            else:
                lab = labels.get((r["job_id"], f["fid"]))
                verdict = lab["verdict"] if lab else "?"
            records.append({"model": model, "doc": key, "review": r["job_id"], "pass": f["category"].split(":")[0],
                            "severity": f["severity"], "score": f.get("score"), "rank": rank, "verdict": verdict,
                            "gold": f["fid"] in matched})

    unl = [x for x in records if x["verdict"] == "?"]
    if unl:
        print(f"! без разметки: {len(unl)} находок — precision по ним не считается")

    def prec(items):
        items = [x for x in items if x["verdict"] != "?"]
        tp = sum(1 for x in items if x["verdict"] == "TP")
        return tp, len(items), (tp / len(items) if items else float("nan"))

    def table(title, keyfn):
        groups = defaultdict(list)
        for x in records:
            groups[keyfn(x)].append(x)
        print(f"\n### {title}\n\n| группа | TP | всего | precision | из них по голду | FP | NA-класс |\n|---|---|---|---|---|---|---|")
        for k in sorted(groups):
            tp, n, p = prec(groups[k])
            g = sum(1 for x in groups[k] if x["gold"])
            fp = sum(1 for x in groups[k] if x["verdict"] == "FP")
            na = sum(1 for x in groups[k] if x["verdict"] == "NA")
            print(f"| {k} | {tp} | {n} | {p:.0%} | {g} | {fp} | {na} |")

    tp, n, p = prec(records)
    print(f"# Precision по сохранённым ревью ({len(rows)} ревью, {n} размеченных находок)\n\n**Итого: {tp}/{n} = {p:.0%}** "
          f"(по голду {sum(1 for x in records if x['gold'])}, размечено вручную TP {sum(1 for x in records if x['verdict']=='TP' and not x['gold'])}, "
          f"FP {sum(1 for x in records if x['verdict']=='FP')}, NA-класс {sum(1 for x in records if x['verdict']=='NA')})")
    table("По модели", lambda x: x["model"])
    table("По документу × модели", lambda x: f"{x['doc']} · {x['model']}")
    table("По проходу", lambda x: x["pass"])
    table("По критичности", lambda x: x["severity"])
    table("По проходу × модели", lambda x: f"{x['pass']} · {x['model']}")
    top = [x for x in records if x["rank"] <= 10]
    tp, n, p = prec(top)
    print(f"\n### Precision@top-10 (порядок критичность → score): {tp}/{n} = {p:.0%}")
    for m in ("gpt-5.5", "gpt-oss-120b"):
        tp, n, p = prec([x for x in top if x["model"] == m])
        print(f"- {m}: {tp}/{n} = {p:.0%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

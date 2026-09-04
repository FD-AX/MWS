"""Проверка живого прогона через контур против голда (EXP-18 и далее).

    python eval/live_check.py <job_id> <doc1|doc2|doc3> [<job_id предыдущего прогона той же модели>]

Печатает: recall по голду, число находок, NA-слоты, вопросы о заглушках (должно быть 0),
LOC-02/LOC-03 в MISSING, топ-10 с пометкой gold/—, и список не совпавших с голдом для ручной разметки.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "eval"))
from run_eval import finding_matches  # noqa: E402
from tz_review.passes import filters  # noqa: E402
from tz_review.schema import Finding  # noqa: E402

API = "http://localhost:18080"
SEV = {"critical": 0, "high": 1, "medium": 2, "low": 3, "advisory": 4}


def get(path):
    return json.loads(urllib.request.urlopen(API + path, timeout=30).read())


def summarize(job_id: str, gold: list[dict]) -> dict:
    job = get(f"/reviews/{job_id}")
    res = job.get("result") or {}
    fs = res.get("findings", [])
    hit = {d["id"] for d in gold if any(finding_matches(d, f) for f in fs)}
    matched_fids = {f["fid"] for d in gold for f in fs if finding_matches(d, f)}
    statuses = res.get("checklist_statuses") or res.get("statuses") or {}
    na = sorted(k for k, v in statuses.items() if v == "NA")
    missing = sorted(k for k, v in statuses.items() if v == "MISSING")
    ph = [f["fid"] for f in fs if filters.is_placeholder_question(
        Finding(**{k: v for k, v in f.items() if k in Finding.model_fields}))]
    top = sorted(fs, key=lambda f: (SEV.get(f["severity"], 9), -(f.get("score") or 0)))[:10]
    return dict(job=job, fs=fs, hit=hit, matched_fids=matched_fids, na=na, missing=missing, ph=ph, top=top,
                model=job.get("model"), duration=job.get("duration_s"))


def main() -> int:
    job_id, key = sys.argv[1], sys.argv[2]
    gold = yaml.safe_load((ROOT / f"eval/gold_{key}.yaml").read_text(encoding="utf-8"))["defects"]
    s = summarize(job_id, gold)
    print(f"# {key} · job {job_id[:8]} · model {s['model']} · {s['duration']} s")
    print(f"recall по голду: {len(s['hit'])}/{len(gold)}  (промахи: {sorted(d['id'] for d in gold if d['id'] not in s['hit'])})")
    print(f"находок: {len(s['fs'])}, совпали с голдом: {len(s['matched_fids'])}, не совпали: {len(s['fs']) - len(s['matched_fids'])}")
    print(f"NA-слоты ({len(s['na'])}): {s['na']}")
    print(f"MISSING ({len(s['missing'])}): {s['missing']}")
    print(f"вопросы о заглушках после фильтра: {len(s['ph'])} {s['ph']}")
    print("\n## топ-10 (критичность → score)")
    for f in s["top"]:
        tag = "gold" if f["fid"] in s["matched_fids"] else "—"
        print(f"- [{tag}] {f['severity']:8} {f.get('score')} {f['category']} · {(f.get('why') or '')[:90]}")
    print("\n## не совпавшие с голдом (на разметку)")
    for f in s["fs"]:
        if f["fid"] not in s["matched_fids"]:
            print(f"- {f['fid']} {f['severity']:8} {f.get('score')} {f['category']} [{f.get('source_pass')}] · {(f.get('why') or '')[:110]}")
    if len(sys.argv) > 3:
        p = summarize(sys.argv[3], gold)
        print(f"\n## сравнение с прошлым прогоном {sys.argv[3][:8]} ({p['model']})")
        print(f"| | recall | находок | не в голде | NA | заглушки | top-10 gold |\n|---|---|---|---|---|---|---|")
        for name, x in (("прошлый", p), ("новый", s)):
            tg = sum(1 for f in x["top"] if f["fid"] in x["matched_fids"])
            print(f"| {name} | {len(x['hit'])}/{len(gold)} | {len(x['fs'])} | {len(x['fs']) - len(x['matched_fids'])} | {len(x['na'])} | {len(x['ph'])} | {tg}/{len(x['top'])} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

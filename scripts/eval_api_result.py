"""Сверка отчёта из API с голд-разметкой: какой дефект пойман (и чем), какой пропущен,
что лишнее. Для демо на документах МТС.

    python scripts/eval_api_result.py http://localhost:18080/reviews/<job_id> eval/gold_doc3.yaml
    python scripts/eval_api_result.py <result.json> eval/gold_doc3.yaml
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))
from run_eval import finding_matches  # noqa: E402


def load_result(src: str) -> dict:
    if src.startswith("http"):
        with urllib.request.urlopen(src, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    return json.loads(Path(src).read_text(encoding="utf-8"))


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    job = load_result(sys.argv[1])
    result = job.get("result") or job
    findings = result.get("findings", [])
    gold = yaml.safe_load(Path(sys.argv[2]).read_text(encoding="utf-8"))["defects"]

    print(f"Документ: {job.get('filename') or '?'} · модель {job.get('model') or '?'} "
          f"· {job.get('duration_s') or '?'} с · вызовов LLM {(job.get('llm_usage') or {}).get('calls', '?')}")
    v = job.get("verdict") or {}
    print(f"Вердикт: {v.get('light', '')} {v.get('text', '')}")
    print(f"Находок: {len(findings)}, срезано критиком: {len(result.get('rejected', []))}, "
          f"отброшено верификацией: {len(result.get('dropped', []))}, "
          f"anchoring {result.get('anchoring_rate', '?')}")
    st = result.get("checklist_statuses", {})
    print(f"Чеклист: OK {sum(1 for s in st.values() if s == 'OK')}, MISSING "
          f"{sum(1 for s in st.values() if s == 'MISSING')}, UNCLEAR "
          f"{sum(1 for s in st.values() if s == 'UNCLEAR')}, UNKNOWN "
          f"{sum(1 for s in st.values() if s == 'UNKNOWN')} из {len(st)}\n")

    matched = set()
    hits = 0
    print("=== Голд-дефекты ===")
    for d in gold:
        found = [f for f in findings if finding_matches(d, f)]
        if found:
            hits += 1
            matched.update(f.get("fid") for f in found)
        mark = "✓" if found else "✗"
        via = f"  ← {found[0]['category']} ({found[0]['severity']})" if found else ""
        print(f"{mark} [{d.get('code', '?')}] {d['id']}: {d['description'][:90]}{via}")
    print(f"\nRecall: {hits}/{len(gold)}")

    extras = [f for f in findings if f.get("fid") not in matched]
    print(f"\n=== Лишние находки (не в голде): {len(extras)} — разметить FP / новый TP ===")
    for f in extras:
        print(f"- {f['category']} ({f['severity']}): {(f.get('why') or '')[:120]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

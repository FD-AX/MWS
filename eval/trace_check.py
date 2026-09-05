"""Разбор трассы вызовов (TZR_TRACE_DIR): одинаковые промпты чеклиста → одинаковые ли ответы?

    python eval/trace_check.py eval/night/trace_m9 [--doc-len 15000-17000]

Для каждого промпта чеклиста (по sha) печатает все вызовы: время, finish, число ответов в JSON и сколько из них
MISSING/UNCLEAR/OK/NA. Так видно, когда один и тот же батч в одном прогоне даёт 4 MISSING, а в другом — 0
(EXP-22: v2g на doc3 → 1 находка чеклиста ×2 при 17–18 у v2x с теми же батчами).
"""
from __future__ import annotations

import glob
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tz_review.llm import _extract_json  # noqa: E402


def main() -> int:
    args = sys.argv[1:]
    d = args[0] if args else "eval/night/trace_m9"
    lo, hi = 0, 10**9
    if "--doc-len" in args:
        a, b = args[args.index("--doc-len") + 1].split("-"); lo, hi = int(a), int(b)
    recs = []
    for f in glob.glob(str(Path(d) / "trace_*.jsonl")):
        for line in open(f, encoding="utf-8"):
            recs.append(json.loads(line))
    by_sha = defaultdict(list)
    for r in recs:
        if "Проверь документ по чеклисту" in r["user_head"] and lo <= r["user_len"] <= hi:
            by_sha[r["prompt_sha"]].append(r)
    print(f"записей в трассе: {len(recs)}; промптов чеклиста в диапазоне длины: {sum(len(v) for v in by_sha.values())} ({len(by_sha)} уникальных)")
    for sha, rs in sorted(by_sha.items(), key=lambda x: x[1][0]["ts"]):
        print(f"\n== sha {sha} · длина {rs[0]['user_len']} · вызовов {len(rs)}")
        for r in rs:
            out = (r["out"] or [""])[0]
            try:
                obj = _extract_json(out)
                st = Counter(a.get("status") for a in obj.get("answers", []))
                ids = [a.get("id") for a in obj.get("answers", [])]
                print(f"   {r['ts']} finish={r['finish']} ответов={sum(st.values())} {dict(st)} ids={ids}")
            except Exception as e:  # noqa: BLE001
                print(f"   {r['ts']} finish={r['finish']} JSON не разобран: {str(e)[:60]} | out[:80]={out[:80]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

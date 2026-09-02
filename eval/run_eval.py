"""Оценка ревьюера по подсаженным дефектам (методика CriticGPT).

Использование:
    python -m tz_review examples/sample_tz.md [--no-llm]
    python eval/run_eval.py out/sample_tz.findings.json eval/seeded_defects.yaml

Метрики:
- recall по подсаженным дефектам (главная);
- anchoring rate (доля находок с верифицированной цитатой);
- список находок вне подсаженных — кандидаты на ручную разметку precision.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tz_review.document import normalize  # noqa: E402


def finding_matches(defect: dict, finding: dict) -> bool:
    if any(finding.get("category", "").startswith(c) for c in defect.get("categories", [])):
        return True
    haystack = normalize(" ".join(str(finding.get(k) or "") for k in ("quote", "why", "ask")))
    # Ключ должен начинаться на границе слова: «оба» не должно матчить «дОБАвь».
    return any(re.search(r"(?<!\w)" + re.escape(normalize(kw)), haystack)
               for kw in defect.get("keywords", []))


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    findings_data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    seeded = yaml.safe_load(Path(sys.argv[2]).read_text(encoding="utf-8"))["defects"]
    findings = findings_data["findings"]

    hits, matched_fids = [], set()
    for defect in seeded:
        found = [f for f in findings if finding_matches(defect, f)]
        hits.append((defect, found))
        matched_fids.update(f["fid"] for f in found)

    n_hit = sum(1 for _, found in hits if found)
    print(f"=== Recall по подсаженным дефектам: {n_hit}/{len(seeded)} "
          f"({100 * n_hit // len(seeded)}%) ===")
    for defect, found in hits:
        mark = "✓" if found else "✗ ПРОПУЩЕН"
        via = ", ".join(sorted({f["category"] for f in found})) if found else ""
        print(f"  {mark} {defect['id']}: {defect['description']}" + (f"  [{via}]" if via else ""))

    print(f"\nAnchoring rate: {findings_data.get('anchoring_rate', 1.0):.0%}")

    extra = [f for f in findings if f["fid"] not in matched_fids]
    if extra:
        print(f"\nНаходки вне подсаженных ({len(extra)}) — разметить вручную как TP/FP:")
        for f in extra:
            print(f"  [{f['fid']}] {f['severity']:9s} {f['category']}: "
                  f"{(f.get('why') or '')[:100]}")
    return 0 if n_hit == len(seeded) else 1


if __name__ == "__main__":
    raise SystemExit(main())

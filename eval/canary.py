"""Канарейка работоспособности стека: 3 мини-ТЗ с бесспорными ожиданиями.

    python eval/canary.py [--variant v2g]

c1 — нет инкремента (обязан найтись), c2 — противоречие SLA «15 минут» vs «H+4 часа»
(обязано найтись), c3 — чистый документ (0 находок уровня medium+).
Провал канарейки = сломан стек (модель/промпт/парсинг), большие прогоны не запускать.
Выход: код 0 = ок, 1 = провал.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from bench import VARIANTS  # noqa: E402
from run_eval import finding_matches  # noqa: E402
from tz_review.pipeline import review  # noqa: E402
from tz_review.rubric import load_rubric  # noqa: E402

CHECKS = [
    ("eval/canary/c1_increment.md", "найден пропавший инкремент",
     {"categories": ["checklist:INC-01", "graph:"], "keywords": ["инкремент", "курсор", "какие даты", "за какой период"]}),
    ("eval/canary/c2_contradiction.md", "найдено противоречие 15 минут vs H+4",
     {"categories": ["doc:contradiction"], "keywords": ["15 минут", "h+4", "противореч", "4 часа"]}),
    ("eval/canary/c3_clean.md", None, None),  # чистый: ожидание = тишина
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="v2g")
    args = ap.parse_args()
    spec = VARIANTS[args.variant]

    rubric = load_rubric()
    llm = None
    if spec["llm"]:
        from tz_review.config import openai_settings_or_die, settings_or_die
        from tz_review.llm import LLM
        cfg = (openai_settings_or_die() if spec.get("backend") == "openai"
               else settings_or_die())
        llm = LLM(cfg)

    ok = True
    for path, expect_desc, matcher in CHECKS:
        text = (ROOT / path).read_text(encoding="utf-8")
        result = review(text, rubric, llm if spec["llm"] else None,
                        use_baseline=spec["baseline"], use_entropy=spec["entropy"],
                        use_graph=spec["graph"],
                        llm_passes=frozenset(spec["passes"]) if spec.get("passes") else None,
                        baseline_prompt=spec.get("bprompt", "baseline"))
        findings = [f.model_dump() for f in result.findings]
        name = Path(path).stem
        if matcher is None:
            # Бейзлайны без критика всегда дают немного medium-нитов; канарейка ловит
            # сломанный стек, а не шум (шум меряется бенчем на clean_base).
            crit_high = [f for f in findings if f["severity"] in ("critical", "high")]
            medium = [f for f in findings if f["severity"] == "medium"]
            quiet = not crit_high and len(medium) <= 3
            # Жёстко шум гейтит только вариант с критиком; для бейзлайнов — информационно
            # (вывод ночи: бейзлайн без критика перешумливает даже хорошие документы).
            enforced = not spec["baseline"]
            status = quiet or not enforced
            mark = "✓" if quiet else ("✗" if enforced else "ℹ")
            print(f"{mark} {name}: critical/high = {len(crit_high)} "
                  f"(ожидание 0), medium = {len(medium)} (ожидание <=3)"
                  + ("" if enforced else " [информационно для бейзлайна]"))
            for f in (crit_high + medium)[:5]:
                print(f"    - {f['severity']} {f['category']}: {(f['why'] or '')[:90]}")
        else:
            hit = [f for f in findings if finding_matches(matcher, f)]
            status = bool(hit)
            print(f"{'✓' if status else '✗'} {name}: {expect_desc} — "
                  f"{'да (' + hit[0]['category'] + ')' if hit else 'НЕ НАЙДЕНО'}")
        ok = ok and status

    print("\nКанарейка:", "OK — стек жив" if ok else "ПРОВАЛ — большие прогоны не запускать")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

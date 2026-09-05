"""Матрица «архитектура × модель» из сырых JSON бенча (PROTOCOL.md).

    python eval/matrix.py eval/night/raw_*.json [--out eval/night/matrix.md]

Строки — варианты (архитектуры), столбцы — модели (поле model/backend сырой записи), ячейка —
recall по голду: медиана [min–max] по повторам (n). Для clean-целей — шум (число находок medium+).
Суффикс « #k» у цели (повторы --repeat) снимается. Записи разных итераций синтетики смешивать нельзя —
это ответственность вызывающего (передавай файлы одной итерации).
"""
from __future__ import annotations

import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path


def base_target(label: str) -> str:
    return re.sub(r"\s*#\d+$", "", label)


def fmt(vals: list[float], total: int | None) -> str:
    if not vals:
        return "—"
    med = statistics.median(vals)
    med_s = f"{med:g}"
    rng = "" if len(vals) == 1 or min(vals) == max(vals) else f" [{min(vals):g}–{max(vals):g}]"
    n = f" (n={len(vals)})" if len(vals) > 1 else ""
    return f"**{med_s}/{total}**{rng}{n}" if total else f"{med_s}{rng}{n}"


def main() -> int:
    args = sys.argv[1:]
    out = None
    if "--out" in args:
        i = args.index("--out"); out = args[i + 1]; args = args[:i] + args[i + 2:]
    recs: list[dict] = []
    for p in args:
        # Легаси-JSON без поля model: «путь=метка» подставляет модель (например raw_exp19_gpt.json=gpt-5.5)
        label = None
        if "=" in p:
            p, label = p.split("=", 1)
        for r in json.loads(Path(p).read_text(encoding="utf-8")):
            if label and not r.get("model"):
                r["model"] = label
            recs.append(r)
    # (target, variant, model) -> list of recall / noise / extras per run
    recall: dict = defaultdict(list); noise: dict = defaultdict(list); extras: dict = defaultdict(list)
    gold_n: dict[str, int] = {}
    models: list[str] = []; variants: list[str] = []; targets: list[str] = []
    for r in recs:
        m = r.get("model") or r.get("backend") or "?"
        t = base_target(r["target"]); v = r["variant"]
        for lst, x in ((models, m), (variants, v), (targets, t)):
            if x not in lst:
                lst.append(x)
        if r.get("defects"):
            gold_n[t] = len(r["defects"])
            recall[(t, v, m)].append(sum(1 for d in r["defects"].values() if d.get("hit")))
            extras[(t, v, m)].append(len(r.get("extras", [])))
        else:
            noise[(t, v, m)].append(len(r.get("noise", [])))
    lines = ["# Матрица архитектура × модель", "",
             "Ячейка: recall по голду, медиана [min–max] (n повторов); для чистой базы — шум (находок medium+). "
             "Числа одной итерации синтетики и одного голда.", ""]
    for t in targets:
        total = gold_n.get(t)
        lines += [f"## {t}" + (f" (голд {total})" if total else " (шум)"), "",
                  "| Архитектура | " + " | ".join(models) + " |",
                  "|---|" + "---|" * len(models)]
        for v in variants:
            cells = []
            for m in models:
                if total:
                    cells.append(fmt(recall.get((t, v, m), []), total)
                                 + (f" · лишних {statistics.median(extras[(t, v, m)]):g}" if extras.get((t, v, m)) else ""))
                else:
                    cells.append(fmt(noise.get((t, v, m), []), None))
            if any(c != "—" for c in cells):
                lines.append(f"| {v} | " + " | ".join(cells) + " |")
        lines.append("")
    # Сводка: сумма медиан по голд-целям
    golded = [t for t in targets if gold_n.get(t)]
    if golded:
        lines += ["## Σ медиан по голд-целям (" + ", ".join(golded) + ")", "",
                  "| Архитектура | " + " | ".join(models) + " |", "|---|" + "---|" * len(models)]
        tot = sum(gold_n[t] for t in golded)
        for v in variants:
            cells = []
            for m in models:
                parts = [recall.get((t, v, m), []) for t in golded]
                if all(parts):
                    cells.append(f"**{sum(statistics.median(p) for p in parts):g}/{tot}**")
                else:
                    cells.append("—")
            if any(c != "—" for c in cells):
                lines.append(f"| {v} | " + " | ".join(cells) + " |")
        lines.append("")
    text = "\n".join(lines)
    if out:
        Path(out).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

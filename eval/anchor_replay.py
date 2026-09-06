"""Реплей верификации цитат по отброшенным находкам из сырых JSON бенча (EXP-24).

    python eval/anchor_replay.py [eval/night/*.json] [--show]

Берёт записи с полем `dropped` (находки, не прошедшие verify в момент прогона), сопоставляет цель →
документ (как eval/rescore.py) и прогоняет ТЕКУЩИЙ tz_review.verify.verify_findings заново.
Печатает: сколько отброшенных теперь верифицируется (и на какой якорь), по целям и по проходам.
Замер «было → стало» для изменений verify/normalize без единого вызова модели: одна и та же
популяция до и после правки.
"""
from __future__ import annotations

import glob
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "eval"))

from rescore import DOCS, _key, gold_for  # noqa: E402
from run_eval import finding_matches  # noqa: E402
from tz_review import document  # noqa: E402
from tz_review.schema import Finding  # noqa: E402
from tz_review.verify import verify_findings  # noqa: E402


def load_records(paths: list[str]) -> list[dict]:
    recs: list[dict] = []
    for fn in paths:
        if fn.endswith(".rescored.json"):
            continue
        try:
            d = json.loads(Path(fn).read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        for r in (d if isinstance(d, list) else [d]):
            if isinstance(r, dict) and r.get("dropped") and r.get("target"):
                r["_file"] = Path(fn).name
                recs.append(r)
    return recs


def main(argv: list[str]) -> int:
    show = "--show" in argv
    show_dropped = "--dropped" in argv
    paths = [a for a in argv if not a.startswith("--")] or sorted(glob.glob(str(ROOT / "eval/night/*.json")))
    recs = load_records(paths)
    docs: dict[str, document.Document] = {}
    total = rescued = 0
    by_target: Counter = Counter(); rescued_target: Counter = Counter()
    by_pass: Counter = Counter(); rescued_pass: Counter = Counter()
    uniq_all: set = set(); uniq_rescued: set = set()
    rows: list[tuple] = []
    left: list[tuple] = []
    new_hits: Counter = Counter()      # (цель, дефект) → в скольких прогонах спасённая находка дала новое попадание в голд
    runs_with_gold = 0
    for r in recs:
        key = _key(str(r["target"]))
        if key is None or key == "clean_base":
            continue  # без документа или шум на чистой базе — спасать нечего
        if key not in docs:
            docs[key] = document.parse((ROOT / DOCS[key]).read_text(encoding="utf-8"))
        doc = docs[key]
        gold = gold_for(str(r["target"]))
        rescued_here: list[dict] = []
        for raw in r["dropped"]:
            if not isinstance(raw, dict) or not raw.get("quote"):
                continue
            data = {k: v for k, v in raw.items() if k in Finding.model_fields}
            data.setdefault("why", "")  # легаси-записи хранят why обрезанным или без него
            f = Finding.model_validate(data)
            before = f.quote
            verified, _dropped = verify_findings([f], doc)
            total += 1; by_target[key] += 1; by_pass[f.source_pass or "?"] += 1
            uid = (key, document.normalize(before or ""))
            uniq_all.add(uid)
            if verified:
                rescued += 1; rescued_target[key] += 1; rescued_pass[f.source_pass or "?"] += 1
                uniq_rescued.add(uid)
                rows.append((r["_file"], key, f.source_pass, before, verified[0].quote, verified[0].section))
                rescued_here.append(verified[0].model_dump())
            else:
                left.append((key, f.source_pass, before))
        # Влияние на recall: дефекты голда, которых не ловила ни одна принятая находка прогона,
        # но ловит спасённая (матчер тот же, что в бенче — eval/run_eval.finding_matches).
        if gold and rescued_here:
            runs_with_gold += 1
            accepted = [x for x in (r.get("findings") or []) if isinstance(x, dict)]
            for d in gold:
                if any(finding_matches(d, x) for x in accepted):
                    continue
                if any(finding_matches(d, x) for x in rescued_here):
                    new_hits[(key, d.get("id") or d.get("description", "?")[:60])] += 1
    print(f"отброшенных с цитатой (цель известна): {total}; верифицируются текущим кодом: {rescued}"
          f" · уникальных цитат: {len(uniq_rescued)}/{len(uniq_all)}")
    print("по целям:", ", ".join(f"{k} {rescued_target[k]}/{by_target[k]}" for k in sorted(by_target)))
    print("по проходам:", ", ".join(f"{k} {rescued_pass[k]}/{by_pass[k]}" for k in sorted(by_pass)))
    if new_hits:
        print(f"новые попадания в голд (дефект не ловился принятыми находками прогона, ловится спасённой): "
              f"{sum(new_hits.values())} в {runs_with_gold} прогонах")
        for (key, did), n in sorted(new_hits.items()):
            print(f"  {key} · {did}: {n} прогон(ов)")
    if show:
        seen: set = set()
        for fn, key, sp, before, after, sec in rows:
            uid = (key, document.normalize(before or ""))
            if uid in seen:
                continue
            seen.add(uid)
            print(f"\n[{fn} · {key} · {sp}] раздел: {sec}")
            print("  было :", re.sub(r"\s+", " ", before)[:200])
            print("  якорь:", after[:200])
    if show_dropped:
        print("\n--- по-прежнему отброшены (уникальные) ---")
        seen = set()
        for key, sp, before in left:
            uid = (key, document.normalize(before or ""))
            if uid in seen:
                continue
            seen.add(uid)
            print(f"[{key} · {sp}] {re.sub(chr(92) + 's+', ' ', before)[:160]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

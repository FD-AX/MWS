"""Точность по «лишним» находкам бенча (raw JSON) — слепая разметка и подсчёт (PROTOCOL.md, п.4).

    # 1) заготовка: находки всех моделей/вариантов перемешаны, модель скрыта; ключ — отдельно
    python eval/bench_precision.py skeleton --blind eval/labels/m_key.json eval/night/m_pod_key.json eval/night/m_gpt_key.json > eval/labels/m_blind.yaml
    # 2) разметить verdict (TP/FP/NA) и cls в m_blind.yaml, НЕ открывая ключ
    # 3) подсчёт по вариантам и моделям
    python eval/bench_precision.py score eval/labels/m_blind.yaml --key eval/labels/m_key.json eval/night/m_pod_key.json eval/night/m_gpt_key.json

verdict ∈ TP / FP / NA; cls — класс мусора (na-slot / placeholder-name / generic-whatif / rule-threshold / gold-dup / new).
score: precision = (совпавшие с голдом + TP среди лишних) / все находки, по (модель, вариант); шум@clean отдельно.
"""
from __future__ import annotations

import json
import random
import sys
from collections import defaultdict
from pathlib import Path

import yaml


def load_raw(paths: list[str]) -> list[dict]:
    recs: list[dict] = []
    for p in paths:
        recs.extend(json.loads(Path(p).read_text(encoding="utf-8")))
    return recs


def _items(r: dict) -> list[dict]:
    return r.get("extras") or r.get("noise") or []


def _norm(s: str) -> str:
    import re
    return re.sub(r"\W+", " ", (s or "").lower()).strip()


def skeleton(paths: list[str], blind_key: str | None) -> None:
    rows, key = [], {}
    for r in load_raw(paths):
        for i, f in enumerate(_items(r)):
            rows.append({"variant": r["variant"], "target": r["target"], "idx": i,
                         "model": r.get("model") or r.get("backend"),
                         "category": f["category"], "severity": f["severity"], "why": f["why"],
                         "verdict": "?", "cls": "?"})
    if blind_key:
        # Одинаковые находки повторяются в разных вариантах/повторах — размечаем уникальные группы
        # (цель × категория × начало why), метка группы распространяется на всех членов при score.
        groups: dict[tuple, list[dict]] = {}
        for row in rows:
            g = (row["target"].split(" #")[0], row["category"], _norm(row["why"])[:70])
            groups.setdefault(g, []).append(row)
        items = list(groups.items())
        random.Random(20260905).shuffle(items)
        out_rows = []
        for n, (g, members) in enumerate(items, 1):
            key[n] = [{k: m[k] for k in ("variant", "target", "idx", "model")} for m in members]
            out_rows.append({"n": n, "target": g[0], "category": g[1], "severity": members[0]["severity"],
                             "why": members[0]["why"], "members": len(members), "verdict": "?", "cls": "?"})
        Path(blind_key).write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8")
        rows = out_rows
    print(yaml.safe_dump({"labels": rows}, allow_unicode=True, sort_keys=False, width=200))


def score(labels_path: str, key_path: str | None, paths: list[str]) -> None:
    labels = yaml.safe_load(Path(labels_path).read_text(encoding="utf-8"))["labels"]
    if key_path:
        key = json.loads(Path(key_path).read_text(encoding="utf-8"))
        expanded = []
        for x in labels:
            members = key[str(x["n"])]
            for m in (members if isinstance(members, list) else [members]):
                expanded.append({**x, **m})
        labels = expanded
    lab = {(x["variant"], x["target"], x["idx"]): x for x in labels}
    per: dict = defaultdict(lambda: defaultdict(int))
    cls_count: dict = defaultdict(lambda: defaultdict(int))
    for r in load_raw(paths):
        k = (r.get("model") or r.get("backend"), r["variant"])
        hits = sum(1 for d in r.get("defects", {}).values() if d.get("hit"))
        is_clean = not r.get("defects")
        per[k]["hit"] += hits
        per[k]["gold"] += len(r.get("defects", {}))
        for i, _ in enumerate(_items(r)):
            x = lab.get((r["variant"], r["target"], i))
            verdict = (x or {}).get("verdict", "?")
            per[k][("clean_" if is_clean else "") + verdict] += 1
            if verdict in ("FP", "NA"):
                cls_count[k][(x or {}).get("cls", "?")] += 1
    print("| Модель | Вариант | recall Σ | находок | TP лишних | FP | NA | ? | precision | шум@clean не-TP |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for (m, v), c in sorted(per.items()):
        total = c["hit"] + c["TP"] + c["FP"] + c["NA"] + c["?"]
        tp = c["hit"] + c["TP"]
        prec = f"{tp / total:.0%}" if total else "—"
        clean_bad = c["clean_FP"] + c["clean_NA"] + c["clean_?"]
        print(f"| {m} | {v} | {c['hit']}/{c['gold']} | {total} | {c['TP']} | {c['FP']} | {c['NA']} | {c['?']} | {prec} | {clean_bad} |")
    print("\nКлассы мусора (FP+NA):")
    for (m, v), cc in sorted(cls_count.items()):
        print(f"- {m} · {v}: " + ", ".join(f"{k} {n}" for k, n in sorted(cc.items(), key=lambda x: -x[1])))


def main() -> int:
    a = sys.argv[1:]
    if len(a) < 2:
        print(__doc__); return 2
    cmd, a = a[0], a[1:]
    opt = {}
    for flag in ("--blind", "--key"):
        if flag in a:
            i = a.index(flag); opt[flag] = a[i + 1]; a = a[:i] + a[i + 2:]
    if cmd == "skeleton":
        skeleton(a, opt.get("--blind"))
    elif cmd == "score":
        score(a[0], opt.get("--key"), a[1:])
    else:
        print(__doc__); return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

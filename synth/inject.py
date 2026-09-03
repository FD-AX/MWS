"""Фабрика синтетики: инъекция дефектов в чистый документ по рецепту.

Использование:
    python synth/inject.py synth/recipes/mart_traffic_v1.yaml

Рецепт (yaml):
    base: путь к чистому документу
    out_doc / out_gold: куда писать испорченный документ и голд-лист
    defects:
      - id, code (код MATRIX.md), description, categories, keywords
        op: replace | delete | insert_after
        find: уникальная подстрока базового документа
        replace / text: чем заменить / что вставить после
        edits: [ {op, find, replace|text}, ... ] — несколько правок на один дефект
               (факт продублирован: таблица + DDL и т.п.)

Принципы качества (см. METRICS.md):
- каждая инъекция — минимальная точечная правка, без LLM-переписывания (нет «швов»);
- find обязан встречаться ровно один раз — иначе фабрика падает;
- голд генерируется из рецепта автоматически → ground truth бесспорен;
- чистая база обязана давать 0 находок нашего же ревьюера (проверяется отдельно).
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml


def _apply_edit(text: str, e: dict, did: str) -> str:
    find = e["find"]
    n = text.count(find)
    if n != 1:
        raise SystemExit(f"[{did}] find встречается {n} раз (нужно ровно 1): {find[:80]!r}")
    op = e.get("op", "replace")
    if op == "delete":
        return text.replace(find, "")
    if op == "replace":
        return text.replace(find, e["replace"])
    if op == "insert_after":
        return text.replace(find, find + " " + e["text"])
    raise SystemExit(f"[{did}] неизвестный op: {op}")


def apply_defect(text: str, d: dict) -> str:
    """Один дефект = одна правка (op/find/replace) или список правок `edits`,
    когда факт продублирован в нескольких местах документа (таблица + DDL)."""
    for e in d.get("edits") or [d]:
        text = _apply_edit(text, e, d["id"])
    return text


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    recipe_path = Path(sys.argv[1])
    recipe = yaml.safe_load(recipe_path.read_text(encoding="utf-8"))
    root = recipe_path.resolve().parent.parent.parent  # корень net-review

    text = (root / recipe["base"]).read_text(encoding="utf-8")
    for d in recipe["defects"]:
        text = apply_defect(text, d)

    out_doc = root / recipe["out_doc"]
    out_gold = root / recipe["out_gold"]
    out_doc.parent.mkdir(parents=True, exist_ok=True)
    out_gold.parent.mkdir(parents=True, exist_ok=True)
    out_doc.write_text(text, encoding="utf-8")

    gold = {"defects": [
        {"id": d["id"], "code": d.get("code", "?"),
         "difficulty": d.get("difficulty", "?"),
         "description": f"[{d.get('code', '?')}] {d['description']}",
         "categories": d.get("categories", []), "keywords": d.get("keywords", [])}
        for d in recipe["defects"]
    ]}
    out_gold.write_text(yaml.safe_dump(gold, allow_unicode=True, sort_keys=False),
                        encoding="utf-8")
    print(f"OK: {len(recipe['defects'])} дефектов -> {out_doc}\nГолд: {out_gold}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

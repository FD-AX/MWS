"""Фабрика синтетики: инъекция дефектов в чистый документ по рецепту.

Использование:
    python synth/inject.py synth/recipes/mart_traffic_v1.yaml   # один рецепт
    python synth/inject.py --all                                # все рецепты synth/recipes/

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


RECIPES_DIR = Path(__file__).resolve().parent / "recipes"


def build(recipe_path: Path, root: Path | None = None) -> tuple[Path, Path]:
    """Собрать один рецепт → (out_doc, out_gold). root — корень репозитория; по умолчанию
    выводится из пути рецепта (synth/recipes/x.yaml → ../../)."""
    recipe_path = Path(recipe_path)
    recipe = yaml.safe_load(recipe_path.read_text(encoding="utf-8"))
    root = root or recipe_path.resolve().parent.parent.parent

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
    return out_doc, out_gold


def build_all(root: Path | None = None) -> list[tuple[Path, Path]]:
    """Собрать все рецепты synth/recipes/*.yaml. synth/out в .gitignore — в свежем клоне его нет;
    tests/conftest.py и CI зовут именно эту функцию. Сборка детерминирована и дешевле 0.1 с,
    поэтому пересобираем всегда: выход не может разойтись с рецептом."""
    root = root or RECIPES_DIR.parent.parent
    return [build(rp, root) for rp in sorted(RECIPES_DIR.glob("*.yaml"))]


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv == ["--all"]:
        for out_doc, out_gold in build_all():
            print(f"OK: {out_doc.name} + {out_gold.name} -> {out_doc.parent}")
        return 0
    if len(argv) != 1:
        print(__doc__)
        return 2
    recipe_path = Path(argv[0])
    n = len(yaml.safe_load(recipe_path.read_text(encoding="utf-8"))["defects"])
    out_doc, out_gold = build(recipe_path)
    print(f"OK: {n} дефектов -> {out_doc}" + chr(10) + f"Голд: {out_gold}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

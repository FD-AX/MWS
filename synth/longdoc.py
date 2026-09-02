"""Эксперимент «длина контекста»: дефектный документ + N чистых витрин-соседей.

    python synth/longdoc.py

Берёт испорченный synth/out/mart_traffic_v1.md и чистую базу, генерирует
объединённые документы «реестр витрин» разных длин, размещая дефектную витрину
в начале или в конце. Голд один и тот же (дефекты только в одной витрине).
Выход: exp/ctx/len{N}_{pos}.md + exp/targets_ctx.yaml для бенча.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
BASE = (ROOT / "synth/base/mart_traffic_clean.md").read_text(encoding="utf-8")
BAD = (ROOT / "synth/out/mart_traffic_v1.md").read_text(encoding="utf-8")
GOLD = "synth/out/mart_traffic_v1.gold.yaml"

SIZES = [0, 2, 5]          # сколько чистых витрин-соседей добавить
POSITIONS = ["start", "end"]  # где стоит дефектная витрина


def clone_clean(i: int) -> str:
    """Чистая витрина-сосед с переименованными сущностями (реалистичный «реестр»)."""
    text = BASE
    for name in ("TABLE_AGG_TRAFFIC_REGION", "TABLE_DPI_RAW_PS", "TABLE_AGG_LOAD_LOG",
                 "DAG_AGG_TRAFFIC", "DAG_BACKFILL_TRAFFIC"):
        text = text.replace(name, f"{name}_V{i}")
    text = text.replace("# Описание витрины-агрегата",
                        f"# Витрина {i}. Описание витрины-агрегата")
    # понизить уровень заголовков, чтобы документы склеились в один реестр
    text = re.sub(r"^## ", "### ", text, flags=re.MULTILINE)
    text = re.sub(r"^# ", "## ", text, flags=re.MULTILINE)
    return text


def main() -> None:
    out_dir = ROOT / "exp/ctx"
    out_dir.mkdir(parents=True, exist_ok=True)
    bad = re.sub(r"^## ", "### ", BAD, flags=re.MULTILINE)
    bad = re.sub(r"^# ", "## ", bad, flags=re.MULTILINE)

    targets = []
    for n in SIZES:
        neighbors = [clone_clean(i + 1) for i in range(n)]
        for pos in (POSITIONS if n else ["start"]):
            parts = [bad] + neighbors if pos == "start" else neighbors + [bad]
            doc = "# Реестр витрин данных\n\n" + "\n\n".join(parts)
            name = f"len{n}_{pos}"
            (out_dir / f"{name}.md").write_text(doc, encoding="utf-8")
            targets.append({
                "label": f"ctx_{name} (~{len(doc) // 1000}k chars)",
                "doc": f"exp/ctx/{name}.md",
                "gold": GOLD,
            })
    (ROOT / "exp/targets_ctx.yaml").write_text(
        yaml.safe_dump({"targets": targets}, allow_unicode=True, sort_keys=False),
        encoding="utf-8")
    print(f"OK: {len(targets)} документов в exp/ctx/, цели в exp/targets_ctx.yaml")


if __name__ == "__main__":
    main()

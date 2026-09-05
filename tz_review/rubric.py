from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

RUBRIC_PATH = Path(__file__).parent / "rubric.yaml"
EXTRA_PATH = Path(__file__).parent / "rubric_extra.yaml"


def load_rubric(path: Path | None = None, extra: bool | None = None) -> dict[str, Any]:
    """Рубрика; extra=True (или TZR_RUBRIC_EXTRA=1) подмешивает общие слоты из rubric_extra.yaml
    (EXP-19). extra=None — по переменной окружения, чтобы сервисы включали слоты конфигом."""
    p = path or RUBRIC_PATH
    with open(p, encoding="utf-8") as f:
        rubric = yaml.safe_load(f)
    if extra is None:
        extra = os.environ.get("TZR_RUBRIC_EXTRA", "").lower() in ("1", "true", "yes")
    if extra and EXTRA_PATH.exists():
        with open(EXTRA_PATH, encoding="utf-8") as f:
            ext = yaml.safe_load(f) or {}
        rubric["checklist"] = list(rubric.get("checklist", [])) + list(ext.get("checklist", []))
        rubric["extra_slots"] = [q["id"] for q in ext.get("checklist", [])]
    ids = [q["id"] for q in rubric.get("checklist", [])]
    assert len(ids) == len(set(ids)), "Дубли id в чеклисте рубрики"
    return rubric

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

RUBRIC_PATH = Path(__file__).parent / "rubric.yaml"


def load_rubric(path: Path | None = None) -> dict[str, Any]:
    p = path or RUBRIC_PATH
    with open(p, encoding="utf-8") as f:
        rubric = yaml.safe_load(f)
    ids = [q["id"] for q in rubric.get("checklist", [])]
    assert len(ids) == len(set(ids)), "Дубли id в чеклисте рубрики"
    return rubric

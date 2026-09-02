from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

Severity = Literal["critical", "high", "medium", "advisory"]

SEVERITY_ORDER: dict[str, int] = {"critical": 0, "high": 1, "medium": 2, "advisory": 3}
SEVERITY_RU: dict[str, str] = {
    "critical": "Критично",
    "high": "Важно",
    "medium": "Средне",
    "advisory": "Стиль",
}


class Finding(BaseModel):
    """Одна находка ревью. quote обязана быть дословной цитатой из документа
    (проверяется в verify), либо missing=True для отсутствующей информации."""

    fid: str = ""
    category: str
    severity: Severity = "medium"
    section: str = ""
    quote: Optional[str] = None
    missing: bool = False
    why: str
    ask: str = ""
    suggested_fix: Optional[str] = None
    source_pass: str = ""
    verified: bool = False
    score: Optional[float] = None      # оценка критика 0-10
    entropy: Optional[float] = None    # semantic entropy (бит), если считалась

    def sort_key(self) -> tuple:
        return (SEVERITY_ORDER.get(self.severity, 9), -(self.score or 0.0))


class ChecklistAnswer(BaseModel):
    """Ответ LLM на один бинарный вопрос рубрики."""

    id: str
    status: Literal["OK", "MISSING", "UNCLEAR"]
    quote: Optional[str] = None
    why: str = ""
    ask: str = ""

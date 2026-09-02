from __future__ import annotations

from ..llm import LLM
from ..schema import Finding
from . import load_prompt

ALLOWED_CATEGORIES = {"consistency", "completeness", "terminology", "contradiction"}


def run(doc_text: str, llm: LLM) -> list[Finding]:
    """Проверки уровня документа: межсекционная согласованность — то, на чём
    умерли sentence-level инструменты (кейс Bosch) и где LLM даёт преимущество."""
    prompt = load_prompt("document_level", document=doc_text)
    raw = llm.chat_json(system="Ты возвращаешь только валидный JSON.", user=prompt)
    findings: list[Finding] = []
    for item in raw.get("findings", []):
        category = item.get("category", "consistency")
        if category not in ALLOWED_CATEGORIES:
            category = "consistency"
        try:
            findings.append(Finding(
                category=f"doc:{category}",
                severity=item.get("severity", "medium"),
                section=item.get("section", ""),
                quote=item.get("quote"),
                why=item.get("why", ""),
                ask=item.get("ask", ""),
                source_pass="document_level",
            ))
        except Exception:
            continue
    return findings

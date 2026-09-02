from __future__ import annotations

from ..llm import LLM
from ..schema import Finding
from . import load_prompt


def run(doc_text: str, llm: LLM) -> list[Finding]:
    """V0b: честный бейзлайн — один сильный вызов с матрицей классов в промпте.
    Точка отсчёта для всех дельт архитектуры (см. METRICS.md)."""
    prompt = load_prompt("baseline", document=doc_text)
    raw = llm.chat_json(system="Ты возвращаешь только валидный JSON.", user=prompt)
    findings: list[Finding] = []
    for item in raw.get("findings", []):
        try:
            findings.append(Finding(
                category=f"base:{item.get('category', 'unknown')}"[:80],
                severity=item.get("severity", "medium"),
                section=item.get("section", ""),
                quote=item.get("quote"),
                missing=bool(item.get("missing")) or item.get("quote") in (None, ""),
                why=item.get("why", ""),
                ask=item.get("ask", ""),
                source_pass="baseline",
            ))
        except Exception:
            continue
    return findings

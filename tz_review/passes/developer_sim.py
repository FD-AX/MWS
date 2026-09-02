from __future__ import annotations

from ..llm import LLM
from ..schema import Finding
from . import load_prompt


def run(doc_text: str, llm: LLM) -> list[Finding]:
    """«Симуляция разработчика»: вопросы, без которых нельзя начать реализацию.
    Ловит неоднозначности, которых нет в чеклисте."""
    prompt = load_prompt("developer_sim", document=doc_text)
    raw = llm.chat_json(system="Ты возвращаешь только валидный JSON.", user=prompt)
    findings: list[Finding] = []
    for item in raw.get("questions", []):
        try:
            findings.append(Finding(
                category="dev_question",
                severity=item.get("severity", "medium"),
                section=item.get("section", ""),
                quote=item.get("quote"),
                missing=item.get("quote") in (None, ""),
                why=item.get("why", ""),
                ask=item.get("ask", ""),
                source_pass="developer_sim",
            ))
        except Exception:
            continue
    return findings

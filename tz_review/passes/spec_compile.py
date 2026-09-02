from __future__ import annotations

from ..llm import LLM
from ..schema import Finding
from . import load_prompt


def run(doc_text: str, llm: LLM) -> list[Finding]:
    """Гипотеза H5 (IDEAS.md): «компиляция ТЗ» — модель проектирует реализацию
    и логирует каждое вынужденное допущение. Допущение = место, где два разработчика
    разойдутся. Ловит дефекты вне рубрики чеклиста."""
    prompt = load_prompt("spec_compile", document=doc_text)
    raw = llm.chat_json(system="Ты возвращаешь только валидный JSON.", user=prompt)
    findings: list[Finding] = []
    for item in raw.get("assumptions", []):
        try:
            decision = item.get("decision", "")
            assumed = item.get("assumed", "")
            findings.append(Finding(
                category="compile:assumption",
                severity=item.get("severity", "medium"),
                section=item.get("section", ""),
                quote=item.get("quote"),
                missing=item.get("quote") in (None, ""),
                why=(f"Реализация требует допущения: {decision} "
                     f"Принято: {assumed} Риск: {item.get('risk', '')}").strip(),
                ask=f"Уточни в ТЗ: {decision}",
                source_pass="spec_compile",
            ))
        except Exception:
            continue
    return findings

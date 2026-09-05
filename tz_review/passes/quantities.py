from __future__ import annotations

from ..llm import LLM
from ..schema import Finding
from . import load_prompt

# EXP-19/20: класс дефектов «величины и сроки между разделами» (v2hard HRD-RET: сверка на 36 мес.
# при retention 24; HRD-TIME: готовность 10:00 2-го при запуске 3-го; HRD-BOUND: граница месяца)
# GPT-5.5 берёт внутри document_level, gpt-oss-120b — нет. Узкий проход задаёт вопрос прямо:
# сначала выписать величины с цитатами, потом найти несовместимые пары.

SEVERITIES = {"critical", "high", "medium"}


def run(doc_text: str, llm: LLM) -> list[Finding]:
    prompt = load_prompt("quantities", document=doc_text)
    raw = llm.chat_json(system="Ты возвращаешь только валидный JSON.", user=prompt)
    findings: list[Finding] = []
    for item in (raw.get("findings") or []) if isinstance(raw, dict) else []:
        if not isinstance(item, dict):
            continue
        sev = item.get("severity", "medium")
        try:
            findings.append(Finding(
                category="doc:quantities",
                severity=sev if sev in SEVERITIES else "medium",
                section=item.get("section") or "",
                quote=item.get("quote"),
                why=item.get("why") or "",
                ask=item.get("ask") or "",
                source_pass="quantities",
            ))
        except Exception:  # noqa: BLE001 — кривой элемент не роняет проход
            continue
    return findings

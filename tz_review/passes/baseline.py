from __future__ import annotations

from ..llm import LLM
from ..schema import Finding
from . import load_prompt


def run(doc_text: str, llm: LLM, prompt_name: str = "baseline") -> list[Finding]:
    """Бейзлайны одним вызовом. prompt_name задаёт ступень промпт-лестницы:
    ablation_p0 (наивный) -> p1 (+цитаты) -> p2 (+таксономия) -> p3 (+обезличивание)
    -> baseline (= V0b: +калибровка severity и бюджет находок).
    Дельты между ступенями показывают, какой компонент промпта помогает/вредит."""
    prompt = load_prompt(prompt_name, document=doc_text)
    raw = llm.chat_json(system="Ты возвращаешь только валидный JSON.", user=prompt)
    findings: list[Finding] = []
    for item in raw.get("findings", []):
        try:
            findings.append(Finding(
                category=f"base:{item.get('category', 'naive')}"[:80],
                severity=item.get("severity", "medium"),
                section=item.get("section", ""),
                quote=item.get("quote"),
                missing=bool(item.get("missing")) or item.get("quote") in (None, ""),
                why=item.get("why") or item.get("issue", ""),
                ask=item.get("ask", ""),
                source_pass=f"baseline:{prompt_name}",
            ))
        except Exception:
            continue
    return findings

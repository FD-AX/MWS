from __future__ import annotations

import json
from typing import Any

from ..llm import LLM
from ..schema import ChecklistAnswer, Finding
from . import load_prompt

BATCH_SIZE = 5  # ограниченная задача на вызов: длинный контекст + много вопросов = деградация


def run(doc_text: str, rubric: dict[str, Any], llm: LLM) -> tuple[list[Finding], dict[str, str]]:
    """Чеклист-аудит «слотов» полноты. Возвращает (находки, статусы всех слотов).
    Статусы нужны для coverage-метрики и для entropy-прохода."""
    questions = rubric["checklist"]
    by_id = {q["id"]: q for q in questions}
    findings: list[Finding] = []
    statuses: dict[str, str] = {}

    for i in range(0, len(questions), BATCH_SIZE):
        batch = questions[i:i + BATCH_SIZE]
        qtext = "\n".join(f'- id "{q["id"]}" [{q["aspect"]}]: {q["question"]}' for q in batch)
        prompt = load_prompt("checklist", questions=qtext, document=doc_text)
        raw = llm.chat_json(system="Ты возвращаешь только валидный JSON.", user=prompt)
        for item in raw.get("answers", []):
            try:
                ans = ChecklistAnswer(**item)
            except Exception:
                continue
            q = by_id.get(ans.id)
            if q is None:
                continue
            statuses[ans.id] = ans.status
            if ans.status == "OK":
                continue
            findings.append(Finding(
                category=f"checklist:{ans.id}",
                severity=q["severity"] if ans.status == "MISSING" else "medium",
                section=q["aspect"],
                quote=ans.quote if ans.status == "UNCLEAR" else None,
                missing=ans.status == "MISSING",
                why=ans.why or f"Слот «{q['question']}» не закрыт документом.",
                ask=ans.ask or q["question"],
                source_pass="checklist",
            ))

    for qid in by_id:
        statuses.setdefault(qid, "UNKNOWN")
    return findings, statuses


def coverage(statuses: dict[str, str]) -> tuple[int, int]:
    ok = sum(1 for s in statuses.values() if s == "OK")
    return ok, len(statuses)


def dump_statuses(statuses: dict[str, str]) -> str:
    return json.dumps(statuses, ensure_ascii=False, indent=2)

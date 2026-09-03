from __future__ import annotations

import json
import sys
from typing import Any

from ..llm import LLM
from ..schema import ChecklistAnswer, Finding
from . import load_prompt

BATCH_SIZE = 5  # ограниченная задача на вызов: длинный контекст + много вопросов = деградация


def _ask(batch: list[dict], doc_text: str, llm: LLM) -> dict[str, ChecklistAnswer]:
    """Один вызов на батч вопросов → валидные ответы по id (только из этого батча)."""
    ids = {q["id"] for q in batch}
    qtext = "\n".join(f'- id "{q["id"]}" [{q["aspect"]}]: {q["question"]}' for q in batch)
    prompt = load_prompt("checklist", questions=qtext, document=doc_text)
    raw = llm.chat_json(system="Ты возвращаешь только валидный JSON.", user=prompt)
    answers: dict[str, ChecklistAnswer] = {}
    for item in (raw.get("answers", []) if isinstance(raw, dict) else []):
        try:
            ans = ChecklistAnswer(**item)
        except Exception:
            continue
        if ans.id in ids:
            answers[ans.id] = ans
    return answers


def run(doc_text: str, rubric: dict[str, Any], llm: LLM) -> tuple[list[Finding], dict[str, str]]:
    """Чеклист-аудит «слотов» полноты. Возвращает (находки, статусы всех слотов).
    Статусы нужны для coverage-метрики и для entropy-прохода."""
    questions = rubric["checklist"]
    findings: list[Finding] = []
    statuses: dict[str, str] = {}
    unanswered: list[str] = []

    for i in range(0, len(questions), BATCH_SIZE):
        batch = questions[i:i + BATCH_SIZE]
        answers = _ask(batch, doc_text, llm)
        rest = [q for q in batch if q["id"] not in answers]
        if rest:
            # Обрезанный max_tokens'ом или неполный JSON терял слоты МОЛЧА
            # (EXP-13: 10/27 слотов UNKNOWN на 17k-документе) — добираем отдельным вызовом.
            answers.update(_ask(rest, doc_text, llm))
        for q in batch:
            ans = answers.get(q["id"])
            if ans is None:
                unanswered.append(q["id"])
                continue
            statuses[q["id"]] = ans.status
            if ans.status == "OK":
                continue
            findings.append(Finding(
                category=f"checklist:{q['id']}",
                severity=q["severity"] if ans.status == "MISSING" else "medium",
                section=q["aspect"],
                quote=ans.quote if ans.status == "UNCLEAR" else None,
                missing=ans.status == "MISSING",
                why=ans.why or f"Слот «{q['question']}» не закрыт документом.",
                ask=ans.ask or q["question"],
                source_pass="checklist",
            ))

    for qid in unanswered:
        statuses[qid] = "UNKNOWN"
    if unanswered:
        print(f"! checklist: слоты без ответа после повтора: {unanswered}",
              file=sys.stderr, flush=True)
    return findings, statuses


def coverage(statuses: dict[str, str]) -> tuple[int, int]:
    ok = sum(1 for s in statuses.values() if s == "OK")
    return ok, len(statuses)


def dump_statuses(statuses: dict[str, str]) -> str:
    return json.dumps(statuses, ensure_ascii=False, indent=2)

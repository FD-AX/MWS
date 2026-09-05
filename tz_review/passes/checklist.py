from __future__ import annotations

import json
import sys
from typing import Any

from ..llm import LLM
from ..schema import ChecklistAnswer, Finding
from . import load_prompt

BATCH_SIZE = 5  # ограниченная задача на вызов: длинный контекст + много вопросов = деградация


def slot_applies(q: dict[str, Any], doc_text: str) -> bool:
    """Применим ли слот к документу по детерминированным условиям рубрики.
    applies_if — регулярка, которая должна встретиться в тексте; not_if — которая не должна.
    Нет условий → применим. Не применим → статус NA без вызова модели."""
    import re
    text = doc_text.lower()
    ok = True
    if q.get("applies_if"):
        ok = re.search(q["applies_if"], text, flags=re.IGNORECASE) is not None
    if ok and q.get("not_if"):
        ok = re.search(q["not_if"], text, flags=re.IGNORECASE) is None
    return ok


def split_applicable(questions: list[dict], doc_text: str) -> tuple[list[dict], list[str]]:
    applicable = [q for q in questions if slot_applies(q, doc_text)]
    na = [q["id"] for q in questions if not slot_applies(q, doc_text)]
    return applicable, na


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
        except Exception as e:  # noqa: BLE001 — невалидный ответ не теряем молча
            print(f"! checklist: невалидный ответ {str(item)[:120]!r}: {str(e)[:120]}",
                  file=sys.stderr, flush=True)
            continue
        if ans.id in ids:
            answers[ans.id] = ans
    return answers


def make_batches(questions: list[dict], extra_ids: set[str],
                 na_ids: set[str] | None = None) -> list[list[dict]]:
    """Батчи по BATCH_SIZE со стабильным составом.
    1) Базовые и дополнительные слоты (rubric_extra) батчатся раздельно: подключение extra не должно
       менять состав батчей базовых 27 слотов (EXP-19: ответы на официальные пункты плывут с контекстом батча).
    2) Батчи режутся по ПОЛНОМУ списку слотов, и только потом из них убираются NA-слоты (правила
       применимости): иначе каждое новое NA-правило перекраивает все батчи (EXP-22: v2g на doc3 10/16, A 3/9
       после включения NA для INC/NUL-02/MAP-02 при том же документе). Пустые батчи выбрасываются."""
    na = na_ids or set()
    base = [q for q in questions if q["id"] not in extra_ids]
    extra = [q for q in questions if q["id"] in extra_ids]
    raw = [g[i:i + BATCH_SIZE] for g in (base, extra) for i in range(0, len(g), BATCH_SIZE)]
    return [b for b in ([q for q in batch if q["id"] not in na] for batch in raw) if b]


def run(doc_text: str, rubric: dict[str, Any], llm: LLM,
        on_batch=None) -> tuple[list[Finding], dict[str, str]]:
    """Чеклист-аудит «слотов» полноты. Возвращает (находки, статусы всех слотов).
    Статусы нужны для coverage-метрики и для entropy-прохода.
    on_batch(i, n) — необязательный колбэк прогресса после каждого батча."""
    questions, na_slots = split_applicable(rubric["checklist"], doc_text)
    findings: list[Finding] = []
    statuses: dict[str, str] = {q: "NA" for q in na_slots}
    unanswered: list[str] = []
    # Батчи — по полному списку слотов рубрики, NA убираются внутри батчей (состав стабилен).
    batches = make_batches(rubric["checklist"], set(rubric.get("extra_slots") or []), set(na_slots))
    n_batches = len(batches)

    for bi, batch in enumerate(batches):
        if on_batch is not None:
            on_batch(bi, n_batches)
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
            if ans.status in ("OK", "NA"):  # NA: аспект не относится к документу — не находка
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
    """Закрытые слоты: OK + NA (не применимо к документу)."""
    ok = sum(1 for s in statuses.values() if s in ("OK", "NA"))
    return ok, len(statuses)


def dump_statuses(statuses: dict[str, str]) -> str:
    return json.dumps(statuses, ensure_ascii=False, indent=2)

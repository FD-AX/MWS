from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from ..llm import LLM
from ..schema import Finding

# Гипотеза H10 (IDEAS.md): неоднозначность из ЛОГИТОВ, без сэмплирования.
# На каждый OK-слот — один вызов max_tokens=1: «ровно один однозначный ответ? YES/NO»;
# сигнал = вероятностная масса токенов, мера = бинарная энтропия H(p).
P_NO_THRESHOLD = 0.35
MARGIN_THRESHOLD = 0.25

PROMPT = (
    "Вопрос по документу: {question}\n\n"
    "Можно ли из документа дать РОВНО ОДИН однозначный ответ на этот вопрос "
    "(без додумывания и без альтернативных прочтений)?\n\n"
    "Документ:\n---\n{document}\n---"
)


def binary_entropy(p: float) -> float:
    p = min(max(p, 1e-9), 1 - 1e-9)
    return -(p * math.log2(p) + (1 - p) * math.log2(1 - p))


def run(doc_text: str, rubric: dict[str, Any], statuses: dict[str, str],
        llm_lp: LLM) -> list[Finding]:
    by_id = {q["id"]: q for q in rubric["checklist"]}
    ok_slots = [qid for qid, s in statuses.items() if s == "OK"]

    def probe(qid: str):
        q = by_id[qid]
        p_yes, p_no = llm_lp.binary_probs(
            "Answer with exactly one word: YES or NO.",
            PROMPT.format(question=q["question"], document=doc_text))
        return qid, p_yes, p_no

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(probe, ok_slots))

    findings: list[Finding] = []
    for qid, p_yes, p_no in results:
        q = by_id[qid]
        total = p_yes + p_no
        if total < 0.5:  # масса ушла в посторонние токены — сигнал не читается
            continue
        p_no_n = p_no / total
        margin = abs(p_yes - p_no) / total
        if p_no_n < P_NO_THRESHOLD and margin > MARGIN_THRESHOLD:
            continue
        verdict = ("уверенно считает, что однозначного ответа НЕТ"
                   if p_no_n >= 0.8 else "колеблется между прочтениями")
        findings.append(Finding(
            category=f"lp:{qid}",
            severity="high" if p_no_n >= 0.6 else "medium",
            section=q["aspect"],
            missing=True,
            why=(f"Логит-зонд: по вопросу «{q['question']}» модель {verdict}: "
                 f"P(нет)={p_no_n:.2f}, бинарная энтропия {binary_entropy(p_no_n):.2f} бит."),
            ask=f"Сформулируй ответ на «{q['question']}» так, чтобы прочтение было единственным.",
            source_pass="uncertainty_lp",
            entropy=round(binary_entropy(p_no_n), 3),
        ))
    return findings

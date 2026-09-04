"""Детерминированные фильтры LLM-находок до критика (разметка «лишних» 05.09).

- Вопросы о настоящем имени заглушки обезличивания («как называется столбец FIELD_IMSI»,
  «точные имена полей для join», «Папка» как отсутствие пути): документ обезличен намеренно,
  такие вопросы — мусор на слабых моделях (5 из 21 не-TP находок).
"""
from __future__ import annotations

import re

from ..schema import Finding

PLACEHOLDER_QUESTION = re.compile(
    r"(как(ое|ие|ой)?\s+(точно\s+|именно\s+)?(называ|назван)|"
    r"(точн|правильн|реальн|настоящ|фактическ)\w*\s+(им[яе]н?\w*|назван\w*)\s+(столбц|пол[еяй]|таблиц|колон|топик|кластер|схем)|"
    r"им(я|ена)\s+(столбц|пол[еяй]|таблиц|колон|топик|кластер)\w*\s+(в|для|содерж|хран)|"
    r"без\s+(точн|правильн|реальн)\w*\s+(им[яе]н?\w*|назван\w*))",
    re.IGNORECASE,
)


def is_placeholder_question(f: Finding) -> bool:
    if f.source_pass in ("deterministic", "doc_graph"):
        return False
    text = f"{f.ask or ''} {f.why or ''}"
    return PLACEHOLDER_QUESTION.search(text) is not None


def drop_placeholder_questions(findings: list[Finding]) -> tuple[list[Finding], list[Finding]]:
    kept, dropped = [], []
    for f in findings:
        if is_placeholder_question(f):
            f.score = 0.0
            f.why = "[фильтр: вопрос о настоящем имени заглушки обезличивания] " + (f.why or "")
            dropped.append(f)
        else:
            kept.append(f)
    return kept, dropped

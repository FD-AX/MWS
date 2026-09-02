from __future__ import annotations

from .document import Document, normalize
from .schema import Finding


def verify_findings(findings: list[Finding], doc: Document) -> tuple[list[Finding], list[Finding]]:
    """Программная верификация якорей: цитата обязана быть подстрокой документа
    (после нормализации). Не нашлась — находка отбрасывается; нашлась в другой
    секции — переанкоривается. MISSING-находки цитат не требуют.

    Возвращает (verified, dropped)."""
    norm_doc = normalize(doc.full_text)
    norm_sections = [(s.title, normalize(s.title + "\n" + s.text)) for s in doc.sections]

    verified: list[Finding] = []
    dropped: list[Finding] = []
    for f in findings:
        if f.missing or not f.quote:
            if f.missing:
                f.verified = True
                verified.append(f)
            else:
                dropped.append(f)  # не MISSING и без цитаты — не принимаем
            continue
        nq = normalize(f.quote)
        # Порог длины защищает от тривиально-совпадающих LLM-цитат («и», «данные»);
        # детерминированные цитаты построены из самого текста — им порог не нужен.
        min_len = 0 if f.source_pass == "deterministic" else 8
        if len(nq) < min_len or nq not in norm_doc:
            dropped.append(f)
            continue
        f.verified = True
        # Переанкоривание: секция, в которой цитата реально находится.
        home = next((title for title, ns in norm_sections if nq in ns), None)
        if home and normalize(f.section) not in normalize(home):
            f.section = home
        elif home and not f.section:
            f.section = home
        verified.append(f)
    return verified, dropped


def mark_only(findings: list[Finding], doc: Document) -> list[Finding]:
    """Для бейзлайна: верифицируем и переанкориваем цитаты, но НИЧЕГО не отбрасываем —
    иначе харнесс улучшал бы бейзлайн и дельты архитектуры были бы нечестными."""
    verified, dropped = verify_findings(findings, doc)
    for f in dropped:
        f.verified = False
    return verified + dropped


def anchoring_rate(verified: list[Finding], dropped: list[Finding]) -> float:
    quoted = [f for f in verified + dropped if not f.missing]
    if not quoted:
        return 1.0
    return sum(1 for f in quoted if f.verified) / len(quoted)

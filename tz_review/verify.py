from __future__ import annotations

import re

from .document import Document, normalize
from .schema import Finding


def _loose(s: str) -> str:
    """Вторая ступень нормализации: без разделителей таблиц. Модели переписывают
    табличные цитаты без «|» и с иными переносами строк (EXP-13: 5/21 находок
    отброшены именно так на 17k-документе)."""
    return re.sub(r"\s+", " ", s.replace("|", " ")).strip()


FRAG_SPLIT = re.compile(r"\s+vs\.?\s+|\s+против\s+|;|…|\.\.\.|\s+[—–]\s+|\s+-\s+|\n|`|«|»|\"")
MIN_FRAG = 25  # символов нормализованного фрагмента: короче — риск тривиального совпадения


def reanchor(nq: str, norm_doc: str, loose_doc: str) -> str | None:
    """Составная или пересказанная цитата («A vs B», «DDL defines X …; earlier description»)
    → самый длинный ДОСЛОВНЫЙ фрагмент (≥ MIN_FRAG), который есть в документе.
    EXP-19: gpt-oss-120b на DDL-плотных документах склеивает цитату из двух мест и пересказывает
    (иногда по-английски) — 25–50 % находок уровня документа отбрасывались целиком, хотя одно из
    мест цитировалось дословно. Фрагмент берётся из документа, поэтому точность не страдает."""
    parts = [p.strip(" .,:;()[]") for p in FRAG_SPLIT.split(nq) if p]
    for p in sorted({p for p in parts if len(p) >= MIN_FRAG}, key=len, reverse=True):
        if p in norm_doc:
            return p
        lp = _loose(p)
        if len(lp) >= MIN_FRAG and lp in loose_doc:
            return lp
    # Скользящее окно по словам: самый длинный отрезок цитаты, присутствующий дословно.
    words = nq.split()
    for n in range(len(words), 3, -1):
        for i in range(0, len(words) - n + 1):
            seg = " ".join(words[i:i + n])
            if len(seg) < MIN_FRAG:
                break
            if seg in norm_doc:
                return seg
    return None


def verify_findings(findings: list[Finding], doc: Document) -> tuple[list[Finding], list[Finding]]:
    """Программная верификация якорей: цитата обязана быть подстрокой документа
    (после нормализации). Не нашлась — находка отбрасывается; нашлась в другой
    секции — переанкоривается. MISSING-находки цитат не требуют.

    Возвращает (verified, dropped)."""
    norm_doc = normalize(doc.full_text)
    loose_doc = _loose(norm_doc)
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
        if len(nq) < min_len:
            dropped.append(f)
            continue
        if nq in norm_doc:
            home = next((title for title, ns in norm_sections if nq in ns), None)
        else:
            lq = _loose(nq)
            if len(lq) >= min_len and lq in loose_doc:
                home = next((title for title, ns in norm_sections if lq in _loose(ns)), None)
            else:
                # Составная/пересказанная цитата: переанкориваем на дословный фрагмент.
                frag = reanchor(nq, norm_doc, loose_doc) if f.source_pass != "deterministic" else None
                if frag is None:
                    dropped.append(f)
                    continue
                f.quote = frag
                home = next((title for title, ns in norm_sections
                             if frag in ns or frag in _loose(ns)), None)
        f.verified = True
        # Переанкоривание: секция, в которой цитата реально находится.
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

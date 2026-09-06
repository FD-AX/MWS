from __future__ import annotations

import difflib
import re

from .document import Document, normalize
from .schema import Finding


def _loose(s: str) -> str:
    """Вторая ступень нормализации: без разделителей таблиц. Модели переписывают
    табличные цитаты без «|» и с иными переносами строк (EXP-13: 5/21 находок
    отброшены именно так на 17k-документе)."""
    return re.sub(r"\s+", " ", s.replace("|", " ")).strip()


def _bare_indexed(s: str) -> tuple[str, list[int]]:
    """Третья ступень: без пунктуации вообще (остаются буквы, цифры, «_», одиночные пробелы) плюс
    карта индексов bare[k] ← s[idx[k]], чтобы совпадение вернуть исходным фрагментом документа
    («field_traffic_gb | decimal(18,3)», а не «field_traffic_gb decimal 18 3»).
    EXP-24: «способ загрузки: инкремент» против заголовка «способ загрузки инкремент» — одно
    двоеточие, и дословная по сути цитата отбрасывалась."""
    out: list[str] = []
    idx: list[int] = []
    gap = False
    for i, ch in enumerate(s):
        if ch.isalnum() or ch == "_":
            if gap and out:
                out.append(" ")
                idx.append(i - 1)
            gap = False
            out.append(ch)
            idx.append(i)
        else:
            gap = True
    return "".join(out), idx


def _bare(s: str) -> str:
    return _bare_indexed(s)[0]


def _bare_span(bp: str, norm_doc: str, bare: tuple[str, list[int]]) -> str | None:
    """Найти bare-фрагмент bp в bare-документе и вернуть соответствующий кусок norm_doc."""
    bare_doc, idx = bare
    j = bare_doc.find(bp)
    if j < 0 or not bp:
        return None
    start, end = idx[j], idx[j + len(bp) - 1] + 1
    # Скобка, открытая внутри фрагмента, закрывается сразу за ним: «decimal(18,3» → «decimal(18,3)».
    while end < len(norm_doc) and norm_doc[end] == ")" and norm_doc[start:end].count("(") > norm_doc[start:end].count(")"):
        end += 1
    return norm_doc[start:end]


_DISTINCT = re.compile(r"[a-z]+_[a-z0-9_]+|\d")  # идентификатор обезличивания (field_x/table_x) или число


def _weight(seg: str) -> tuple[bool, int]:
    """Чем якорить составную цитату: фрагмент с идентификатором/числом важнее общей фразы
    («в разделе структура данных» проигрывает «field_traffic_gb decimal(18,2)»), затем — длина."""
    return (bool(_DISTINCT.search(seg)), len(seg))


FRAG_SPLIT = re.compile(r"\s+vs\.?\s+|\s+против\s+|;|…|\.\.\.|\s+[—–]\s+|\s+-\s+|\n|`|«|»|\"")
MIN_FRAG = 25  # символов нормализованного фрагмента: короче — риск тривиального совпадения

# Нечёткий якорь (последний рубеж): строка документа, похожая на цитату не менее чем на FUZZY_MIN_RATIO.
# EXP-24 на 54 отброшенных находках бенча: верные якоря ≥ 0.72 (перифраз одним словом
# «последняя/актуальная запись за месяц»), все ошибочные кандидаты ≤ 0.52. Якорь берётся из
# ДОКУМЕНТА, поэтому в отчёт попадает его текст, а не пересказ модели.
FUZZY_MIN_RATIO = 0.70
FUZZY_MIN_LEN = 20


def reanchor(nq: str, norm_doc: str, loose_doc: str,
             bare: tuple[str, list[int]] | None = None) -> str | None:
    """Составная или пересказанная цитата («A vs B», «DDL defines X …; earlier description»)
    → самый длинный ДОСЛОВНЫЙ фрагмент (≥ MIN_FRAG), который есть в документе.
    EXP-19: gpt-oss-120b на DDL-плотных документах склеивает цитату из двух мест и пересказывает
    (иногда по-английски) — 25–50 % находок уровня документа отбрасывались целиком, хотя одно из
    мест цитировалось дословно. Фрагмент берётся из документа, поэтому точность не страдает."""
    bare = _bare_indexed(norm_doc) if bare is None else bare
    parts = [p.strip(" .,:;()[]") for p in FRAG_SPLIT.split(nq) if p]
    for p in sorted({p for p in parts if len(p) >= MIN_FRAG}, key=len, reverse=True):
        if p in norm_doc:
            return p
        lp = _loose(p)
        if len(lp) >= MIN_FRAG and lp in loose_doc:
            return lp
        bp = _bare(p)
        if len(bp) >= MIN_FRAG:
            span = _bare_span(bp, norm_doc, bare)
            if span:
                return span
    # Скользящее окно по словам: отрезки цитаты (≥ 2 слов, ≥ MIN_FRAG символов), присутствующие
    # дословно; из них берём лучший по _weight. EXP-24: раньше короткий первый отрезок обрывал
    # перебор (break) — «шаг 1. … шаг 5. определение региона» не находил «шаг 5. определение региона»;
    # а первый найденный отрезок мог быть общей фразой вместо строки с идентификатором.
    words = nq.split()
    found: list[str] = []
    for n in range(len(words), 1, -1):
        for i in range(0, len(words) - n + 1):
            seg = " ".join(words[i:i + n])
            if len(seg) < MIN_FRAG:
                continue
            if seg in norm_doc:
                found.append(seg)
                continue
            bs = _bare(seg)
            if len(bs) >= MIN_FRAG:
                span = _bare_span(bs, norm_doc, bare)
                if span:
                    found.append(span)
    return max(found, key=_weight) if found else None


def _unique_line(nq: str, norm_doc: str, raw: str) -> str | None:
    """Строка документа, содержащая короткую цитату, если цитата встречается в документе ровно один раз
    (как отдельное слово/токен, а не внутри другого слова)."""
    if len(re.findall(r"(?<!\w)" + re.escape(nq) + r"(?!\w)", norm_doc)) != 1:
        return None
    pat = re.compile(r"(?<!\w)" + re.escape(nq) + r"(?!\w)")
    for ln in raw.splitlines():
        n = normalize(re.sub(r"^\s*#+\s*", "", ln))
        if n and pat.search(n):
            return n
    return None


def doc_units(raw: str) -> list[str]:
    """Кандидаты для нечёткого якоря: нормализованные строки документа (без маркеров заголовков)
    и пары соседних строк — цитата может захватывать перенос."""
    lines = [normalize(re.sub(r"^\s*#+\s*", "", ln)) for ln in raw.splitlines()]
    lines = [ln for ln in lines if ln]
    return lines + [a + " " + b for a, b in zip(lines, lines[1:])]


def _best_window(nq: str, unit: str) -> tuple[str, float]:
    """Цитата — часть длинной строки (табличный ряд): лучшее окно по словам длиной с цитату."""
    words = unit.split()
    k = max(3, len(nq.split()))
    best = ("", 0.0)
    for i in range(0, max(1, len(words) - k + 1)):
        cand = " ".join(words[i:i + k])
        sm = difflib.SequenceMatcher(None, nq, cand, autojunk=False)
        if sm.quick_ratio() < best[1]:
            continue
        r = sm.ratio()
        if r > best[1]:
            best = (cand, r)
    return best


def fuzzy_anchor(nq: str, units: list[str], min_ratio: float = FUZZY_MIN_RATIO) -> tuple[str, float] | None:
    """Последний рубеж после reanchor: строка документа, максимально похожая на цитату
    (difflib.ratio ≥ min_ratio). Возвращает (текст документа, похожесть) или None.
    Дешёвый предфильтр по общим словам держит перебор в миллисекундах на документ."""
    if len(nq) < FUZZY_MIN_LEN:
        return None
    q_words = set(nq.split())
    best = ("", 0.0)
    for u in units:
        if len(q_words & set(u.split())) < max(2, len(q_words) // 4):
            continue
        if len(u) > 1.5 * len(nq):
            cand, r = _best_window(nq, u)
        else:
            cand, r = u, difflib.SequenceMatcher(None, nq, u, autojunk=False).ratio()
        if r > best[1]:
            best = (cand, r)
    if not best[0] or best[1] < min_ratio:
        return None
    return best[0].strip(" .,:;()[]|"), best[1]


def verify_findings(findings: list[Finding], doc: Document) -> tuple[list[Finding], list[Finding]]:
    """Программная верификация якорей: цитата обязана быть подстрокой документа
    (после нормализации). Не нашлась — находка отбрасывается; нашлась в другой
    секции — переанкоривается. MISSING-находки цитат не требуют.

    Возвращает (verified, dropped)."""
    norm_doc = normalize(doc.full_text)
    loose_doc = _loose(norm_doc)
    bare = _bare_indexed(norm_doc)
    norm_sections = [(s.title, normalize(s.title + "\n" + s.text)) for s in doc.sections]
    units: list[str] | None = None  # кандидаты нечёткого якоря — лениво, нужны редко

    def _home(frag: str) -> str | None:
        return next((title for title, ns in norm_sections
                     if frag in ns or frag in _loose(ns) or frag in _bare(ns)), None)

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
            # EXP-24: короткая цитата, которая встречается в документе РОВНО один раз («5G» в примере
            # данных), не тривиальна — якорим на её строку; в отчёт идёт строка документа.
            line = _unique_line(nq, norm_doc, doc.full_text) if nq else None
            if line is None:
                dropped.append(f)
                continue
            f.quote = line
            f.verified = True
            home = _home(line)
            if home and normalize(f.section) not in normalize(home):
                f.section = home
            elif home and not f.section:
                f.section = home
            verified.append(f)
            continue
        lq, bq = _loose(nq), _bare(nq)
        span = _bare_span(bq, norm_doc, bare) if len(bq) >= min_len else None
        if nq in norm_doc:
            home = next((title for title, ns in norm_sections if nq in ns), None)
        elif len(lq) >= min_len and lq in loose_doc:
            home = next((title for title, ns in norm_sections if lq in _loose(ns)), None)
        elif span:
            f.quote = span  # отличие только в пунктуации → в отчёт идёт фрагмент документа
            home = _home(span)
        elif f.source_pass == "deterministic":
            dropped.append(f)  # детерминированные цитаты построены из текста — им спасение не положено
            continue
        else:
            # Составная/пересказанная цитата: переанкориваем на дословный фрагмент.
            frag = reanchor(nq, norm_doc, loose_doc, bare)
            if frag is None:
                # Последний рубеж: похожая строка документа (артефакты конвертации, перифраз одним словом).
                if units is None:
                    units = doc_units(doc.full_text)
                hit = fuzzy_anchor(nq, units)
                if hit is None:
                    dropped.append(f)
                    continue
                frag = hit[0]
            f.quote = frag
            home = _home(frag)
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

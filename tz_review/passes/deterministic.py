from __future__ import annotations

import re
from typing import Any

from ..document import Document, normalize
from ..schema import Finding


def _sentence_around(text: str, start: int, end: int, max_len: int = 200) -> str:
    """Расширяем матч до границ предложения, чтобы цитата была читаемой."""
    left = max(text.rfind(".", 0, start), text.rfind("\n", 0, start), 0)
    right_candidates = [i for i in (text.find(".", end), text.find("\n", end)) if i != -1]
    right = min(right_candidates) + 1 if right_candidates else len(text)
    quote = text[left:right].strip().lstrip(".").strip()
    return quote[:max_len]


_PLACEHOLDER_WORDS = {"tbd", "todo", "n/a", "na", "xxx", "???"}


def _is_empty_body(body: str, min_chars: int) -> bool:
    """Пуст ли раздел: нет ни одного слова, либо только маркер-заглушка (TBD/TODO).
    Короткий содержательный ответ («Способ загрузки: Инкремент») пустым не считается
    (разметка 05.09: ложное «пусто» на doc3)."""
    words = re.findall(r"[а-яёa-z0-9/?]+", body.lower())
    if not words:
        return True
    if all(w in _PLACEHOLDER_WORDS for w in words):
        return True
    return len(body.strip("-—* ")) < min_chars and len(words) < 2 and words[0] in _PLACEHOLDER_WORDS


def run(doc: Document, rubric: dict[str, Any]) -> list[Finding]:
    """Детерминированный слой: языковые паттерны + пустые обязательные разделы.
    Бесплатно по токенам, precision правил ~100% на своих классах."""
    findings: list[Finding] = []

    for group, spec in rubric.get("language_patterns", {}).items():
        for pattern in spec["patterns"]:
            rx = re.compile(pattern, re.IGNORECASE)
            for section in doc.sections:
                for m in rx.finditer(section.text):
                    findings.append(Finding(
                        category=f"lang:{group}",
                        severity=spec["severity"],
                        section=section.title,
                        quote=_sentence_around(section.text, m.start(), m.end()),
                        why=f"«{m.group(0)}» — {spec['why']}",
                        ask="Замени на закрытую, измеримую формулировку.",
                        source_pass="deterministic",
                    ))

    min_chars = int(rubric.get("min_section_chars", 40))
    titles_norm = [(s, normalize(s.title)) for s in doc.sections]

    # Официальный шаблон МТС: все разделы сохраняются; пустой допустим только
    # с явным «не применимо» (keypoints_official.md, п.5).
    doc_norm = normalize(doc.raw)
    absent = [name for name in rubric.get("official_sections", [])
              if normalize(name) not in doc_norm]
    if absent:
        findings.append(Finding(
            category="template:official_missing",
            severity="medium",
            section="(шаблон)",
            missing=True,
            why=("Отсутствуют разделы официального шаблона (по правилам кейсодателя "
                 "все разделы сохраняются, неиспользуемые помечаются «не применимо»): "
                 + ", ".join(absent) + "."),
            ask="Добавь недостающие разделы или явно пометь их «не применимо».",
            source_pass="deterministic",
        ))
    flagged_empty: set[str] = set()
    for req in rubric.get("required_sections", []):
        aliases = [normalize(a) for a in [req["name"], *req.get("aliases", [])]]
        matched = [s for s, tn in titles_norm if any(a in tn for a in aliases)]
        if not matched:
            # Разделы нашей доменной рубрики, которых нет в официальном шаблоне МТС
            # («Регламент загрузки», «Контроль качества»), — medium: это рекомендация,
            # а не нарушение шаблона кейсодателя (разметка 05.09: 2 FP на doc2).
            in_official = any(normalize(a) in normalize(o) or normalize(o) in normalize(a)
                              for o in rubric.get("official_sections", []) for a in aliases if len(a) > 5)
            findings.append(Finding(
                category="template:missing_section",
                severity="high" if in_official else "medium",
                section=req["name"],
                missing=True,
                why=f"Обязательный раздел шаблона «{req['name']}» отсутствует в документе.",
                ask=f"Добавь раздел «{req['name']}» или укажи, почему он не применим.",
                source_pass="deterministic",
            ))
            continue
        if all(_is_empty_body(s.body, min_chars)
               and "не применимо" not in normalize(s.body) for s in matched):
            findings.append(Finding(
                category="template:empty_section",
                severity="high",
                section=matched[0].title,
                missing=True,
                why=f"Раздел «{matched[0].title}» присутствует, но фактически пуст "
                    f"(<{min_chars} символов содержимого).",
                ask="Заполни раздел или явно укажи «не применимо» с обоснованием.",
                source_pass="deterministic",
            ))
            flagged_empty.add(matched[0].title)

    # Раздел официального шаблона есть заголовком, но пуст (прочерк/ничего) без
    # «не применимо» — нарушение п.5 «Основных моментов» (раздел сохранён формально).
    official_norm = [normalize(n) for n in rubric.get("official_sections", [])]
    for s, tn in titles_norm:
        if s.title in flagged_empty or not any(n in tn for n in official_norm):
            continue
        if re.sub(r"[\s\-—–*_.:;|]+", "", s.body) or "не применимо" in normalize(s.body):
            continue
        findings.append(Finding(
            category="template:empty_section",
            severity="medium",
            section=s.title,
            missing=True,
            why=(f"Раздел официального шаблона «{s.title}» присутствует, но пуст: "
                 "по правилам кейсодателя неиспользуемый раздел помечается «не применимо»."),
            ask="Заполни раздел или явно укажи «не применимо» с обоснованием.",
            source_pass="deterministic",
        ))

    return findings

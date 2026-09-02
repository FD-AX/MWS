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
    for req in rubric.get("required_sections", []):
        aliases = [normalize(a) for a in [req["name"], *req.get("aliases", [])]]
        matched = [s for s, tn in titles_norm if any(a in tn for a in aliases)]
        if not matched:
            findings.append(Finding(
                category="template:missing_section",
                severity="high",
                section=req["name"],
                missing=True,
                why=f"Обязательный раздел шаблона «{req['name']}» отсутствует в документе.",
                ask=f"Добавь раздел «{req['name']}» или укажи, почему он не применим.",
                source_pass="deterministic",
            ))
            continue
        if all(len(s.body.strip("-—* ")) < min_chars for s in matched):
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

    return findings

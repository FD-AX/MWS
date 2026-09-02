from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Section:
    title: str
    level: int
    text: str = ""

    @property
    def body(self) -> str:
        return self.text.strip()


@dataclass
class Document:
    raw: str
    sections: list[Section] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        return self.raw

    def section_titles(self) -> list[str]:
        return [s.title for s in self.sections]


_HEADER = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
# «1. Источник данных» / «2.3 Регламент» в начале строки тоже считаем заголовком,
# если строка короткая и без точки на конце — так размечают ТЗ без markdown.
_NUM_HEADER = re.compile(r"^(\d+(?:\.\d+)*)[.)]\s+([А-ЯЁA-Z].{2,60}?)\s*$")


def parse(text: str) -> Document:
    doc = Document(raw=text)
    current = Section(title="(преамбула)", level=0)
    for line in text.splitlines():
        m = _HEADER.match(line)
        level_title = None
        if m:
            level_title = (len(m.group(1)), m.group(2))
        else:
            n = _NUM_HEADER.match(line)
            if n and not line.rstrip().endswith("."):
                level_title = (n.group(1).count(".") + 1, f"{n.group(1)}. {n.group(2)}")
        if level_title:
            if current.body or current.title != "(преамбула)":
                doc.sections.append(current)
            current = Section(title=level_title[1], level=level_title[0])
        else:
            current.text += line + "\n"
    doc.sections.append(current)
    if not any(s.body for s in doc.sections):
        doc.sections = [Section(title="Документ", level=1, text=text)]
    return doc


def normalize(s: str) -> str:
    """Нормализация для поиска цитат: пробелы, ё, кавычки, дефисы, регистр."""
    s = s.lower().replace("ё", "е")
    s = re.sub(r"[«»\"'`]", "", s)
    s = re.sub(r"[–—]", "-", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()

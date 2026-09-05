from __future__ import annotations

import re
from collections import defaultdict

from ..document import Document
from ..schema import Finding

# Гипотеза H1 (IDEAS.md): обезличивание = бесплатная разметка сущностей.
ENT = re.compile(r"\b(?:TABLE|FIELD|TOPIC|SCHEMA|DAG)_[A-Z0-9_]+\b")
FIELD = re.compile(r"^FIELD_[A-Z0-9_]+$")
SEC_REF = re.compile(r"раздел[ае]?\s+(\d+)", re.IGNORECASE)
# Ссылка на раздел по имени в кавычках: «в разделе „Оркестрация“», «см. раздел «Регламент»»
SEC_NAME_REF = re.compile(r"раздел[ае]?\s+[«\"„]([^»\"“]{2,60})[»\"“]", re.IGNORECASE)


def _cells(line: str) -> list[str] | None:
    if not line.lstrip().startswith("|"):
        return None
    return [c.strip() for c in line.strip().strip("|").split("|")]


def run(doc: Document) -> list[Finding]:
    """Детерминированный граф документа: поля-фантомы (используются, но не описаны),
    дрейф имён таблиц (анаграммы по '_'-токенам), битые ссылки на разделы.
    Ноль LLM-вызовов, precision по построению ~1.0."""
    lines = doc.raw.splitlines()
    mentions: dict[str, list[int]] = defaultdict(list)
    field_defs: set[str] = set()

    for i, line in enumerate(lines):
        for m in ENT.finditer(line):
            mentions[m.group(0)].append(i)
        cells = _cells(line)
        if cells and len(cells) >= 3:
            # Строка таблицы структуры: поле в первой или второй колонке
            # (вторая — когда есть колонка «Номер», как в doc3).
            for c in cells[:2]:
                if FIELD.fullmatch(c):
                    field_defs.add(c)

    findings: list[Finding] = []

    # 1. Поля-фантомы: используются, но не описаны ни в одной структуре.
    if field_defs:  # без единой структуры проверка не имеет смысла
        phantom = sorted(e for e in mentions
                         if e.startswith("FIELD_") and e not in field_defs)
        if phantom:
            first_line = lines[min(mentions[p][0] for p in phantom)].strip()
            findings.append(Finding(
                category="graph:undefined_field",
                severity="critical",
                quote=first_line[:200],
                why=("Поля используются в алгоритме/правилах, но не описаны ни в одной "
                     "структуре данных документа: " + ", ".join(phantom) + "."),
                ask="Добавь эти поля в структуры соответствующих таблиц-источников "
                    "или укажи документ, где они определены.",
                source_pass="doc_graph",
            ))

    # 2. Дрейф имён таблиц: два имени из одних и тех же '_'-токенов в разном порядке.
    groups: dict[tuple, list[str]] = defaultdict(list)
    for ent in mentions:
        if ent.startswith("TABLE_"):
            groups[tuple(sorted(ent.split("_")))].append(ent)
    for names in groups.values():
        if len(names) > 1:
            names.sort(key=lambda t: len(mentions[t]))
            rare, common = names[0], names[-1]
            findings.append(Finding(
                category="graph:name_drift",
                severity="high",
                quote=lines[mentions[rare][0]].strip()[:200],
                why=(f"«{rare}» упоминается {len(mentions[rare])} раз(а), "
                     f"«{common}» — {len(mentions[common])}; имена состоят из одних "
                     "и тех же частей — вероятно, одна таблица под двумя именами."),
                ask=f"Приведи имя к одному варианту: {common} или {rare}.",
                source_pass="doc_graph",
            ))

    # 3. Битые ссылки на разделы.
    secnums = {int(m.group(1)) for s in doc.sections
               if (m := re.match(r"(\d+)", s.title))}
    for i, line in enumerate(lines):
        for m in SEC_REF.finditer(line):
            n = int(m.group(1))
            broken = (n not in secnums) if secnums else (n > len(doc.sections))
            if broken:
                findings.append(Finding(
                    category="graph:broken_ref",
                    severity="high",
                    quote=line.strip()[:200],
                    why=(f"Ссылка на раздел {n}, которого нет в документе"
                         + (f" (есть номера: {sorted(secnums)})." if secnums else ".")),
                    ask=f"Исправь номер раздела или добавь раздел {n}.",
                    source_pass="doc_graph",
                ))

    # 3b. Ссылки на разделы по имени: «в разделе „Оркестрация“» — заголовка с таким именем нет
    # (EXP-19: HRD-REFNAME брала только GPT; для графа это детерминированная проверка).
    from ..document import normalize
    titles_norm = [normalize(s.title) for s in doc.sections]
    reported: set[str] = set()
    for line in lines:
        for m in SEC_NAME_REF.finditer(line):
            name = m.group(1).strip()
            key = normalize(name)
            if not key or key in reported:
                continue
            if any(key in t or t in key for t in titles_norm):
                continue
            reported.add(key)
            findings.append(Finding(
                category="graph:broken_ref",
                severity="high",
                quote=line.strip()[:200],
                why=f"Ссылка на раздел «{name}», которого нет в документе (такого заголовка нет).",
                ask=f"Добавь раздел «{name}» или исправь ссылку на существующий раздел.",
                source_pass="doc_graph",
            ))
    return findings

from __future__ import annotations

import json
from collections import Counter

from .pipeline import ReviewResult
from .schema import SEVERITY_RU, Finding


def verdict(result: ReviewResult) -> tuple[str, str]:
    sev = Counter(f.severity for f in result.findings)
    if sev["critical"]:
        return "🔴", "Документ не готов к передаче в разработку"
    if sev["high"] or sev["medium"]:
        return "🟡", "Документ требует доработки перед передачей"
    return "🟢", "Существенных проблем не найдено"


def _finding_md(f: Finding) -> str:
    lines = [f"**[{f.fid}] {SEVERITY_RU[f.severity]} · {f.category}**"
             + (f" · score {f.score:.0f}" if f.score is not None else "")]
    if f.quote:
        lines.append(f"> {f.quote}")
    if f.missing and not f.quote:
        lines.append("_Информация в документе отсутствует._")
    lines.append(f"**Почему:** {f.why}")
    if f.ask:
        lines.append(f"**Что уточнить:** {f.ask}")
    if f.suggested_fix:
        lines.append(f"**Вариант формулировки:** {f.suggested_fix}")
    return "\n\n".join(lines)


def to_markdown(result: ReviewResult, doc_name: str = "ТЗ") -> str:
    light, verdict_text = verdict(result)
    sev = Counter(f.severity for f in result.findings)
    parts = [
        f"# Ревью: {doc_name}",
        f"## {light} {verdict_text}",
        "| Критично | Важно | Средне | Стиль |\n"
        "|---|---|---|---|\n"
        f"| {sev['critical']} | {sev['high']} | {sev['medium']} | {sev['advisory']} |",
    ]

    if result.statuses:
        ok = sum(1 for s in result.statuses.values() if s == "OK")
        total = len(result.statuses)
        parts.append(f"**Покрытие чеклиста полноты:** {ok}/{total} слотов закрыто "
                     f"({100 * ok // max(total, 1)}%). Anchoring rate цитат: "
                     f"{result.anchoring:.0%}.")

    main = [f for f in result.findings if f.severity != "advisory"]
    advisory = [f for f in result.findings if f.severity == "advisory"]

    if main:
        parts.append("## Находки")
        by_section: dict[str, list[Finding]] = {}
        for f in main:
            by_section.setdefault(f.section or "(документ в целом)", []).append(f)
        for section, items in by_section.items():
            parts.append(f"### {section}")
            parts.extend(_finding_md(f) + "\n\n---" for f in items)
    else:
        parts.append("## Находки\n\nЗамечаний уровня «средне» и выше нет. "
                     "Молчание — валидный результат проверки.")

    if advisory:
        parts.append("## Стилистика (не блокирует)")
        parts.extend(f"- **{f.category}** ({f.section}): {f.why}" for f in advisory)

    if result.rejected:
        parts.append(f"<details><summary>Отсеяно критиком: {len(result.rejected)}"
                     "</summary>\n\n"
                     + "\n".join(f"- [{f.fid}] score {f.score:.0f}: {f.why[:120]}"
                                 for f in result.rejected)
                     + "\n\n</details>")
    if result.dropped:
        parts.append(f"_Отброшено на верификации цитат (галлюцинированный якорь): "
                     f"{len(result.dropped)}._")

    parts.append(f"_Проходы: {', '.join(result.passes_run)}._")
    return "\n\n".join(parts) + "\n"


def to_json(result: ReviewResult) -> str:
    return json.dumps({
        "verdict": verdict(result)[1],
        "anchoring_rate": result.anchoring,
        "checklist_statuses": result.statuses,
        "findings": [f.model_dump() for f in result.findings],
        "rejected": [f.model_dump() for f in result.rejected],
        "dropped": [f.model_dump() for f in result.dropped],
    }, ensure_ascii=False, indent=2)

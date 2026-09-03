from __future__ import annotations

import json

from ..llm import LLM
from ..schema import SEVERITY_ORDER, Finding
from . import load_prompt

DEFAULT_THRESHOLD = 4.0  # по свипу 2026-09-03: recall держится, мусорный хвост −40%
DETERMINISTIC_PASSES = frozenset({"deterministic", "doc_graph"})


def run(findings: list[Finding], doc_text: str, llm: LLM,
        threshold: float = DEFAULT_THRESHOLD,
        protected: frozenset[str] = frozenset()) -> tuple[list[Finding], list[Finding]]:
    """Критик-ранжировщик. Ключевое (Greptile vs PR-Agent): судья видит ВСЕ находки
    сразу и оценивает сравнительно, а не каждую в изоляции.
    Детерминированные находки критику не отдаём — их precision и так ~100%.
    `protected` — категории, которые критик не вправе опустить ниже порога
    (официальные требования кейсодателя: EXP-13 показал score 0–2 на верных
    MISSING по Data Catalog / кластеру Kafka / типовым фильтрам); дедупликация
    на них действует по-прежнему.

    Возвращает (kept, rejected)."""
    # Детерминированные проходы (regex-слой и граф сущностей) критику не отдаём:
    # их precision ~1.0 по построению, а критик резал graph:undefined_field
    # (EXP-14: OFF-HIST найден графом и потерян на v2g).
    llm_findings = [f for f in findings if f.source_pass not in DETERMINISTIC_PASSES]
    det_findings = [f for f in findings if f.source_pass in DETERMINISTIC_PASSES]
    if not llm_findings:
        return findings, []

    payload = json.dumps(
        [f.model_dump(include={"fid", "category", "severity", "section",
                               "quote", "missing", "why", "ask"})
         for f in llm_findings],
        ensure_ascii=False, indent=1,
    )
    prompt = load_prompt("critic", document=doc_text, findings=payload)
    raw = llm.chat_json(system="Ты возвращаешь только валидный JSON.", user=prompt)

    scores = {s.get("fid"): float(s.get("score", 5)) for s in raw.get("scores", [])}
    drop_ids: set[str] = set()
    for group in raw.get("duplicates", []):
        if len(group) > 1:
            keep = max(group, key=lambda fid: scores.get(fid, 0))
            drop_ids.update(fid for fid in group if fid != keep)

    kept, rejected = [], []
    for f in llm_findings:
        f.score = scores.get(f.fid, 5.0)
        if f.category in protected and f.fid not in drop_ids:
            f.score = max(f.score, threshold)  # пол: требование кейсодателя не режется
            kept.append(f)
            continue
        if f.fid in drop_ids or f.score < threshold:
            rejected.append(f)
        else:
            kept.append(f)

    result = det_findings + kept
    result.sort(key=lambda f: (SEVERITY_ORDER.get(f.severity, 9), -(f.score or 0.0)))
    return result, rejected

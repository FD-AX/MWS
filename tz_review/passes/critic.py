from __future__ import annotations

import json

from ..llm import LLM
from ..schema import SEVERITY_ORDER, Finding
from . import load_prompt

DEFAULT_THRESHOLD = 3.0


def run(findings: list[Finding], doc_text: str, llm: LLM,
        threshold: float = DEFAULT_THRESHOLD) -> tuple[list[Finding], list[Finding]]:
    """Критик-ранжировщик. Ключевое (Greptile vs PR-Agent): судья видит ВСЕ находки
    сразу и оценивает сравнительно, а не каждую в изоляции.
    Детерминированные находки критику не отдаём — их precision и так ~100%.

    Возвращает (kept, rejected)."""
    llm_findings = [f for f in findings if f.source_pass != "deterministic"]
    det_findings = [f for f in findings if f.source_pass == "deterministic"]
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
        if f.fid in drop_ids or f.score < threshold:
            rejected.append(f)
        else:
            kept.append(f)

    result = det_findings + kept
    result.sort(key=lambda f: (SEVERITY_ORDER.get(f.severity, 9), -(f.score or 0.0)))
    return result, rejected

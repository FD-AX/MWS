from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import document as docmod
from .passes import (baseline, checklist, critic, deterministic, developer_sim,
                     document_level, uncertainty)
from .schema import Finding
from .verify import anchoring_rate, mark_only, verify_findings


@dataclass
class ReviewResult:
    findings: list[Finding] = field(default_factory=list)
    rejected: list[Finding] = field(default_factory=list)   # отсеяно критиком
    dropped: list[Finding] = field(default_factory=list)    # провалили верификацию цитат
    statuses: dict[str, str] = field(default_factory=dict)  # слоты чеклиста
    anchoring: float = 1.0
    passes_run: list[str] = field(default_factory=list)


def _assign_ids(findings: list[Finding]) -> None:
    for i, f in enumerate(findings, 1):
        f.fid = f"F{i:03d}"


def review(text: str, rubric: dict[str, Any], llm=None, *,
           use_entropy: bool = False,
           use_baseline: bool = False,
           critic_threshold: float = critic.DEFAULT_THRESHOLD) -> ReviewResult:
    """Полный конвейер: детерминированный слой -> чеклист -> документ-уровень ->
    персона разработчика -> [semantic entropy] -> верификация цитат -> критик.

    use_baseline=True — режим V0b: один сильный вызов вместо конвейера; цитаты
    верифицируются, но не отбрасываются (см. METRICS.md)."""
    doc = docmod.parse(text)
    result = ReviewResult()

    if use_baseline:
        if llm is None:
            raise ValueError("--baseline требует LLM (заполни .env)")
        marked = mark_only(baseline.run(text, llm), doc)
        marked.sort(key=lambda f: f.sort_key())
        _assign_ids(marked)
        quoted = [f for f in marked if not f.missing]
        result.anchoring = (sum(1 for f in quoted if f.verified) / len(quoted)) if quoted else 1.0
        result.findings = marked
        result.passes_run = ["baseline"]
        return result

    findings: list[Finding] = []

    findings += deterministic.run(doc, rubric)
    result.passes_run.append("deterministic")

    if llm is not None:
        cl_findings, statuses = checklist.run(text, rubric, llm)
        findings += cl_findings
        result.statuses = statuses
        result.passes_run.append("checklist")

        findings += document_level.run(text, llm)
        result.passes_run.append("document_level")

        findings += developer_sim.run(text, llm)
        result.passes_run.append("developer_sim")

        if use_entropy:
            findings += uncertainty.run(text, rubric, statuses, llm)
            result.passes_run.append("uncertainty")

    verified, dropped = verify_findings(findings, doc)
    result.dropped = dropped
    result.anchoring = anchoring_rate(verified, dropped)
    _assign_ids(verified)

    if llm is not None and verified:
        kept, rejected = critic.run(verified, text, llm, threshold=critic_threshold)
        result.findings = kept
        result.rejected = rejected
        result.passes_run.append("critic")
    else:
        verified.sort(key=lambda f: f.sort_key())
        result.findings = verified

    return result

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import document as docmod
from .passes import (baseline, checklist, critic, deterministic, developer_sim,
                     doc_graph, document_level, spec_compile, uncertainty,
                     uncertainty_lp)

DEFAULT_LLM_PASSES = frozenset({"checklist", "document_level", "developer_sim"})
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
           use_graph: bool = False,
           llm_passes: frozenset[str] | None = None,
           baseline_prompt: str = "baseline",
           llm_cheap=None,
           use_lp: bool = False,
           llm_lp=None,
           critic_threshold: float = critic.DEFAULT_THRESHOLD,
           progress=None) -> ReviewResult:
    """Полный конвейер: детерминированный слой -> чеклист -> документ-уровень ->
    персона разработчика -> [semantic entropy] -> верификация цитат -> критик.

    use_baseline=True — режим V0b: один сильный вызов вместо конвейера; цитаты
    верифицируются, но не отбрасываются (см. METRICS.md).
    progress(stage, fraction) — необязательный колбэк хода ревью (UI/воркер)."""
    doc = docmod.parse(text)
    result = ReviewResult()

    findings: list[Finding] = []

    def _p(stage: str, frac: float, **info) -> None:
        if progress is not None:
            try:
                progress(stage, max(0.0, min(1.0, frac)),
                         {"candidates": len(findings), **info})
            except Exception:  # noqa: BLE001 — прогресс не должен ронять ревью
                pass

    if use_baseline:
        if llm is None:
            raise ValueError("--baseline требует LLM (заполни .env)")
        marked = mark_only(baseline.run(text, llm, baseline_prompt), doc)
        marked.sort(key=lambda f: f.sort_key())
        _assign_ids(marked)
        quoted = [f for f in marked if not f.missing]
        result.anchoring = (sum(1 for f in quoted if f.verified) / len(quoted)) if quoted else 1.0
        result.findings = marked
        result.passes_run = ["baseline"]
        return result

    _p("deterministic", 0.01)
    findings += deterministic.run(doc, rubric)
    result.passes_run.append("deterministic")
    _p("deterministic", 0.03)

    if use_graph:
        findings += doc_graph.run(doc)
        result.passes_run.append("doc_graph")
        _p("doc_graph", 0.05)

    lp = DEFAULT_LLM_PASSES if llm_passes is None else llm_passes
    if llm is not None:
        if "checklist" in lp:
            _p("checklist", 0.05)
            cl_findings, statuses = checklist.run(
                text, rubric, llm,
                on_batch=lambda i, n: _p("checklist", 0.05 + 0.45 * i / max(n, 1),
                                         batch=i + 1, batches=n))
            findings += cl_findings
            result.statuses = statuses
            result.passes_run.append("checklist")
            _p("checklist", 0.50)

        if "document_level" in lp:
            _p("document_level", 0.52)
            findings += document_level.run(text, llm)
            result.passes_run.append("document_level")
            _p("document_level", 0.65)

        if "developer_sim" in lp:
            _p("developer_sim", 0.66)
            findings += developer_sim.run(text, llm)
            result.passes_run.append("developer_sim")
            _p("developer_sim", 0.80)

        if "compile" in lp:
            _p("spec_compile", 0.81)
            findings += spec_compile.run(text, llm)
            result.passes_run.append("spec_compile")
            _p("spec_compile", 0.85)

        if use_entropy and result.statuses:
            _p("uncertainty", 0.86)
            findings += uncertainty.run(text, rubric, result.statuses, llm_cheap or llm)
            result.passes_run.append("uncertainty")
            _p("uncertainty", 0.90)

        if use_lp and result.statuses and llm_lp is not None:
            _p("uncertainty_lp", 0.90)
            findings += uncertainty_lp.run(text, rubric, result.statuses, llm_lp)
            result.passes_run.append("uncertainty_lp")
            _p("uncertainty_lp", 0.92)

    _p("verify", 0.93)
    verified, dropped = verify_findings(findings, doc)
    result.dropped = dropped
    result.anchoring = anchoring_rate(verified, dropped)
    _p("critic", 0.94)
    _assign_ids(verified)

    if llm is not None and verified:
        protected = frozenset(f"checklist:{q['id']}" for q in rubric.get("checklist", [])
                              if q.get("official"))
        kept, rejected = critic.run(verified, text, llm, threshold=critic_threshold,
                                    protected=protected)
        result.findings = kept
        result.rejected = rejected
        result.passes_run.append("critic")
    else:
        verified.sort(key=lambda f: f.sort_key())
        result.findings = verified

    _p("done", 1.0)
    return result

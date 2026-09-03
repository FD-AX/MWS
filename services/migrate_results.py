"""Разовая миграция файловых результатов (/data/results/*.json) в Postgres.

    docker compose -f deploy/docker-compose.yml exec api python -m services.migrate_results
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services import db  # noqa: E402
from services.common import RESULTS_DIR, doc_hash  # noqa: E402


def main() -> int:
    db.init()
    n = 0
    for p in sorted(RESULTS_DIR.glob("*.json")):
        if p.name == "index.json":
            continue
        j = json.loads(p.read_text(encoding="utf-8"))
        job_id = j.get("job_id")
        if not job_id or db.get_review(job_id, with_result=False):
            continue
        src = RESULTS_DIR / f"{job_id}.source.md"
        md = src.read_text(encoding="utf-8") if src.exists() else ""
        dh = j.get("doc_hash") or doc_hash(md)
        doc_id = db.upsert_document(dh, j.get("filename") or "текст", j.get("kind") or "text",
                                    j.get("chars") or len(md), md)
        db.create_review(job_id, doc_id, j.get("config_hash") or "legacy")
        rep = RESULTS_DIR / f"{job_id}.report.md"
        res = j.get("result")
        usage = j.get("llm_usage") or {}
        if j.get("status") == "done" and res:
            db.save_result(job_id, result=res, report_md=rep.read_text(encoding="utf-8") if rep.exists() else "",
                           statuses=res.get("checklist_statuses", {}), findings=res.get("findings", []),
                           duration_s=j.get("duration_s"), llm_calls=usage.get("calls"),
                           prompt_tokens=usage.get("prompt_tokens"), completion_tokens=usage.get("completion_tokens"),
                           model=j.get("model"), backend=j.get("backend"),
                           verdict_light=(j.get("verdict") or {}).get("light"),
                           verdict_text=(j.get("verdict") or {}).get("text"),
                           anchoring=res.get("anchoring_rate"), cached_from=j.get("cached_from"))
        else:
            db.update_review(job_id, status=j.get("status") or "failed", error=j.get("error"))
        if j.get("created_at"):
            db.update_review(job_id, started_at=j.get("started_at") or j["created_at"])
        n += 1
        print("migrated", job_id, j.get("status"), j.get("filename"))
    print(f"done: {n} заданий; {db.stats()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

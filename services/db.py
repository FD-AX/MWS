"""История проверок в Postgres: документы (с версиями по имени файла), задания ревью,
находки, статусы чеклиста, обратная связь аналитика. Источник истины для API и воркера.

Схема создаётся при старте (CREATE TABLE IF NOT EXISTS) — миграции не нужны на этом этапе.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

DSN = os.environ.get("TZR_PG_DSN", "postgresql://tzr:tzr@postgres:5432/tzr")

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
  id            BIGSERIAL PRIMARY KEY,
  doc_hash      TEXT NOT NULL UNIQUE,
  filename      TEXT,
  kind          TEXT,
  chars         INT,
  normalized_md TEXT NOT NULL,
  parent_id     BIGINT REFERENCES documents(id),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS reviews (
  job_id            TEXT PRIMARY KEY,
  document_id       BIGINT NOT NULL REFERENCES documents(id),
  config_hash       TEXT NOT NULL,
  status            TEXT NOT NULL,
  model             TEXT,
  backend           TEXT,
  duration_s        REAL,
  llm_calls         INT,
  prompt_tokens     INT,
  completion_tokens INT,
  verdict_light     TEXT,
  verdict_text      TEXT,
  anchoring         REAL,
  progress          JSONB,
  error             TEXT,
  cached_from       TEXT,
  result            JSONB,
  report_md         TEXT,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  started_at        TIMESTAMPTZ,
  finished_at       TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS reviews_created_idx ON reviews (created_at DESC);
CREATE INDEX IF NOT EXISTS reviews_doc_cfg_idx ON reviews (document_id, config_hash);
CREATE TABLE IF NOT EXISTS findings (
  id          BIGSERIAL PRIMARY KEY,
  job_id      TEXT NOT NULL REFERENCES reviews(job_id) ON DELETE CASCADE,
  fid         TEXT,
  category    TEXT,
  severity    TEXT,
  section     TEXT,
  quote       TEXT,
  why         TEXT,
  ask         TEXT,
  score       REAL,
  source_pass TEXT,
  verified    BOOLEAN,
  missing     BOOLEAN
);
CREATE INDEX IF NOT EXISTS findings_job_idx ON findings (job_id);
CREATE INDEX IF NOT EXISTS findings_cat_idx ON findings (category, severity);
CREATE TABLE IF NOT EXISTS checklist_status (
  job_id TEXT NOT NULL REFERENCES reviews(job_id) ON DELETE CASCADE,
  slot   TEXT NOT NULL,
  status TEXT NOT NULL,
  PRIMARY KEY (job_id, slot)
);
CREATE TABLE IF NOT EXISTS feedback (
  id         BIGSERIAL PRIMARY KEY,
  finding_id BIGINT NOT NULL REFERENCES findings(id) ON DELETE CASCADE,
  author     TEXT,
  vote       SMALLINT NOT NULL,
  comment    TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def connect(retries: int = 30, delay: float = 2.0):
    last: Exception | None = None
    for _ in range(retries):
        try:
            return psycopg.connect(DSN, row_factory=dict_row, autocommit=True)
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(delay)
    raise RuntimeError(f"Postgres недоступен: {last}")


def init() -> None:
    with connect() as c:
        c.execute(SCHEMA)


def _ts(v) -> float | None:
    return v.timestamp() if v is not None else None


# ---------- документы ----------

def upsert_document(doc_hash: str, filename: str | None, kind: str, chars: int, md: str) -> int:
    """Новый хэш с тем же именем файла = новая версия: parent_id → последняя версия по имени."""
    with connect() as c:
        row = c.execute("SELECT id FROM documents WHERE doc_hash = %s", (doc_hash,)).fetchone()
        if row:
            return row["id"]
        parent = None
        if filename:
            p = c.execute("SELECT id FROM documents WHERE filename = %s ORDER BY created_at DESC LIMIT 1",
                          (filename,)).fetchone()
            parent = p["id"] if p else None
        row = c.execute(
            "INSERT INTO documents (doc_hash, filename, kind, chars, normalized_md, parent_id) "
            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (doc_hash, filename, kind, chars, md, parent)).fetchone()
        return row["id"]


def list_documents(limit: int = 50) -> list[dict]:
    with connect() as c:
        rows = c.execute("""
            SELECT d.id, d.doc_hash, d.filename, d.kind, d.chars, d.parent_id, d.created_at,
                   COUNT(r.job_id) AS reviews,
                   MAX(r.finished_at) AS last_review_at
            FROM documents d LEFT JOIN reviews r ON r.document_id = d.id
            GROUP BY d.id ORDER BY d.created_at DESC LIMIT %s""", (limit,)).fetchall()
    for r in rows:
        r["created_at"] = _ts(r["created_at"])
        r["last_review_at"] = _ts(r["last_review_at"])
    return rows


def document_history(doc_hash: str) -> dict:
    """Версии документа (цепочка по имени файла) и все ревью каждой версии."""
    with connect() as c:
        d = c.execute("SELECT * FROM documents WHERE doc_hash = %s", (doc_hash,)).fetchone()
        if not d:
            return {}
        versions = c.execute(
            "SELECT id, doc_hash, filename, chars, parent_id, created_at FROM documents "
            "WHERE filename = %s OR id = %s ORDER BY created_at", (d["filename"], d["id"])).fetchall()
        ids = [v["id"] for v in versions]
        reviews = c.execute("""
            SELECT job_id, document_id, status, model, backend, duration_s, llm_calls,
                   verdict_light, verdict_text, anchoring, cached_from, created_at, finished_at,
                   (SELECT COUNT(*) FROM findings f WHERE f.job_id = r.job_id) AS findings
            FROM reviews r WHERE document_id = ANY(%s) ORDER BY created_at""", (ids,)).fetchall()
    for v in versions:
        v["created_at"] = _ts(v["created_at"])
        v["reviews"] = [r for r in reviews if r["document_id"] == v["id"]]
    for r in reviews:
        r["created_at"] = _ts(r["created_at"])
        r["finished_at"] = _ts(r["finished_at"])
    return {"document": {"id": d["id"], "doc_hash": d["doc_hash"], "filename": d["filename"]},
            "versions": versions}


# ---------- ревью ----------

def create_review(job_id: str, document_id: int, config_hash: str) -> None:
    with connect() as c:
        c.execute("INSERT INTO reviews (job_id, document_id, config_hash, status) VALUES (%s, %s, %s, 'queued')",
                  (job_id, document_id, config_hash))


def find_done_review(document_id: int, config_hash: str) -> str | None:
    with connect() as c:
        row = c.execute(
            "SELECT job_id FROM reviews WHERE document_id = %s AND config_hash = %s AND status = 'done' "
            "AND result IS NOT NULL ORDER BY finished_at DESC LIMIT 1", (document_id, config_hash)).fetchone()
    return row["job_id"] if row else None


_JSON_COLS = {"progress", "result"}
_TS_COLS = {"started_at", "finished_at"}


def update_review(job_id: str, **fields: Any) -> None:
    if not fields:
        return
    sets, vals = [], []
    for k, v in fields.items():
        if k in _JSON_COLS:
            v = Jsonb(v)
        elif k in _TS_COLS and isinstance(v, (int, float)):
            sets.append(f"{k} = to_timestamp(%s)")
            vals.append(v)
            continue
        sets.append(f"{k} = %s")
        vals.append(v)
    vals.append(job_id)
    with connect() as c:
        c.execute(f"UPDATE reviews SET {', '.join(sets)} WHERE job_id = %s", vals)


def save_result(job_id: str, *, result: dict, report_md: str, statuses: dict[str, str],
                findings: list[dict], **fields: Any) -> None:
    """Результат целиком в одной транзакции: шапка ревью + находки + статусы слотов."""
    with connect() as c, c.transaction():
        update_sets = ["status = 'done'", "result = %s", "report_md = %s", "finished_at = now()"]
        vals: list[Any] = [Jsonb(result), report_md]
        for k, v in fields.items():
            update_sets.append(f"{k} = %s")
            vals.append(v)
        vals.append(job_id)
        c.execute(f"UPDATE reviews SET {', '.join(update_sets)} WHERE job_id = %s", vals)
        c.execute("DELETE FROM findings WHERE job_id = %s", (job_id,))
        c.execute("DELETE FROM checklist_status WHERE job_id = %s", (job_id,))
        for f in findings:
            c.execute(
                "INSERT INTO findings (job_id, fid, category, severity, section, quote, why, ask, score, "
                "source_pass, verified, missing) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (job_id, f.get("fid"), f.get("category"), f.get("severity"), f.get("section"),
                 f.get("quote"), f.get("why"), f.get("ask"), f.get("score"), f.get("source_pass"),
                 f.get("verified"), f.get("missing")))
        for slot, st in statuses.items():
            c.execute("INSERT INTO checklist_status (job_id, slot, status) VALUES (%s, %s, %s)",
                      (job_id, slot, st))


def get_review(job_id: str, with_result: bool = True) -> dict | None:
    cols = "r.*, d.doc_hash, d.filename, d.kind, d.chars" if with_result else \
        "r.job_id, r.status, r.progress, r.model, r.backend, r.duration_s, r.verdict_light, r.verdict_text, " \
        "r.created_at, r.started_at, r.finished_at, r.cached_from, r.error, d.doc_hash, d.filename"
    with connect() as c:
        r = c.execute(f"SELECT {cols} FROM reviews r JOIN documents d ON d.id = r.document_id "
                      "WHERE r.job_id = %s", (job_id,)).fetchone()
        if not r:
            return None
        if with_result and r.get("result"):
            fids = c.execute("SELECT id, fid FROM findings WHERE job_id = %s", (job_id,)).fetchall()
            id_by_fid = {x["fid"]: x["id"] for x in fids}
            for f in r["result"].get("findings", []):
                f["db_id"] = id_by_fid.get(f.get("fid"))
    out = dict(r)
    for k in ("created_at", "started_at", "finished_at"):
        out[k] = _ts(out.get(k))
    out["verdict"] = ({"light": out.pop("verdict_light", None), "text": out.pop("verdict_text", None)}
                      if out.get("verdict_light") or out.get("verdict_text") else None)
    out.pop("report_md", None)
    return out


def get_report(job_id: str) -> str | None:
    with connect() as c:
        r = c.execute("SELECT report_md FROM reviews WHERE job_id = %s", (job_id,)).fetchone()
    return r["report_md"] if r else None


def list_reviews(limit: int = 20) -> list[dict]:
    with connect() as c:
        rows = c.execute("""
            SELECT r.job_id, r.status, r.model, r.duration_s, r.verdict_light, r.verdict_text,
                   r.cached_from, r.created_at, r.finished_at, d.filename, d.doc_hash,
                   (SELECT COUNT(*) FROM findings f WHERE f.job_id = r.job_id) AS findings
            FROM reviews r JOIN documents d ON d.id = r.document_id
            ORDER BY r.created_at DESC LIMIT %s""", (limit,)).fetchall()
    out = []
    for r in rows:
        o = dict(r)
        o["created_at"] = _ts(o["created_at"])
        o["finished_at"] = _ts(o["finished_at"])
        o["verdict"] = {"light": o.pop("verdict_light"), "text": o.pop("verdict_text")}
        out.append(o)
    return out


def add_feedback(finding_id: int, vote: int, author: str | None, comment: str | None) -> int:
    with connect() as c:
        row = c.execute("INSERT INTO feedback (finding_id, author, vote, comment) VALUES (%s, %s, %s, %s) RETURNING id",
                        (finding_id, author, vote, comment)).fetchone()
    return row["id"]


def stats() -> dict:
    with connect() as c:
        return {
            "documents": c.execute("SELECT COUNT(*) AS n FROM documents").fetchone()["n"],
            "reviews": c.execute("SELECT COUNT(*) AS n FROM reviews").fetchone()["n"],
            "findings": c.execute("SELECT COUNT(*) AS n FROM findings").fetchone()["n"],
            "feedback": c.execute("SELECT COUNT(*) AS n FROM feedback").fetchone()["n"],
        }

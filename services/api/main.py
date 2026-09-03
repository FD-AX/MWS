"""API ревью: принимает документ, ставит задание в очередь, отдаёт результат.

    POST /reviews            (multipart file | form text)  -> 202 {job_id, status, doc_hash}
    GET  /reviews/{job_id}                                  -> {status, ...результат}
    GET  /reviews/{job_id}/report.md                        -> markdown-отчёт
    GET  /healthz, GET /metrics
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path

import httpx
import pika
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from prometheus_client import Counter, make_asgi_app

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from services.common import (QUEUE, RESULTS_DIR, config_hash, connect, declare,  # noqa: E402
                             index_get, load_job, save_job)

DOCS_URL = os.environ.get("TZR_DOCS_URL", "http://docs:8081")

app = FastAPI(title="tz_review API", version="0.1")
app.mount("/metrics", make_asgi_app())
ACCEPTED = Counter("tzr_api_reviews_total", "Запросов на ревью", ["outcome"])


STATIC = Path(__file__).resolve().parent / "static"


@app.get("/", include_in_schema=False)
def index():
    """Минимальный UI: загрузка документа, статус, вердикт и находки, последние проверки."""
    return FileResponse(STATIC / "index.html")


@app.get("/healthz")
def healthz():
    return {"ok": True, "results_dir": str(RESULTS_DIR)}


@app.get("/reviews")
def list_reviews(limit: int = 20):
    """Последние задания (для UI): без результата, только шапка."""
    jobs = []
    for p in RESULTS_DIR.glob("*.json"):
        if p.name == "index.json" or p.name.endswith(".tmp"):
            continue
        try:
            j = json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        jobs.append({k: j.get(k) for k in ("job_id", "status", "filename", "created_at",
                                            "duration_s", "verdict", "model", "cached_from")})
    jobs.sort(key=lambda j: j.get("created_at") or 0, reverse=True)
    return jobs[:limit]


@app.post("/reviews", status_code=202)
async def create_review(file: UploadFile | None = File(None), text: str | None = Form(None)):
    if file is None and not text:
        raise HTTPException(400, "нужен file (md/txt/docx/pdf) или text")
    async with httpx.AsyncClient(timeout=120) as client:
        if file is not None:
            r = await client.post(f"{DOCS_URL}/normalize",
                                  files={"file": (file.filename, await file.read())})
        else:
            r = await client.post(f"{DOCS_URL}/normalize", data={"text": text})
    if r.status_code != 200:
        ACCEPTED.labels("docs_error").inc()
        raise HTTPException(502, f"docs: {r.text[:300]}")
    norm = r.json()

    chash = config_hash()
    cached = index_get(norm["doc_hash"], chash)
    if cached and (load_job(cached) or {}).get("status") == "done":
        ACCEPTED.labels("cached").inc()
        return {"job_id": cached, "status": "done", "cached": True, "doc_hash": norm["doc_hash"]}

    job_id = uuid.uuid4().hex[:12]
    job = {
        "job_id": job_id, "status": "queued", "doc_hash": norm["doc_hash"], "config_hash": chash,
        "filename": getattr(file, "filename", None), "kind": norm["kind"], "chars": norm["chars"],
        "sections": norm["sections"], "created_at": time.time(),
    }
    save_job(job)
    (RESULTS_DIR / f"{job_id}.source.md").write_text(norm["markdown"], encoding="utf-8")

    # Сообщение самодостаточно (текст внутри): воркер не зависит от общего тома.
    conn = connect()
    try:
        ch = conn.channel()
        declare(ch)
        ch.confirm_delivery()  # publisher confirms: брокер подтвердил запись на диск
        ch.basic_publish(
            exchange="", routing_key=QUEUE,
            body=json.dumps({"job_id": job_id, "doc_hash": norm["doc_hash"],
                             "config_hash": chash, "text": norm["markdown"]}).encode("utf-8"),
            properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"),
            mandatory=True,
        )
    finally:
        conn.close()
    ACCEPTED.labels("queued").inc()
    return {"job_id": job_id, "status": "queued", "doc_hash": norm["doc_hash"], "chars": norm["chars"]}


@app.get("/reviews/{job_id}")
def get_review(job_id: str):
    job = load_job(job_id)
    if job is None:
        raise HTTPException(404, "нет такого задания")
    return job


@app.get("/reviews/{job_id}/report.md", response_class=PlainTextResponse)
def get_report(job_id: str):
    p = RESULTS_DIR / f"{job_id}.report.md"
    if not p.exists():
        job = load_job(job_id)
        raise HTTPException(404 if job is None else 409,
                            "отчёта ещё нет" if job else "нет такого задания")
    return p.read_text(encoding="utf-8")

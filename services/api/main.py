"""API ревью: принимает документ, ставит задание в очередь, отдаёт результат и историю.

    GET  /                                  минимальный UI
    POST /reviews            (multipart file | form text)  -> 202 {job_id, status, doc_hash}
    GET  /reviews                           последние задания
    GET  /reviews/{job_id}                  статус / прогресс / результат
    GET  /reviews/{job_id}/report.md        markdown-отчёт
    GET  /documents                         документы и число проверок
    GET  /documents/{doc_hash}/history      версии документа и все их ревью
    POST /findings/{id}/feedback            👍/👎 аналитика по находке
    GET  /healthz, GET /metrics
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

import httpx
import pika
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from prometheus_client import Counter, make_asgi_app
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from services import db  # noqa: E402
from services.common import QUEUE, config_hash, connect, declare  # noqa: E402

DOCS_URL = os.environ.get("TZR_DOCS_URL", "http://docs:8081")
STATIC = Path(__file__).resolve().parent / "static"

app = FastAPI(title="tz_review API", version="0.2")
app.mount("/metrics", make_asgi_app())

# Отдельный фронтенд (другой origin) ходит в API напрямую — CORS открыт для демо;
# в контуре заказчика сузить до домена фронта (TZR_CORS_ORIGINS).
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.environ.get("TZR_CORS_ORIGINS", "*").split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)
ACCEPTED = Counter("tzr_api_reviews_total", "Запросов на ревью", ["outcome"])


@app.on_event("startup")
def _startup() -> None:
    db.init()


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/healthz")
def healthz():
    return {"ok": True, **db.stats()}


@app.post("/reviews", status_code=202)
async def create_review(file: UploadFile | None = File(None), text: str | None = Form(None)):
    if file is None and not (text and text.strip() and text.strip() != "string"):
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

    filename = getattr(file, "filename", None) or "текст"
    doc_id = db.upsert_document(norm["doc_hash"], filename, norm["kind"], norm["chars"], norm["markdown"])
    chash = config_hash()
    cached = db.find_done_review(doc_id, chash)
    if cached:
        ACCEPTED.labels("cached").inc()
        return {"job_id": cached, "status": "done", "cached": True, "doc_hash": norm["doc_hash"]}

    job_id = uuid.uuid4().hex[:12]
    db.create_review(job_id, doc_id, chash)

    conn = connect()
    try:
        ch = conn.channel()
        declare(ch)
        ch.confirm_delivery()  # publisher confirms: брокер подтвердил запись на диск
        ch.basic_publish(
            exchange="", routing_key=QUEUE,
            body=json.dumps({"job_id": job_id, "doc_hash": norm["doc_hash"], "document_id": doc_id,
                             "config_hash": chash, "filename": filename,
                             "text": norm["markdown"]}).encode("utf-8"),
            properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"),
            mandatory=True,
        )
    finally:
        conn.close()
    ACCEPTED.labels("queued").inc()
    return {"job_id": job_id, "status": "queued", "doc_hash": norm["doc_hash"], "chars": norm["chars"]}


@app.get("/reviews")
def list_reviews(limit: int = 20):
    return db.list_reviews(limit)


@app.get("/reviews/{job_id}")
def get_review(job_id: str):
    job = db.get_review(job_id)
    if job is None:
        raise HTTPException(404, "нет такого задания")
    return job


@app.get("/reviews/{job_id}/report.md", response_class=PlainTextResponse)
def get_report(job_id: str):
    md = db.get_report(job_id)
    if md is None:
        job = db.get_review(job_id, with_result=False)
        raise HTTPException(404 if job is None else 409,
                            "нет такого задания" if job is None else "отчёта ещё нет")
    return md


@app.get("/documents")
def list_documents(limit: int = 50):
    return db.list_documents(limit)


@app.get("/documents/{doc_hash}/text")
def document_text(doc_hash: str):
    """Нормализованный markdown документа (после docs-сервиса) — для вкладок «Текст»/«Структура» во фронте."""
    d = db.get_document_text(doc_hash)
    if not d:
        raise HTTPException(404, "нет такого документа")
    return {"doc_hash": d["doc_hash"], "filename": d["filename"], "kind": d["kind"],
            "chars": d["chars"], "markdown": d["normalized_md"]}


@app.get("/documents/{doc_hash}/history")
def document_history(doc_hash: str):
    h = db.document_history(doc_hash)
    if not h:
        raise HTTPException(404, "нет такого документа")
    return h


class Feedback(BaseModel):
    vote: int  # +1 полезно / -1 не полезно
    author: str | None = None
    comment: str | None = None


@app.post("/findings/{finding_id}/feedback", status_code=201)
def add_feedback(finding_id: int, fb: Feedback):
    if fb.vote not in (-1, 1):
        raise HTTPException(400, "vote = 1 или -1")
    try:
        fid = db.add_feedback(finding_id, fb.vote, fb.author, fb.comment)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(404, f"нет такой находки: {str(e)[:100]}") from e
    return {"id": fid}

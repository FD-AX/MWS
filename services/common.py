"""Общее для сервисов: очередь, каталог результатов, хэши документа и конфига."""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

RABBIT_URL = os.environ.get("TZR_RABBIT_URL", "amqp://guest:guest@rabbitmq:5672/%2F")
QUEUE = os.environ.get("TZR_QUEUE", "review.jobs")
DLQ = os.environ.get("TZR_DLQ", "review.dead")
RESULTS_DIR = Path(os.environ.get("TZR_RESULTS_DIR", "/data/results"))


def doc_hash(text: str) -> str:
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()[:16]


def config_hash() -> str:
    """Хэш конфигурации ревью: рубрика + промпты + модель/вариант. Один документ с одним
    конфигом = один результат (идемпотентность), новый промпт = новый результат."""
    h = hashlib.sha256()
    for p in sorted([ROOT / "tz_review" / "rubric.yaml", *(ROOT / "prompts").glob("*.md")]):
        h.update(p.read_bytes())
    for var in ("TZR_BACKEND", "TZR_MODEL", "OPENAI_MODEL", "TZR_LOGPROBS", "TZR_ENTROPY", "TZR_THRESHOLD"):
        h.update(f"{var}={os.environ.get(var, '')};".encode())
    return h.hexdigest()[:12]


def connect(retries: int = 30, delay: float = 2.0):
    """Подключение к RabbitMQ с ожиданием старта брокера (compose поднимает всё разом)."""
    import pika

    last: Exception | None = None
    for _ in range(retries):
        try:
            return pika.BlockingConnection(pika.URLParameters(RABBIT_URL))
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(delay)
    raise RuntimeError(f"RabbitMQ недоступен: {last}")


def declare(ch) -> None:
    """Очередь заданий durable + DLQ: сообщение, отвергнутое воркером (nack без requeue),
    уходит в review.dead, а не теряется."""
    ch.queue_declare(queue=DLQ, durable=True)
    ch.queue_declare(queue=QUEUE, durable=True, arguments={
        "x-dead-letter-exchange": "",
        "x-dead-letter-routing-key": DLQ,
    })


# --- реестр результатов (файловый; для прода — Postgres) ---

def job_path(job_id: str) -> Path:
    return RESULTS_DIR / f"{job_id}.json"


def load_job(job_id: str) -> dict | None:
    p = job_path(job_id)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def save_job(job: dict) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = job_path(job["job_id"]).with_suffix(".tmp")
    tmp.write_text(json.dumps(job, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(job_path(job["job_id"]))  # атомарная подмена: читатель не видит полузаписи


def update_job(job_id: str, **fields) -> dict:
    job = load_job(job_id) or {"job_id": job_id}
    job.update(fields)
    job["updated_at"] = time.time()
    save_job(job)
    return job


def _index_path() -> Path:
    return RESULTS_DIR / "index.json"


def index_get(dhash: str, chash: str) -> str | None:
    p = _index_path()
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8")).get(f"{dhash}:{chash}")


def index_put(dhash: str, chash: str, job_id: str) -> None:
    p = _index_path()
    idx = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    idx[f"{dhash}:{chash}"] = job_id
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)

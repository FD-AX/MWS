"""Воркер ревью: берёт задание из очереди, гонит конвейер tz_review, пишет результат,
подтверждает сообщение только после записи. Метрики — на :9100/metrics.

Семантика: prefetch=1; ревью идёт в отдельном потоке, а поток соединения продолжает
обслуживать heartbeat'ы (ревью на 7 минут иначе рвёт соединение и сообщение
доставляется повторно). Исключение → первый раз requeue, повторный сбой → DLQ
(review.dead). Идемпотентность: повторная доставка уже посчитанного задания
(потеря соединения на ack) — только ack, без пересчёта.
"""
from __future__ import annotations

import functools
import json
import os
import sys
import threading
import time
import traceback
from pathlib import Path

from prometheus_client import Counter, Gauge, Histogram, start_http_server

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from services.common import (QUEUE, RESULTS_DIR, connect, declare, index_put,  # noqa: E402
                             load_job, update_job)
from tz_review.config import openai_settings_or_die, settings_or_die  # noqa: E402
from tz_review.llm import LLM  # noqa: E402
from tz_review.pipeline import review  # noqa: E402
from tz_review.report import to_json, to_markdown, verdict  # noqa: E402
from tz_review.rubric import load_rubric  # noqa: E402

REVIEWS = Counter("tzr_worker_reviews_total", "Обработанных заданий", ["status"])
DURATION = Histogram("tzr_worker_review_seconds", "Длительность ревью одного документа, с",
                     buckets=(30, 60, 120, 180, 300, 600, 900, 1800))
FINDINGS = Counter("tzr_worker_findings_total", "Находок в отчётах", ["klass", "severity", "source_pass"])
SLOTS = Counter("tzr_worker_checklist_status_total", "Статусы слотов чеклиста", ["slot", "status"])
UNKNOWN = Gauge("tzr_worker_unknown_slots", "Слотов UNKNOWN в последнем ревью (алерт при > 0)")
LLM_CALLS = Counter("tzr_worker_llm_calls_total", "Вызовов LLM", ["backend", "model"])
LLM_TOKENS = Counter("tzr_worker_llm_tokens_total", "Токенов LLM", ["backend", "model", "kind"])
ANCHORING = Gauge("tzr_worker_anchoring_rate", "Доля верифицированных цитат в последнем ревью")
INFLIGHT = Gauge("tzr_worker_inflight", "Заданий в работе")

BACKEND = os.environ.get("TZR_BACKEND", "pod")
THRESHOLD = float(os.environ.get("TZR_THRESHOLD", "4.0"))
USE_LP = os.environ.get("TZR_LOGPROBS", "0") == "1"       # логит-зонд (vLLM/gpt-4.1: да; ollama: нет)
USE_ENTROPY = os.environ.get("TZR_ENTROPY", "0") == "1"   # semantic entropy (дорого)


def build_llm() -> tuple[LLM, str]:
    cfg = openai_settings_or_die() if BACKEND == "openai" else settings_or_die()
    return LLM(cfg), cfg.model


def _snapshot(llm: LLM) -> dict:
    return dict(getattr(llm, "stats", {}) or {})


def _account(llm: LLM, model: str, before: dict) -> dict:
    after = _snapshot(llm)
    delta = {k: after.get(k, 0) - before.get(k, 0) for k in ("calls", "prompt_tokens", "completion_tokens")}
    LLM_CALLS.labels(BACKEND, model).inc(delta["calls"])
    LLM_TOKENS.labels(BACKEND, model, "prompt").inc(delta["prompt_tokens"])
    LLM_TOKENS.labels(BACKEND, model, "completion").inc(delta["completion_tokens"])
    return delta


def process(conn, ch, tag: int, redelivered: bool, body: bytes, *,
            llm: LLM, model: str, rubric: dict) -> None:
    """Рабочий поток: считает ревью и планирует ack/nack в поток соединения."""
    ack = functools.partial(conn.add_callback_threadsafe, lambda: ch.basic_ack(tag))

    def nack(requeue: bool) -> None:
        conn.add_callback_threadsafe(lambda: ch.basic_nack(tag, requeue=requeue))

    msg = json.loads(body.decode("utf-8"))
    job_id = msg["job_id"]
    prior = load_job(job_id) or {}
    if prior.get("result"):
        # Уже посчитано (повторная доставка после потери соединения на ack) — не пересчитываем.
        update_job(job_id, status="done")
        index_put(msg.get("doc_hash", ""), msg.get("config_hash", ""), job_id)
        REVIEWS.labels("dup_ack").inc()
        print(f"= {job_id}: повторная доставка, результат уже есть — ack", flush=True)
        ack()
        return

    text = msg.get("text") or (RESULTS_DIR / f"{job_id}.source.md").read_text(encoding="utf-8")
    update_job(job_id, status="running", started_at=time.time(), worker_pid=os.getpid(),
               redelivered=redelivered)
    INFLIGHT.inc()
    t0 = time.time()
    before = _snapshot(llm)
    try:
        result = review(text, rubric, llm, use_graph=True, use_entropy=USE_ENTROPY,
                        use_lp=USE_LP, llm_lp=llm if USE_LP else None,
                        critic_threshold=THRESHOLD)
    except Exception as e:  # noqa: BLE001
        INFLIGHT.dec()
        usage = _account(llm, model, before)
        err = f"{type(e).__name__}: {str(e)[:500]}"
        requeue = not redelivered  # второй сбой подряд → DLQ, не бесконечный цикл
        update_job(job_id, status="failed" if not requeue else "retrying", error=err,
                   traceback=traceback.format_exc()[-2000:], llm_usage=usage)
        REVIEWS.labels("failed" if not requeue else "retry").inc()
        print(f"! {job_id}: {err} (requeue={requeue})", file=sys.stderr, flush=True)
        nack(requeue)
        return

    dur = time.time() - t0
    usage = _account(llm, model, before)
    DURATION.observe(dur)
    INFLIGHT.dec()
    for f in result.findings:
        FINDINGS.labels(f.category.split(":")[0], f.severity, f.source_pass or "?").inc()
    statuses = getattr(result, "statuses", {}) or {}
    for slot, st in statuses.items():
        SLOTS.labels(slot, st).inc()
    UNKNOWN.set(sum(1 for s in statuses.values() if s == "UNKNOWN"))
    ANCHORING.set(result.anchoring)

    light, vtext = verdict(result)
    report_md = to_markdown(result, doc_name=msg.get("filename") or job_id)
    (RESULTS_DIR / f"{job_id}.report.md").write_text(report_md, encoding="utf-8")
    payload = json.loads(to_json(result))
    update_job(job_id, status="done", finished_at=time.time(), duration_s=round(dur, 1),
               verdict={"light": light, "text": vtext}, llm_usage=usage,
               model=model, backend=BACKEND, result=payload)
    index_put(msg.get("doc_hash", ""), msg.get("config_hash", ""), job_id)
    REVIEWS.labels("done").inc()
    print(f"✓ {job_id}: {light} {vtext}; находок {len(result.findings)}, {dur:.0f}s, "
          f"вызовов {usage['calls']}", flush=True)
    ack()  # ack только после записи результата (в потоке соединения)


def on_message(ch, method, properties, body, *, conn, llm, model, rubric) -> None:
    """Колбэк консьюмера: не блокирует поток соединения — работа уходит в поток."""
    threading.Thread(
        target=process, args=(conn, ch, method.delivery_tag, method.redelivered, body),
        kwargs={"llm": llm, "model": model, "rubric": rubric}, daemon=True,
    ).start()


def main() -> int:
    start_http_server(int(os.environ.get("TZR_METRICS_PORT", "9100")))
    llm, model = build_llm()
    rubric = load_rubric()
    print(f"worker: backend={BACKEND} model={model} lp={USE_LP} entropy={USE_ENTROPY} "
          f"threshold={THRESHOLD}", flush=True)
    while True:
        conn = connect()
        ch = conn.channel()
        declare(ch)
        ch.basic_qos(prefetch_count=1)
        ch.basic_consume(queue=QUEUE, on_message_callback=functools.partial(
            on_message, conn=conn, llm=llm, model=model, rubric=rubric))
        print(f"worker: слушаю {QUEUE}", flush=True)
        try:
            ch.start_consuming()
        except KeyboardInterrupt:
            return 0
        except Exception as e:  # noqa: BLE001 — обрыв соединения: переподключаемся
            print(f"! соединение с брокером потеряно: {e}; переподключение", file=sys.stderr, flush=True)
            time.sleep(3)


if __name__ == "__main__":
    raise SystemExit(main())

> Дополнительные материалы — промежуточная версия · 04.09.2026 · команда TZ Review (кейс МТС NET) · github.com/FD-AX/MWS
> Статус: работает локально (docker compose, ветка arch/compose-stack); фронтенд аналитика — к финалу

# Демо: документ МТС → очередь → конвейер на self-hosted модели → отчёт (+ сверка с голдом)

Предусловия: Docker Desktop запущен; `deploy/.env` заполнен (TZR_BASE_URL/TZR_MODEL пода или OPENAI_*).

```bash
# 1. Поднять контур (из корня репо)
docker compose -f deploy/docker-compose.yml up -d --build
docker compose -f deploy/docker-compose.yml ps        # api/docs/worker/rabbitmq healthy

# 2. Показать, что вход — любой формат: PDF МТС раскладывается на секции с таблицами
curl -s -X POST http://localhost:18081/normalize -F "file=@../Тестовые данные для Хакатона.pdf" | python -c "import json,sys; d=json.load(sys.stdin); print(d['kind'], d['chars'], 'символов,', len(d['sections']), 'секций')"

# 3. Отправить целевой документ (витрина-агрегат) на ревью → job_id (202, в очереди)
curl -s -X POST http://localhost:18080/reviews -F "file=@casedata/doc3_mart_devices.md"

# 4. Статус / отчёт
curl -s http://localhost:18080/reviews/<job_id> | python -m json.tool | head -40
curl -s http://localhost:18080/reviews/<job_id>/report.md

# 5. Сверка с голд-разметкой (16 дефектов doc3, включая 4 официальных пункта МТС)
python scripts/eval_api_result.py http://localhost:18080/reviews/<job_id> eval/gold_doc3.yaml
```

Что показать на экране:
- **RabbitMQ** http://localhost:15672 (guest/guest): очередь `review.jobs`, DLQ `review.dead` — «ничего не теряем».
- **Grafana** http://localhost:13000 (admin/admin) → дашборд «TZ Review — обзор»: ревью/сбои, длительность p50/p95,
  вызовы и токены LLM по модели, находки по классам и проходам, статусы слотов чеклиста, UNKNOWN-слоты (алерт).
- **Prometheus** http://localhost:9090/targets — api, docs, worker, rabbitmq (llm — при профиле gpu).
- Отчёт: светофор, coverage чеклиста, находки по разделам с цитатой / почему / что уточнить.

Смена модели = одна переменная: `TZR_BASE_URL` (RunPod-под, vLLM в контуре заказчика, облако через `TZR_BACKEND=openai`).
Лестница моделей и цифры — `experiments/` (EXP-13/14 GPT-5.5, EXP-15 gpt-oss-120b).


---

# API ревью — контракт для фронтенда

База: `http://localhost:18080` (compose). Swagger/OpenAPI: `/docs`, `/openapi.json`. CORS открыт (`TZR_CORS_ORIGINS`, по умолчанию `*`).

| Метод | Путь | Что делает | Ответ |
|---|---|---|---|
| POST | `/reviews` | multipart: `file` (md/txt/docx/pdf) **или** form `text` | `202 {job_id, status: "queued", doc_hash, chars}`; если такой документ с тем же конфигом уже проверен — `{job_id, status: "done", cached: true}` |
| GET | `/reviews/{job_id}` | статус и результат | см. ниже |
| GET | `/reviews/{job_id}/report.md` | markdown-отчёт (text/plain) | 409 пока не готов |
| GET | `/reviews?limit=20` | последние проверки | `[{job_id, status, filename, doc_hash, model, duration_s, findings, verdict{light,text}, cached_from, created_at, finished_at}]` |
| GET | `/documents?limit=50` | документы и число проверок | `[{id, doc_hash, filename, kind, chars, parent_id, reviews, created_at, last_review_at}]` |
| GET | `/documents/{doc_hash}/history` | версии документа (цепочка по имени файла) и все их ревью | `{document, versions: [{id, doc_hash, filename, chars, parent_id, created_at, reviews: [...]}]}` |
| POST | `/findings/{finding_id}/feedback` | `{vote: 1 | -1, author?, comment?}` | `201 {id}` |
| GET | `/healthz` | живость + счётчики базы | `{ok, documents, reviews, findings, feedback}` |

## `GET /reviews/{job_id}`

```json
{
  "job_id": "07190ce6b716",
  "status": "queued | running | retrying | done | failed",
  "progress": {"stage": "checklist", "pct": 28, "elapsed_s": 110, "batch": 4, "batches": 6,
               "candidates": 4, "calls": 3, "tokens": 11720},
  "filename": "doc3_mart_devices.md", "doc_hash": "d5316ee9ef6c5eed", "kind": "text", "chars": 3222,
  "model": "gpt-oss-120b-b64", "backend": "pod", "duration_s": 414.1,
  "llm_calls": 9, "prompt_tokens": 40210, "completion_tokens": 12873, "anchoring": 0.75,
  "verdict": {"light": "🔴", "text": "Документ не готов к передаче в разработку"},
  "cached_from": null, "error": null,
  "created_at": 1788470000.1, "started_at": 1788470001.2, "finished_at": 1788470415.3,
  "result": {
    "verdict": "...", "anchoring_rate": 0.75,
    "checklist_statuses": {"SRC-01": "OK", "NUL-03": "MISSING", "LOC-02": "NA", "...": "..."},
    "findings": [{"fid": "F008", "db_id": 123, "category": "checklist:INC-01", "severity": "critical",
                  "section": "Инкрементальность", "quote": null, "missing": true,
                  "why": "...", "ask": "...", "score": 9.0, "source_pass": "checklist", "verified": true}],
    "rejected": [{"...": "срезано критиком, есть score"}],
    "dropped":  [{"...": "цитата не найдена в документе"}]
  }
}
```

Этапы `progress.stage`: `deterministic`, `doc_graph`, `checklist`, `document_level`, `developer_sim`,
`uncertainty`, `uncertainty_lp`, `verify`, `critic`, `done`. `severity`: `critical | high | medium | low | advisory`.
`db_id` у находки — ключ для `POST /findings/{db_id}/feedback`.

Рекомендуемый опрос статуса: каждые 3 с, пока `status` не `done`/`failed`. Полный сценарий — `DEMO.md`,
эталонная реализация UI — `services/api/static/index.html` (ванильный JS, те же вызовы).

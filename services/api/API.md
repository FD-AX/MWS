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

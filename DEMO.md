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

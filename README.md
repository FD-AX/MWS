# tz_review — предварительное ревью ТЗ на потоки и витрины данных

Кейс NET (хакатон ИТМО): аналитик готовит ТЗ на поток/витрину, инструмент делает
pre-review — находит места, которые разработчики поймут неоднозначно или которых
не хватает, с дословной цитатой-якорем и конкретным вопросом. Не заменяет
аналитика: вердикт всегда за человеком.

## Быстрый старт: скачать и запустить (docker compose)

Нужны Docker Desktop и ключ модели (облако) или адрес своего OpenAI-совместимого сервера (vLLM/ollama).

```bash
git clone https://github.com/FD-AX/MWS.git && cd MWS
cp deploy/.env.example deploy/.env      # заполнить: OPENAI_API_KEY (TZR_BACKEND=openai)
                                        #   или TZR_BASE_URL/TZR_MODEL своего сервера (TZR_BACKEND=pod)
docker compose -f deploy/docker-compose.yml up -d --build
```

| Что | Где |
|---|---|
| Интерфейс аналитика (загрузка md/txt/docx/pdf, прогресс, отчёт, история, 👍/👎) | http://localhost:18080/ |
| API и Swagger | http://localhost:18080/docs · контракт: `services/api/API.md` |
| Очередь RabbitMQ (guest/guest) | http://localhost:15672 |
| Grafana (admin/admin), Prometheus | http://localhost:13000 · http://localhost:9090 |
| История проверок (Postgres) | localhost:15432, tzr/tzr |

Проверка без Docker и без модели: `pip install -r requirements.txt && python -m tz_review examples/sample_tz.md --no-llm`.
Сценарий демо — [DEMO.md](DEMO.md); архитектура и обоснование — [ARCHITECTURE.md](ARCHITECTURE.md),
[experiments/](experiments/README.md); готовность — [READINESS.md](READINESS.md); артефакты сдачи — [deliverables/](deliverables/).
Фронтенд аналитика (отдельная сборка) подключается как сервис `front` — см. [front/README.md](front/README.md).

Обоснование каждого архитектурного решения — в [RESEARCH.md](RESEARCH.md)
(рисёрч: академия RE, коммерческие инструменты, LLM-практика).
Предметка кейса — в [DOMAIN.md](DOMAIN.md).

## Архитектура

```
ТЗ (markdown/текст)
  │
  ├─ 0. deterministic  — regex-слой: TBD, «и т.д.», лазейки, пустые разделы шаблона
  │                      (бесплатно, precision ~100%)
  ├─ 1. checklist      — LLM-аудит «слотов» полноты по доменной рубрике
  │                      (батчи по 5 вопросов; OK требует цитаты, иначе MISSING/UNCLEAR)
  ├─ 2. document_level — межсекционная согласованность: поле без источника,
  │                      термин-дрейф, противоречия разделов
  ├─ 3. developer_sim  — «ты разработчик, что заставит тебя угадывать?»
  ├─ 4. uncertainty*   — semantic entropy: слоты со статусом OK перечитываются
  │                      N раз с температурой; расходящиеся ответы = неоднозначность
  │                      (*опционально, --entropy)
  │
  ├─ verify            — программная верификация цитат (substring-match после
  │                      нормализации): не нашлась → дроп, не там → переанкорить
  ├─ critic            — судья видит ВСЕ находки разом, скорит 0–10, режет дубли
  │                      и general-советы (порог --threshold)
  │
  └─ report            — светофор документа + coverage чеклиста + находки по
                         разделам + свёрнутая стилистика
```

Ключевые принципы (см. RESEARCH.md §4): генерация отделена от фильтрации;
каждая находка заякорена верифицированной цитатой; чеклист бинарный, а не
«оцени качество»; молчание — валидный результат.

## Запуск

```bash
pip install -r requirements.txt

# Локальный веб-интерфейс:
streamlit run app.py

# Без LLM (только детерминированный слой) — работает сразу:
python -m tz_review examples/sample_tz.md --no-llm

# Полный конвейер в CLI или веб-интерфейсе: скопируй .env.example в .env, заполни
# TZR_BASE_URL / TZR_API_KEY / TZR_MODEL (OpenAI-совместимый API:
# облако, OpenRouter, LM Studio, vLLM), затем:
python -m tz_review examples/sample_tz.md
python -m tz_review examples/sample_tz.md --entropy   # + semantic entropy

# Отчёты: out/<имя>.report.md и out/<имя>.findings.json
```

## Оценка (этап 5 кейса)

`examples/sample_tz.md` содержит 12 подсаженных дефектов
(`eval/seeded_defects.yaml`), `examples/sample_tz_clean.md` — чистое ТЗ
для проверки уровня шума.

```bash
python -m tz_review examples/sample_tz.md
python eval/run_eval.py out/sample_tz.findings.json eval/seeded_defects.yaml
```

Метрики: recall по подсаженным, anchoring rate, список находок для ручной
разметки precision. Тесты: `python -m unittest discover tests -v`.

## Данные кейса

Когда придут реальные шаблон/примеры/корректировки:

1. Шаблон → `required_sections` в `tz_review/rubric.yaml`.
2. Корректировки разработчиков → пополнить чеклист + 10–20 few-shot примеров
   с объяснениями в промпты (главный рычаг precision: +20% по ICSME 2025).
3. Примеры ТЗ → калибровка порогов критика и entropy бэктестом:
   «энтропия/score vs было ли место позже уточнено».

## Роадмап

- [ ] **GraphRLM-полнота**: заменить плоский чеклист типизированным графом
      слотов (слот → суб-слоты → evidence-спаны документа); coverage-метрика
      документа как в GraphRLM (см. github.com/FD-AX/GraphRLM).
- [ ] **Semantic entropy v2**: кластеризация ответов эмбеддингами
      (multilingual MiniLM из GraphRLM) вместо канонизации строк; калибровка
      порога ROC-ом на исторических корректировках.
- [ ] Consensus: 2–3 прогона генеративных проходов с перемешанным порядком
      секций, находка проходит при подтверждении ≥2 прогонами (паттерн Bugbot).
- [ ] Структурный парсинг таблиц маппинга (главная боль LLM на design-doc).
- [ ] Suggested fix в EARS-стиле для UNCLEAR-находок.
- [ ] UI (streamlit) для демо + 👍/👎 разметка находок аналитиком.

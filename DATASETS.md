# Датасеты для ревьюера ТЗ (проверено 2026-09-02)

Ранжирование по близости к задаче «ревью русскоязычных ТЗ на потоки/витрины данных».
Все ✅-ссылки проверены агентом на доступность. Полный разбор тупиков — внизу.

## Ядро (брать в первую очередь)

| Датасет | Что внутри | Роль у нас | Ссылка |
|---|---|---|---|
| **QuRE** | 2 111 промышленных требований Mercedes-Benz (англ.), метка defect/ok **из реального ревью-процесса** + 23 типа weak words (633 дефектных / 1 478 ок) | **Главный eval-бенчмарк**: precision/recall детектора формулировок на метках живого ревью; калибровка порогов; few-shot пары | ✅ [zenodo 15656471](https://zenodo.org/records/15656471), CC-BY. NB: в статье 2 111, не 1 266 |
| **PURE** | 79 **полных** SRS-документов, ~34k предложений (англ.), без разметки дефектов | Единственный корпус целых документов → **подсадка дефектов** (битые ссылки, противоречия секций, удалённые SLA); DigitalHome = стандартный документ LLM-экспериментов | ✅ [zenodo 1414117](https://zenodo.org/records/1414117), CC-BY. ETL/DWH-спек внутри нет |
| **ReqEval 2020** | 200 требований, местоимения nocuous/innocuous + правильный антецедент, 2+ аннотатора | Точечный eval модуля **анафоры/висячих ссылок**: ровно граница «флажить или нет» | ✅ [github frieden84/nlp4re-reqeval](https://github.com/frieden84/nlp4re-reqeval), CC-BY |
| **Data-contract примеры** | YAML-контракты с полями, quality-чеками, **servicelevels (freshness/retention/latency)** | **Эталон полноты ТЗ на поток** + фабрика синтетики: валидный контракт → выбрасываем секции → пары (дефект, диагноз) | ✅ [datacontract-specification](https://github.com/datacontract/datacontract-specification), ✅ [ODCS/bitol](https://github.com/bitol-io/open-data-contract-standard), MIT |

## Второй эшелон

| Датасет | Что внутри | Роль | Ссылка |
|---|---|---|---|
| Dalpiaz 22 бэклога | ~1 680 user stories реальных проектов | Подсадка QUS-дефектов; стресс-тест на коротких требованиях; AQUSA = 13 критериев для промпта | ✅ [mendeley 7zbk8zsd8y](https://data.mendeley.com/datasets/7zbk8zsd8y/1) |
| PROMISE NFR / _exp | 625 / 969 требований, классы FR/NFR | Smoke-test; few-shot «как выглядит NFR» | ✅ [zenodo 268542](https://zenodo.org/records/268542), [PROMISE_exp](https://github.com/AleksandarMitrevski/se-requirements-classification) |
| Публичные dbt-проекты | cal-itp/data-infra, catalyst-cooperative/pudl: schema.yml с описаниями колонок + тестами not_null/unique | «Как выглядит правильно документированная витрина»; терминология для промптов | ✅ [cal-itp](https://github.com/cal-itp/data-infra), ✅ [pudl](https://github.com/catalyst-cooperative/pudl) |
| RuREBus | ~300 размеченных документов Минэка (NER/RE) + 280M токенов сырья, **русский** | Ближайший корпус русского канцелярита: домен-адаптация энкодера, NER «показатель/срок». Дефектов не даст | ✅ [github RuREBus](https://github.com/dialogue-evaluation/RuREBus) |
| Frattini recovery-бандл | Онтология 206 quality-факторов + спасённые артефакты | Мета-таксономия для сверки с MATRIX.md | ✅ [zenodo 7708571](https://zenodo.org/records/7708571) |
| TAPHSIR (тул) | Детектор+резолвер анафоры (390 MB) | Бейзлайн для сравнения; данные DAMIR не опубликованы — брать ReqEval | ✅ [zenodo 5903104](https://zenodo.org/records/5903104) |

## Тупики (проверено, не тратить время)

- **Smella-данные** (Daimler/Wacker) — не опубликованы; брать только 9 смеллов как таксономию.
- **Fujitsu design-doc review** (arxiv 2509.09975) — идейно ближайшая работа, артефактов нет.
- **Lubos RE'24** — реплик-пакета нет, но сетап воспроизводим (DigitalHome из PURE + 9 характеристик ISO 29148).
- **Публичного корпуса русских ТЗ по ГОСТ 34.602 не существует** (GitHub/HF/Zenodo). prj-exp.ru мёртв. Реальные ТЗ на ИС/ХД — вложениями на zakupki.gov.ru.
- Датасет 8 120 требований × 11 смеллов (Alem 2025) — «upon reasonable request».

## План действий

1. **QuRE + ReqEval = eval-ядро** (метки реального ревью + анафора), скачиваются за минуту.
2. **PURE + data contracts = фабрика синтетики под DWH**: ни один датасет не покрывает
   инкремент/NULL/маппинг — этот слой делаем сами: структура контракта как эталон
   полноты, генерация пар (испорченное ТЗ, диагноз) с бесспорным ground truth.
3. **Русский слой — свой мини-корпус**: 20–40 ТЗ с zakupki.gov.ru + обезличенные
   внутренние + подсадка дефектов; разметка по нашей схеме (2 размётчика + арбитр + κ).
   RuREBus — вспомогательный.
4. Расширение бенчмарка — сверяться с обзором [Characterizing Datasets for LLM-based RE](https://arxiv.org/abs/2510.18787).

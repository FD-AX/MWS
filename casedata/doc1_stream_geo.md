# Описание потоковой обработки геоданных

## Общие сведения

Модуль обеспечивает получение сведений о текущем и историческом местоположении абонентских устройств в реальном времени. Обработка основана на сигнальном трафике сетей радиодоступа (3G/4G), поступающем от платформы PROVIDER_GEO.

## Решаемая проблема

Замена устаревшей технологии геолокации абонентов по данным радиоинтерфейса. Цель — создание отечественного решения с потоковой обработкой и интеграцией в Data Lake.

## Продуктовые метрики

- Задержка: < 1 мин
- Пропускная способность: до 100 000 событий/сек
- Точность локации: 3G — 50–500 м, 4G — 10–100 м

## Заказчики

BigData Unit X

## Нефункциональные требования

- Инкрементная загрузка по часовым партициям
- Географическое разбиение по регионам
- Стриминг в реальном времени (задержка ≈ 0 сек)
- Хранение: Kafka — 24 ч, RAW-слой — 30 дней

## Системы-источники

- PROVIDER_GEO — мультивендорная платформа агрегации событий 3G/4G и MDT.

## Схема потоков данных

PROVIDER_GEO → Kafka (топики по регионам) → Apache Flink → RAW → DDS → ADDS → CDM

- Мониторинг: LINK_DASHBOARD_GEO
- Исходный код: LINK_GITLAB_PROJECT

## JIRA

PROJECT-XX123 — Описание потоковой обработки геоданных
LINK_JIRA_TASK

## Команда

- USER_A — Product Owner
- USER_B — Data Analyst
- USER_C — Backend Developer

## Источники и приемники данных

PROVIDER_GEO → Kafka (24 часа хранения):

| Регион | Топик 3G | Топик 4G |
|---|---|---|
| Центр | TOPIC_GEO3G_CENTRAL | TOPIC_GEO4G_CENTRAL |
| Дальний Восток | TOPIC_GEO3G_EAST | TOPIC_GEO4G_EAST |
| Северо-Запад | TOPIC_GEO3G_NW | TOPIC_GEO4G_NW |
| Поволжье | TOPIC_GEO3G_VOLGA | TOPIC_GEO4G_VOLGA |
| Сибирь | TOPIC_GEO3G_SIB | TOPIC_GEO4G_SIB |
| Юг | TOPIC_GEO3G_SOUTH | TOPIC_GEO4G_SOUTH |
| Урал | TOPIC_GEO3G_URAL | TOPIC_GEO4G_URAL |

Приемники:

| Слой | Таблица | Описание |
|---|---|---|
| RAW | TABLE_GEO_RAW_3G | Данные по 3G (необработанные) |
| RAW | TABLE_GEO_RAW_4G | Данные по 4G (необработанные) |
| DDS | TABLE_GEO_DDS_DETAILED | Детальные события геолокации |
| ADDS | TABLE_GEO_ADDS_AGG | Агрегированные события |
| CDM | TABLE_GEO_CDM_INTERVALS | Геоинтервалы по абонентам |

## Структура данных

Таблица: TABLE_GEO_RAW_3G

| Поле | Тип данных | Описание |
|---|---|---|
| FIELD_REGION | string | Регион |
| FIELD_DATE_EVENT | date | Дата события |
| FIELD_HOUR | int | Час события (партиция) |
| FIELD_IMSI | string | IMSI |
| FIELD_MSISDN | string | MSISDN |
| FIELD_IMEI | string | IMEI |
| FIELD_LAT | double | Широта геопозиции |
| FIELD_LON | double | Долгота геопозиции |
| FIELD_RADIUS | int | Радиус точности (метры) |
| FIELD_CELL_START | long | ID начальной базовой станции |
| FIELD_CELL_END | long | ID конечной БС |
| FIELD_TIME_START | long | Время начала события |
| FIELD_TIME_END | long | Время окончания события |
| FIELD_LOC_ACCURACY | int | Точность локации (метры) |
| FIELD_VENDOR | string | Вендор оборудования БС |

Таблица: TABLE_GEO_RAW_4G

| Поле | Тип данных | Описание |
|---|---|---|
| FIELD_REGION | string | Регион |
| FIELD_DATE_EVENT | date | Дата события |
| FIELD_HOUR | int | Час события (партиция) |
| FIELD_IMSI | string | IMSI |
| FIELD_MSISDN | string | MSISDN |
| FIELD_IMEI | string | IMEI |
| FIELD_LAT | double | Широта геопозиции |
| FIELD_LON | double | Долгота геопозиции |
| FIELD_RADIUS | int | Радиус точности (метры) |
| FIELD_CELL_START | long | ID начальной БС |
| FIELD_CELL_END | long | ID конечной БС |
| FIELD_TIME_START | long | Время начала события (Unix-время) |
| FIELD_TIME_END | long | Время окончания события |
| FIELD_SERVICE_TYPE | int | Тип формата связи (услуга) |

## Дополнительная информация

Документы:

- «Описание протоколов сигнальных сообщений в 3G/4G»
- «Форматы MDT и Measurement Trigger»

Алгоритмы: обработка хэндоверов, геоинтервалов, работа с RNC/eNodeB.

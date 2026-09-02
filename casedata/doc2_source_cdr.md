# Описание данных системы-источника (CDR-платформа prepaid)

## Общие сведения

Платформа обслуживает prepaid-абонентов. Файлы, поступающие с системы, содержат телеком-события абонентов, заведённых на платформе.

## Заказчики

BigData

## Системы-источники

PI_System — система сбора CDR-файлов с сетевых элементов подвижной связи.

## Команда

- USER_A — Product Owner
- USER_B — Data Analyst
- USER_C — Backend Developer

## Источники и приёмники данных

Источники (CDR в формате CSV, сжатые gzip)
Данные поступают в Kafka по топикам, соответствующим регионам:

| Регион | Kafka-топик | SFTP-папка HDFS |
|---|---|---|
| Центр | TOPIC_MSCP_CDR_CENTRAL | Папка |
| Дальний Восток | TOPIC_MSCP_CDR_EAST | Папка |
| Сибирь | TOPIC_MSCP_CDR_SIB | Папка |
| Северо-Запад | TOPIC_MSCP_CDR_NW | Папка |
| Поволжье | TOPIC_MSCP_CDR_VOLGA | Папка |
| Юг | TOPIC_MSCP_CDR_SOUTH | Папка |

Приёмники:

- TABLE_MSCP_RAW_KFK — необработанные CDR из Kafka (ORC)
- TABLE_MSCP_RAW_SFTP — необработанные CDR из SFTP (CSV)

## Алгоритм обработки потока

Шаг 1. Фильтрация данных
Учитываются только события, произошедшие не ранее 7 дней назад и не позже 2 часов вперёд от текущего времени (на стороне обработки).

Шаг 2. Преобразования на потоке

Очистка числовых строк от лидирующих нулей:

Из этих полей удаляются лидирующие нули до первого значимого символа.

Коррекция часового пояса для временных меток:

- Для региона east: 7 часов
- Для регионов central, nw, volga, south: 3 часа
- Примечание: регион sib соответствует east.

## Структура данных

Таблица: TABLE_MSCP_RAW_KFK
(из Kafka, ORC-формат, 15 полей)

| Поле | Тип данных | Описание |
|---|---|---|
| FIELD_REGION | string | Название региона |
| FIELD_BIZ_DATE | date | Бизнес-дата события |
| FIELD_HOUR | int | Часовая партиция |
| FIELD_IMSI | bigint | IMSI |
| FIELD_CALLING_NUMBER | string | Номер вызывающего абонента |
| FIELD_CALLED_NUMBER | string | Номер вызываемого абонента |
| FIELD_CALL_START_TIME | timestamp | Время начала вызова |
| FIELD_CALL_END_TIME | timestamp | Время окончания вызова |
| FIELD_CALL_DURATION | int | Длительность вызова (сек) |
| FIELD_IS_ROAMING | string | Признак роуминга (true/false) |
| FIELD_OL_SERVICE_TYPE | tinyint | Тип сервиса |
| FIELD_TIME_ZONE_SHIFT | string | Сдвиг часового пояса |
| FIELD_TIMEZONE_CALC | int | Вычисленный сдвиг в минутах |
| FIELD_BALANCE | double | Текущий баланс абонента |
| FIELD_BALANCE_EXPIRE | timestamp | Срок истечения баланса |

## FAQ (обобщённо, без реальных ссылок)

Тип события (голос, SMS, данные):
Определяется по FIELD_OL_SERVICE_TYPE (см. выше).

Определение технологии связи (2G/3G/4G/5G):

Для data-трафика — по полю radioAccessTechnology.

Для голоса и SMS — косвенно: по наличию/отсутствию полей геолокации (например, CELL_ID, LAC).

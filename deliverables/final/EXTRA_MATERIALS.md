# DocReview AI — дополнительные материалы (финальная версия)

06.09.2026 · команда 7 · кейс МТС NET · [github.com/FD-AX/MWS](https://github.com/FD-AX/MWS)

Материалы для кейсодателя и экспертов. Презентацию Demo Day (`TZ_Review_pitch.html`) и видео демо сюда не дублируем. Статус каждого файла — в его шапке.

| # | Файл | Зачем смотреть |
|---|---|---|
| 1 | [extra/01_experiments_journal.md](extra/01_experiments_journal.md) | Журнал EXP-01…24: вопрос, ожидание до прогона, результат, вердикт |
| 2 | [extra/02_rejected_hypotheses.md](extra/02_rejected_hypotheses.md) | 17 гипотез, отвергнутых измерением — такой же результат, как подтверждённые |
| 3 | [extra/03_prod_config_metrics.md](extra/03_prod_config_metrics.md) | Прод-конфиг v2x, таблица recall/precision из презентации, оговорки к цифрам |
| 4 | [extra/04_gold_markup_mts.md](extra/04_gold_markup_mts.md) | 36 размеченных дефектов на трёх ТЗ МТС (9 — официальные пункты) |
| 5 | [extra/05_demo_scenario_and_api.md](extra/05_demo_scenario_and_api.md) | Как воспроизвести сценарий и контракт API |
| 6 | [extra/06_architecture.md](extra/06_architecture.md) | Схема контура и восемь механизмов конвейера |
| 7 | [extra/07_quote_verification_exp24.md](extra/07_quote_verification_exp24.md) | Почему в отчёт попадает текст документа: 4→17 из 28 спасённых цитат |

Репозиторий открыт: https://github.com/FD-AX/MWS

Кратко, что считать доказанным на 06.09:

- Прод на gpt-oss-120b находит **15 из 16** дефектов целевого ТЗ, recall **92%**, precision **88%**, шум@clean **7.5**.
- Один промпт на той же задаче — около **46%** полноты и 0 из 6 нарушений шаблона.
- Все четыре результата из брифа (фрагмент, почему, что уточнить, общий вердикт) есть в отчёте аналитика.
- Не измерено: доля полезных замечаний глазами аналитиков NET — это шаг пилота на 5–10 новых ТЗ.

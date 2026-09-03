# EXP-14: критик не режет официальные пункты + добор слотов + база it6

Дата: 2026-09-03 (заведён до прогона) · Итерация синтетики: **it6** · Голды: v1 12 / v3official 13 / doc3 16.
Данные (после прогона): `eval/night/bench_exp14.md`, `eval/night/raw_exp14.json`, `eval/night/exp14.log`.

## Вопрос
Поднимут ли четыре фикса из диагностики EXP-13 recall официальных пунктов МТС на v3official,
не увеличив шум на чистой базе?

## Что изменилось (относительно EXP-13)
1. **Критик**: находки чеклиста по слотам с `official: true` (SER-01, CAT-01, NUL-03, FIL-02, LOC-02,
   LOC-03, REF-01, KEY-02) не подлежат порогу — пол = порог, дедупликация действует. В промпте критика
   правило: требования кейсодателя ≠ «бюрократия»/«другой документ». (EXP-13: CAT-01/FIL-02/LOC-02
   найдены чеклистом и срезаны со score 0.0.)
2. **Чеклист**: слоты без ответа в батче добираются отдельным вызовом (EXP-13: 10/27 UNKNOWN молча).
3. **Вопросы слотов МТС** уточнены: заглушка засчитывается только в позиции слота (топик без кластера,
   «в HDFS кластера X» без пути, «по умолчанию» для формата, обещание карточки Data Catalog = не указано);
   REF-01: «не применимо» допустимо только без джойнов со справочниками.
4. **Верификация цитат**: вторая ступень без «|» и переносов (табличные цитаты; EXP-13: 5/21 отброшены).
5. **База it6**: ~10 реальных дефектов чистой базы закрыты (см. EXP-13 «Вычитка шума»).

## Ожидание (до прогона)
| Что | Ожидание | Почему |
|---|---|---|
| v2g v3official | **≥ 11/13** (было 9/13) | CAT/FIL/LOC-02 больше не режутся; NUL-03/LOC-03 находились в диагностике |
| v2e/v2l v3official | ≥ 10/13 | тот же чеклист/критик |
| Слепые зоны на v3official | ≤ 1 (кандидат: OFF-FIL — самый «мягкий» слот) | |
| Слоты UNKNOWN | **0** | добор |
| шум@clean (it6) | ≤ 8 у конвейера, ≤ 12 у промпта | база чище; защита слотов может добавить 1–2 ложных «официальных» |
| anchoring | ≥ 80% на synth_v1 (было 56–81%) | табличные цитаты |
| doc3 (контроль) | 13–14/16 | без изменений в доке; разброс GPT |
| Стабильность | 2 прогона v2g на v3official расходятся ≤ 1 дефект | проверка на разброс (EXP-04) |

## Конфигурация
Варианты: `v2g_gpt, v2e_gpt, v2l_gpt` (+ `v0b_gpt` как референс промпта); цели: `eval/targets_key.yaml`
(synth_v1, doc3, v2hard, v3official, clean). Второй прогон v2g_gpt по тем же целям — оценка разброса.

## Воспроизведение
```
python synth/inject.py synth/recipes/mart_traffic_v1.yaml
python synth/inject.py synth/recipes/mart_traffic_v2hard.yaml
python synth/inject.py synth/recipes/mart_traffic_v3official.yaml
python eval/bench.py --variants v0b_gpt,v2g_gpt,v2e_gpt,v2l_gpt --targets eval/targets_key.yaml --out eval/night/bench_exp14.md --json eval/night/raw_exp14.json 2> eval/night/exp14.log
python eval/bench.py --variants v2g_gpt --targets eval/targets_key.yaml --out eval/night/bench_exp14_rerun.md --json eval/night/raw_exp14_rerun.json 2> eval/night/exp14_rerun.log
python eval/error_matrix.py eval/night/raw_exp14.json --out eval/error_matrix_exp14.md
```

## Результат
_(заполняется после прогона)_

## Выводы
_(заполняется после прогона)_

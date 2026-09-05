# EXP-20: проход «сверка величин и сроков между разделами» (v2q) — закрыть устойчивые промахи 120b

Дата: 2026-09-05 (заведён до прогона) · Ветка: main · Итерация: it7, голд-ключи v2 · Протокол: [PROTOCOL.md](PROTOCOL.md).

## Вопрос
В одиночных прогонах EXP-19 gpt-oss-120b стабильно (4–5 конфигураций из 5) не берёт на v2hard дефекты класса
«несовместимые величины между разделами»: **HRD-RET** (сверка на глубину 36 месяцев при retention 24), **HRD-TIME**
(срок готовности 10:00 2-го при запуске 3-го), нестабильно — **HRD-BOUND** (граница месяца включает 1-е число следующего).
GPT-5.5 берёт их внутри document_level в 4/4 конфигураций. Даёт ли узкий проход с прямым вопросом («выпиши величины
с цитатами, найди несовместимые пары») этот класс модели поменьше, и что он стоит по шуму?

## Конфигурация
- `tz_review/passes/quantities.py` + `prompts/quantities.md`; в конвейере — после document_level, до developer_sim.
- Бенч: каноническая строка `v2q` = v2g + quantities (`--backend pod|openai`, `--repeat 2`), targets_key + targets_docs.
- Сравнение: со строкой `v2g` той же модели из матрицы `m2_*` (тот же код, та же итерация).

## Ожидание (до прогона)
| Что | 120b | GPT-5.5 | Почему |
|---|---|---|---|
| v2hard | **+1…+2 к v2g** (HRD-RET, HRD-TIME) | ±0 (уже 7–8/8) | прямой вопрос вместо «додумай» |
| doc3 / v3official / synth_v1 | ±1 (в пределах размаха) | ±0 | класс редкий вне v2hard; G3-8 (UTC) может добраться |
| шум@clean | +0…+1 | +0…+1 | чистая база согласована по величинам; риск — придирки к точности типов |
| время | +1 вызов/документ (~15–30 с на 120b) | | один вызов |

Критерий «в прод»: медиана v2hard 120b растёт ≥ +1 при шуме ≤ v2g + 1 и без потерь на других целях.

## Воспроизведение
```
python eval/bench.py --backend pod    --variants v2q --repeat 2 --targets eval/targets_key.yaml --out eval/night/m2_pod_v2q.md --json eval/night/m2_pod_v2q.json
python eval/bench.py --backend openai --variants v2q --repeat 2 --targets eval/targets_key.yaml --out eval/night/m2_gpt_v2q.md --json eval/night/m2_gpt_v2q.json
python eval/matrix.py eval/night/m2_pod_key.json eval/night/m2_pod_v2q.json eval/night/m2_gpt_key.json eval/night/m2_gpt_v2q.json
```

## Результат
_(после матрицы m2 — запуск последовательно, пункт 3 протокола)_

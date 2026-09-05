# EXP-19: gpt-oss-120b на vLLM — уравнять с GPT-5.5 (логиты, энтропия, правила точности)

Дата: 2026-09-05 (заведён до прогона) · Ветка: main · Итерация синтетики: **it7** · Голды: `eval/targets_key.yaml`
(v1 12 / doc3 16 / v2hard 8 / v3official 13 + clean) + документы МТС doc1 12 / doc2 8 через контур.
Данные (после прогона): `eval/night/bench_exp19_*.md`, `eval/night/raw_exp19_*.json`, `eval/night/exp19_*.log`.

## Вопрос
Закрывают ли три рычага разрыв 120b ↔ GPT-5.5 на одной и той же базе it7:
1. **vLLM вместо ollama** → logprobs → логит-зонд v2l (на GPT — единственный, кто ловит анафору) и энтропия v2e с `n>1`;
2. **правила точности EXP-18** (NA-слоты, фильтр заглушек, severity из score) — на 120b, где был весь мусор;
3. прежний конвейер v2g на новой инфре — контроль, что смена ollama→vLLM сама по себе ничего не меняет.

4. **общие слоты `rubric_extra.yaml`** (ORD-01 поле упорядочивания «последней» записи, REF-02 lookup-miss в справочнике,
   HIS-01 бэкфилл, TZ-01 часовой пояс границ периода) — прямой вопрос вместо «додумай следствие». Варианты `*_x`.
   Честно: слоты калиброваны на промахах doc3 (G3-4/6/7/8), поэтому doc3 для них «обучающий»; доказательство переносимости —
   synth (SYN-A-BCKF, HRD-RET) и doc1/doc2, плюс шум@clean (база упоминает UTC 6 раз и справочники 7 → слоты применимы,
   модель должна ответить OK/NA, а не MISSING).

Сравнение только внутри it7: GPT-5.5 прогоняется на it7 в этом же эксперименте (закрывает открытый вопрос
CURRENT.md «что даёт it7 сама по себе»). Порядок на поде: сначала `v2g` (контроль инфры), потом `v2l/v2e`, потом `*_x` —
каждый рычаг = отдельная строка, вклад читается как разность соседних строк.

## Конфигурация
- Под: RunPod H100 80GB, `vllm/vllm-openai:latest`, `openai/gpt-oss-120b` (served as `gpt-oss-120b`), `max-model-len 32768`,
  `infra/runpod.py create-vllm-oss`. Клиент: `TZR_MAX_TOKENS=4096`, `TZR_REASONING_EFFORT=medium`, `TZR_PROBE_MODE=harmony`
  (зонд через `/v1/completions` с raw harmony-промптом и открытым каналом final — иначе первый токен `<|channel|>`).
- Варианты 120b: `v2g`, `v2e`, `v2l`, `v2el`. Варианты GPT-5.5: `v2g_gpt`, `v2e_gpt`, `v2l_gpt` (зонд gpt-4.1-mini).
- Правила EXP-18 включены у всех (это уже main).

## Ожидание (до прогона)
| Что | 120b vLLM | GPT-5.5 it7 | Почему |
|---|---|---|---|
| v2g doc3 | 12–14/16 (как EXP-16) | 14–16/16 | инфра не меняет модель; разброс 120b ±1–2 |
| v2l doc3 | **14–16/16** | 16/16 | зонд на GPT давал doc3 16/16 и B-класс 9/9; на 120b логиты слабее калиброваны |
| v2l SYN-B-ANAPH (анафора) | ✓ | ✓ | единственный сигнал, который её ловит |
| v3official | 11–12/13 | 12/13 | A-класс защищён (EXP-14); D-класс — понимание |
| synth_v1 / v2hard | 9–10/12 · 6–7/8 | 8–10/12 · 7/8 | |
| шум@clean | **≤ 5** (было 7) | ≤ 7 (было 7–9) | правила EXP-18 + чистая база it7 |
| precision high-тира 120b (разметка) | ≥ 90% (было 80%) | ≥ 95% | NA-слоты и заглушки срезаны до модели |
| Время/документ 120b | 2–4 мин v2g, +1–2 мин v2l (27 зондов ×1 токен) | | vLLM батчит зонды |
| v2g_x doc3 (слоты) | **+2…+4 к v2g** (G3-4/6/7/8 спрошены прямо) | +0…+1 | на doc3 это «обучающая» выборка — не доказательство |
| v2g_x v3official / synth_v1 | +0…+1 (SYN-A-BCKF) | +0…+1 | перенос слотов на другие документы |
| v2g_x шум@clean | ≤ v2g + 2 | ≤ v2g + 1 | TZ-01/ORD-01 применимы к базе, но ответ должен быть OK/NA |

Критерий «уравняли»: на doc3 и v3official 120b-v2l/v2el попадает в диапазон GPT той же итерации, шум не выше GPT,
precision по разметке ≥ 95%. Если v2l на 120b не даёт прироста — логиты 120b не калиброваны под YES/NO, следующий рычаг —
reasoning high и консенсус ×2.

## Воспроизведение
```
python infra/runpod.py create-vllm-oss && python infra/runpod.py wait <pod>
# .env: TZR_BASE_URL=https://<pod>-8000.proxy.runpod.net/v1 TZR_MODEL=gpt-oss-120b TZR_API_KEY=<VLLM_API_KEY>
#       TZR_MAX_TOKENS=4096 TZR_REASONING_EFFORT=medium TZR_PROBE_MODE=harmony
python eval/bench.py --variants v2g_gpt,v2e_gpt,v2l_gpt --targets eval/targets_key.yaml --out eval/night/bench_exp19_gpt.md --json eval/night/raw_exp19_gpt.json 2> eval/night/exp19_gpt.log
python eval/canary.py --variant v2g
python eval/bench.py --variants v2g,v2l,v2e,v2el --targets eval/targets_key.yaml --out eval/night/bench_exp19_oss.md --json eval/night/raw_exp19_oss.json 2> eval/night/exp19_oss.log
```

## Ход прогона (факты по дороге)
- Под `whpex5r9snz802` (H100 80GB, $3.49/ч) поднялся за ~4 мин с `vllm/vllm-openai:latest`; смоук: JSON в content 5.9 с,
  n=5 одним вызовом 1.3 с, зонд 1.7 с.
- **Логит-зонд на reasoning-модели не работает как на gpt-4.1.** (1) Первый токен chat-ответа — всегда `<|channel|>` (p=1.0),
  поэтому нужен raw harmony-промпт с открытым каналом final. (2) Но первый токен *до размышления* смещён и зависит от
  раскладки: на doc3 «упоминается ли Kafka?» → YES 0.97 при документе в конце промпта и NO 0.96 при документе в начале;
  однозначный вопрос про расписание при документе в начале — NO 0.56. (3) Токен *после* размышления (chat с logprobs,
  reasoning low/medium) вырожден: 1.0 всегда, при этом ответ меняется от low к medium (дедупликация NO→YES).
  → Для 120b зонд переведён в режим `TZR_PROBE_MODE=sample`: n=8 коротких ответов при t=1 одним вызовом, P(NO) = доля.
  Это уже не «логиты», а Монте-Карло-оценка той же величины; v2l на 120b читать как «v2l-sample».

- **Заякоренность 120b проваливалась в длинных процессах (25–50 % на v3official/v2hard), а в отдельном прогоне той же
  конфигурации держалась 89–93 %.** Разбор: в длинном процессе модель отвечала на v3official **по-английски**
  («DDL defines FIELD_TRAFFIC_GB as decimal(18,2)…», «Version 1.1 added FIELD_ROAMING_FLAG…»), цитаты-переводы
  не верифицируются и уходят в dropped → recall 12/13 → 8/13. Флаги клиента (temperature / max_completion_tokens) не
  дрейфовали. Исправление в клиенте: `quotes_off_language` → один повтор с `LANG_GUARD` (тест `tests/test_lang_guard.py`).
  Матрица по PROTOCOL перезапущена с нуля в 04:13 (файлы `m2_*`); первая попытка (`eval/night/aborted_0412/`) в таблицы
  не входит.
- Одиночные легаси-прогоны (до предохранителя, ключи голда v2): 120b v2g doc3 13/16, v2g_x 15/16, v2el_x 14/16;
  v3official v2g 11, v2e 12, v2l 12, v2el_x 10; v2hard 4–5/8 во всех конфигурациях (GPT 7–8/8) — устойчивый разрыв;
  шум@clean 120b v2g 7, v2g_x 5, v2e 7, v2l 10, v2el_x 12; GPT v2g 6, v2e 5, v2l 9, v2g_x 11 (одна конфигурация
  v2g/v2g_x: 6 ↔ 11 — размах шума на одиночном прогоне). Полная таблица: `eval/night/bench_exp19_*.md`.

## Результат
_(матрица `m2_*` по PROTOCOL, ×2 повтора — заполняется после прогона)_

## Выводы
_(после прогона)_

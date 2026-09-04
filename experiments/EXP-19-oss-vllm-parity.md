# EXP-19: gpt-oss-120b на vLLM — уравнять с GPT-5.5 (логиты, энтропия, правила точности)

Дата: 2026-09-05 (заведён до прогона) · Ветка: main · Итерация синтетики: **it7** · Голды: `eval/targets_key.yaml`
(v1 12 / doc3 16 / v2hard 8 / v3official 13 + clean) + документы МТС doc1 12 / doc2 8 через контур.
Данные (после прогона): `eval/night/bench_exp19_*.md`, `eval/night/raw_exp19_*.json`, `eval/night/exp19_*.log`.

## Вопрос
Закрывают ли три рычага разрыв 120b ↔ GPT-5.5 на одной и той же базе it7:
1. **vLLM вместо ollama** → logprobs → логит-зонд v2l (на GPT — единственный, кто ловит анафору) и энтропия v2e с `n>1`;
2. **правила точности EXP-18** (NA-слоты, фильтр заглушек, severity из score) — на 120b, где был весь мусор;
3. прежний конвейер v2g на новой инфре — контроль, что смена ollama→vLLM сама по себе ничего не меняет.

Сравнение только внутри it7: GPT-5.5 прогоняется на it7 в этом же эксперименте (закрывает открытый вопрос
CURRENT.md «что даёт it7 сама по себе»).

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

## Результат
_(заполняется после прогона)_

## Выводы
_(после прогона)_

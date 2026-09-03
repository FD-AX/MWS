#!/usr/bin/env bash
# Ночной прогон на поде (запускается после готовности vLLM).
# Логи и отчёты — в eval/night/.
set -x
cd "$(dirname "$0")/.."
mkdir -p eval/night
export PYTHONIOENCODING=utf-8

echo "=== 1. Канарейка v2g (гейт) ===" | tee eval/night/00_canary.log
python eval/canary.py --variant v2g >> eval/night/00_canary.log 2>&1
CANARY=$?
# Для слабой модели провал канарейки — результат (фиксируем), а не блокер:
# стек проверен на GPT; продолжаем, чтобы снять полную лестницу на Qwen.
echo "canary exit=$CANARY (информационно)" | tee -a eval/night/00_canary.log

echo "=== 2. Полная лестница на поде ==="
python eval/bench.py --variants p0,p1,p2,p3,v0b,v2g,h5,v3 \
  --out eval/night/bench_pod_full.md > eval/night/01_ladder.log 2>&1

echo "=== 3. Длина контекста (v2g) ==="
python eval/bench.py --variants v2g --targets exp/targets_ctx.yaml \
  --out eval/night/ctx_report_llm.md > eval/night/02_ctx.log 2>&1

echo "=== 4. Стабильность: v2g x3 на ключевых целях ==="
for i in 1 2 3; do
  python eval/bench.py --variants v2g --targets eval/targets_key.yaml \
    --out eval/night/stab_$i.md > eval/night/03_stab_$i.log 2>&1
done

echo "NIGHT RUN DONE"

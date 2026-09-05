"""Смоук vLLM-пода с gpt-oss: три вещи, без которых бенч не имеет смысла.

    python infra/vllm_smoke.py

1. chat.completions с reasoning_effort → JSON приходит в content (а не только в reasoning);
2. harmony-зонд: /v1/completions с открытым каналом final отдаёт YES/NO первым токеном с logprobs;
3. n=5 сэмплов одним вызовом (энтропия без 5 отдельных запросов).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tz_review.config import settings_or_die  # noqa: E402
from tz_review.llm import LLM  # noqa: E402

DOC = ("Витрина считается ежемесячно. Для каждого абонента берётся последняя запись "
       "по полю FIELD_TIME_STAMP. Записи с пустым lac отбрасываются.")


def main() -> int:
    cfg = settings_or_die()
    print("endpoint:", cfg.base_url, "| model:", cfg.model, "| probe:", cfg.probe_mode,
          "| reasoning:", cfg.reasoning_effort, "| floor:", cfg.max_tokens_floor)
    llm = LLM(cfg)

    t0 = time.time()
    out = llm.chat_json("Отвечай строго JSON.",
                        "Верни объект {\"fields\": [список имён полей из текста], \"period\": строка}.\n\n" + DOC)
    print(f"1) chat_json за {time.time() - t0:.1f}s:", json.dumps(out, ensure_ascii=False)[:200])

    t0 = time.time()
    yes = llm.binary_probs("Answer with exactly one word: YES or NO.",
                           "Есть ли в тексте поле времени?\n\n" + DOC)
    no = llm.binary_probs("Answer with exactly one word: YES or NO.",
                          "Упоминается ли в тексте Kafka?\n\n" + DOC)
    print(f"2) зонд за {time.time() - t0:.1f}s: P(yes/no) на «есть поле времени» = {yes}, "
          f"на «есть Kafka» = {no}  (ожидание: первое → YES, второе → NO, масса ≥ 0.5)")

    t0 = time.time()
    samples = llm.sample("Отвечай одной короткой фразой.",
                         "По какому полю выбирается последняя запись?\n\n" + DOC, n=5, temperature=0.9)
    print(f"3) n=5 за {time.time() - t0:.1f}s, вызовов всего {llm.stats['calls']}:",
          [s.strip()[:40] for s in samples])
    ok = (yes[0] > yes[1] and no[1] > no[0] and sum(yes) >= 0.5 and sum(no) >= 0.5
          and isinstance(out, dict) and len(samples) == 5)
    print("SMOKE", "OK" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

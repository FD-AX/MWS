from __future__ import annotations

import json
import random
import time
from typing import Any

from .config import Settings

ATTEMPTS = 4  # попыток на вызов: транспортные сбои и пустые ответы ретраятся с jitter


def _extract_json(text: str) -> Any:
    """Модели любят заворачивать JSON в ```-заборы и пояснения — достаём объект."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    start = min((i for i in (text.find("{"), text.find("[")) if i >= 0), default=-1)
    if start < 0:
        raise ValueError(f"В ответе модели нет JSON: {text[:200]!r}")
    for end in range(len(text), start, -1):
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            continue
    # Ремонт обрезанного max_tokens'ом ответа: режем до последнего целого объекта
    # массива и дозакрываем структуру ("...},{"неполный..." -> "...}]}").
    body = text[start:]
    cut = body.rfind("}")
    tries = 0
    while cut > 0 and tries < 8:
        for suffix in ("]}", "}]}", "\"]}"):
            try:
                return json.loads(body[:cut + 1] + suffix)
            except json.JSONDecodeError:
                continue
        cut = body.rfind("}", 0, cut)
        tries += 1
    raise ValueError(f"Не удалось распарсить JSON из ответа: {text[:200]!r}")


def aggregate_yes_no(top_tokens: list[tuple[str, float]],
                     pos: str = "YES", neg: str = "NO") -> tuple[float, float]:
    """Суммирует вероятностную массу top-токенов в P(pos)/P(neg).
    Токен засчитывается, если он префикс слова или слово — его префикс
    (BPE может отдать 'YES', 'YE', ' YES' и т.п.)."""
    p_pos = p_neg = 0.0
    for token, prob in top_tokens:
        t = token.strip().upper()
        if not t:
            continue
        if pos.startswith(t) or t.startswith(pos):
            p_pos += prob
        elif neg.startswith(t) or t.startswith(neg):
            p_neg += prob
    return p_pos, p_neg


class LLM:
    def __init__(self, settings: Settings):
        from openai import OpenAI  # ленивый импорт: --no-llm работает без пакета

        self._client = OpenAI(base_url=settings.base_url, api_key=settings.api_key)
        self._model = settings.model
        self._no_temperature = False  # reasoning-модели OpenAI не принимают temperature
        self._use_completion_tokens = False  # gpt-5.x: max_completion_tokens вместо max_tokens
        # Учёт вызовов/токенов (метрики воркера, стоимость документа)
        self.stats = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0}

    def _account(self, resp) -> None:
        self.stats["calls"] += 1
        usage = getattr(resp, "usage", None)
        if usage is not None:
            self.stats["prompt_tokens"] += getattr(usage, "prompt_tokens", 0) or 0
            self.stats["completion_tokens"] += getattr(usage, "completion_tokens", 0) or 0

    def _chat(self, system: str, user: str, temperature: float = 0.0, n: int = 1,
              max_tokens: int = 1600) -> list[str]:
        # max_tokens ограничен: прокси RunPod (Cloudflare) рвёт запросы >120s,
        # а длинные генерации на медленных картах в окно не влезают.
        last_err: Exception | None = None
        budget_mult = 1
        for attempt in range(ATTEMPTS):
            kwargs = {} if self._no_temperature else {"temperature": temperature}
            if self._use_completion_tokens:
                # reasoning-модели тратят этот же бюджет на размышления — даём запас
                kwargs["max_completion_tokens"] = max(max_tokens * 4, 6000) * budget_mult
            else:
                kwargs["max_tokens"] = max_tokens
            try:
                resp = self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    n=n,
                    **kwargs,
                )
                self._account(resp)
                outs = [c.message.content or "" for c in resp.choices]
                if any(o.strip() for o in outs):
                    return outs
                # Пустой ответ (reasoning съел бюджет / сбой генерации) — это не успех:
                # раньше уходил дальше как '' и ронял проход «В ответе модели нет JSON».
                finish = (getattr(resp.choices[0], "finish_reason", None)
                          if resp.choices else None)
                last_err = RuntimeError(f"пустой ответ модели (finish_reason={finish})")
                if finish == "length":
                    budget_mult *= 2
            except Exception as e:  # noqa: BLE001 - ретраим любой сбой транспорта
                if "temperature" in str(e) and not self._no_temperature:
                    self._no_temperature = True
                    continue  # повтор без параметра, попытку не тратим
                if "max_completion_tokens" in str(e) and not self._use_completion_tokens:
                    self._use_completion_tokens = True
                    continue
                last_err = e
            time.sleep(2 * (attempt + 1) + random.uniform(0.0, 1.5))  # jitter
        raise RuntimeError(f"LLM недоступна после {ATTEMPTS} попыток: {last_err}")

    def chat_json(self, system: str, user: str, temperature: float = 0.0) -> Any:
        return _extract_json(self._chat(system, user, temperature)[0])

    def binary_probs(self, system: str, user: str,
                     pos: str = "YES", neg: str = "NO") -> tuple[float, float]:
        """Числовой сигнал из логитов (H10): P(pos)/P(neg) первого токена ответа.
        Требует бэкенд с поддержкой logprobs (gpt-4.1-*, vLLM; reasoning gpt-5.x — нет)."""
        import math

        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            max_tokens=1, temperature=0, logprobs=True, top_logprobs=10,
        )
        self._account(resp)
        content = resp.choices[0].logprobs.content
        if not content:
            return 0.0, 0.0
        tops = [(t.token, math.exp(t.logprob)) for t in content[0].top_logprobs]
        return aggregate_yes_no(tops, pos, neg)

    def sample(self, system: str, user: str, n: int = 5, temperature: float = 0.9) -> list[str]:
        """n независимых сэмплов (для semantic entropy). Некоторые локальные бэкенды
        не поддерживают n>1 — тогда добираем отдельными вызовами."""
        try:
            outs = self._chat(system, user, temperature, n=n, max_tokens=200)
            if len(outs) == n:
                return outs
        except Exception:
            outs = []
        while len(outs) < n:
            outs.extend(self._chat(system, user, temperature, max_tokens=200))
        return outs[:n]

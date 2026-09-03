from __future__ import annotations

import json
import time
from typing import Any

from .config import Settings


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
    raise ValueError(f"Не удалось распарсить JSON из ответа: {text[:200]!r}")


class LLM:
    def __init__(self, settings: Settings):
        from openai import OpenAI  # ленивый импорт: --no-llm работает без пакета

        self._client = OpenAI(base_url=settings.base_url, api_key=settings.api_key)
        self._model = settings.model
        self._no_temperature = False  # reasoning-модели OpenAI не принимают temperature

    def _chat(self, system: str, user: str, temperature: float = 0.0, n: int = 1,
              max_tokens: int = 1600) -> list[str]:
        # max_tokens ограничен: прокси RunPod (Cloudflare) рвёт запросы >120s,
        # а длинные генерации на медленных картах в окно не влезают.
        last_err: Exception | None = None
        for attempt in range(3):
            kwargs = {} if self._no_temperature else {"temperature": temperature}
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
                return [c.message.content or "" for c in resp.choices]
            except Exception as e:  # noqa: BLE001 - ретраим любой сбой транспорта
                if "temperature" in str(e) and not self._no_temperature:
                    self._no_temperature = True
                    continue  # повтор без параметра, попытку не тратим
                last_err = e
                time.sleep(2 * (attempt + 1))
        raise RuntimeError(f"LLM недоступна после 3 попыток: {last_err}")

    def chat_json(self, system: str, user: str, temperature: float = 0.0) -> Any:
        return _extract_json(self._chat(system, user, temperature)[0])

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

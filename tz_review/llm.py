from __future__ import annotations

import json
import random
import time
from typing import Any

from .config import Settings

ATTEMPTS = 4  # попыток на вызов: транспортные сбои и пустые ответы ретраятся с jitter

# Системная преамбула harmony (gpt-oss): reasoning low — зонду нужен только первый токен ответа.
HARMONY_SYSTEM = ("You are ChatGPT, a large language model trained by OpenAI.\n"
                  "Knowledge cutoff: 2024-06\n\nReasoning: low\n\n"
                  "# Valid channels: analysis, commentary, final. "
                  "Channel must be included for every message.")


def harmony_prompt(system: str, user: str) -> str:
    """Raw-промпт в формате harmony с уже открытым каналом final: следующий токен,
    который сгенерирует gpt-oss, — первый токен ответа (а не служебный <|channel|>)."""
    return ("<|start|>system<|message|>" + HARMONY_SYSTEM + "<|end|>"
            "<|start|>developer<|message|># Instructions\n\n" + system + "<|end|>"
            "<|start|>user<|message|>" + user + "<|end|>"
            "<|start|>assistant<|channel|>final<|message|>")


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
    # strict=False: открытые модели кладут сырые переносы строк внутрь цитат-строк
    # (табличные цитаты gpt-oss) — по стандарту это невалидно, по смыслу — нормально.
    for end in range(len(text), start, -1):
        try:
            return json.loads(text[start:end], strict=False)
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
                return json.loads(body[:cut + 1] + suffix, strict=False)
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
        self._floor = int(getattr(settings, "max_tokens_floor", 0) or 0)
        self._reasoning = getattr(settings, "reasoning_effort", None)
        self._probe_mode = getattr(settings, "probe_mode", "chat") or "chat"
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
        max_tokens = max(max_tokens, self._floor)  # reasoning-модели на pod: пол бюджета
        for attempt in range(ATTEMPTS):
            kwargs = {} if self._no_temperature else {"temperature": temperature}
            if self._use_completion_tokens:
                # reasoning-модели тратят этот же бюджет на размышления — даём запас
                kwargs["max_completion_tokens"] = max(max_tokens * 4, 6000) * budget_mult
            else:
                kwargs["max_tokens"] = max_tokens * budget_mult
            if self._reasoning:
                kwargs["extra_body"] = {"reasoning_effort": self._reasoning}
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
                self.last_finish = (getattr(resp.choices[0], "finish_reason", None)
                                    if resp.choices else None)
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

    def chat_json(self, system: str, user: str, temperature: float = 0.0,
                  max_tokens: int = 1600) -> Any:
        """JSON-ответ с повтором: обрезанный (finish_reason=length) или битый JSON
        не роняет проход — повторяем с удвоенным бюджетом (EXP-15: gpt-oss на doc3)."""
        last_err: Exception | None = None
        for attempt in range(3):
            text = self._chat(system, user, temperature, max_tokens=max_tokens)[0]
            try:
                return _extract_json(text)
            except ValueError as e:
                last_err = e
                if getattr(self, "last_finish", None) == "length" or attempt == 0:
                    max_tokens *= 2
        raise ValueError(f"JSON не получен за 3 попытки: {last_err}")

    def binary_probs(self, system: str, user: str,
                     pos: str = "YES", neg: str = "NO") -> tuple[float, float]:
        """Числовой сигнал из логитов (H10): P(pos)/P(neg) первого токена ответа.
        Требует бэкенд с поддержкой logprobs (gpt-4.1-*, vLLM; reasoning gpt-5.x — нет)."""
        import math

        if self._probe_mode == "harmony":
            return self._binary_probs_harmony(system, user, pos, neg)
        if self._probe_mode == "sample":
            return self._binary_probs_sample(system, user, pos, neg)
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

    def _binary_probs_harmony(self, system: str, user: str,
                              pos: str, neg: str) -> tuple[float, float]:
        """gpt-oss через vLLM: в chat-режиме первый токен — <|channel|>analysis…, поэтому
        зонд идёт через /v1/completions с raw harmony-промптом и открытым каналом final."""
        import math

        last_err: Exception | None = None
        for attempt in range(ATTEMPTS):
            try:
                resp = self._client.completions.create(
                    model=self._model, prompt=harmony_prompt(system, user),
                    max_tokens=1, temperature=0, logprobs=10,
                )
                self._account(resp)
                lp = resp.choices[0].logprobs
                if not lp or not lp.top_logprobs:
                    return 0.0, 0.0
                tops = [(tok, math.exp(v)) for tok, v in lp.top_logprobs[0].items()]
                return aggregate_yes_no(tops, pos, neg)
            except Exception as e:  # noqa: BLE001
                last_err = e
                time.sleep(2 * (attempt + 1) + random.uniform(0.0, 1.5))
        raise RuntimeError(f"logprob-зонд недоступен после {ATTEMPTS} попыток: {last_err}")

    PROBE_SAMPLES = 8
    _RU = {"ДА": "YES", "НЕТ": "NO"}

    def _binary_probs_sample(self, system: str, user: str,
                             pos: str, neg: str) -> tuple[float, float]:
        """Reasoning-модели (gpt-oss): первый токен ДО размышления смещён и зависит от раскладки
        промпта (EXP-19: «есть ли Kafka» → YES 0.97 при документе в конце), а ПОСЛЕ размышления
        вырожден (1.0 при t=0). Поэтому P(pos)/P(neg) оцениваем Монте-Карло: n коротких ответов
        при t=1 одним вызовом (vLLM батчит n), доля YES/NO среди первых слов."""
        outs = self._chat(system, user, temperature=1.0, n=self.PROBE_SAMPLES, max_tokens=400)
        votes: list[tuple[str, float]] = []
        for o in outs:
            first = (o.strip().split() or [""])[0].strip(".,!:;«»\"'*").upper()
            votes.append((self._RU.get(first, first), 1.0 / max(len(outs), 1)))
        return aggregate_yes_no(votes, pos, neg)

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

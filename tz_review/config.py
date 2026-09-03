from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ENV_VARS = ("TZR_BASE_URL", "TZR_API_KEY", "TZR_MODEL")


def load_dotenv(path: Path | None = None) -> None:
    """Мини-загрузчик .env без зависимостей. Не перетирает уже выставленные переменные."""
    p = path or ROOT / ".env"
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


@dataclass(frozen=True)
class Settings:
    base_url: str
    api_key: str
    model: str
    # Пол бюджета генерации на вызов: reasoning-модели (gpt-oss, gpt-5.x через pod)
    # тратят тот же max_tokens на размышления — 1600 им мало, пустой content.
    max_tokens_floor: int = 0
    # Уровень размышлений (low/medium/high) — extra_body.reasoning_effort; None = не слать.
    reasoning_effort: str | None = None


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


def settings_or_die() -> Settings:
    """Fail-fast: LLM-проходы не запускаются с дефолтами — все переменные явные."""
    load_dotenv()
    missing = [v for v in ENV_VARS if not os.environ.get(v)]
    if missing:
        raise SystemExit(
            "Не заданы переменные окружения: " + ", ".join(missing)
            + "\nСкопируй .env.example в .env и заполни, либо запусти с --no-llm."
        )
    return Settings(
        base_url=os.environ["TZR_BASE_URL"],
        api_key=os.environ["TZR_API_KEY"],
        model=os.environ["TZR_MODEL"],
        max_tokens_floor=_int_env("TZR_MAX_TOKENS", 0),
        reasoning_effort=os.environ.get("TZR_REASONING_EFFORT") or None,
    )


def openai_settings_or_die() -> Settings:
    """Второй бэкенд (референс/кросс-чек другого семейства моделей)."""
    load_dotenv()
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise SystemExit("OPENAI_API_KEY не задан в .env — бэкенд openai недоступен.")
    return Settings(
        base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        api_key=key,
        model=os.environ.get("OPENAI_MODEL", "gpt-5.5"),
    )


def openai_logprob_settings() -> Settings | None:
    """Модель с поддержкой logprobs для числовых зондов (H10); reasoning не умеют."""
    load_dotenv()
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        return None
    return Settings(
        base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        api_key=key,
        model=os.environ.get("OPENAI_MODEL_LOGPROB", "gpt-4.1-mini"),
    )


def openai_cheap_settings() -> Settings | None:
    """Дешёвая модель для массовых мелких вызовов (entropy-сэмплы, канонизация)."""
    load_dotenv()
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        return None
    return Settings(
        base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        api_key=key,
        model=os.environ.get("OPENAI_MODEL_CHEAP", "gpt-5.4-mini"),
    )

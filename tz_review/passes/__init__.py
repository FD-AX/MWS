from __future__ import annotations

from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


def load_prompt(name: str, **subs: str) -> str:
    """Шаблоны используют <<VAR>>-плейсхолдеры, чтобы фигурные скобки JSON-примеров
    не конфликтовали со str.format."""
    text = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    for key, value in subs.items():
        text = text.replace(f"<<{key.upper()}>>", value)
    return text

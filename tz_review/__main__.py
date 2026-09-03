from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import settings_or_die
from .pipeline import review
from .report import to_json, to_markdown
from .rubric import load_rubric


def main(argv: list[str] | None = None) -> int:
    try:  # cp1251-консоли Windows не умеют эмодзи вердикта
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    parser = argparse.ArgumentParser(
        prog="tz_review",
        description="Предварительное LLM-ревью ТЗ на потоки и витрины данных.",
    )
    parser.add_argument("path", help="Путь к файлу ТЗ (markdown или plain text)")
    parser.add_argument("--no-llm", action="store_true",
                        help="Только детерминированный слой (без API-ключа)")
    parser.add_argument("--entropy", action="store_true",
                        help="Включить semantic-entropy проход (дорого: N сэмплов на слот)")
    parser.add_argument("--baseline", action="store_true",
                        help="Режим V0b: один сильный вызов вместо конвейера (для замера дельт)")
    parser.add_argument("--backend", choices=["pod", "openai"], default="pod",
                        help="LLM-бэкенд: pod (TZR_*) или openai (OPENAI_*)")
    parser.add_argument("--threshold", type=float, default=3.0,
                        help="Порог критика 0-10 (default: 3.0)")
    parser.add_argument("--out", default="out", help="Каталог для отчётов (default: out)")
    args = parser.parse_args(argv)

    src = Path(args.path)
    if not src.exists():
        print(f"Файл не найден: {src}", file=sys.stderr)
        return 2
    text = src.read_text(encoding="utf-8")
    rubric = load_rubric()

    llm = None
    if not args.no_llm:
        from .config import openai_settings_or_die
        from .llm import LLM
        llm = LLM(openai_settings_or_die() if args.backend == "openai"
                  else settings_or_die())

    result = review(text, rubric, llm,
                    use_entropy=args.entropy, use_baseline=args.baseline,
                    critic_threshold=args.threshold)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / f"{src.stem}.report.md"
    json_path = out_dir / f"{src.stem}.findings.json"
    md_path.write_text(to_markdown(result, doc_name=src.name), encoding="utf-8")
    json_path.write_text(to_json(result), encoding="utf-8")

    from .report import verdict
    light, vtext = verdict(result)
    print(f"{light} {vtext}")
    print(f"Находок: {len(result.findings)} "
          f"(отсеяно критиком: {len(result.rejected)}, "
          f"отброшено верификацией: {len(result.dropped)})")
    print(f"Отчёт: {md_path}\nJSON:  {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

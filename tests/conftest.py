"""Общие фикстуры pytest.

synth/out (испорченные документы + голды) в .gitignore: в свежем клоне их нет, и тесты,
читающие синтетику (tests/test_doc_graph_refs.py), падали с FileNotFoundError.
Собираем её из рецептов перед сессией — детерминированно и дешевле 0.1 с.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from synth.inject import build_all  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def synth_outputs() -> list[tuple[Path, Path]]:
    """Все рецепты synth/recipes/*.yaml → synth/out/. Autouse: действует и на unittest.TestCase."""
    return build_all(ROOT)

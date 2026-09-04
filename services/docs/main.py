"""Сервис документов: любой вход (текст, .md/.txt, .docx, .pdf) → markdown с таблицами,
разбор секций, хэш документа. Ревьюер дальше работает только с markdown.

    POST /normalize  (multipart: file | form: text) -> {markdown, doc_hash, chars, sections[]}
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from prometheus_client import Counter, Histogram, make_asgi_app

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from services.common import doc_hash  # noqa: E402
from tz_review.document import normalize as norm_text, parse  # noqa: E402
from tz_review.rubric import load_rubric  # noqa: E402

_RUBRIC = load_rubric()
# Имена разделов, которые в PDF/DOCX-выгрузках стоят голой строкой без разметки:
# официальный шаблон + алиасы обязательных разделов + фактические заголовки доков МТС.
_KNOWN_HEADINGS = {norm_text(n) for n in _RUBRIC.get("official_sections", [])}
for req in _RUBRIC.get("required_sections", []):
    _KNOWN_HEADINGS.update(norm_text(a) for a in [req["name"], *req.get("aliases", [])])
_KNOWN_HEADINGS.update(norm_text(n) for n in (
    "Бизнес-требования", "Способ загрузки", "Регламент", "Глубина данных", "Команда",
    "Алгоритм расчёта", "Алгоритм расчета", "Требования к агрегату", "Структура данных CDM",
    "Источники данных", "Описание", "Контроль качества", "Нефункциональные требования",
    "Источники и приёмники данных", "Источники и приемники данных", "Приёмники данных",
    "Алгоритм обработки потока", "Структура данных", "FAQ", "История изменений",
))


def _is_known_heading(key: str) -> bool:
    """Точное совпадение или известное имя как префикс: «FAQ (обобщённо…)»,
    «Алгоритм обработки потока» при известном «Алгоритм обработки»."""
    return key in _KNOWN_HEADINGS or any(key.startswith(k + " ") or key.startswith(k + " (")
                                         for k in _KNOWN_HEADINGS if len(k) >= 4)
# Нумерация обязана быть с точкой/скобкой: «1 FIELD_X string …» из расплющенных
# PDF-таблиц заголовком не считается.
_NUM_HEADING = re.compile(r"^(\d+(?:\.\d+)*)[.)]\s+([А-ЯЁA-Z][^.|]{2,60})$")


def promote_headings(md: str) -> str:
    """Короткие строки, совпадающие с именем раздела шаблона или нумерованные
    («1. Источники данных»), становятся заголовками markdown, если в тексте
    заголовков ещё нет. Иначе секционный парсер видит один сплошной документ."""
    if re.search(r"^#{1,6}\s", md, flags=re.M):
        return md
    out: list[str] = []
    for line in md.splitlines():
        s = line.strip()
        if 3 <= len(s) <= 70 and not s.endswith((".", ";", ",")) and not s.startswith("|"):
            key = norm_text(s.rstrip(":"))
            if _is_known_heading(key) or _NUM_HEADING.match(s):
                out.append(f"## {s.rstrip(':')}")
                continue
        out.append(line)
    return "\n".join(out)

app = FastAPI(title="tz_review docs", version="0.1")
app.mount("/metrics", make_asgi_app())

NORMALIZED = Counter("tzr_docs_normalized_total", "Нормализованных документов", ["kind", "outcome"])
CHARS = Histogram("tzr_docs_chars", "Длина документа после нормализации, символов",
                  buckets=(2000, 5000, 10000, 17000, 28000, 50000, 100000))


def _table_to_md(rows: list[list[str | None]]) -> str:
    rows = [[(c or "").replace("\n", " ").strip() for c in r] for r in rows if r]
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    out = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * width]
    out += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(out)


def docx_to_md(data: bytes) -> str:
    import mammoth

    return mammoth.convert_to_markdown(io.BytesIO(data)).value


def pdf_to_md(data: bytes) -> str:
    """Текст постранично + таблицы markdown'ом (pdfplumber). Текст таблиц может
    дублироваться в потоке страницы — для ревью это безопасно (цитаты якорятся)."""
    import pdfplumber

    parts: list[str] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if text.strip():
                parts.append(text)
            for table in page.extract_tables() or []:
                md = _table_to_md(table)
                if md:
                    parts.append(md)
    return "\n\n".join(parts)


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.post("/normalize")
async def normalize_endpoint(file: UploadFile | None = File(None), text: str | None = Form(None)):
    if file is not None:
        data = await file.read()
        name = (file.filename or "").lower()
        try:
            if name.endswith(".docx"):
                kind, md = "docx", docx_to_md(data)
            elif name.endswith(".pdf"):
                kind, md = "pdf", pdf_to_md(data)
            else:
                kind, md = "text", data.decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            NORMALIZED.labels(kind if "kind" in dir() else "unknown", "error").inc()
            raise HTTPException(422, f"не удалось разобрать {name}: {e}") from e
    elif text:
        kind, md = "text", text
    else:
        raise HTTPException(400, "нужен file (md/txt/docx/pdf) или text")

    md = md.replace("\r\n", "\n").strip() + "\n"
    if not md.strip():
        NORMALIZED.labels(kind, "empty").inc()
        raise HTTPException(422, "документ пуст после нормализации")
    md = promote_headings(md)
    doc = parse(md)
    NORMALIZED.labels(kind, "ok").inc()
    CHARS.observe(len(md))
    return {
        "markdown": md,
        "doc_hash": doc_hash(md),
        "chars": len(md),
        "kind": kind,
        "sections": [{"title": s.title, "chars": len(s.body)} for s in doc.sections],
    }

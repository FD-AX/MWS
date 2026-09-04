"""Клиент API ревью для фронтенда (Streamlit): отправить документ → ждать → собрать ReviewResult.

Включается переменной TZR_API_URL (например, http://api:8080 в compose). Без неё фронт
гоняет конвейер в своём процессе, как раньше. Зависимостей сверх стандартной библиотеки нет.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
import uuid
from typing import Any, Callable

from .pipeline import ReviewResult
from .schema import Finding


def api_url() -> str | None:
    url = (os.environ.get("TZR_API_URL") or "").strip().rstrip("/")
    return url or None


def _multipart(fields: dict[str, str], files: dict[str, tuple[str, bytes, str]]) -> tuple[bytes, str]:
    boundary = "----tzr" + uuid.uuid4().hex
    out = bytearray()
    for name, value in fields.items():
        out += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n").encode("utf-8")
    for name, (filename, data, ctype) in files.items():
        out += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; filename=\"{filename}\"\r\n"
                f"Content-Type: {ctype}\r\n\r\n").encode("utf-8") + data + b"\r\n"
    out += f"--{boundary}--\r\n".encode("utf-8")
    return bytes(out), f"multipart/form-data; boundary={boundary}"


def _request(method: str, path: str, body: bytes | None = None, ctype: str | None = None,
             timeout: float = 120) -> dict[str, Any]:
    base = api_url()
    if not base:
        raise RuntimeError("TZR_API_URL не задан")
    headers = {"Accept": "application/json"}
    if ctype:
        headers["Content-Type"] = ctype
    req = urllib.request.Request(base + path, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"API {e.code}: {detail}") from e


def submit_review(text: str, filename: str = "документ.md") -> dict[str, Any]:
    """POST /reviews как файл (имя сохраняется в истории; docs-сервис восстановит заголовки)."""
    name = filename if filename.lower().endswith((".md", ".txt")) else filename.rsplit(".", 1)[0] + ".md"
    body, ctype = _multipart({}, {"file": (name, text.encode("utf-8"), "text/markdown")})
    return _request("POST", "/reviews", body, ctype)


def submit_review_file(filename: str, data: bytes, content_type: str | None = None) -> dict[str, Any]:
    """POST /reviews исходным файлом (pdf/docx/md/txt): таблицы и заголовки восстановит docs-сервис."""
    ctype = content_type or {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".md": "text/markdown",
    }.get(filename[filename.rfind("."):].lower() if "." in filename else "", "application/octet-stream")
    body, mtype = _multipart({}, {"file": (filename, data, ctype)})
    return _request("POST", "/reviews", body, mtype)


def get_review(job_id: str) -> dict[str, Any]:
    return _request("GET", f"/reviews/{job_id}", timeout=30)


def list_reviews(limit: int = 20) -> list[dict[str, Any]]:
    data = _request("GET", f"/reviews?limit={limit}", timeout=30)
    return data if isinstance(data, list) else []


def get_document_text(doc_hash: str) -> str:
    """Нормализованный markdown документа из истории (после docs-сервиса)."""
    data = _request("GET", f"/documents/{doc_hash}/text", timeout=30)
    return str(data.get("markdown") or "")


def document_history(doc_hash: str) -> dict[str, Any]:
    return _request("GET", f"/documents/{doc_hash}/history", timeout=30)


def send_feedback(finding_id: int, vote: int, author: str | None = None, comment: str | None = None) -> dict[str, Any]:
    body = json.dumps({"vote": vote, "author": author, "comment": comment}).encode("utf-8")
    return _request("POST", f"/findings/{finding_id}/feedback", body, "application/json", timeout=30)


def finding_db_ids(job: dict[str, Any]) -> dict[str, int]:
    """fid → id находки в базе (ключ для 👍/👎)."""
    res = job.get("result") or {}
    return {f["fid"]: f["db_id"] for f in res.get("findings", []) if f.get("fid") and f.get("db_id")}


def wait_for_review(job_id: str, on_progress: Callable[[dict[str, Any]], None] | None = None,
                    poll_s: float = 3.0, timeout_s: float = 1800) -> dict[str, Any]:
    """Опрос статуса до done/failed; on_progress получает payload['progress'] и статус."""
    t0 = time.time()
    while True:
        job = get_review(job_id)
        if on_progress is not None:
            info = dict(job.get("progress") or {})
            info["status"] = job.get("status")
            on_progress(info)
        if job.get("status") in ("done", "failed"):
            return job
        if time.time() - t0 > timeout_s:
            raise TimeoutError(f"ревью {job_id} не завершилось за {timeout_s:.0f} с")
        time.sleep(poll_s)


def _findings(items: list[dict[str, Any]]) -> list[Finding]:
    """Находки из JSON API. Лишние поля (db_id) отбрасываем; запись с невалидным
    значением (например, неизвестная severity) приводим к medium, а не роняем UI."""
    allowed = set(Finding.model_fields)
    out: list[Finding] = []
    for f in items or []:
        data = {k: v for k, v in (f or {}).items() if k in allowed}
        try:
            out.append(Finding(**data))
        except Exception:  # noqa: BLE001
            data["severity"] = "medium"
            data.setdefault("why", "")
            data.setdefault("category", "unknown")
            try:
                out.append(Finding(**data))
            except Exception:  # noqa: BLE001 — совсем битая запись: пропускаем
                continue
    return out


def result_from_payload(job: dict[str, Any]) -> ReviewResult:
    """ReviewResult из ответа API — чтобы фронт рендерил его теми же виджетами, что и локальный прогон."""
    res = job.get("result") or {}
    return ReviewResult(
        findings=_findings(res.get("findings", [])),
        rejected=_findings(res.get("rejected", [])),
        dropped=_findings(res.get("dropped", [])),
        statuses=dict(res.get("checklist_statuses") or {}),
        anchoring=float(res.get("anchoring_rate") or job.get("anchoring") or 1.0),
        passes_run=["api", str(job.get("model") or "")],
    )

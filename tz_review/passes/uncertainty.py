from __future__ import annotations

import math
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from ..llm import LLM
from ..schema import Finding
from . import load_prompt

N_SAMPLES = 5
TEMPERATURE = 0.9
ENTROPY_THRESHOLD = 0.9  # бит; калибровать бэктестом на исторических корректировках


_HARD = re.compile(r"[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+|\d+(?:[:.,]\d+)*|\b(?:utc|msk|gmt)\b|\b(?:да|нет|no|yes)\b|нет ответа",
                   re.IGNORECASE)
_STOP = {"в", "на", "по", "из", "за", "и", "с", "для", "данных", "данные", "поле", "поля", "то", "есть",
         "это", "что", "как", "а", "но", "или", "у", "о", "об", "при", "к", "до", "от", "не"}


def _canon(answer: str) -> str:
    """Канонизация ответа перед кластеризацией (EXP-21).
    Пять сэмплов gpt-oss-120b при t=0.9 говорят одно и то же разными словами
    («ежемесячно — 2‑го числа в 03:00 UTC» / «ежемесячный запуск 2‑го числа в 03:00 UTC»),
    и лексическая канонизация считала это разными смыслами: 18–27 ложных entropy-находок
    на документ (EXP-19, матрица m4). Теперь ключ кластера — «жёсткие» токены: идентификаторы
    FIELD_*/TABLE_*, числа и времена, полярность да/нет, «нет ответа». Слова — только запасной ключ,
    когда жёстких токенов нет, и тогда сравниваются основы (первые 5 символов), чтобы склеивать формы слов."""
    a = answer.strip().replace("ё", "е").replace("Ё", "Е").replace("‑", "-").replace(" ", " ")
    hard = [h.lower() for h in _HARD.findall(a)]
    hard = [re.sub(r"[-]?го$", "", h) for h in hard]  # «2-го» → «2»
    if hard:
        return "H:" + " ".join(sorted(set(hard)))
    low = re.sub(r"[«»\"'`.,;:!()]", "", a.lower())
    low = re.sub(r"\s+", " ", low)
    stems = sorted({t[:5] for t in low.split() if t not in _STOP and len(t) > 1})
    return "S:" + " ".join(stems) if stems else low


def semantic_entropy(answers: list[str]) -> tuple[float, list[list[str]]]:
    """Semantic entropy (Kuhn/Farquhar, Nature 2024) в лайт-версии: кластеризуем
    сэмплированные ответы по смыслу и считаем энтропию распределения кластеров.
    Высокая энтропия = разные «читатели» извлекают из документа разные ответы."""
    clusters: dict[str, list[str]] = {}
    for ans in answers:
        clusters.setdefault(_canon(ans), []).append(ans)
    counts = Counter({k: len(v) for k, v in clusters.items()})
    total = sum(counts.values())
    entropy = -sum((c / total) * math.log2(c / total) for c in counts.values())
    return entropy, list(clusters.values())


def run(doc_text: str, rubric: dict[str, Any], statuses: dict[str, str],
        llm: LLM) -> list[Finding]:
    """Entropy-проход: слоты, которые чеклист посчитал закрытыми (OK), перепроверяем
    на неоднозначность. Вопрос задаётся N раз с температурой; если ответы
    расходятся по смыслу — документ отвечает на вопрос неоднозначно, даже если
    формально отвечает. Это находки класса «разработчики поймут по-разному»."""
    by_id = {q["id"]: q for q in rubric["checklist"]}
    findings: list[Finding] = []

    ok_slots = [qid for qid, s in statuses.items() if s == "OK"]

    def sample_slot(qid: str) -> tuple[str, list[str]]:
        q = by_id[qid]
        prompt = load_prompt("entropy_answer", question=q["question"], document=doc_text)
        return qid, llm.sample("Отвечай одной короткой фразой.", prompt,
                               n=N_SAMPLES, temperature=TEMPERATURE)

    # Слоты независимы — сэмплируем параллельно (иначе 27 слотов × 5 сэмплов
    # последовательно превращают проход в десятки минут).
    with ThreadPoolExecutor(max_workers=6) as pool:
        sampled = dict(pool.map(sample_slot, ok_slots))

    for qid in ok_slots:
        q = by_id[qid]
        answers = sampled[qid]
        entropy, clusters = semantic_entropy(answers)
        if entropy < ENTROPY_THRESHOLD:
            continue
        variants = " | ".join(sorted({c[0].strip() for c in clusters})[:4])
        findings.append(Finding(
            category=f"entropy:{qid}",
            severity="medium",
            section=q["aspect"],
            missing=True,  # цитаты нет: находка про свойство документа, не про фразу
            why=(f"Документ формально отвечает на вопрос «{q['question']}», но {N_SAMPLES} "
                 f"независимых прочтений дали разные ответы ({variants}). "
                 f"Semantic entropy = {entropy:.2f} бит — место будет понято по-разному."),
            ask=f"Сформулируй ответ на «{q['question']}» так, чтобы он читался однозначно.",
            source_pass="uncertainty",
            entropy=round(entropy, 3),
        ))
    return findings

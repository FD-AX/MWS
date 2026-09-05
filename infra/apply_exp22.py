"""EXP-22: применить правила применимости v2 к рубрике (запускать ПОСЛЕ EXP-20/21, см. experiments/EXP-22-na-rules-v2.md).

    python infra/apply_exp22.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FULL_REWRITE = r"полн(ая|ой|ую|ый|ое)\s+(перезапис|перезагруз|пересч[её]т|перегруз)"
ORD_APPLIES = (r"последн\w*\s+(по времени|запис|верси|значен|состоян|актуальн)|актуальн\w+\s+(запис|верси|значен)"
               r"|latest record|last record|max\(|min\(")
# NUL-02 (краевые случаи формул) — только при явном делении на переменную/агрегат, не на константу («/ 1024»)
NUL2_APPLIES = (r"\)\s*/\s*[A-Za-zА-Яа-я_(]|[A-Za-zА-Яа-я_)]\s*/\s*\(|/\s*(?:nullif|sum|count|avg)\b"
                r"|\bделени[еяю]\s+на\b|знаменател")
# MAP-02 (точность/длина типов) — только если документ вообще использует типы с точностью
MAP2_APPLIES = r"decimal\s*\(|numeric\s*\(|varchar\s*\(|char\s*\(|точност[ьи]\s+(?:типа|данных|поля)"


def patch_yaml(path: Path, slot_id: str, key: str, value: str) -> None:
    text = path.read_text(encoding="utf-8")
    m = re.search(rf"(  - id: {re.escape(slot_id)}\n)((?:    .*\n)+)", text)
    if not m:
        raise SystemExit(f"{path.name}: слот {slot_id} не найден")
    block = m.group(2)
    line = f"    {key}: '{value}'\n"
    if re.search(rf"^    {key}:", block, re.M):
        block = re.sub(rf"^    {key}:.*\n", line, block, count=1, flags=re.M)
    else:
        block = block + line
    text = text[:m.start(2)] + block + text[m.end(2):]
    path.write_text(text, encoding="utf-8")
    print(f"{path.name}: {slot_id}.{key} = {value}")


def main() -> int:
    rubric = ROOT / "tz_review" / "rubric.yaml"
    extra = ROOT / "tz_review" / "rubric_extra.yaml"
    patch_yaml(rubric, "INC-01", "not_if", FULL_REWRITE)
    patch_yaml(rubric, "INC-03", "not_if", FULL_REWRITE)
    patch_yaml(extra, "ORD-01", "applies_if", ORD_APPLIES)
    patch_yaml(rubric, "NUL-02", "applies_if", NUL2_APPLIES)
    patch_yaml(rubric, "MAP-02", "applies_if", MAP2_APPLIES)
    # Проверка: рубрика читается, правила применяются к нашим документам как ожидалось
    from tz_review.passes.checklist import split_applicable
    from tz_review.rubric import load_rubric
    r = load_rubric(extra=True)
    for name, p in (("doc3", "casedata/doc3_mart_devices.md"), ("clean", "synth/base/mart_traffic_official_clean.md"),
                    ("doc1", "casedata/doc1_stream_geo.md"), ("doc2", "casedata/doc2_source_cdr.md")):
        _, na = split_applicable(r["checklist"], (ROOT / p).read_text(encoding="utf-8"))
        print(f"  {name:6} NA: {sorted(x for x in na if x in ('INC-01', 'INC-03', 'ORD-01', 'NUL-02', 'MAP-02'))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

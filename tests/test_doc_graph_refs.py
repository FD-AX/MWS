import unittest
from pathlib import Path

from tz_review import document
from tz_review.passes import doc_graph

ROOT = Path(__file__).resolve().parent.parent

DOC = """# ТЗ

## 1. Структура данных
| Поле | Тип | Комментарий |
|---|---|---|
| FIELD_PROC_TS | timestamp | метка запуска DAG (детали — в разделе «Оркестрация») |

## 2. Регламент
Структуры таблиц приведены в разделе «Структура данных». См. также раздел „Регламент“.
"""


class SectionNameRefTests(unittest.TestCase):
    def test_reference_to_missing_section_by_name(self):
        fs = doc_graph.run(document.parse(DOC))
        broken = [f for f in fs if f.category == "graph:broken_ref"]
        self.assertEqual(len(broken), 1, [f.why for f in broken])
        self.assertIn("Оркестрация", broken[0].why)
        self.assertIn("в разделе «Оркестрация»", broken[0].quote)

    def test_existing_names_not_flagged(self):
        doc = DOC.replace("«Оркестрация»", "«Регламент»")
        fs = doc_graph.run(document.parse(doc))
        self.assertFalse([f for f in fs if f.category == "graph:broken_ref"])

    def test_v2hard_orchestration_reference_detected(self):
        text = (ROOT / "synth/out/mart_traffic_v2h.md").read_text(encoding="utf-8")
        fs = doc_graph.run(document.parse(text))
        self.assertTrue(any("Оркестрац" in (f.why or "") for f in fs if f.category == "graph:broken_ref"))

    def test_clean_base_has_no_name_refs_flagged(self):
        text = (ROOT / "synth/base/mart_traffic_official_clean.md").read_text(encoding="utf-8")
        fs = doc_graph.run(document.parse(text))
        self.assertFalse([f.why for f in fs if f.category == "graph:broken_ref" and "«" in (f.why or "")])


if __name__ == "__main__":
    unittest.main()

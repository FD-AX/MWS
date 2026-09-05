import unittest
from pathlib import Path

from tz_review import document
from tz_review.passes import uncertainty_graph as ug

ROOT = Path(__file__).resolve().parent.parent


class FakeLLM:
    def __init__(self, answers_by_name):
        self.answers_by_name = answers_by_name
        self.calls = 0

    def sample(self, system, user, n=5, temperature=0.9):
        self.calls += 1
        for name, answers in self.answers_by_name.items():
            if f"«{name}»" in user:
                return list(answers)
        return ["Определено однозначно."] * n


class NodeSelectionTests(unittest.TestCase):
    def test_doc3_nodes_are_cross_section_entities_without_placeholders(self):
        doc = document.parse((ROOT / "casedata/doc3_mart_devices.md").read_text(encoding="utf-8"))
        nodes = ug.select_nodes(doc)
        self.assertGreaterEqual(len(nodes), 5)
        names = [n["name"] for n in nodes]
        self.assertTrue(any(x.startswith("FIELD_") or x.startswith("TABLE_") for x in names))
        self.assertFalse(any(x.startswith(("USER_", "LINK_", "REGION_NAME")) for x in names), names)
        for n in nodes:
            self.assertGreaterEqual(len(n["sections"]), 2)
            self.assertTrue(n["quote"])

    def test_canon_removes_node_name_and_separates_meanings(self):
        a = ug.canon_node("FIELD_BIZ_DATE — дата сессии в источнике", "FIELD_BIZ_DATE")
        b = ug.canon_node("FIELD_BIZ_DATE — первое число месяца в витрине", "FIELD_BIZ_DATE")
        c = ug.canon_node("Дата сессии в источнике (FIELD_BIZ_DATE)", "FIELD_BIZ_DATE")
        self.assertNotEqual(a, b)
        self.assertEqual(a, c)


class GraphEntropyRunTests(unittest.TestCase):
    DOC = """# ТЗ

## Структура данных
| FIELD_BIZ_DATE | date | Дата бизнес-события |

## Алгоритм
Группировка по FIELD_BIZ_DATE, усечённой до первого числа месяца. Категория UNKNOWN — для NULL типа сети.

## Контроль качества
Доля UNKNOWN не более 5 %; FIELD_BIZ_DATE партиции равна первому числу месяца.
"""

    def test_divergent_definitions_produce_finding(self):
        doc = document.parse(self.DOC)
        llm = FakeLLM({"FIELD_BIZ_DATE": ["Дата сессии в источнике", "Дата события", "Первое число месяца в витрине",
                                          "Дата сессии", "Первое число месяца"]})
        fs = ug.run(doc, llm)
        cats = [f.category for f in fs]
        self.assertIn("gentropy:entity", cats)
        f = next(f for f in fs if "FIELD_BIZ_DATE" in f.why)
        self.assertEqual(f.source_pass, "uncertainty_graph")
        self.assertTrue(f.quote and "FIELD_BIZ_DATE" in f.quote)

    def test_consistent_definitions_produce_nothing(self):
        doc = document.parse(self.DOC)
        llm = FakeLLM({})
        self.assertEqual(ug.run(doc, llm), [])


if __name__ == "__main__":
    unittest.main()

import unittest

from tz_review.passes import quantities
from tz_review.passes import load_prompt


class FakeLLM:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def chat_json(self, system, user, **kw):
        self.calls.append(user)
        return self.payload


class QuantitiesPassTests(unittest.TestCase):
    def test_prompt_has_document_and_rules(self):
        p = load_prompt("quantities", document="ТЕКСТ-ДОКУМЕНТА")
        self.assertIn("ТЕКСТ-ДОКУМЕНТА", p)
        for marker in ("retention", "готов", "границы период", "findings"):
            self.assertIn(marker, p)

    def test_findings_parsed_with_pass_and_category(self):
        llm = FakeLLM({"quantities": [{"name": "retention", "value": "24 месяца", "section": "Регламент", "quote": "..."}],
                       "findings": [{"severity": "high", "section": "Контроль качества",
                                     "quote": "сверка на глубину 36 месяцев",
                                     "why": "Сверка 36 мес. при retention витрины 24 мес.", "ask": "Что сверять за 25–36 мес.?"},
                                    {"severity": "bogus", "quote": "x", "why": "y", "ask": "z"}]})
        fs = quantities.run("док", llm)
        self.assertEqual(len(fs), 2)
        self.assertEqual(fs[0].category, "doc:quantities")
        self.assertEqual(fs[0].source_pass, "quantities")
        self.assertEqual(fs[0].severity, "high")
        self.assertEqual(fs[1].severity, "medium")  # неизвестная severity → medium

    def test_empty_and_malformed_are_safe(self):
        self.assertEqual(quantities.run("док", FakeLLM({"findings": []})), [])
        self.assertEqual(quantities.run("док", FakeLLM({"findings": ["строка", 5]})), [])
        self.assertEqual(quantities.run("док", FakeLLM([1, 2])), [])


if __name__ == "__main__":
    unittest.main()

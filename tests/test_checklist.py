import unittest

from tz_review.passes import checklist

RUBRIC = {"checklist": [
    {"id": "Q1", "aspect": "a", "severity": "high", "question": "q1?"},
    {"id": "Q2", "aspect": "a", "severity": "high", "question": "q2?"},
    {"id": "Q3", "aspect": "b", "severity": "medium", "question": "q3?"},
]}


class PartialLLM:
    """Первый вызов теряет часть ответов (обрезанный JSON), повтор — отвечает на остаток."""

    def __init__(self):
        self.calls = []

    def chat_json(self, system, user, temperature=0.0):
        self.calls.append(user)
        if len(self.calls) == 1:
            return {"answers": [{"id": "Q1", "status": "OK", "quote": "x", "why": "", "ask": ""}]}
        return {"answers": [
            {"id": "Q2", "status": "MISSING", "quote": None, "why": "нет", "ask": "где?"},
            {"id": "Q3", "status": "UNCLEAR", "quote": "q", "why": "двояко", "ask": "уточни"},
        ]}


class SilentLLM:
    def chat_json(self, system, user, temperature=0.0):
        return {"answers": []}


class TestChecklistRetry(unittest.TestCase):
    def test_missing_answers_are_re_asked(self):
        llm = PartialLLM()
        findings, statuses = checklist.run("doc", RUBRIC, llm)
        self.assertEqual(len(llm.calls), 2)
        self.assertNotIn('"Q1"', llm.calls[1])  # повтор только по неотвеченным слотам
        self.assertIn('"Q2"', llm.calls[1])
        self.assertEqual(statuses, {"Q1": "OK", "Q2": "MISSING", "Q3": "UNCLEAR"})
        self.assertEqual(sorted(f.category for f in findings),
                         ["checklist:Q2", "checklist:Q3"])
        self.assertTrue(next(f for f in findings if f.category == "checklist:Q2").missing)

    def test_still_unanswered_becomes_unknown(self):
        findings, statuses = checklist.run("doc", RUBRIC, SilentLLM())
        self.assertEqual(findings, [])
        self.assertEqual(set(statuses.values()), {"UNKNOWN"})


if __name__ == "__main__":
    unittest.main()

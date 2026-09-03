import unittest

from tz_review.llm import LLM, _extract_json


class TestExtractJson(unittest.TestCase):
    def test_raw_newline_inside_string_is_tolerated(self):
        # gpt-oss кладёт сырые переносы строк в цитаты (табличные строки) — strict=False
        raw = '{"answers": [{"id": "Q1", "status": "OK", "quote": "| a |\n| b |", "why": null}]}'
        self.assertEqual(_extract_json(raw)["answers"][0]["quote"], "| a |\n| b |")

    def test_truncated_array_is_repaired(self):
        raw = '{"answers": [{"id": "Q1", "status": "OK"}, {"id": "Q2", "sta'
        self.assertEqual([a["id"] for a in _extract_json(raw)["answers"]], ["Q1"])

    def test_no_json_raises(self):
        with self.assertRaises(ValueError):
            _extract_json("")


class FakeLLM(LLM):
    """Первый ответ обрезан (finish=length), второй — полный."""

    def __init__(self):  # noqa: D107 — без OpenAI-клиента
        self.calls = []
        self.last_finish = None

    def _chat(self, system, user, temperature=0.0, n=1, max_tokens=1600):
        self.calls.append(max_tokens)
        if len(self.calls) == 1:
            self.last_finish = "length"
            return ["Ответ без JSON: модель ушла в рассуждения и упёрлась в лимит"]
        self.last_finish = "stop"
        return ['{"answers": [{"id": "Q1", "status": "OK"}, {"id": "Q2", "status": "MISSING"}]}']


class TestChatJsonRetry(unittest.TestCase):
    def test_truncated_then_full(self):
        llm = FakeLLM()
        out = llm.chat_json("s", "u", max_tokens=1000)
        self.assertEqual([a["id"] for a in out["answers"]], ["Q1", "Q2"])
        self.assertEqual(llm.calls, [1000, 2000])  # повтор с удвоенным бюджетом


if __name__ == "__main__":
    unittest.main()

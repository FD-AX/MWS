import unittest

from tz_review import llm as llm_mod
from tz_review.llm import LLM, cyrillic_share, quotes_off_language


class LangGuardTests(unittest.TestCase):
    def test_cyrillic_share(self):
        self.assertGreater(cyrillic_share("Способ загрузки: Инкремент (FIELD_BIZ_DATE)"), 0.6)
        self.assertLess(cyrillic_share("DDL defines FIELD_TRAFFIC_GB as decimal(18,2)"), 0.1)
        self.assertEqual(cyrillic_share("123 ---"), 1.0)  # без букв — не сигнал

    def test_quotes_off_language_detects_translations(self):
        bad = {"findings": [{"quote": "Version 1.1 added FIELD_ROAMING_FLAG to the structure", "why": "..."},
                            {"quote": "Step 4 states that any RAT value outside", "why": "..."}]}
        good = {"findings": [{"quote": "Способ загрузки: Инкремент", "why": "нет курсора"}]}
        self.assertTrue(quotes_off_language(bad))
        self.assertFalse(quotes_off_language(good))
        self.assertFalse(quotes_off_language({"answers": [{"id": "SRC-01", "status": "OK", "quote": None}]}))

    def test_chat_json_retries_once_with_guard(self):
        """Первый ответ с английскими цитатами → повтор с LANG_GUARD в system; второй принимается."""
        calls = []

        class Fake(LLM):
            def __init__(self):
                self.stats = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0}
                self.last_finish = "stop"

            def _chat(self, system, user, temperature=0.0, n=1, max_tokens=1600):
                calls.append(system)
                if len(calls) == 1:
                    return ['{"findings": [{"quote": "DDL defines FIELD_X as decimal", "why": "x"}]}']
                return ['{"findings": [{"quote": "DDL задаёт FIELD_X как decimal", "why": "x"}]}']

        out = Fake().chat_json("Системный промпт.", "Документ")
        self.assertEqual(len(calls), 2)
        self.assertNotIn(llm_mod.LANG_GUARD, calls[0])
        self.assertIn(llm_mod.LANG_GUARD, calls[1])
        self.assertIn("задаёт", out["findings"][0]["quote"])


if __name__ == "__main__":
    unittest.main()

import unittest

from tz_review import llm as llm_mod
from tz_review.llm import LLM, cyrillic_share, lang_guard, quotes_off_language, script_share


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

    # --- язык документа как настройка (Settings.doc_lang / TZR_DOC_LANG) ---

    def test_script_share_latin(self):
        self.assertGreater(script_share("Load mode: incremental by FIELD_BIZ_DATE", "latin"), 0.9)
        self.assertLess(script_share("Способ загрузки: Инкремент", "latin"), 0.1)

    def test_english_document_accepts_english_quotes_and_flags_russian(self):
        en = {"findings": [{"quote": "Version 1.1 added FIELD_ROAMING_FLAG to the structure", "why": "..."}]}
        ru = {"findings": [{"quote": "Способ загрузки: Инкремент", "why": "..."}]}
        self.assertFalse(quotes_off_language(en, lang="en"))
        self.assertTrue(quotes_off_language(ru, lang="en"))
        self.assertTrue(quotes_off_language(en, lang="ru"))  # прежнее поведение по умолчанию

    def test_unknown_language_disables_guard(self):
        en = {"findings": [{"quote": "Version 1.1 added FIELD_ROAMING_FLAG", "why": "..."}]}
        self.assertFalse(quotes_off_language(en, lang="de"))
        self.assertFalse(quotes_off_language(en, lang=""))

    def test_chat_json_respects_configured_language(self):
        """doc_lang=en: английские цитаты принимаются с первого раза, без повтора."""
        calls = []

        class Fake(LLM):
            def __init__(self):
                self.stats = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0}
                self.last_finish = "stop"
                self._doc_lang = "en"

            def _chat(self, system, user, temperature=0.0, n=1, max_tokens=1600):
                calls.append(system)
                return ['{"findings": [{"quote": "DDL defines FIELD_X as decimal", "why": "x"}]}']

        out = Fake().chat_json("System prompt.", "Document")
        self.assertEqual(len(calls), 1)
        self.assertEqual(out["findings"][0]["quote"], "DDL defines FIELD_X as decimal")

    def test_lang_guard_text_by_language(self):
        self.assertEqual(lang_guard("ru"), llm_mod.LANG_GUARD)
        self.assertIn("English", lang_guard("en"))
        self.assertEqual(lang_guard("xx"), llm_mod.LANG_GUARD)

    def test_settings_doc_lang_from_env(self):
        import os
        from tz_review import config
        old = os.environ.get("TZR_DOC_LANG")
        try:
            os.environ["TZR_DOC_LANG"] = " EN "
            self.assertEqual(config._doc_lang_env(), "en")
            os.environ.pop("TZR_DOC_LANG")
            self.assertEqual(config._doc_lang_env(), "ru")
            self.assertEqual(config.Settings(base_url="u", api_key="k", model="m").doc_lang, "ru")
        finally:
            if old is not None:
                os.environ["TZR_DOC_LANG"] = old


if __name__ == "__main__":
    unittest.main()

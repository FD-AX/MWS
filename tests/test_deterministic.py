import unittest

from tz_review import document
from tz_review.passes import deterministic
from tz_review.rubric import load_rubric

RUBRIC = load_rubric()


def run_on(text: str):
    return deterministic.run(document.parse(text), RUBRIC)


class TestLanguagePatterns(unittest.TestCase):
    def test_open_ended(self):
        findings = run_on("## Источник данных\nПоля: A, B, C и т. д.\n")
        self.assertTrue(any(f.category == "lang:open_ended" for f in findings))

    def test_escape_clause(self):
        findings = run_on("## Регламент загрузки\nПри необходимости выполняется перезагрузка.\n")
        self.assertTrue(any(f.category == "lang:escape" for f in findings))

    def test_incomplete_tbd(self):
        findings = run_on("## Контроль качества\nTBD\n")
        cats = {f.category for f in findings}
        self.assertIn("lang:incomplete", cats)
        self.assertIn("template:empty_section", cats)

    def test_quote_is_substring(self):
        text = "## Регламент загрузки\nЗагрузка выполняется оперативно каждый день.\n"
        for f in run_on(text):
            if f.quote:
                self.assertIn(f.quote, text)

    def test_clean_text_no_language_findings(self):
        findings = run_on("## Регламент загрузки\nЗапуск ежедневно в 06:00 МСК, "
                          "окно перезагрузки 3 дня.\n")
        self.assertFalse([f for f in findings if f.category.startswith("lang:")])


class TestRequiredSections(unittest.TestCase):
    def test_missing_section_flagged(self):
        findings = run_on("## Источник данных\nОписание источника длиннее сорока "
                          "символов для порога.\n")
        missing = [f for f in findings if f.category == "template:missing_section"]
        self.assertTrue(any("Регламент" in f.section for f in missing))


if __name__ == "__main__":
    unittest.main()

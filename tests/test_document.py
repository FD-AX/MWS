import unittest

from tz_review import document


class TestParse(unittest.TestCase):
    def test_markdown_headers(self):
        doc = document.parse("# Титул\n## Источник данных\nтело\n## Регламент\nещё\n")
        titles = doc.section_titles()
        self.assertIn("Источник данных", titles)
        self.assertIn("Регламент", titles)

    def test_numbered_headers(self):
        doc = document.parse("1. Общие сведения\nтекст раздела\n2. Источник данных\nтело\n")
        self.assertTrue(any("Источник данных" in t for t in doc.section_titles()))

    def test_numbered_sentence_not_header(self):
        doc = document.parse("## Раздел\n1. Первый пункт списка обычного перечисления.\n")
        self.assertEqual(len([s for s in doc.sections if s.body]), 1)

    def test_plain_text_single_section(self):
        doc = document.parse("просто текст без заголовков")
        self.assertTrue(doc.sections)
        self.assertTrue(doc.sections[-1].body)

    def test_normalize(self):
        self.assertEqual(document.normalize("Ёжик  «в» — тумане"), "ежик в - тумане")


if __name__ == "__main__":
    unittest.main()

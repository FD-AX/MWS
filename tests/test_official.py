import unittest

from tz_review import document
from tz_review.passes import deterministic
from tz_review.rubric import load_rubric

RUBRIC = load_rubric()


def run_on(text: str):
    return deterministic.run(document.parse(text), RUBRIC)


class TestOfficialTemplate(unittest.TestCase):
    def test_missing_official_sections_grouped_into_one(self):
        findings = run_on("## Источник данных\nОписание источника достаточной длины "
                          "для порога пустоты.\n")
        off = [f for f in findings if f.category == "template:official_missing"]
        self.assertEqual(len(off), 1)  # сводная находка, не по одной на раздел
        self.assertIn("Data Catalog", off[0].why)
        self.assertIn("не применимо", off[0].why)

    def test_all_sections_mentioned_no_finding(self):
        names = RUBRIC["official_sections"]
        text = "## Шапка\n" + "\n".join(f"## {n}\nсодержимое раздела" for n in names)
        off = [f for f in run_on(text) if f.category == "template:official_missing"]
        self.assertEqual(off, [])

    def test_ne_primenimo_satisfies_official_rule(self):
        # Хвостовой раздел со списком «не применимо» закрывает official-проверку
        names = ", ".join(RUBRIC["official_sections"])
        text = ("## Источник данных\nдостаточно длинное описание источника\n"
                f"## Прочие разделы шаблона\n{names} — не применимо.\n")
        off = [f for f in run_on(text) if f.category == "template:official_missing"]
        self.assertEqual(off, [])

    def test_ne_primenimo_suppresses_empty_section(self):
        findings = run_on("## Контроль качества\nне применимо\n")
        self.assertFalse([f for f in findings if f.category == "template:empty_section"])

    def test_empty_section_without_mark_still_flagged(self):
        findings = run_on("## Контроль качества\n—\n")
        self.assertTrue([f for f in findings if f.category == "template:empty_section"])


class TestOfficialSlots(unittest.TestCase):
    def test_mts_slots_present(self):
        ids = {q["id"] for q in RUBRIC["checklist"]}
        for slot in ("SER-01", "CAT-01", "NUL-03", "FIL-02",
                     "LOC-02", "LOC-03", "REF-01", "KEY-02"):
            self.assertIn(slot, ids)

    def test_mts_slots_marked_official(self):
        # official: true → критик не вправе опустить такие находки ниже порога (EXP-13)
        official = {q["id"] for q in RUBRIC["checklist"] if q.get("official")}
        self.assertEqual(official, {"SER-01", "CAT-01", "NUL-03", "FIL-02",
                                    "LOC-02", "LOC-03", "REF-01", "KEY-02"})


class TestOfficialEmptySection(unittest.TestCase):
    BODY = "## Источники данных\nДостаточно длинное описание источника данных для порога.\n"

    def test_empty_official_section_dash_flagged(self):
        findings = run_on(self.BODY + "## Data Catalog\n—\n")
        empty = [f for f in findings if f.category == "template:empty_section"]
        self.assertEqual([f.section for f in empty], ["Data Catalog"])

    def test_empty_official_section_with_mark_ok(self):
        findings = run_on(self.BODY + "## Data Catalog\nне применимо: витрина без каталога\n")
        self.assertFalse([f for f in findings if f.category == "template:empty_section"])

    def test_required_and_official_not_double_flagged(self):
        findings = run_on("## Источники данных\n—\n")
        empty = [f for f in findings if f.category == "template:empty_section"]
        self.assertEqual(len(empty), 1)  # required-проверка уже отметила, official молчит


if __name__ == "__main__":
    unittest.main()

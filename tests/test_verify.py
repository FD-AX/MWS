import unittest

from tz_review import document
from tz_review.schema import Finding
from tz_review.verify import anchoring_rate, verify_findings

DOC = document.parse(
    "## Источник данных\nФайлы CSV на SFTP-сервере в каталоге /export/pm/.\n"
    "## Регламент загрузки\nДанные загружаются ежедневно и добавляются в витрину.\n"
)


def make(quote=None, section="", missing=False, source_pass=""):
    return Finding(category="t", why="w", quote=quote, section=section,
                   missing=missing, source_pass=source_pass)


class TestVerify(unittest.TestCase):
    def test_exact_quote_verified(self):
        v, d = verify_findings([make(quote="Данные загружаются ежедневно")], DOC)
        self.assertEqual(len(v), 1)
        self.assertTrue(v[0].verified)

    def test_hallucinated_quote_dropped(self):
        v, d = verify_findings([make(quote="Данные загружаются раз в час")], DOC)
        self.assertEqual((len(v), len(d)), (0, 1))

    def test_normalization_tolerant(self):
        v, _ = verify_findings([make(quote="данные  загружаются ЕЖЕДНЕВНО")], DOC)
        self.assertEqual(len(v), 1)

    def test_reanchored_to_real_section(self):
        v, _ = verify_findings(
            [make(quote="Файлы CSV на SFTP-сервере", section="Регламент загрузки")], DOC)
        self.assertIn("Источник", v[0].section)

    def test_short_llm_quote_dropped_but_deterministic_kept(self):
        doc = document.parse("## Контроль качества\nTBD\n")
        v, d = verify_findings([make(quote="TBD")], doc)
        self.assertEqual(len(v), 0)  # короткая LLM-цитата не принимается
        v, d = verify_findings([make(quote="TBD", source_pass="deterministic")], doc)
        self.assertEqual(len(v), 1)

    def test_missing_needs_no_quote(self):
        v, d = verify_findings([make(missing=True)], DOC)
        self.assertEqual((len(v), len(d)), (1, 0))

    def test_no_quote_no_missing_dropped(self):
        v, d = verify_findings([make()], DOC)
        self.assertEqual((len(v), len(d)), (0, 1))

    def test_anchoring_rate(self):
        v, d = verify_findings(
            [make(quote="Данные загружаются ежедневно"), make(quote="выдумка про кластер")],
            DOC)
        self.assertAlmostEqual(anchoring_rate(v, d), 0.5)


class TestEntropy(unittest.TestCase):
    def test_identical_answers_zero(self):
        from tz_review.passes.uncertainty import semantic_entropy
        h, clusters = semantic_entropy(["по полю UPDATED_AT"] * 5)
        self.assertEqual(h, 0.0)
        self.assertEqual(len(clusters), 1)

    def test_divergent_answers_positive(self):
        from tz_review.passes.uncertainty import semantic_entropy
        h, clusters = semantic_entropy(
            ["по полю UPDATED_AT", "по дате файла", "НЕТ ОТВЕТА",
             "по полю UPDATED_AT", "по дате файла"])
        self.assertGreater(h, 1.0)
        self.assertEqual(len(clusters), 3)


if __name__ == "__main__":
    unittest.main()

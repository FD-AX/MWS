import unittest

from tz_review import document
from tz_review.schema import Finding
from tz_review.verify import anchoring_rate, reanchor, verify_findings

DOC = """# ТЗ

## Структура данных
| FIELD_TRAFFIC_GB | decimal(18,2) | NOT NULL | Суммарный трафик за месяц, ГБ |

## Алгоритм
Округление трафика выполняется до трёх знаков после запятой (decimal(18,3)) перед записью.

## Регламент
Срок готовности: данные за месяц M доступны потребителям не позднее 10:00 UTC 2-го числа месяца M+1.
"""


def _f(quote, src="document_level"):
    return Finding(category="doc:contradiction", severity="high", section="", quote=quote,
                   why="w", ask="a", source_pass=src)


class ReanchorTests(unittest.TestCase):
    def test_composite_quote_reanchored_to_verbatim_fragment(self):
        doc = document.parse(DOC)
        f = _f("DDL defines FIELD_TRAFFIC_GB as decimal(18,2) vs Округление трафика выполняется до трёх знаков после запятой")
        verified, dropped = verify_findings([f], doc)
        self.assertEqual(len(verified), 1, [d.quote for d in dropped])
        self.assertIn("округление трафика выполняется до трех знаков", verified[0].quote)
        self.assertEqual(verified[0].section, "Алгоритм")

    def test_paraphrase_without_verbatim_fragment_is_dropped(self):
        doc = document.parse(DOC)
        f = _f("The traffic field precision differs between the DDL and the algorithm description")
        verified, dropped = verify_findings([f], doc)
        self.assertEqual(len(verified), 0)
        self.assertEqual(len(dropped), 1)

    def test_sliding_window_recovers_partial_quote(self):
        doc = document.parse(DOC)
        f = _f("по регламенту данные за месяц M доступны потребителям не позднее 10:00 UTC 2-го числа месяца M+1 (см. SLA)")
        verified, dropped = verify_findings([f], doc)
        self.assertEqual(len(verified), 1, [d.quote for d in dropped])
        self.assertTrue(verified[0].quote.startswith("данные за месяц m доступны"))

    def test_short_fragments_not_accepted(self):
        norm_doc = document.normalize(DOC)
        self.assertIsNone(reanchor("срок готовности vs нечто иное", norm_doc, norm_doc))

    def test_deterministic_findings_not_reanchored(self):
        doc = document.parse(DOC)
        f = _f("Срок готовности: данные за месяц M vs что-то", src="deterministic")
        verified, dropped = verify_findings([f], doc)
        self.assertEqual(len(dropped), 1)
        self.assertEqual(anchoring_rate(verified, dropped), 0.0)


if __name__ == "__main__":
    unittest.main()

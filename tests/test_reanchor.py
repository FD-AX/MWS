import unittest

from tz_review import document
from tz_review.schema import Finding
from tz_review.verify import FUZZY_MIN_RATIO, anchoring_rate, doc_units, fuzzy_anchor, reanchor, verify_findings

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


DOC2 = """# ТЗ

## Способ загрузки Инкремент
Хранение: Kafka — 24 ч, RAW-слой — 30 дней.

## Алгоритм расчёта
Шаг 1. Отбор данных
Берутся записи за отчётный месяц.
Шаг 5. Определение региона
Для каждого IMSI берётся актуальная запись за месяц (по FIELD_TIME_STAMP).
"""


class AnchorRescueTests(unittest.TestCase):
    """EXP-24: классы отброшенных цитат из ночных JSON (eval/anchor_replay.py)."""

    def test_nonbreaking_hyphen_is_normalized(self):
        doc = document.parse(DOC2)
        f = _f("Хранение: Kafka — 24 ч, RAW‑слой — 30 дней", src="developer_sim")  # U+2011
        verified, dropped = verify_findings([f], doc)
        self.assertEqual(len(verified), 1, [d.quote for d in dropped])
        self.assertEqual(verified[0].quote, "Хранение: Kafka — 24 ч, RAW‑слой — 30 дней")  # дословно — не трогаем

    def test_punctuation_only_difference_matches(self):
        doc = document.parse(DOC2)
        f = _f("Способ загрузки: Инкремент", src="developer_sim")
        verified, dropped = verify_findings([f], doc)
        self.assertEqual(len(verified), 1, [d.quote for d in dropped])
        self.assertEqual(verified[0].section, "Способ загрузки Инкремент")

    def test_sliding_window_skips_short_segments(self):
        doc = document.parse(DOC2)
        f = _f("Шаг 1. … Шаг 2. … Шаг 3. … Шаг 5. Определение региона")
        verified, dropped = verify_findings([f], doc)
        self.assertEqual(len(verified), 1, [d.quote for d in dropped])
        self.assertEqual(verified[0].quote, "шаг 5. определение региона")
        self.assertEqual(verified[0].section, "Алгоритм расчёта")

    def test_fuzzy_anchor_rescues_one_word_paraphrase_with_document_text(self):
        doc = document.parse(DOC2)
        f = _f("последняя запись за месяц", src="developer_sim")
        verified, dropped = verify_findings([f], doc)
        self.assertEqual(len(verified), 1, [d.quote for d in dropped])
        self.assertIn("актуальная запись за месяц", verified[0].quote)  # текст документа, не модели
        self.assertEqual(verified[0].section, "Алгоритм расчёта")

    def test_fuzzy_anchor_needs_length_and_similarity(self):
        doc = document.parse(DOC2)
        short = _f("последняя строка", src="developer_sim")           # < FUZZY_MIN_LEN
        far = _f("The latest record per month is taken", src="developer_sim")  # перевод
        other = _f("совсем другая фраза про регион и трафик", src="developer_sim")
        verified, dropped = verify_findings([short, far, other], doc)
        self.assertEqual(len(verified), 0, [v.quote for v in verified])
        self.assertEqual(len(dropped), 3)

    def test_fuzzy_anchor_function_threshold(self):
        units = doc_units(DOC2)
        hit = fuzzy_anchor(document.normalize("последняя запись за месяц"), units)
        self.assertIsNotNone(hit)
        self.assertGreaterEqual(hit[1], FUZZY_MIN_RATIO)
        self.assertIsNone(fuzzy_anchor(document.normalize("совсем другая фраза про регион и трафик"), units))

    def test_fuzzy_not_applied_to_deterministic(self):
        doc = document.parse(DOC2)
        f = _f("последняя запись за месяц", src="deterministic")
        verified, dropped = verify_findings([f], doc)
        self.assertEqual(len(dropped), 1)

    def test_reanchor_prefers_fragment_with_identifier_over_generic_phrase(self):
        doc = document.parse("""# ТЗ

## Источники данных
Подробности см. в разделе Структура данных ниже.

## Структура данных
| FIELD_TRAFFIC_GB | decimal(18,3) | Суммарный трафик |

## DDL
CREATE TABLE TABLE_AGG (FIELD_TRAFFIC_GB decimal(18,2) NOT NULL);
""")
        f = _f("`FIELD_TRAFFIC_GB decimal(18,2)` в DDL, тогда как в разделе Структура данных указано `decimal(18,3)`")
        verified, dropped = verify_findings([f], doc)
        self.assertEqual(len(verified), 1, [d.quote for d in dropped])
        self.assertEqual(verified[0].quote, "field_traffic_gb decimal(18,2)")
        self.assertEqual(verified[0].section, "DDL")

    def test_bare_span_closes_parenthesis(self):
        doc = document.parse(DOC)
        f = _f("Структура данных: FIELD_TRAFFIC_GB | decimal(18,2) ... DDL: FIELD_TRAFFIC_GB decimal(18,9)")
        verified, dropped = verify_findings([f], doc)
        self.assertEqual(len(verified), 1, [d.quote for d in dropped])
        # заголовок стоит вплотную к строке таблицы, поэтому bare-фрагмент захватывает и его; скобка закрыта
        self.assertEqual(verified[0].quote, "структура данных | field_traffic_gb | decimal(18,2)")

    def test_unique_short_quote_anchors_to_its_line(self):
        doc = document.parse("""# ТЗ

## Пример данных
| FIELD_BIZ_DATE | FIELD_RAT_NAME | FIELD_TRAFFIC_GB |
| 2026-01-01 | 5G | 12.5 |
| 2026-01-01 | 4G | 3.1 |
""")
        unique = _f("5G", src="developer_sim")
        common = _f("и", src="developer_sim")
        verified, dropped = verify_findings([unique, common], doc)
        self.assertEqual([v.quote for v in verified], ["| 2026-01-01 | 5g | 12.5 |"])
        self.assertEqual(verified[0].section, "Пример данных")
        self.assertEqual([d.quote for d in dropped], ["и"])

    def test_short_quote_unique_as_whole_word_only(self):
        doc = document.parse(DOC2)
        # «запись» — одно слово-вхождение (в «записи» не считается) → якорь на строку;
        # «шаг» встречается дважды («Шаг 1.», «Шаг 5.») → отбрасывается.
        verified, dropped = verify_findings([_f("запись", src="developer_sim")], doc)
        self.assertEqual(len(verified), 1, [d.quote for d in dropped])
        self.assertIn("актуальная запись за месяц", verified[0].quote)
        verified2, dropped2 = verify_findings([_f("шаг", src="developer_sim")], doc)
        self.assertEqual(len(dropped2), 1)


if __name__ == "__main__":
    unittest.main()

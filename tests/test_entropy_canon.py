import unittest

from tz_review.passes.uncertainty import _canon, semantic_entropy


class EntropyCanonTests(unittest.TestCase):
    def test_same_fact_different_words_is_one_cluster(self):
        answers = ["Да, ежемесячно — 2‑го числа в 03:00 UTC.",
                   "Да, ежемесячный запуск 2‑го числа в 03:00 UTC",
                   "Ежемесячно, 2-го числа, в 03:00 UTC.",
                   "да — раз в месяц 2 числа в 03:00 UTC",
                   "Да, запуск ежемесячно 2-го числа в 03:00 UTC."]
        entropy, clusters = semantic_entropy(answers)
        self.assertEqual(len(clusters), 1, [c[0] for c in clusters])
        self.assertEqual(entropy, 0.0)

    def test_field_names_drive_the_cluster(self):
        self.assertEqual(_canon("По полю FIELD_TIME_STAMP."), _canon("FIELD_TIME_STAMP"))
        self.assertEqual(_canon("Последняя запись выбирается по полю FIELD_TIME_STAMP"), _canon("FIELD_TIME_STAMP."))
        self.assertNotEqual(_canon("FIELD_TIME_STAMP"), _canon("FIELD_EVENT_TS"))

    def test_polarity_and_no_answer_differ(self):
        self.assertNotEqual(_canon("НЕТ ОТВЕТА"), _canon("Да, дедупликация по (FIELD_IMSI, FIELD_TIME_STAMP)"))
        self.assertNotEqual(_canon("Да"), _canon("Нет"))

    def test_real_disagreement_keeps_entropy(self):
        answers = ["FIELD_TIME_STAMP", "FIELD_TIME_STAMP", "FIELD_EVENT_TS", "FIELD_EVENT_TS", "FIELD_LOAD_TS"]
        entropy, clusters = semantic_entropy(answers)
        self.assertEqual(len(clusters), 3)
        self.assertGreater(entropy, 1.0)

    def test_wordy_answers_without_hard_tokens_merge_by_stems(self):
        self.assertEqual(_canon("Записи отбрасываются и логируются"), _canon("записи отбрасывают и логируют"))


if __name__ == "__main__":
    unittest.main()

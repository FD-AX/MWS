import unittest
from pathlib import Path

from tz_review.passes.checklist import split_applicable
from tz_review.rubric import load_rubric

ROOT = Path(__file__).resolve().parent.parent
EXTRA_IDS = {"ORD-01", "REF-02", "HIS-01", "TZ-01"}


class RubricExtraTests(unittest.TestCase):
    def test_extra_off_by_default_arg(self):
        r = load_rubric(extra=False)
        self.assertFalse(EXTRA_IDS & {q["id"] for q in r["checklist"]})

    def test_extra_merges_without_id_clash(self):
        r = load_rubric(extra=True)
        ids = [q["id"] for q in r["checklist"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(EXTRA_IDS <= set(ids))
        self.assertEqual(set(r["extra_slots"]), EXTRA_IDS)
        for q in r["checklist"]:
            if q["id"] in EXTRA_IDS:
                self.assertTrue(q.get("applies_if"), q["id"])
                self.assertIn("aspect", q)
                self.assertIn("question", q)

    def test_extra_slots_apply_to_doc3(self):
        """doc3 упоминает UTC, справочник, историю и «последнюю» запись — все 4 слота применимы."""
        text = (ROOT / "casedata/doc3_mart_devices.md").read_text(encoding="utf-8")
        r = load_rubric(extra=True)
        applicable, na = split_applicable(r["checklist"], text)
        self.assertFalse(EXTRA_IDS & set(na), f"NA среди extra: {EXTRA_IDS & set(na)}")

    def test_extra_slots_batched_separately(self):
        """Батчи базовых слотов не меняются от подключения extra (иначе плывут ответы на официальные пункты)."""
        from tz_review.passes.checklist import make_batches
        base = load_rubric(extra=False)["checklist"]
        ext = load_rubric(extra=True)
        b0 = make_batches(base, set())
        b1 = make_batches(ext["checklist"], set(ext["extra_slots"]))
        self.assertEqual([[q["id"] for q in b] for b in b0], [[q["id"] for q in b] for b in b1[:len(b0)]])
        tail = {q["id"] for b in b1[len(b0):] for q in b}
        self.assertEqual(tail, EXTRA_IDS)

    def test_na_slots_do_not_reshuffle_batches(self):
        """NA-правила убирают слоты внутри батчей, не перекраивая соседей (EXP-22: doc3 v2g 10/16 после NA)."""
        from tz_review.passes.checklist import make_batches
        base = load_rubric(extra=False)["checklist"]
        full = make_batches(base, set())
        na = {"INC-01", "INC-03", "NUL-02", "MAP-02"}
        with_na = make_batches(base, set(), na)
        expected = [[q["id"] for q in b if q["id"] not in na] for b in full]
        expected = [b for b in expected if b]
        self.assertEqual([[q["id"] for q in b] for b in with_na], expected)
        self.assertFalse(na & {q["id"] for b in with_na for q in b})

    def test_extra_slots_na_on_unrelated_text(self):
        text = "Поток принимает события из Kafka и пишет их в HDFS как есть, без преобразований."
        r = load_rubric(extra=True)
        _, na = split_applicable(r["checklist"], text)
        self.assertTrue(EXTRA_IDS <= set(na), f"должны быть NA: {EXTRA_IDS - set(na)}")


if __name__ == "__main__":
    unittest.main()

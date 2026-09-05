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

    def test_extra_slots_na_on_unrelated_text(self):
        text = "Поток принимает события из Kafka и пишет их в HDFS как есть, без преобразований."
        r = load_rubric(extra=True)
        _, na = split_applicable(r["checklist"], text)
        self.assertTrue(EXTRA_IDS <= set(na), f"должны быть NA: {EXTRA_IDS - set(na)}")


if __name__ == "__main__":
    unittest.main()

import unittest

from tz_review.passes import critic
from tz_review.schema import Finding


class FakeLLM:
    """Критик, который ставит заданные оценки по fid и объявляет заданные дубли."""

    def __init__(self, scores, duplicates=None):
        self.scores, self.duplicates = scores, duplicates or []

    def chat_json(self, system, user, temperature=0.0):
        return {"scores": [{"fid": k, "score": v, "reason": ""} for k, v in self.scores.items()],
                "duplicates": self.duplicates}


def make(fid, category, source_pass="checklist"):
    return Finding(fid=fid, category=category, why="w", missing=True, source_pass=source_pass)


class TestCriticProtected(unittest.TestCase):
    def test_protected_official_slot_survives_zero_score(self):
        # EXP-13: чеклист нашёл отсутствие кластера Kafka, критик поставил 0.0 и срезал
        fs = [make("F1", "checklist:LOC-02"), make("F2", "checklist:INC-03")]
        kept, rejected = critic.run(fs, "doc", FakeLLM({"F1": 0.0, "F2": 0.0}),
                                    threshold=4.0, protected=frozenset({"checklist:LOC-02"}))
        self.assertEqual([f.fid for f in kept], ["F1"])
        self.assertEqual([f.fid for f in rejected], ["F2"])
        self.assertEqual(kept[0].score, 4.0)  # пол = порог

    def test_protected_still_deduplicated(self):
        fs = [make("F1", "checklist:LOC-02"), make("F2", "checklist:LOC-02")]
        kept, rejected = critic.run(fs, "doc", FakeLLM({"F1": 7.0, "F2": 6.0}, [["F1", "F2"]]),
                                    threshold=4.0, protected=frozenset({"checklist:LOC-02"}))
        self.assertEqual([f.fid for f in kept], ["F1"])
        self.assertEqual([f.fid for f in rejected], ["F2"])

    def test_unprotected_below_threshold_rejected(self):
        fs = [make("F1", "checklist:LOC-02")]
        kept, rejected = critic.run(fs, "doc", FakeLLM({"F1": 1.0}), threshold=4.0)
        self.assertEqual((len(kept), len(rejected)), (0, 1))

    def test_deterministic_findings_bypass_critic(self):
        fs = [make("F1", "lang:vague", source_pass="deterministic")]
        kept, rejected = critic.run(fs, "doc", FakeLLM({}), threshold=4.0)
        self.assertEqual((len(kept), len(rejected)), (1, 0))


if __name__ == "__main__":
    unittest.main()

import os
import unittest
from unittest import mock

from tz_review import api_client


PAYLOAD = {
    "job_id": "abc123", "status": "done", "model": "gpt-5.5", "anchoring": 0.9,
    "result": {
        "anchoring_rate": 0.875,
        "checklist_statuses": {"SRC-01": "OK", "NUL-03": "MISSING", "LOC-02": "NA"},
        "findings": [
            {"fid": "F001", "db_id": 7, "category": "checklist:NUL-03", "severity": "high", "section": "Обязательность полей",
             "quote": None, "missing": True, "why": "нет NOT NULL", "ask": "укажи", "score": 6.0,
             "source_pass": "checklist", "verified": True},
            {"fid": "F002", "category": "dev_question", "severity": "medium", "quote": "текст", "why": "почему",
             "ask": "что", "score": 4.0, "source_pass": "developer_sim", "verified": True},
        ],
        "rejected": [{"fid": "F003", "category": "dev_question", "severity": "low", "why": "мусор", "score": 1.0}],
        "dropped": [],
    },
}


class TestResultFromPayload(unittest.TestCase):
    def test_builds_review_result_and_ignores_extra_fields(self):
        r = api_client.result_from_payload(PAYLOAD)
        self.assertEqual([f.fid for f in r.findings], ["F001", "F002"])
        self.assertTrue(r.findings[0].missing)
        self.assertEqual(r.findings[0].score, 6.0)      # db_id (нет в схеме) не ломает сборку
        self.assertEqual([f.fid for f in r.rejected], ["F003"])
        self.assertEqual(r.statuses["LOC-02"], "NA")
        self.assertAlmostEqual(r.anchoring, 0.875)
        self.assertIn("api", r.passes_run)

    def test_api_url_from_env(self):
        with mock.patch.dict(os.environ, {"TZR_API_URL": "http://api:8080/"}):
            self.assertEqual(api_client.api_url(), "http://api:8080")
        with mock.patch.dict(os.environ, {"TZR_API_URL": ""}):
            self.assertIsNone(api_client.api_url())

    def test_multipart_body_has_file_part(self):
        body, ctype = api_client._multipart({}, {"file": ("doc.md", "# ТЗ".encode("utf-8"), "text/markdown")})
        self.assertIn("multipart/form-data; boundary=", ctype)
        self.assertIn(b'filename="doc.md"', body)
        self.assertIn("# ТЗ".encode("utf-8"), body)


if __name__ == "__main__":
    unittest.main()

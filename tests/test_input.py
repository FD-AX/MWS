import unittest

from tz_review.input import DocumentInputError, extract_text


class TestDocumentInput(unittest.TestCase):
    def test_utf8_text(self):
        self.assertEqual(extract_text("sample.md", "Техническое задание".encode()),
                         "Техническое задание")

    def test_cp1251_text(self):
        value = "Источник данных"
        self.assertEqual(extract_text("sample.txt", value.encode("cp1251")), value)

    def test_empty_document_rejected(self):
        with self.assertRaises(DocumentInputError):
            extract_text("empty.txt", b"  \n")

    def test_unknown_format_rejected(self):
        with self.assertRaises(DocumentInputError):
            extract_text("sample.xlsx", b"data")


if __name__ == "__main__":
    unittest.main()

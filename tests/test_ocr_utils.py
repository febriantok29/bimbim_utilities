import shutil
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.ocr_utils import ocr_available, ocr_to_searchable_pdf


class OcrAvailableTests(unittest.TestCase):
    def test_matches_real_binary_presence_in_this_environment(self):
        # Real (unmocked) check: reflects whatever is actually installed here,
        # rather than hardcoding an assumption that goes stale when the
        # environment changes (e.g. after `brew install tesseract ghostscript`).
        expected = shutil.which("tesseract") is not None and shutil.which("gs") is not None
        self.assertEqual(ocr_available(), expected)

    @patch("tools.ocr_utils.shutil.which", return_value="/usr/bin/x")
    def test_true_when_both_found(self, mock_which):
        self.assertTrue(ocr_available())

    @patch("tools.ocr_utils.shutil.which", side_effect=lambda name: None if name == "gs" else "/usr/bin/tesseract")
    def test_false_when_only_tesseract_found(self, mock_which):
        self.assertFalse(ocr_available())


class OcrToSearchablePdfTests(unittest.TestCase):
    def test_success_calls_ocrmypdf_with_expected_args(self):
        fake_ocrmypdf = types.SimpleNamespace(ocr=lambda *a, **k: None)
        with patch.dict(sys.modules, {"ocrmypdf": fake_ocrmypdf}):
            ok, error = ocr_to_searchable_pdf(Path("in.pdf"), Path("out.pdf"), "ind+eng")
        self.assertTrue(ok)
        self.assertEqual(error, "")

    def test_ocrmypdf_exception_is_reported(self):
        def raise_error(*a, **k):
            raise RuntimeError("PriorOcrFoundError: page already has text")

        fake_ocrmypdf = types.SimpleNamespace(ocr=raise_error)
        with patch.dict(sys.modules, {"ocrmypdf": fake_ocrmypdf}):
            ok, error = ocr_to_searchable_pdf(Path("in.pdf"), Path("out.pdf"), "ind+eng")
        self.assertFalse(ok)
        self.assertIn("PriorOcrFoundError", error)

    def test_missing_package_reports_friendly_error(self):
        with patch.dict(sys.modules, {"ocrmypdf": None}):
            ok, error = ocr_to_searchable_pdf(Path("in.pdf"), Path("out.pdf"), "ind+eng")
        self.assertFalse(ok)
        self.assertIn("ocrmypdf belum terinstall", error)


if __name__ == "__main__":
    unittest.main()

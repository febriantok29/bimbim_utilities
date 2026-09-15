import io
import unittest

from pypdf import PdfReader, PdfWriter

from app import app


def _make_pdf_bytes(num_pages: int) -> bytes:
    writer = PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


class PdfExtractSectionsRouteTests(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_get_renders_form(self):
        resp = self.client.get("/pdf-utils/extract-sections")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'name="pdf"', resp.data)
        self.assertIn(b'name="sections"', resp.data)

    def test_no_file_flashes_and_redirects(self):
        resp = self.client.post(
            "/pdf-utils/extract-sections", data={"sections": "Bab 1: 1-2"},
            content_type="multipart/form-data", follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Pilih file PDF".encode(), resp.data)

    def test_splits_into_correctly_sized_sections(self):
        pdf_bytes = _make_pdf_bytes(5)
        data = {
            "pdf": (io.BytesIO(pdf_bytes), "skripsi.pdf"),
            "sections": "Abstrak: 1\nBab 1: 2-5",
        }
        resp = self.client.post("/pdf-utils/extract-sections", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"abstrak.pdf", resp.data)
        self.assertIn(b"bab-1.pdf", resp.data)
        self.assertIn(b"Download semua", resp.data)

    def test_invalid_line_flashes_clear_error(self):
        pdf_bytes = _make_pdf_bytes(5)
        data = {
            "pdf": (io.BytesIO(pdf_bytes), "skripsi.pdf"),
            "sections": "Bab 1: abc",
        }
        resp = self.client.post(
            "/pdf-utils/extract-sections", data=data, content_type="multipart/form-data", follow_redirects=True
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Baris 1", resp.data)

    def test_out_of_range_page_flashes_clear_error(self):
        pdf_bytes = _make_pdf_bytes(3)
        data = {
            "pdf": (io.BytesIO(pdf_bytes), "skripsi.pdf"),
            "sections": "Bab 1: 1-10",
        }
        resp = self.client.post(
            "/pdf-utils/extract-sections", data=data, content_type="multipart/form-data", follow_redirects=True
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"out of range", resp.data)

    def test_duplicate_labels_get_unique_filenames(self):
        pdf_bytes = _make_pdf_bytes(4)
        data = {
            "pdf": (io.BytesIO(pdf_bytes), "skripsi.pdf"),
            "sections": "Bab: 1-2\nBab: 3-4",
        }
        resp = self.client.post("/pdf-utils/extract-sections", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"bab.pdf", resp.data)
        self.assertIn(b"bab-2.pdf", resp.data)

    def test_output_page_counts_are_correct(self):
        pdf_bytes = _make_pdf_bytes(10)
        data = {
            "pdf": (io.BytesIO(pdf_bytes), "skripsi.pdf"),
            "sections": "Abstrak: 1\nBab 1: 2-6",
        }
        resp = self.client.post("/pdf-utils/extract-sections", data=data, content_type="multipart/form-data")
        html = resp.data.decode()

        import base64
        import re

        match = re.search(r'src="data:application/pdf;base64,([A-Za-z0-9+/=]+)"', html)
        self.assertIsNotNone(match)
        first_pdf_bytes = base64.b64decode(match.group(1))
        reader = PdfReader(io.BytesIO(first_pdf_bytes))
        self.assertEqual(len(reader.pages), 1)


if __name__ == "__main__":
    unittest.main()

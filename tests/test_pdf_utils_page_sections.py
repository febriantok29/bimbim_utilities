import unittest

from tools.pdf_utils import parse_page_sections


class ParsePageSectionsTests(unittest.TestCase):
    def test_label_with_range(self):
        result = parse_page_sections("Bab 1: 5-20")
        self.assertEqual(result, [("Bab 1", list(range(5, 21)))])

    def test_label_with_single_page(self):
        result = parse_page_sections("Abstrak: 1")
        self.assertEqual(result, [("Abstrak", [1])])

    def test_multiple_lines(self):
        text = "Abstrak: 1\nBab 1: 5-20\nBab 2: 21-45"
        result = parse_page_sections(text)
        self.assertEqual(
            result,
            [
                ("Abstrak", [1]),
                ("Bab 1", list(range(5, 21))),
                ("Bab 2", list(range(21, 46))),
            ],
        )

    def test_blank_lines_are_skipped(self):
        text = "Abstrak: 1\n\n\nBab 1: 5-20\n"
        result = parse_page_sections(text)
        self.assertEqual(len(result), 2)

    def test_no_label_auto_names_section(self):
        result = parse_page_sections("5-20")
        self.assertEqual(result, [("Bagian 1", list(range(5, 21)))])

    def test_no_label_multiple_auto_named_sequentially(self):
        result = parse_page_sections("1\n2-3")
        self.assertEqual(result, [("Bagian 1", [1]), ("Bagian 2", [2, 3])])

    def test_whitespace_around_range_is_tolerated(self):
        result = parse_page_sections("Bab 1 :  5 - 20 ")
        self.assertEqual(result, [("Bab 1", list(range(5, 21)))])

    def test_start_greater_than_end_raises(self):
        with self.assertRaisesRegex(ValueError, "lebih besar"):
            parse_page_sections("Bab 1: 20-5")

    def test_non_numeric_range_raises(self):
        with self.assertRaisesRegex(ValueError, "Baris 1"):
            parse_page_sections("Bab 1: lima-dua puluh")

    def test_non_numeric_single_page_raises(self):
        with self.assertRaisesRegex(ValueError, "Baris 1"):
            parse_page_sections("Bab 1: abc")

    def test_error_reports_correct_line_number(self):
        with self.assertRaisesRegex(ValueError, "Baris 3"):
            parse_page_sections("Abstrak: 1\nBab 1: 5-20\nBab 2: xx")

    def test_empty_input_raises(self):
        with self.assertRaises(ValueError):
            parse_page_sections("")

    def test_only_blank_lines_raises(self):
        with self.assertRaises(ValueError):
            parse_page_sections("\n\n  \n")


if __name__ == "__main__":
    unittest.main()

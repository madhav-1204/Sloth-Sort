"""Unit tests for filename cleaning and category matching."""

import unittest
from sloth_sort.model import clean_filename, match_category

ALLOWED_CATEGORIES = [
    "Invoices",
    "Study",
    "Photos",
    "Installers",
    "Code",
    "Documents",
    "Media",
    "Misc",
]


class TestFilenameCleaning(unittest.TestCase):
    def test_strips_illegal_characters(self):
        dirty = 'invoice: 2026/10/22 <final>? *draft*|"approved"'
        cleaned = clean_filename(dirty, ".pdf", "orig_invoice")
        self.assertEqual(cleaned, "invoice 2026 10 22 final draft approved.pdf")
        self.assertNotIn(":", cleaned)
        self.assertNotIn("/", cleaned)
        self.assertNotIn("?", cleaned)
        self.assertNotIn("*", cleaned)
        self.assertNotIn("|", cleaned)

    def test_preserves_original_extension(self):
        cleaned = clean_filename("receipt_october", ".csv", "orig_csv")
        self.assertEqual(cleaned, "receipt_october.csv")

    def test_prevents_duplicate_extension(self):
        cleaned = clean_filename("receipt_october.pdf", ".pdf", "orig")
        self.assertEqual(cleaned, "receipt_october.pdf")

    def test_model_suggested_different_extension_is_overridden(self):
        # Even if the model proposes .txt for a .pdf file, the tool must enforce the original .pdf
        cleaned = clean_filename("document_notes.txt", ".pdf", "orig")
        self.assertEqual(cleaned, "document_notes.pdf")

    def test_empty_string_falls_back_to_original_stem(self):
        cleaned = clean_filename("", ".jpg", "IMG_0001")
        self.assertEqual(cleaned, "IMG_0001.jpg")

    def test_pure_punctuation_falls_back_to_original_stem(self):
        cleaned = clean_filename("...:::???", ".png", "screenshot")
        self.assertEqual(cleaned, "screenshot.png")

    def test_very_long_filename_is_truncated(self):
        long_stem = "a" * 200
        cleaned = clean_filename(long_stem, ".txt", "original_long")
        # clean_filename truncates stems to at most 120 chars
        stem = cleaned[:-4]
        self.assertLessEqual(len(stem), 120)
        self.assertTrue(cleaned.endswith(".txt"))


class TestCategoryMatching(unittest.TestCase):
    def test_exact_match(self):
        self.assertEqual(match_category("Invoices", ALLOWED_CATEGORIES), "Invoices")

    def test_case_insensitive_match(self):
        self.assertEqual(match_category("photos", ALLOWED_CATEGORIES), "Photos")
        self.assertEqual(match_category("INSTALLERS", ALLOWED_CATEGORIES), "Installers")

    def test_partial_match_phrase(self):
        self.assertEqual(match_category("Documents folder", ALLOWED_CATEGORIES), "Documents")

    def test_unknown_category_falls_back_to_misc(self):
        self.assertEqual(match_category("Cryptocurrency", ALLOWED_CATEGORIES, fallback="Misc"), "Misc")
        self.assertEqual(match_category("", ALLOWED_CATEGORIES, fallback="Misc"), "Misc")


if __name__ == "__main__":
    unittest.main()

"""Unit tests for file scanner filtering rules and text reader."""

import os
from pathlib import Path
import tempfile
import time
import unittest

from sloth_sort.reader import read_file_snippet
from sloth_sort.scanner import scan_directory


class TestScannerAndReader(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_scanner_skips_hidden_files(self):
        hidden = self.root / ".hidden_file.txt"
        hidden.write_text("hidden")
        # Age file artificially so age check passes
        old_time = time.time() - 1000
        os.utime(hidden, (old_time, old_time))

        eligible, skipped = scan_directory(self.root, min_age_seconds=600)
        self.assertEqual(len(eligible), 0)
        self.assertEqual(len(skipped), 1)
        self.assertEqual(skipped[0].reason, "Hidden file")

    def test_scanner_skips_partial_downloads(self):
        partial = self.root / "installer.exe.crdownload"
        partial.write_text("in progress")
        old_time = time.time() - 1000
        os.utime(partial, (old_time, old_time))

        eligible, skipped = scan_directory(self.root, min_age_seconds=600)
        self.assertEqual(len(eligible), 0)
        self.assertEqual(len(skipped), 1)
        self.assertIn("Incomplete download", skipped[0].reason)

    def test_scanner_skips_recently_modified_files(self):
        fresh = self.root / "downloading_now.pdf"
        fresh.write_text("freshly written")

        eligible, skipped = scan_directory(self.root, min_age_seconds=600)
        self.assertEqual(len(eligible), 0)
        self.assertEqual(len(skipped), 1)
        self.assertIn("Modified recently", skipped[0].reason)

    def test_scanner_skips_subdirectories(self):
        sub_folder = self.root / "ExistingSubfolder"
        sub_folder.mkdir()
        nested_file = sub_folder / "nested.txt"
        nested_file.write_text("nested")

        eligible, skipped = scan_directory(self.root, min_age_seconds=0)
        self.assertEqual(len(eligible), 0)

    def test_scanner_includes_eligible_old_files(self):
        valid = self.root / "contract_2025.txt"
        valid.write_text("Valid contract snippet")
        old_time = time.time() - 1000
        os.utime(valid, (old_time, old_time))

        eligible, skipped = scan_directory(self.root, min_age_seconds=600)
        self.assertEqual(len(eligible), 1)
        self.assertEqual(eligible[0].name, "contract_2025.txt")

    def test_reader_extracts_plain_text(self):
        test_file = self.root / "sample.md"
        test_file.write_text("# Title\n\nThis is a sample markdown snippet.")
        snippet = read_file_snippet(test_file, max_chars=100)
        self.assertIn("sample markdown snippet", snippet)

    def test_reader_ignores_binary_files(self):
        bin_file = self.root / "sample.bin"
        bin_file.write_bytes(b"\x00\x01\x02\x03\xff")
        snippet = read_file_snippet(bin_file, max_chars=100)
        self.assertEqual(snippet, "")


if __name__ == "__main__":
    unittest.main()

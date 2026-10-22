"""Unit tests for move execution and reversible undo operations."""

from pathlib import Path
import tempfile
import time
import unittest

from sloth_sort.mover import apply_plan, revert_undo_log
from sloth_sort.planner import PlanAction, PlanResult


class TestMoverAndUndo(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

        # Create source files
        self.file1 = self.root / "inv_123.txt"
        self.file1.write_text("Invoice details")

        self.file2 = self.root / "setup.exe"
        self.file2.write_text("Binary installer")

        self.undo_log_path = self.root / "undo_log.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_apply_and_revert_moves(self):
        plan = PlanResult(
            target_dir=str(self.root),
            model_name="test_model",
            created_at=time.time(),
            actions=[
                PlanAction(
                    original_path=str(self.file1),
                    original_name=self.file1.name,
                    target_path=str(self.root / "Invoices" / "Invoice_October.txt"),
                    new_name="Invoice_October.txt",
                    folder="Invoices",
                    size_bytes=len("Invoice details"),
                ),
                PlanAction(
                    original_path=str(self.file2),
                    original_name=self.file2.name,
                    target_path=str(self.root / "Installers" / "Software_Setup.exe"),
                    new_name="Software_Setup.exe",
                    folder="Installers",
                    size_bytes=len("Binary installer"),
                ),
            ],
            skipped=[],
        )

        # Apply the plan
        success, skipped, errors = apply_plan(plan, self.undo_log_path)
        self.assertEqual(success, 2)
        self.assertEqual(skipped, 0)
        self.assertFalse(self.file1.exists())
        self.assertFalse(self.file2.exists())
        self.assertTrue((self.root / "Invoices" / "Invoice_October.txt").exists())
        self.assertTrue((self.root / "Installers" / "Software_Setup.exe").exists())
        self.assertTrue(self.undo_log_path.exists())

        # Revert the plan
        undo_success, undo_skipped, undo_errors = revert_undo_log(self.undo_log_path)
        self.assertEqual(undo_success, 2)
        self.assertEqual(undo_skipped, 0)

        # Original files restored
        self.assertTrue(self.file1.exists())
        self.assertTrue(self.file2.exists())
        self.assertEqual(self.file1.read_text(), "Invoice details")
        self.assertEqual(self.file2.read_text(), "Binary installer")

        # Empty category directories cleaned up
        self.assertFalse((self.root / "Invoices").exists())
        self.assertFalse((self.root / "Installers").exists())

        # Undo log removed after complete reversal
        self.assertFalse(self.undo_log_path.exists())

    def test_security_prevents_escape_outside_target_folder(self):
        outside_file = self.root.parent / "sensitive.txt"
        plan = PlanResult(
            target_dir=str(self.root),
            model_name="test_model",
            created_at=time.time(),
            actions=[
                PlanAction(
                    original_path=str(outside_file),
                    original_name="sensitive.txt",
                    target_path=str(self.root / "Misc" / "sensitive.txt"),
                    new_name="sensitive.txt",
                    folder="Misc",
                    size_bytes=10,
                )
            ],
            skipped=[],
        )
        success, skipped, errors = apply_plan(plan, self.undo_log_path)
        self.assertEqual(success, 0)
        self.assertEqual(skipped, 1)
        self.assertIn("path outside target folder", errors[0])


if __name__ == "__main__":
    unittest.main()

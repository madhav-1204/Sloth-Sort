"""Unit tests for filename collision resolution."""

from pathlib import Path
import tempfile
import unittest

from sloth_sort.planner import resolve_collision


class TestCollisionResolution(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dest_folder = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_no_collision(self):
        reserved = set()
        chosen_name, dest_path = resolve_collision("report.pdf", self.dest_folder, reserved)
        self.assertEqual(chosen_name, "report.pdf")
        self.assertEqual(dest_path, self.dest_folder / "report.pdf")
        self.assertIn(dest_path, reserved)

    def test_collision_with_existing_disk_file(self):
        # Create report.pdf on disk
        (self.dest_folder / "report.pdf").write_text("existing content")

        reserved = set()
        chosen_name, dest_path = resolve_collision("report.pdf", self.dest_folder, reserved)
        self.assertEqual(chosen_name, "report_1.pdf")
        self.assertEqual(dest_path, self.dest_folder / "report_1.pdf")
        self.assertIn(dest_path, reserved)

    def test_multiple_collisions_with_disk_files(self):
        (self.dest_folder / "photo.jpg").write_text("photo 0")
        (self.dest_folder / "photo_1.jpg").write_text("photo 1")
        (self.dest_folder / "photo_2.jpg").write_text("photo 2")

        reserved = set()
        chosen_name, dest_path = resolve_collision("photo.jpg", self.dest_folder, reserved)
        self.assertEqual(chosen_name, "photo_3.jpg")
        self.assertEqual(dest_path, self.dest_folder / "photo_3.jpg")

    def test_in_batch_collision_between_two_planned_moves(self):
        # Two files want the exact same destination in the same plan
        reserved = set()
        name1, dest1 = resolve_collision("notes.txt", self.dest_folder, reserved)
        name2, dest2 = resolve_collision("notes.txt", self.dest_folder, reserved)

        self.assertEqual(name1, "notes.txt")
        self.assertEqual(name2, "notes_1.txt")
        self.assertNotEqual(dest1, dest2)
        self.assertIn(dest1, reserved)
        self.assertIn(dest2, reserved)


if __name__ == "__main__":
    unittest.main()

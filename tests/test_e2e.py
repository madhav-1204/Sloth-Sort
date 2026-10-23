"""End-to-end test script verifying plan, apply, undo, and integrity guarantees."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def get_folder_manifest(folder: Path) -> dict[str, str]:
    """Compute sha256 hash for every file relative to folder root."""
    manifest = {}
    for item in sorted(folder.rglob("*")):
        if item.is_file():
            rel = str(item.relative_to(folder)).replace("\\", "/")
            content = item.read_bytes()
            manifest[rel] = hashlib.sha256(content).hexdigest()
    return manifest


def run_e2e():
    print("--- Starting sloth-sort End-to-End Validation ---")
    fixtures_dir = PROJECT_ROOT / "tests" / "fixtures"
    backup_dir = fixtures_dir / "messy_folder_backup"
    e2e_dir = fixtures_dir / "e2e_test_folder"

    # Reset e2e folder from backup
    if e2e_dir.exists():
        shutil.rmtree(e2e_dir)
    shutil.copytree(backup_dir, e2e_dir)

    # Clean any leftover plan.json or undo_log.json
    (PROJECT_ROOT / "plan.json").unlink(missing_ok=True)
    (PROJECT_ROOT / "undo_log.json").unlink(missing_ok=True)

    initial_manifest = get_folder_manifest(e2e_dir)
    initial_count = len(initial_manifest)
    print(f"[Initial State] Total files: {initial_count}")
    assert initial_count == 40, f"Expected 40 files, got {initial_count}"

    # CHECK 1: sloth-sort plan makes NO changes
    print("\n[Check 1] Running sloth-sort plan ...")
    cmd_plan = [
        sys.executable,
        "-m",
        "sloth_sort.cli",
        "plan",
        str(e2e_dir),
        "--model",
        "gemma3:1b",
    ]
    res_plan = subprocess.run(cmd_plan, cwd=str(PROJECT_ROOT), capture_output=True, text=True)
    print(f"Plan exited with code {res_plan.returncode}")
    if res_plan.returncode != 0:
        print("STDERR:", res_plan.stderr)
        print("STDOUT:", res_plan.stdout)
        sys.exit(1)

    plan_manifest = get_folder_manifest(e2e_dir)
    assert plan_manifest == initial_manifest, "Check 1 FAILED: Files were changed during plan!"
    print("Check 1 PASSED: Plan made zero changes to files or folder layout.")
    assert (PROJECT_ROOT / "plan.json").exists(), "plan.json was not created!"

    # CHECK 2 & 3: sloth-sort apply moves files and preserves exact count
    print("\n[Check 2 & 3] Running sloth-sort apply ...")
    cmd_apply = [
        sys.executable,
        "-m",
        "sloth_sort.cli",
        "apply",
        "-y",
    ]
    res_apply = subprocess.run(cmd_apply, cwd=str(PROJECT_ROOT), capture_output=True, text=True)
    print(f"Apply exited with code {res_apply.returncode}")
    if res_apply.returncode != 0:
        print("STDERR:", res_apply.stderr)
        print("STDOUT:", res_apply.stdout)
        sys.exit(1)

    post_apply_manifest = get_folder_manifest(e2e_dir)
    post_apply_count = len(post_apply_manifest)
    print(f"[Post-Apply State] Total files: {post_apply_count}")
    assert post_apply_count == initial_count, (
        f"Check 3 FAILED: File count mismatch! Before: {initial_count}, After: {post_apply_count}"
    )
    # Check that category subfolders were created
    subdirs = [d.name for d in e2e_dir.iterdir() if d.is_dir()]
    print(f"Created category directories: {subdirs}")
    assert len(subdirs) > 0, "No category directories were created!"
    print("Check 2 & 3 PASSED: Files successfully moved into category folders; file count preserved.")

    # CHECK 4: sloth-sort undo restores exact original state
    print("\n[Check 4] Running sloth-sort undo ...")
    cmd_undo = [
        sys.executable,
        "-m",
        "sloth_sort.cli",
        "undo",
    ]
    res_undo = subprocess.run(cmd_undo, cwd=str(PROJECT_ROOT), capture_output=True, text=True)
    print(f"Undo exited with code {res_undo.returncode}")
    if res_undo.returncode != 0:
        print("STDERR:", res_undo.stderr)
        print("STDOUT:", res_undo.stdout)
        sys.exit(1)

    post_undo_manifest = get_folder_manifest(e2e_dir)
    assert post_undo_manifest == initial_manifest, (
        "Check 4 FAILED: Restored folder does not match original SHA256 hashes or paths!"
    )
    # Check no leftover category directories
    remaining_dirs = [d.name for d in e2e_dir.iterdir() if d.is_dir()]
    assert len(remaining_dirs) == 0, f"Empty category folders left over: {remaining_dirs}"
    print("Check 4 PASSED: Undo restored all 40 files to exact paths and hashes.")

    # Clean up test directory
    shutil.rmtree(e2e_dir)
    print("\n--- All End-to-End Checks Succeeded! ---")


if __name__ == "__main__":
    run_e2e()

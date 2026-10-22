"""Executes file operations safely and logs actions for full reversibility."""

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import shutil
import time
from typing import Dict, List, Optional, Tuple

from sloth_sort.planner import PlanAction, PlanResult, resolve_collision


@dataclass
class MovedFileRecord:
    original_path: str
    moved_path: str
    timestamp: float


@dataclass
class UndoLog:
    target_dir: str
    created_at: float
    records: List[MovedFileRecord]


def apply_plan(
    plan: PlanResult,
    undo_log_path: Path,
) -> Tuple[int, int, List[str]]:
    """
    Execute the actions specified in a plan.
    Ensures safe moves, checks collision at runtime, and writes an undo log.
    Returns (success_count, skipped_count, error_messages).
    """
    target_dir = Path(plan.target_dir).resolve()
    success_count = 0
    skipped_count = 0
    errors: List[str] = []
    records: List[MovedFileRecord] = []

    for action in plan.actions:
        source = Path(action.original_path).resolve()
        destination = Path(action.target_path).resolve()

        # Guard against path traversal
        try:
            source.relative_to(target_dir)
            destination.relative_to(target_dir)
        except ValueError:
            msg = f"Skipping {source.name}: path outside target folder."
            errors.append(msg)
            skipped_count += 1
            continue

        if not source.exists():
            msg = f"Skipping {source.name}: source file no longer exists."
            errors.append(msg)
            skipped_count += 1
            continue

        # Ensure parent category directory exists
        destination.parent.mkdir(parents=True, exist_ok=True)

        # Collision guard right before move
        if destination.exists():
            # In case a file appeared at destination between plan and apply
            reserved = {destination}
            _, destination = resolve_collision(destination.name, destination.parent, reserved)

        try:
            shutil.move(str(source), str(destination))
            records.append(
                MovedFileRecord(
                    original_path=str(source),
                    moved_path=str(destination),
                    timestamp=time.time(),
                )
            )
            success_count += 1
        except Exception as e:
            msg = f"Failed to move {source.name} to {destination.name}: {e}"
            errors.append(msg)
            skipped_count += 1

    # Save undo log
    undo_data = {
        "target_dir": str(target_dir),
        "created_at": time.time(),
        "records": [asdict(r) for r in records],
    }
    with open(undo_log_path, "w", encoding="utf-8") as f:
        json.dump(undo_data, f, indent=2)

    return success_count, skipped_count, errors


def revert_undo_log(undo_log_path: Path) -> Tuple[int, int, List[str]]:
    """
    Revert the moves recorded in the undo log.
    Restores files to their original paths and cleans up newly empty category folders.
    """
    if not undo_log_path.exists():
        raise FileNotFoundError(f"No undo log found at {undo_log_path}. Nothing to revert.")

    with open(undo_log_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    target_dir = Path(data.get("target_dir", "")).resolve()
    records_data = data.get("records", [])
    if not records_data:
        return 0, 0, ["Undo log is empty."]

    success_count = 0
    skipped_count = 0
    errors: List[str] = []
    touched_dirs = set()

    for item in records_data:
        moved_file = Path(item["moved_path"]).resolve()
        original_file = Path(item["original_path"]).resolve()

        if not moved_file.exists():
            errors.append(f"Cannot revert {moved_file.name}: file is missing.")
            skipped_count += 1
            continue

        if original_file.exists():
            errors.append(f"Cannot revert {moved_file.name}: original destination {original_file.name} already exists.")
            skipped_count += 1
            continue

        try:
            original_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(moved_file), str(original_file))
            touched_dirs.add(moved_file.parent)
            success_count += 1
        except Exception as e:
            errors.append(f"Error reverting {moved_file.name}: {e}")
            skipped_count += 1

    # Safely clean up empty category directories inside target_dir
    for d in touched_dirs:
        try:
            if d.resolve() != target_dir and d.resolve().is_relative_to(target_dir):
                # Only remove if directory is completely empty
                if not any(d.iterdir()):
                    d.rmdir()
        except Exception:
            pass

    # Clear undo log so it cannot be run twice
    undo_log_path.unlink(missing_ok=True)

    return success_count, skipped_count, errors

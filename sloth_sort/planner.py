"""Generates sorting plans with collision detection and formats console tables."""

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from sloth_sort.model import generate_file_plan
from sloth_sort.reader import read_file_snippet
from sloth_sort.scanner import ScannedFile, SkippedFile


@dataclass
class PlanAction:
    original_path: str
    original_name: str
    target_path: str
    new_name: str
    folder: str
    size_bytes: int


@dataclass
class PlanResult:
    target_dir: str
    model_name: str
    created_at: float
    actions: List[PlanAction]
    skipped: List[Dict[str, str]]


def resolve_collision(
    candidate_name: str,
    target_folder: Path,
    reserved_destinations: Set[Path],
) -> Tuple[str, Path]:
    """
    Ensure the target filename does not overwrite an existing file on disk
    or collide with another planned move in the same batch.
    Appends _1, _2, etc. before the extension if a collision occurs.
    """
    candidate_path = Path(candidate_name)
    stem = candidate_path.stem
    extension = candidate_path.suffix

    destination = target_folder / candidate_name
    if not destination.exists() and destination not in reserved_destinations:
        reserved_destinations.add(destination)
        return candidate_name, destination

    counter = 1
    while True:
        numbered_name = f"{stem}_{counter}{extension}"
        destination = target_folder / numbered_name
        if not destination.exists() and destination not in reserved_destinations:
            reserved_destinations.add(destination)
            return numbered_name, destination
        counter += 1


def create_plan(
    target_dir: Path,
    files: List[ScannedFile],
    endpoint: str,
    model_name: str,
    allowed_categories: List[str],
    fallback_category: str = "Misc",
    max_snippet_chars: int = 1000,
) -> PlanResult:
    """
    Generate an organization plan for all eligible scanned files.
    Queries the model one file at a time, printing progress.
    """
    import time

    target_dir = target_dir.resolve()
    actions: List[PlanAction] = []
    skipped_records: List[Dict[str, str]] = []
    reserved_destinations: Set[Path] = set()

    total = len(files)
    for idx, scanned in enumerate(files, 1):
        print(f"[{idx}/{total}] Processing: {scanned.name} ...", end=" ", flush=True)

        snippet = read_file_snippet(scanned.path, max_chars=max_snippet_chars)
        new_name, folder, error = generate_file_plan(
            endpoint=endpoint,
            model_name=model_name,
            filename=scanned.name,
            snippet=snippet,
            allowed_categories=allowed_categories,
            fallback_category=fallback_category,
        )

        if error or not new_name or not folder:
            reason = error or "Model returned empty or invalid response"
            print(f"FAILED ({reason})")
            skipped_records.append({
                "path": str(scanned.path),
                "name": scanned.name,
                "reason": reason,
            })
            continue

        category_folder = target_dir / folder
        final_name, destination = resolve_collision(
            new_name, category_folder, reserved_destinations
        )

        # Confirm destination is strictly inside target_dir
        try:
            destination.relative_to(target_dir)
        except ValueError:
            print("FAILED (Security: attempted path traversal outside target folder)")
            skipped_records.append({
                "path": str(scanned.path),
                "name": scanned.name,
                "reason": "Destination escaped target directory",
            })
            continue

        actions.append(
            PlanAction(
                original_path=str(scanned.path),
                original_name=scanned.name,
                target_path=str(destination),
                new_name=final_name,
                folder=folder,
                size_bytes=scanned.size_bytes,
            )
        )
        print(f"-> {folder}/{final_name}")

    return PlanResult(
        target_dir=str(target_dir),
        model_name=model_name,
        created_at=time.time(),
        actions=actions,
        skipped=skipped_records,
    )


def save_plan(plan: PlanResult, plan_path: Path) -> None:
    """Persist the plan to a JSON file."""
    data = {
        "target_dir": plan.target_dir,
        "model_name": plan.model_name,
        "created_at": plan.created_at,
        "actions": [asdict(a) for a in plan.actions],
        "skipped": plan.skipped,
    }
    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_plan(plan_path: Path) -> PlanResult:
    """Load an existing plan from a JSON file."""
    if not plan_path.exists():
        raise FileNotFoundError(f"Plan file not found: {plan_path}. Run 'sloth-sort plan' first.")

    with open(plan_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    actions = [PlanAction(**a) for a in data.get("actions", [])]
    return PlanResult(
        target_dir=data["target_dir"],
        model_name=data["model_name"],
        created_at=data["created_at"],
        actions=actions,
        skipped=data.get("skipped", []),
    )


def format_plan_table(plan: PlanResult) -> str:
    """Format the plan as a clean terminal table without external dependencies or emoji."""
    if not plan.actions:
        return "No files scheduled for organization."

    headers = ("Original Name", "New Name", "Category")
    rows = []
    for action in plan.actions:
        rows.append((action.original_name, action.new_name, action.folder))

    # Calculate column widths, capped for terminal readability
    col0_w = max(len(headers[0]), max(min(len(r[0]), 36) for r in rows))
    col1_w = max(len(headers[1]), max(min(len(r[1]), 36) for r in rows))
    col2_w = max(len(headers[2]), max(len(r[2]) for r in rows))

    def truncate(text: str, width: int) -> str:
        if len(text) <= width:
            return text
        return text[: width - 3] + "..."

    separator = f"+-{'-' * col0_w}-+-{'-' * col1_w}-+-{'-' * col2_w}-+"
    header_line = (
        f"| {headers[0].ljust(col0_w)} "
        f"| {headers[1].ljust(col1_w)} "
        f"| {headers[2].ljust(col2_w)} |"
    )

    lines = [separator, header_line, separator]
    for orig, new, cat in rows:
        lines.append(
            f"| {truncate(orig, col0_w).ljust(col0_w)} "
            f"| {truncate(new, col1_w).ljust(col1_w)} "
            f"| {cat.ljust(col2_w)} |"
        )
    lines.append(separator)

    return "\n".join(lines)

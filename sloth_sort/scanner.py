"""Scans a target directory for loose files eligible for sorting."""

from dataclasses import dataclass
from pathlib import Path
import time
from typing import List, Tuple


@dataclass
class ScannedFile:
    path: Path
    name: str
    extension: str
    size_bytes: int
    mtime: float


@dataclass
class SkippedFile:
    path: Path
    reason: str


def scan_directory(
    target_dir: Path,
    min_age_seconds: int = 600,
    ignored_extensions: List[str] = None,
) -> Tuple[List[ScannedFile], List[SkippedFile]]:
    """
    Scan loose files directly inside target_dir.
    Skips subdirectories, hidden files, partial downloads, and recently modified files.
    """
    if ignored_extensions is None:
        ignored_extensions = [".crdownload", ".part", ".tmp", ".download"]

    normalized_ignored_exts = {ext.lower() for ext in ignored_extensions}
    current_time = time.time()

    eligible: List[ScannedFile] = []
    skipped: List[SkippedFile] = []

    target_dir = target_dir.expanduser().resolve()
    if not target_dir.exists() or not target_dir.is_dir():
        raise FileNotFoundError(f"Directory not found: {target_dir}")

    # Only inspect direct children in the folder
    for item in sorted(target_dir.iterdir()):
        # Directories are never moved or renamed
        if item.is_dir():
            continue

        if not item.is_file():
            continue

        filename = item.name

        # Skip hidden files
        if filename.startswith("."):
            skipped.append(SkippedFile(path=item, reason="Hidden file"))
            continue

        # Skip partial downloads or temporary files
        suffix = item.suffix.lower()
        if suffix in normalized_ignored_exts:
            skipped.append(SkippedFile(path=item, reason="Incomplete download / temporary file"))
            continue

        try:
            stat = item.stat()
        except OSError as e:
            skipped.append(SkippedFile(path=item, reason=f"Cannot stat file: {e}"))
            continue

        # Skip files modified in the last min_age_seconds (e.g. 10 minutes)
        # Avoids renaming files currently being written or downloaded
        file_age = current_time - stat.st_mtime
        if file_age < min_age_seconds:
            remaining_mins = int((min_age_seconds - file_age) / 60) + 1
            skipped.append(
                SkippedFile(
                    path=item,
                    reason=f"Modified recently ({int(file_age)}s ago, cooldown {remaining_mins}m)",
                )
            )
            continue

        eligible.append(
            ScannedFile(
                path=item,
                name=filename,
                extension=suffix,
                size_bytes=stat.st_size,
                mtime=stat.st_mtime,
            )
        )

    return eligible, skipped

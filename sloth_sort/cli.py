"""Command-line interface for sloth-sort."""

import argparse
from pathlib import Path
import sys
import tomllib
from typing import Any, Dict

from sloth_sort.mover import apply_plan, revert_undo_log
from sloth_sort.planner import create_plan, format_plan_table, load_plan, save_plan
from sloth_sort.scanner import scan_directory

DEFAULT_CONFIG: Dict[str, Any] = {
    "model": {
        "name": "gemma3:1b",
        "endpoint": "http://127.0.0.1:11434",
    },
    "categories": {
        "allowed": [
            "Invoices",
            "Study",
            "Photos",
            "Installers",
            "Code",
            "Documents",
            "Media",
            "Misc",
        ],
        "fallback": "Misc",
    },
    "scanner": {
        "min_age_seconds": 600,
        "ignored_extensions": [".crdownload", ".part", ".tmp", ".download"],
        "max_text_chars": 1000,
    },
}


def load_configuration(custom_path: Path | None = None) -> Dict[str, Any]:
    """Load config.toml from custom path, current directory, or user home."""
    candidates = []
    if custom_path:
        candidates.append(custom_path)
    candidates.append(Path.cwd() / "config.toml")
    candidates.append(Path.home() / ".config" / "sloth-sort" / "config.toml")

    for path in candidates:
        if path.is_file():
            try:
                with open(path, "rb") as f:
                    user_cfg = tomllib.load(f)
                # Shallow-merge with defaults
                merged = {**DEFAULT_CONFIG}
                for key, val in user_cfg.items():
                    if isinstance(val, dict) and key in merged:
                        merged[key] = {**merged[key], **val}
                    else:
                        merged[key] = val
                return merged
            except Exception as e:
                print(f"Warning: could not read {path}: {e}. Using defaults.")

    return DEFAULT_CONFIG


def run_plan(args: argparse.Namespace) -> int:
    """Execute dry-run scanning and planning."""
    config = load_configuration(Path(args.config) if args.config else None)

    target_dir_str = args.folder or str(Path.home() / "Downloads")
    target_dir = Path(target_dir_str).expanduser().resolve()

    if not target_dir.exists():
        print(f"Error: target folder does not exist: {target_dir}")
        return 1

    if not target_dir.is_dir():
        print(f"Error: target path is not a directory: {target_dir}")
        return 1

    model_name = args.model or config["model"]["name"]
    endpoint = config["model"]["endpoint"]
    allowed_categories = config["categories"]["allowed"]
    fallback_category = config["categories"]["fallback"]
    min_age = args.min_age if args.min_age is not None else config["scanner"]["min_age_seconds"]
    ignored_exts = config["scanner"]["ignored_extensions"]
    max_chars = config["scanner"]["max_text_chars"]

    print(f"Target folder: {target_dir}")
    print(f"Using local model: {model_name} via {endpoint}")
    print("Scanning for files ...")

    try:
        eligible, skipped = scan_directory(
            target_dir=target_dir,
            min_age_seconds=min_age,
            ignored_extensions=ignored_exts,
        )
    except Exception as e:
        print(f"Error while scanning folder: {e}")
        return 1

    if skipped:
        print(f"Skipped {len(skipped)} files (active cooldown, hidden, or incomplete downloads).")

    if not eligible:
        print("No files eligible for sorting.")
        return 0

    print(f"Found {len(eligible)} files to analyze.\n")

    try:
        plan = create_plan(
            target_dir=target_dir,
            files=eligible,
            endpoint=endpoint,
            model_name=model_name,
            allowed_categories=allowed_categories,
            fallback_category=fallback_category,
            max_snippet_chars=max_chars,
        )
    except ConnectionError as e:
        print(f"\n{e}")
        return 1

    print("\nProposed Plan:")
    print(format_plan_table(plan))

    plan_path = Path.cwd() / "plan.json"
    save_plan(plan, plan_path)
    print(f"\nPlan saved to {plan_path.name}")
    print("Run 'sloth-sort apply' to execute these changes.")
    return 0


def run_apply(args: argparse.Namespace) -> int:
    """Apply the last generated plan."""
    plan_path = Path.cwd() / "plan.json"
    undo_path = Path.cwd() / "undo_log.json"

    try:
        plan = load_plan(plan_path)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1

    if not plan.actions:
        print("The plan has no file movements scheduled.")
        return 0

    print(f"Loaded plan for: {plan.target_dir}")
    print(format_plan_table(plan))

    if not args.yes:
        confirm = input(f"\nApply plan to move {len(plan.actions)} files? [y/N]: ").strip().lower()
        if confirm not in ("y", "yes"):
            print("Operation aborted. No files were moved.")
            return 0

    print("\nApplying changes ...")
    success, skipped, errors = apply_plan(plan, undo_path)

    for err in errors:
        print(f"Note: {err}")

    print(f"\nCompleted: {success} files moved, {skipped} skipped.")
    print(f"Undo log written to {undo_path.name}.")
    print("Run 'sloth-sort undo' if you want to revert this operation.")

    # Remove completed plan file
    plan_path.unlink(missing_ok=True)
    return 0


def run_undo(args: argparse.Namespace) -> int:
    """Revert the last applied operations."""
    undo_path = Path.cwd() / "undo_log.json"

    try:
        success, skipped, errors = revert_undo_log(undo_path)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1

    for err in errors:
        print(f"Note: {err}")

    print(f"Undo complete: {success} files restored to original locations, {skipped} skipped.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for sloth-sort."""
    parser = argparse.ArgumentParser(
        prog="sloth-sort",
        description="Tidy messy folders using a local model.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # plan command
    plan_parser = subparsers.add_parser(
        "plan",
        help="Dry run. Prints the proposed plan and saves it to plan.json.",
    )
    plan_parser.add_argument(
        "folder",
        nargs="?",
        default=None,
        help="Target directory to sort (default: ~/Downloads).",
    )
    plan_parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Local model name to use with Ollama (e.g. gemma3:1b, gemma3:4b).",
    )
    plan_parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to custom config.toml file.",
    )
    plan_parser.add_argument(
        "--min-age",
        type=int,
        default=None,
        help="Cooldown threshold in seconds for recent file modifications (default: 600).",
    )

    # apply command
    apply_parser = subparsers.add_parser(
        "apply",
        help="Applies the last plan after a y/n confirmation. Writes undo_log.json.",
    )
    apply_parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Skip interactive confirmation prompt.",
    )

    # undo command
    subparsers.add_parser(
        "undo",
        help="Reverts the last applied run using the undo log.",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "plan":
        sys.exit(run_plan(args))
    elif args.command == "apply":
        sys.exit(run_apply(args))
    elif args.command == "undo":
        sys.exit(run_undo(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

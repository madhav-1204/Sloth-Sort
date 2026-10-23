"""Benchmark suite for sloth-sort across Ollama local models."""

import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import time
from typing import Any, Dict, List, Tuple

from sloth_sort.model import (
    TEXT_READABLE_EXTENSIONS,
    _send_ollama_request,
    clean_filename,
    match_category,
)
from sloth_sort.planner import resolve_collision
from sloth_sort.reader import read_file_snippet
from sloth_sort.scanner import scan_directory

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"
MESSY_DIR = FIXTURES_DIR / "messy_folder"
BACKUP_DIR = FIXTURES_DIR / "messy_folder_backup"
GROUND_TRUTH_PATH = FIXTURES_DIR / "ground_truth.json"

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


def collect_environment_info() -> Dict[str, str]:
    """Gather machine, runtime, and hardware details."""
    env = {
        "os": platform.platform(),
        "python": platform.python_version(),
        "cpu": platform.processor() or "AMD64 Family",
        "cpu_cores": str(os.cpu_count() or "unknown"),
        "ram": "unknown",
        "gpu": "unknown",
        "ollama_version": "unknown",
    }

    # Query Ollama version
    try:
        out = subprocess.check_output(["ollama", "--version"], text=True)
        env["ollama_version"] = out.strip().replace("ollama version is ", "")
    except Exception:
        pass

    # Windows-specific system inspection
    if platform.system() == "Windows":
        try:
            ps_cmd = (
                "Get-CimInstance Win32_OperatingSystem | Select-Object -ExpandProperty Caption; "
                "Get-CimInstance Win32_Processor | Select-Object -ExpandProperty Name; "
                "Get-CimInstance Win32_OperatingSystem | Select-Object -ExpandProperty TotalVisibleMemorySize; "
                "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"
            )
            out = subprocess.check_output(["powershell", "-NoProfile", "-Command", ps_cmd], text=True)
            lines = [line.strip() for line in out.splitlines() if line.strip()]
            if len(lines) >= 1:
                env["os_caption"] = lines[0]
            if len(lines) >= 2:
                env["cpu"] = lines[1]
            if len(lines) >= 3:
                kb = int(lines[2])
                env["ram"] = f"{kb / (1024 * 1024):.2f} GB ({kb} KB)"
            if len(lines) >= 4:
                env["gpu"] = lines[3]
        except Exception:
            pass

    return env


def benchmark_single_file(
    endpoint: str,
    model_name: str,
    scanned_file: Any,
    allowed_categories: List[str],
    fallback_category: str = "Misc",
) -> Tuple[str, str, Dict[str, Any]]:
    """
    Execute generation for a single file while instrumenting JSON validity and retries.
    Returns (cleaned_name, category, metrics_dict).
    """
    filename = scanned_file.name
    original_path = scanned_file.path
    original_extension = original_path.suffix
    original_stem = original_path.stem
    is_text_readable = original_extension.lower() in TEXT_READABLE_EXTENSIONS

    snippet = read_file_snippet(original_path, max_chars=1000)
    category_list_str = ", ".join(allowed_categories)

    base_prompt = (
        f"You are a file organization assistant. Analyze this file:\n"
        f"Original filename: {filename}\n"
    )
    if is_text_readable and snippet:
        base_prompt += f"First {len(snippet)} characters of content:\n\"\"\"\n{snippet}\n\"\"\"\n\n"
    elif is_text_readable:
        base_prompt += "No readable text content. Base your decision purely on the filename and file extension.\n\n"
    else:
        base_prompt += "Binary or media file. Base your decision purely on the filename and file extension.\n\n"

    base_prompt += (
        f"Tasks:\n"
        f"1. Choose exactly one category folder from [{category_list_str}]:\n"
        f"   - Invoices: bills, receipts, payment notices, invoices\n"
        f"   - Study: courses, lectures, academic papers, homework\n"
        f"   - Photos: pictures, screenshots, images\n"
        f"   - Installers: executable setups, installers (.exe, .msi, .dmg, etc.)\n"
        f"   - Code: source code, scripts (.py, .js, .html, etc.)\n"
        f"   - Documents: agreements, forms, spreadsheets, reports, generic docs\n"
        f"   - Media: audio, video, podcasts, music\n"
        f"   - Misc: only if it does not fit any of the above\n"
    )
    if is_text_readable:
        base_prompt += (
            f"2. Suggest a clean, descriptive, human-readable file name (without extension or with same extension).\n"
            f"Output MUST be strict JSON with exactly two string keys: 'new_name' and 'folder'. Do not include explanation."
        )
    else:
        base_prompt += (
            f"2. Do not rename binary or image files. Keep 'new_name' exactly as '{filename}'.\n"
            f"Output MUST be strict JSON with exactly two string keys: 'new_name' and 'folder'. Do not include explanation."
        )

    file_metrics = {
        "filename": filename,
        "is_text_readable": is_text_readable,
        "attempts": 0,
        "invalid_json_attempts": 0,
        "retry_fixed": False,
        "skipped": False,
        "raw_responses": [],
        "duration_seconds": 0.0,
    }

    t0 = time.perf_counter()
    for attempt in range(2):
        file_metrics["attempts"] += 1
        prompt = (
            base_prompt
            if attempt == 0
            else f"{base_prompt}\nReminder: output only valid JSON with 'new_name' and 'folder'."
        )

        try:
            raw = _send_ollama_request(endpoint, model_name, prompt)
            file_metrics["raw_responses"].append(raw)
        except Exception as e:
            file_metrics["skipped"] = True
            file_metrics["duration_seconds"] = time.perf_counter() - t0
            return filename, fallback_category, file_metrics

        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                file_metrics["invalid_json_attempts"] += 1
                continue

            raw_new_name = parsed.get("new_name")
            raw_folder = parsed.get("folder")

            if not raw_folder or not isinstance(raw_folder, str) or not raw_folder.strip():
                if attempt == 0:
                    file_metrics["invalid_json_attempts"] += 1
                    continue
                raw_folder = fallback_category

            category = match_category(str(raw_folder).strip(), allowed_categories, fallback_category)

            if not is_text_readable:
                cleaned_name = filename
                if attempt == 1 and file_metrics["invalid_json_attempts"] > 0:
                    file_metrics["retry_fixed"] = True
                file_metrics["duration_seconds"] = time.perf_counter() - t0
                return cleaned_name, category, file_metrics

            if not raw_new_name or not isinstance(raw_new_name, str) or not raw_new_name.strip():
                file_metrics["invalid_json_attempts"] += 1
                continue

            cleaned_name = clean_filename(raw_new_name, original_extension, original_stem)
            if attempt == 1 and file_metrics["invalid_json_attempts"] > 0:
                file_metrics["retry_fixed"] = True
            file_metrics["duration_seconds"] = time.perf_counter() - t0
            return cleaned_name, category, file_metrics

        except (json.JSONDecodeError, ValueError):
            file_metrics["invalid_json_attempts"] += 1
            continue

    file_metrics["skipped"] = True
    file_metrics["duration_seconds"] = time.perf_counter() - t0
    return filename, fallback_category, file_metrics


def run_benchmark_for_model(
    model_name: str,
    endpoint: str = "http://127.0.0.1:11434",
) -> Dict[str, Any]:
    """Execute a complete plan benchmark run on the 40-file fixtures folder."""
    print(f"\n==================================================")
    print(f"BENCHMARKING MODEL: {model_name}")
    print(f"==================================================")

    # 1. Reset folder from backup
    if MESSY_DIR.exists():
        shutil.rmtree(MESSY_DIR)
    shutil.copytree(BACKUP_DIR, MESSY_DIR)

    # 2. Load ground truth
    with open(GROUND_TRUTH_PATH, "r", encoding="utf-8") as f:
        ground_truth: Dict[str, str] = json.load(f)

    # 3. Scan directory
    eligible, skipped = scan_directory(
        target_dir=MESSY_DIR,
        min_age_seconds=600,
        ignored_extensions=[".crdownload", ".part", ".tmp", ".download"],
    )

    safety_skipped_records = [
        {"name": s.path.name, "reason": s.reason} for s in skipped
    ]
    print(f"Files scanned: {len(eligible) + len(skipped)} total (Eligible: {len(eligible)}, Skipped by safety: {len(skipped)})")

    # 4. Plan generation with real timing
    reserved_destinations = set()
    results = []
    file_metrics_list = []
    total_start = time.perf_counter()

    for idx, scanned in enumerate(eligible, 1):
        print(f"[{idx:02d}/{len(eligible):02d}] {scanned.name[:35].ljust(35)} ...", end=" ", flush=True)
        chosen_name, category, metrics = benchmark_single_file(
            endpoint=endpoint,
            model_name=model_name,
            scanned_file=scanned,
            allowed_categories=ALLOWED_CATEGORIES,
        )

        category_folder = MESSY_DIR / category
        final_name, dest = resolve_collision(chosen_name, category_folder, reserved_destinations)

        expected = ground_truth.get(scanned.name, "Misc")
        is_correct = (category.lower() == expected.lower())
        status_str = f"-> {category} ({'CORRECT' if is_correct else 'WRONG: exp ' + expected})"
        print(f"{status_str} [{metrics['duration_seconds']:.2f}s]")

        results.append({
            "original_name": scanned.name,
            "proposed_name": final_name,
            "category": category,
            "expected_category": expected,
            "is_correct": is_correct,
            "is_text_readable": metrics["is_text_readable"],
            "duration_seconds": metrics["duration_seconds"],
        })
        file_metrics_list.append(metrics)

    total_duration = time.perf_counter() - total_start
    avg_seconds = total_duration / len(eligible) if eligible else 0.0

    # Accuracy calculations
    correct_count = sum(1 for r in results if r["is_correct"])
    accuracy_pct = (correct_count / len(results) * 100) if results else 0.0

    wrong_files = [
        {
            "filename": r["original_name"],
            "expected": r["expected_category"],
            "proposed": r["category"],
        }
        for r in results
        if not r["is_correct"]
    ]

    # JSON validation statistics
    invalid_json_count = sum(m["invalid_json_attempts"] for m in file_metrics_list)
    fixed_by_retry = sum(1 for m in file_metrics_list if m["retry_fixed"])
    skipped_by_model_error = sum(1 for m in file_metrics_list if m["skipped"])

    # Rename pairs for text files
    text_renames = [
        {"original": r["original_name"], "proposed": r["proposed_name"], "category": r["category"]}
        for r in results
        if r["is_text_readable"]
    ]

    report = {
        "model_name": model_name,
        "total_files": len(eligible) + len(skipped),
        "eligible_files": len(eligible),
        "safety_skipped_count": len(skipped),
        "safety_skipped_files": safety_skipped_records,
        "total_time_seconds": round(total_duration, 2),
        "avg_seconds_per_file": round(avg_seconds, 2),
        "correct_count": correct_count,
        "accuracy_percent": round(accuracy_pct, 1),
        "wrong_files": wrong_files,
        "invalid_json_count": invalid_json_count,
        "fixed_by_retry_count": fixed_by_retry,
        "skipped_by_model_error_count": skipped_by_model_error,
        "text_renames": text_renames,
    }

    print(f"\n--- Summary for {model_name} ---")
    print(f"Total Time: {total_duration:.2f}s (Average: {avg_seconds:.2f}s/file)")
    print(f"Category Accuracy: {correct_count}/{len(results)} ({accuracy_pct:.1f}%)")
    print(f"Wrong Classifications: {len(wrong_files)}")
    print(f"Invalid JSON Occurrences: {invalid_json_count} (Fixed by retry: {fixed_by_retry}, Skipped: {skipped_by_model_error})")
    print(f"Safety Skipped: {len(skipped)}")

    return report


def main():
    env = collect_environment_info()
    models = ["gemma3:1b", "gemma3:4b"]
    all_reports = {"environment": env, "models": {}}

    for model in models:
        report = run_benchmark_for_model(model)
        all_reports["models"][model] = report

    output_path = PROJECT_ROOT / "tests" / "benchmark_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_reports, f, indent=2)

    print(f"\nSaved benchmark results to {output_path}")


if __name__ == "__main__":
    main()

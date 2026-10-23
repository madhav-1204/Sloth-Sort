"""Local model interaction and JSON response validation."""

import json
from pathlib import Path
import re
import urllib.error
import urllib.request
from typing import Dict, List, Optional, Tuple

ILLEGAL_CHAR_PATTERN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def clean_filename(raw_name: str, original_extension: str, original_stem: str) -> str:
    """
    Sanitize the suggested filename for cross-platform safety.
    Always preserves the original file extension.
    """
    if not raw_name:
        return f"{original_stem}{original_extension}"

    # Remove any extension the model might have appended to prevent double extensions (e.g., name.pdf.pdf)
    candidate_stem = raw_name.strip()
    if original_extension and candidate_stem.lower().endswith(original_extension.lower()):
        candidate_stem = candidate_stem[: -len(original_extension)].strip()

    # Remove any other extension-like suffix if the model changed the extension
    if "." in candidate_stem:
        # Check if last token is an extension-like word (3-4 chars alphanumeric)
        parts = candidate_stem.rsplit(".", 1)
        if len(parts) == 2 and 1 <= len(parts[1]) <= 5 and parts[1].isalnum():
            candidate_stem = parts[0].strip()

    # Replace characters illegal on Windows/Unix with a space so words don't collide
    cleaned = ILLEGAL_CHAR_PATTERN.sub(" ", candidate_stem)

    # Replace multiple consecutive spaces or underscores with single ones
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned)

    # Windows prohibits names ending with dots or spaces
    cleaned = cleaned.strip(". -_")

    # If stripped completely down to nothing, revert to original stem
    if not cleaned:
        cleaned = original_stem

    # Truncate overly long file stems to 120 characters for filesystem sanity
    if len(cleaned) > 120:
        cleaned = cleaned[:120].rstrip(". -_")

    return f"{cleaned}{original_extension}"


def match_category(suggested_folder: str, allowed_categories: List[str], fallback: str = "Misc") -> str:
    """Match the suggested category against the allowed whitelist case-insensitively."""
    if not suggested_folder:
        return fallback

    cleaned_suggestion = suggested_folder.strip().lower()
    for cat in allowed_categories:
        if cat.lower() == cleaned_suggestion:
            return cat

    # Partial substring check if model said e.g. "Documents folder" or "Photos / Images"
    for cat in allowed_categories:
        if cat.lower() in cleaned_suggestion:
            return cat

    return fallback


def _send_ollama_request(endpoint: str, model_name: str, prompt: str, timeout: int = 60) -> str:
    """Send a single generation request to Ollama with JSON formatting enabled."""
    url = f"{endpoint.rstrip('/')}/api/generate"
    payload = {
        "model": model_name,
        "prompt": prompt,
        "format": "json",
        "stream": False,
        "options": {
            "temperature": 0.1,  # Low temperature for stable and deterministic extraction
        },
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result.get("response", "")
    except urllib.error.URLError as e:
        raise ConnectionError(
            f"Could not connect to Ollama at {endpoint}. Ensure Ollama is running (`ollama serve`). Details: {e}"
        ) from e


TEXT_READABLE_EXTENSIONS = {".txt", ".md", ".pdf", ".docx", ".csv"}


def generate_file_plan(
    endpoint: str,
    model_name: str,
    filename: str,
    snippet: str,
    allowed_categories: List[str],
    fallback_category: str = "Misc",
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Query the local model for a descriptive file name and category folder.
    Retries once on invalid JSON. Returns (clean_new_name, target_folder, error_reason).
    Only text-readable files (.txt, .md, .pdf, .docx, .csv) are renamed.
    Binary and image files are never renamed and keep their original filename.
    """
    original_path = Path(filename)
    original_extension = original_path.suffix
    original_stem = original_path.stem
    is_text_readable = original_extension.lower() in TEXT_READABLE_EXTENSIONS

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

    for attempt in range(2):
        prompt = base_prompt if attempt == 0 else f"{base_prompt}\nReminder: output only valid JSON with 'new_name' and 'folder'."
        try:
            raw_response = _send_ollama_request(endpoint, model_name, prompt)
        except Exception as e:
            return None, None, str(e)

        if not raw_response:
            continue

        try:
            parsed = json.loads(raw_response)
            if not isinstance(parsed, dict):
                continue

            raw_new_name = parsed.get("new_name")
            raw_folder = parsed.get("folder")

            # Validate folder
            if not raw_folder or not isinstance(raw_folder, str) or not raw_folder.strip():
                if attempt == 0:
                    continue
                raw_folder = fallback_category

            category = match_category(str(raw_folder).strip(), allowed_categories, fallback_category)

            if not is_text_readable:
                # For binary files and images, never rename. Always keep original filename.
                cleaned_name = filename
                return cleaned_name, category, None

            if not raw_new_name or not isinstance(raw_new_name, str) or not raw_new_name.strip():
                continue

            cleaned_name = clean_filename(raw_new_name, original_extension, original_stem)
            return cleaned_name, category, None
        except (json.JSONDecodeError, ValueError):
            continue

    return None, None, "Model returned invalid JSON or missing fields after retry"

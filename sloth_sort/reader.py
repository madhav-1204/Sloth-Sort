"""Extracts snippet text from readable file formats."""

from pathlib import Path
import csv
import io


def read_file_snippet(file_path: Path, max_chars: int = 1000) -> str:
    """Read up to max_chars of text from a file if readable, else return empty string."""
    suffix = file_path.suffix.lower()

    if suffix in {".txt", ".md", ".csv", ".json", ".xml", ".html", ".htm", ".log", ".py", ".sh", ".yaml", ".yml"}:
        return _read_plain_text(file_path, max_chars)

    if suffix == ".pdf":
        return _read_pdf(file_path, max_chars)

    if suffix == ".docx":
        return _read_docx(file_path, max_chars)

    # Binary files, images, archives, installers, etc.
    return ""


def _read_plain_text(file_path: Path, max_chars: int) -> str:
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(max_chars)
            return content.strip()
    except Exception:
        # If text reading fails for any reason, fall back gracefully
        return ""


def _read_pdf(file_path: Path, max_chars: int) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(file_path))
        extracted = []
        chars_collected = 0
        for page in reader.pages:
            text = page.extract_text() or ""
            extracted.append(text)
            chars_collected += len(text)
            if chars_collected >= max_chars:
                break
        return " ".join("".join(extracted).split())[:max_chars].strip()
    except Exception:
        return ""


def _read_docx(file_path: Path, max_chars: int) -> str:
    try:
        import docx
        doc = docx.Document(str(file_path))
        extracted = []
        chars_collected = 0
        for para in doc.paragraphs:
            text = para.text
            if text:
                extracted.append(text)
                chars_collected += len(text)
                if chars_collected >= max_chars:
                    break
        return " ".join(" ".join(extracted).split())[:max_chars].strip()
    except Exception:
        return ""

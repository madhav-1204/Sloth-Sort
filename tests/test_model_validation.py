"""Unit tests for model output validation, retry fallback, and binary non-renaming."""

import json
from unittest.mock import patch
import pytest

from sloth_sort.model import generate_file_plan

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


class TestModelValidation:
    @patch("sloth_sort.model._send_ollama_request")
    def test_valid_json_text_file_renamed_and_categorized(self, mock_request):
        mock_request.return_value = json.dumps({
            "new_name": "Quarterly_Tax_Invoice_2026.pdf",
            "folder": "Invoices",
        })

        new_name, folder, error = generate_file_plan(
            endpoint="http://127.0.0.1:11434",
            model_name="gemma3:1b",
            filename="scan_001.pdf",
            snippet="Tax invoice details for Q3 2026",
            allowed_categories=ALLOWED_CATEGORIES,
        )

        assert error is None
        assert folder == "Invoices"
        assert new_name == "Quarterly_Tax_Invoice_2026.pdf"
        assert mock_request.call_count == 1

    @patch("sloth_sort.model._send_ollama_request")
    def test_binary_and_image_files_never_renamed(self, mock_request):
        # Even if the model proposes a new name for an installer or image, keep original filename
        mock_request.return_value = json.dumps({
            "new_name": "clean_installer.exe",
            "folder": "Installers",
        })

        new_name, folder, error = generate_file_plan(
            endpoint="http://127.0.0.1:11434",
            model_name="gemma3:1b",
            filename="setup_app_installer (1).exe",
            snippet="",
            allowed_categories=ALLOWED_CATEGORIES,
        )

        assert error is None
        assert folder == "Installers"
        assert new_name == "setup_app_installer (1).exe"

        # Test image file (.png)
        mock_request.return_value = json.dumps({
            "new_name": "family_photo.png",
            "folder": "Photos",
        })

        new_name, folder, error = generate_file_plan(
            endpoint="http://127.0.0.1:11434",
            model_name="gemma3:1b",
            filename="IMG_20261019_182045.jpg",
            snippet="",
            allowed_categories=ALLOWED_CATEGORIES,
        )

        assert error is None
        assert folder == "Photos"
        assert new_name == "IMG_20261019_182045.jpg"

    @patch("sloth_sort.model._send_ollama_request")
    def test_invalid_json_retries_once_and_recovers(self, mock_request):
        mock_request.side_effect = [
            "This is not valid json at all",
            json.dumps({"new_name": "recovered_notes.txt", "folder": "Study"}),
        ]

        new_name, folder, error = generate_file_plan(
            endpoint="http://127.0.0.1:11434",
            model_name="gemma3:1b",
            filename="raw_notes.txt",
            snippet="Lecture 1 notes",
            allowed_categories=ALLOWED_CATEGORIES,
        )

        assert error is None
        assert folder == "Study"
        assert new_name == "recovered_notes.txt"
        assert mock_request.call_count == 2

    @patch("sloth_sort.model._send_ollama_request")
    def test_invalid_json_fails_safely_after_retry(self, mock_request):
        mock_request.side_effect = [
            "Malformed JSON {",
            "Still broken JSON {{{",
        ]

        new_name, folder, error = generate_file_plan(
            endpoint="http://127.0.0.1:11434",
            model_name="gemma3:1b",
            filename="broken.txt",
            snippet="Sample text",
            allowed_categories=ALLOWED_CATEGORIES,
        )

        assert new_name is None
        assert folder is None
        assert "invalid JSON" in error
        assert mock_request.call_count == 2

    @patch("sloth_sort.model._send_ollama_request")
    def test_missing_keys_or_empty_strings_handled_safely(self, mock_request):
        # Empty string for new_name on text file retries once, then skips
        mock_request.side_effect = [
            json.dumps({"new_name": "", "folder": "Study"}),
            json.dumps({"new_name": "   ", "folder": "Study"}),
        ]

        new_name, folder, error = generate_file_plan(
            endpoint="http://127.0.0.1:11434",
            model_name="gemma3:1b",
            filename="test.txt",
            snippet="Study notes",
            allowed_categories=ALLOWED_CATEGORIES,
        )

        assert new_name is None
        assert folder is None
        assert "invalid JSON or missing fields" in error

    @patch("sloth_sort.model._send_ollama_request")
    def test_missing_folder_falls_back_to_misc(self, mock_request):
        # Missing folder retries once, then falls back to fallback_category (Misc)
        mock_request.side_effect = [
            json.dumps({"new_name": "valid_name.txt"}),
            json.dumps({"new_name": "valid_name.txt"}),
        ]

        new_name, folder, error = generate_file_plan(
            endpoint="http://127.0.0.1:11434",
            model_name="gemma3:1b",
            filename="test.txt",
            snippet="General text",
            allowed_categories=ALLOWED_CATEGORIES,
            fallback_category="Misc",
        )

        assert error is None
        assert folder == "Misc"
        assert new_name == "valid_name.txt"

    @patch("sloth_sort.model._send_ollama_request")
    def test_category_not_in_allowed_list_falls_back_to_misc(self, mock_request):
        mock_request.return_value = json.dumps({
            "new_name": "clean_crypto.txt",
            "folder": "CryptocurrencyAndBlockchain",
        })

        new_name, folder, error = generate_file_plan(
            endpoint="http://127.0.0.1:11434",
            model_name="gemma3:1b",
            filename="crypto.txt",
            snippet="Bitcoin whitepaper",
            allowed_categories=ALLOWED_CATEGORIES,
            fallback_category="Misc",
        )

        assert error is None
        assert folder == "Misc"
        assert new_name == "clean_crypto.txt"

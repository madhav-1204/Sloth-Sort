# Project Notes: sloth-sort

Development notes, experiment metrics, and observations for the DEV Hacktoberfest Open-Source AI Challenge (Week 3: Slow and Steady).

## Environment and Hardware Specs

- Operating System: Windows 11
- Python Version: 3.14.3
- Local Model Runtime: Ollama 0.35.1
- Primary Local Model: gemma3:1b (quantized Q4_K_M, size ~806 MB)
- CPU / Memory: Recorded during local test runs

## Implementation Log & Bug Fixes

- Initial repository structure set up inside challenge window.
- Minimal dependencies selected: standard library (`argparse`, `tomllib`, `urllib.request`, `pathlib`), plus `pypdf` and `python-docx` for document text extraction. No heavy web frameworks, no external cloud dependencies.

## Test Run Metrics

(To be populated with real measurement data upon running on test sets)

- Files processed:
- Files renamed & categorized accurately:
- Files skipped (recent modification, bad output, unsupported):
- Average time per file:
- Model output quality and edge cases:

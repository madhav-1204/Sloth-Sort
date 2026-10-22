# Project Notes: sloth-sort

Development notes, experiment metrics, and observations for the DEV Hacktoberfest Open-Source AI Challenge (Week 3: Slow and Steady).

---

## Machine and Environment Specs

- Operating System: Windows 11 Pro (Build 10.0.26200)
- Processor: AMD Ryzen 5000 Series (AMD64 Family 25 Model 80 Stepping 0, AuthenticAMD)
- Python Version: 3.14.3
- Model Runtime: Ollama 0.35.1 running locally (`http://127.0.0.1:11434`)
- Primary Model Tested: `gemma3:1b` (quantized Q4_K_M, size 806 MB, context length 32k)

---

## Real Test Run Metrics

### Test Run: 10 Realistic Synthetic Files

We tested `sloth-sort` on a batch of 10 real files covering documents, code, images, installers, receipts, audio, and plain notes.

- Total files scanned in test folder: 13
- Skipped automatically: 3 files
  - `.gitkeep`: Skipped (hidden file rule)
  - `ubuntu-26.04-desktop-amd64.iso.crdownload`: Skipped (incomplete download extension rule)
  - `file_downloading_right_now.pdf`: Skipped (modified 30 seconds ago, under the 10-minute cooldown rule)
- Files analyzed by local model: 10
- Successful JSON generations: 10 / 10 (100% valid JSON on first attempt using Ollama `format: "json"`)
- Average time per file: 4.8 to 5.3 seconds
- Fast execution: ~3.2 seconds (for short binary filename judgments without snippet reading)
- Slower execution: ~5.9 to 6.1 seconds (for files with extracted text snippets)

### Categorization Accuracy Breakdown

Using `gemma3:1b` with explicit category guidelines:
- `INV-2026-9812.pdf` -> `Invoices/INV-2026-9812_invoice.pdf` (Correct)
- `IMG_20261015_142301.png` -> `Photos/IMG_20261015_142301_v2.png` (Correct)
- `tech_talk_episode_42_local_models.mp3` -> `Media/tech_talk_episode_42_local_models.mp3` (Correct)
- `weekend_grocery_errands.txt` -> `Misc/Grocery Errands.txt` (Correct fallback)
- `notes_oct22_rough.docx` -> `Code/Backend Architecture Discussion.docx` (Partially accurate: the meeting notes were discussing backend architecture, so the 1B model placed it in `Code` rather than `Documents`)
- `cs350_operating_systems_lab2.md` -> `Code/Operating Systems Lab 2.md` (Acceptable: lab assignment containing virtual memory code instructions)
- `VSCodeUserSetup-x64-1.95.0.exe` -> `Code/VSCodeUserSetup.exe` (Interesting mistake: it recognized VS Code as a coding tool and assigned it to `Code` instead of `Installers` because binary judgment relies solely on filename)
- `receipt_homedepot_hardware_repair.txt` -> `Misc/Receipt_HomeDepot_Hardware_Repair.txt` (Categorized as `Misc` instead of `Invoices`)
- `q3_operating_expenses_2026.csv` -> `Misc/Servers_Salaries_2026.csv` (Renamed cleanly based on table columns, placed in `Misc`)
- `sync_s3_buckets_cron.py` -> `Misc/sync_s3_buckets_cron.py` (Retained filename, placed in `Misc`)

---

## Surprising Model Mistakes and Behaviors

1. **Association Overriding Extension**:
   `VSCodeUserSetup-x64-1.95.0.exe` was sorted into `Code` instead of `Installers`. The model saw "VSCode" and strongly associated it with programming, completely bypassing the `.exe` extension rule.
2. **Conservative Fallback**:
   When the prompt only listed category names without short descriptions, `gemma3:1b` defaulted to `Misc` for over 60% of files. Adding a brief one-line bullet per category in the system prompt immediately lifted categorization into specific folders.
3. **Double Extensions Tendency**:
   Small models frequently produce output like `report.pdf.pdf` or attempt to change `.txt` to `.md` because the content looks like markdown. Enforcing `clean_filename()` in code to strip duplicate extensions and guarantee the original extension was critical.

---

## Bugs Hit During Build and How They Were Fixed

1. **Character Stripping Colliding Words**:
   - *Bug*: In `clean_filename`, stripping illegal characters with empty string `""` on dirty inputs like `'*draft*|"approved"'` merged words into `'draftapproved'`.
   - *Fix*: Replaced illegal characters with a single space `ILLEGAL_CHAR_PATTERN.sub(" ", text)`, then collapsed multiple whitespace characters with regex before trimming.
2. **PowerShell Multi-line Command Quoting**:
   - *Bug*: Multi-line inline python scripts failed under PowerShell when using standard bash `&&` separators or double-quote escapes.
   - *Fix*: Standardized test runs into Python scripts (`python -m unittest discover tests`) and used semicolon command separators.
3. **Directory Cleanup Safety**:
   - *Bug*: During `undo`, if category directories were left empty, the user's folder would end up with abandoned empty directories.
   - *Fix*: Added safe cleanup in `mover.revert_undo_log()` that checks if newly emptied category directories inside `target_dir` contain any remaining files, removing only empty folders and never touching the root directory.

---

## Honest Comparison: Local Open Model vs. Closed Cloud API

### Where Local Won:
1. **Zero Privacy Leak**:
   Personal receipts, NDAs, and private meeting notes were parsed and organized without a single byte leaving localhost.
2. **No Cost & Offline**:
   Running 20 or 2,000 files costs $0.00 and works on an airplane or without Wi-Fi.
3. **Predictable Latency**:
   Ollama with `gemma3:1b` maintained a stable ~3.5 to 5.0 seconds per file without rate limits or API key throttling.

### Where Cloud Models Are Still Better:
1. **Nuanced Classification**:
   A 70B or cloud frontier model reliably distinguishes an installer (`.exe`) for a coding tool from actual source code files, and recognizes that a hardware store receipt is an invoice.
2. **Batch Context**:
   Cloud models can take larger batches in one go with higher confidence, whereas small local models perform best when constrained to one file at a time with strict JSON mode.

---

## What I Would Do Differently Next Time

1. **Hybrid Heuristic Pre-Filter**:
   For obvious extensions (`.exe`, `.dmg`, `.msi` for Installers, `.jpg`, `.png` for Photos), passing extension-based prior hints to the prompt would eliminate silly misclassifications like putting setup executables into `Code`.
2. **Model Swapping Benchmark**:
   Compare `gemma3:1b` directly against `gemma3:4b` across 50 real Downloads files to measure accuracy gains versus latency trade-offs.

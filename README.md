# sloth-sort

A small command-line tool that tidies a messy folder (like your Downloads directory) using a local open-weight model, so you never have to sort files by hand.

It reads the first few paragraphs of readable files (or just the file name and extension for binaries and images), asks a local model running on your machine to suggest a clean filename and a folder category, shows you a dry-run plan, and moves the files only when you tell it to.

Every operation is logged and can be completely reverted with one command.

Built for the DEV Hacktoberfest Open-Source AI Challenge (Week 3: Slow and Steady).

---

## Why a local model?

Most file organizers either rely on hardcoded extension rules (dumping all PDFs into one folder regardless of whether they are tax returns, research papers, or appliance manuals) or send file names and contents to third-party cloud APIs.

sloth-sort runs entirely on your computer using Ollama:
- Your files and file names never leave your machine.
- It works without an internet connection once the model is downloaded.
- It costs nothing per run.
- You can swap the model for any other open-weight model supported by Ollama.

---

## Requirements

1. Python 3.11 or newer
2. [Ollama](https://ollama.com/) installed and running locally
3. A local model pulled in Ollama (default is `gemma3:1b`, but you can use `gemma3:4b`, `llama3.2`, or any other model):

```bash
ollama pull gemma3:1b
```

---

## Installation

Clone the repository and install it in editable mode:

```bash
git clone https://github.com/madhav-1204/Sloh-Sort.git
cd Sloh-Sort
pip install -e .
```

The tool depends only on `pypdf`, `python-docx`, and standard library modules (`argparse`, `tomllib`, `urllib`, `pathlib`).

---

## How to use it

### 1. Dry run (default)

Point sloth-sort at a folder to see what it wants to do:

```bash
sloth-sort plan ~/Downloads
```

If you do not pass a folder, it defaults to `~/Downloads`.

You can also specify a different model directly from the command line:

```bash
sloth-sort plan ~/Downloads --model gemma3:4b
```

The tool inspects each eligible file, asks the model for a clean name and category, prints a comparison table, and writes the proposal to `plan.json`. It does not touch or move any file during this step.

### 2. Apply the plan

When you are satisfied with the dry run:

```bash
sloth-sort apply
```

The tool asks for a simple confirmation (`[y/N]`), creates the category directories inside your target folder, moves and renames the files, and writes an `undo_log.json` file.

### 3. Undo

If you change your mind or want to put everything back exactly where it came from:

```bash
sloth-sort undo
```

This reads `undo_log.json`, moves all files back to their original paths and names, and cleans up empty category folders that it created.

---

## Configuration

Settings can be customized in `config.toml` in your working directory or in `~/.config/sloth-sort/config.toml`:

```toml
[model]
name = "gemma3:1b"
endpoint = "http://127.0.0.1:11434"

[categories]
# Fixed list of target folders so the model does not invent arbitrary names
allowed = [
    "Invoices",
    "Study",
    "Photos",
    "Installers",
    "Code",
    "Documents",
    "Media",
    "Misc"
]
fallback = "Misc"

[scanner]
# Minimum file age in seconds before it is touched (default 600 = 10 minutes)
min_age_seconds = 600
ignored_extensions = [".crdownload", ".part", ".tmp", ".download"]
max_text_chars = 1000
```

---

## Safety rules: what this tool will never do

- It will never delete anything.
- It will never overwrite an existing file. If a file with the target name already exists, it appends a number (e.g. `document_1.pdf`).
- It will never touch files outside the target directory you pointed it at.
- It will skip hidden files (files starting with `.`).
- It will skip active downloads (`.crdownload`, `.part`, `.tmp`).
- It will skip files modified in the last 10 minutes, avoiding files that are still being written.
- If the model returns invalid output or fails to respond, the file is left alone.

---

## Known limits

- Binary formats without plain text (such as compiled executables or images) are categorized based on their file names and extensions alone.
- Smaller models (like 1B parameters) can occasionally misclassify nuanced documents (for example, putting a consulting contract into "Study" instead of "Documents"). Using a 4B or 7B model improves categorization accuracy.
- Scanning is sequential (one file at a time) to keep terminal output readable and avoid overwhelming local GPU/CPU memory.

---

## Running the tests

The project includes unit tests for filename sanitization, collision handling, scanner filters, and undo reversibility:

```bash
python -m unittest discover tests
```

---

## License

MIT

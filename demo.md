# sloth-sort 60-90 Second Terminal Demo

Follow these exact commands in order for a clean terminal recording:

### 1. Regenerate the messy test folder
```bash
python tests/make_fixtures.py
```

### 2. Inspect the messy folder before sorting
```bash
ls tests/fixtures/messy_folder
```
*(On Windows Command Prompt, use `dir /b tests\fixtures\messy_folder`)*

### 3. Generate a plan (dry run)
```bash
sloth-sort plan tests/fixtures/messy_folder
```

### 4. Apply the organization plan
```bash
sloth-sort apply
```
*(Type `y` when prompted to confirm)*

### 5. Inspect the sorted folder structure
```bash
tree /f tests/fixtures/messy_folder
```
*(On Linux/macOS, use `tree tests/fixtures/messy_folder`)*

### 6. Undo the changes
```bash
sloth-sort undo
```

### 7. Confirm the folder is restored to its exact original state
```bash
ls tests/fixtures/messy_folder
```
*(On Windows Command Prompt, use `dir /b tests\fixtures\messy_folder`)*

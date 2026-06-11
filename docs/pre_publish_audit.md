# Pre-Publish Audit

Date: 2026-06-11

## Result

The repository is ready to be initialized for GitHub after repairing or recreating `.git`.

PDF files and generated OCR artifacts are protected by `.gitignore`.

## Git State

Current project `.git` is not a valid Git repository:

```text
git rev-parse --show-toplevel
fatal: not a git repository
```

The visible `.git/` directory is effectively empty/read-only in this workspace. Before the first commit, run:

```bash
git init
git status --ignored
```

## Ignore Check

The `.gitignore` was tested in a temporary Git repository.

Expected Git-visible paths:

```text
README.md
.gitignore
docs/
scripts/
data/public/
manifests/
```

Expected ignored paths:

```text
downloads/
approved_pdfs/
prepared_pdfs/
generated_pdfs/
duplicates_removed/
duplicates_removed_visual/
selected_one_page_handfill_candidates/
selected_pradeep_single_pages/
user_provided_documents/
output/
venv/
scripts/__pycache__/
data/*.csv
*.pdf
```

## PII Scan

Scanned intended GitHub paths:

```text
README.md
.gitignore
docs/
scripts/
data/public/
manifests/
```

Patterns checked:

```text
email
Ukrainian phone-like numbers
UA IBAN
passport-like IDs
```

Result:

```text
PII-like hits: 0
```

Raw `data/*.csv` files are intentionally ignored because search snippets contained public email/phone/IBAN/sample-person data. Public metadata is regenerated with:

```bash
python3 scripts/sanitize_metadata.py
```

## Manifest

Generated:

```text
manifests/pdf_inventory.csv
```

Current manifest summary:

```text
PDF rows: 1054
Total size: 984.31 MB
Manifest size: about 0.24 MB
```

The manifest contains filenames, relative paths, statuses, categories, sizes, and SHA256 hashes. PDF files themselves remain outside Git.

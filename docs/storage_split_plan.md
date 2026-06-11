# Ukrainian Document Sourcing: GitHub vs Google Drive Split

## Current State

The workspace mixes code, metadata, downloaded PDFs, OCR outputs, and manual selections in one project tree.

Approximate current sizes:

| Path | Purpose | Size |
| --- | --- | ---: |
| `downloads/` | Raw downloaded PDF corpus | 877 MB |
| `output/` | OCR PDFs, extracted text, CSV reports | 85 MB |
| `approved_pdfs/` | Previously approved PDF set | 17 MB |
| `prepared_pdfs/` | Prepared/manual PDF subsets | 13 MB |
| `user_provided_documents/` | PDFs manually provided by URL | 9 MB |
| `scripts/` | Python pipeline code | 188 KB |
| `data/` | Link/source CSV metadata | 360 KB |

The GitHub repository should not store the PDF archive or generated OCR artifacts. GitHub should store only reproducible code, lightweight metadata, validation reports that are useful as text/CSV, and documentation.

## GitHub Scope

Keep in GitHub:

```text
ukrainian-doc-sourcing/
├── README.md
├── .gitignore
├── docs/
│   └── storage_split_plan.md
├── scripts/
│   ├── download_pdfs.py
│   ├── qa_check.py
│   ├── final_validate_documents.py
│   ├── find_ocr_gain_candidates.py
│   ├── targeted_pradeep_run.py
│   └── ...
├── data/
│   └── public/
│       ├── candidate_links.csv
│       ├── manual_links.csv
│       └── pradeep_targeted_candidate_links.csv
└── manifests/
    ├── drive_inventory.csv
    ├── approved_manifest.csv
    ├── ocr_gain_manifest.csv
    └── user_provided_manifest.csv
```

Recommended GitHub files:

- Pipeline scripts.
- Sanitized search query and link CSVs from `data/public/`.
- CSV manifests with `drive_path`, `source_url`, `category`, `format`, `extracted_word_count`, `ocr_word_count`, `ocr_quality`, `accepted`, and `rejection_reason`.
- Small text reports such as final validation summaries.
- Documentation explaining how to restore files from Drive.

Do not keep in GitHub:

- Raw PDFs.
- OCR-generated PDFs.
- Extracted text dumps if they are large or generated.
- Duplicate-removal working folders.
- Virtual environments and caches.

## Google Drive Scope

Move the PDF archive and generated heavy artifacts to Google Drive.

Proposed Drive structure:

```text
Google Drive/
└── ukrainian-doc-sourcing-archive/
    ├── 00_manifests/
    │   ├── drive_inventory.csv
    │   ├── approved_manifest.csv
    │   ├── ocr_gain_manifest.csv
    │   └── user_provided_manifest.csv
    │
    ├── 01_raw_downloads/
    │   ├── downloads/
    │   ├── pradeep_targeted/
    │   └── pradeep_targeted_single_pages/
    │
    ├── 02_manual_user_links/
    │   ├── zvil_polon_mobilizovani.pdf
    │   ├── zbirka-raportiv-dlya-vijskovosluzhbovcziv-2024.pdf
    │   └── source_links.txt
    │
    ├── 03_approved_sets/
    │   ├── approved_pdfs/
    │   ├── selected_pradeep_single_pages/
    │   └── ocr_gain_selected_pdfs/
    │
    ├── 04_prepared_sets/
    │   ├── prepared_pdfs/
    │   ├── selected_one_page_handfill_candidates/
    │   └── generated_pdfs/
    │
    ├── 05_ocr_outputs/
    │   ├── pradeep_targeted_ocr/
    │   ├── ocr_gain_ocr/
    │   └── extracted_text/
    │
    └── 90_duplicates_and_working/
        ├── duplicates_removed/
        └── duplicates_removed_visual/
```

## Local Working Tree After Split

Recommended local project structure after moving heavy files:

```text
ukrainian-doc-sourcing/
├── README.md
├── .gitignore
├── docs/
├── scripts/
├── data/
├── manifests/
├── local_data/                  # ignored; optional local restore point from Drive
│   ├── downloads/
│   ├── approved_pdfs/
│   ├── output/
│   └── user_provided_documents/
└── tmp/                         # ignored scratch space
```

If you want scripts to keep their current relative paths, restore Drive folders back to the current names locally:

```text
downloads/
approved_pdfs/
prepared_pdfs/
output/
user_provided_documents/
```

These paths are ignored by `.gitignore`, so they can exist locally without being committed.

## Manifest Columns

Every PDF stored in Drive should have a row in a manifest CSV:

```text
document_id
filename
drive_path
local_restore_path
source_url
category
format
pages
extracted_word_count
ocr_word_count
ocr_character_count
ocr_quality
accepted
rejection_reason
sha256
file_size_bytes
created_at
notes
```

Use `sha256` to detect duplicate files even if filenames change.

## Migration Plan

1. Create the Drive root folder:

   ```text
   ukrainian-doc-sourcing-archive/
   ```

2. Upload heavy folders to Drive:

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
   ```

3. Keep lightweight sanitized CSVs and docs in GitHub:

   ```text
   data/public/*.csv
   docs/*.md
   scripts/*.py
   README.md
   .gitignore
   ```

4. Generate or update Drive manifests with file size, SHA256, Drive path, source URL, and validation metrics.

5. After verifying Drive upload, remove heavy local folders from Git tracking if they were ever tracked:

   ```bash
   git rm -r --cached downloads approved_pdfs prepared_pdfs output user_provided_documents
   ```

6. Commit only code, docs, `.gitignore`, and metadata manifests.

7. For future work, restore PDFs from Drive locally only when needed. Do not commit restored PDFs.

## Pre-GitHub Checks

Before the first GitHub push, run:

```bash
du -sh .
git rev-parse --show-toplevel
git status --ignored
```

If `git rev-parse --show-toplevel` fails, initialize or repair Git before committing:

```bash
git init
git status --ignored
```

The ignored list should include heavy local folders such as:

```text
downloads/
approved_pdfs/
prepared_pdfs/
output/
user_provided_documents/
venv/
```

## Privacy and PII Review

Before publishing, even to a private repository, manually review PDF collections for:

- Real medical records or patient data.
- Passport, tax ID, bank, address, phone, or email data.
- Third-party signatures or identifiable handwritten forms.
- Accidentally OCR-extracted text containing personal information.

High-risk local paths:

```text
user_provided_documents/
approved_pdfs/
output/
downloads/
```

Do not publish raw PDFs publicly unless licensing, privacy, and source permissions are clear.

## Building the PDF Inventory

Generate a lightweight manifest for GitHub:

```bash
python3 scripts/build_manifest.py
```

Default output:

```text
manifests/pdf_inventory.csv
```

The manifest stores file name, relative path, source folder, status, inferred category, size, and SHA256. Fill `drive_path` after uploading files to Google Drive.

Generate sanitized public link metadata:

```bash
python3 scripts/sanitize_metadata.py
```

Default output:

```text
data/public/*.csv
```

Raw `data/*.csv` files are ignored by Git because search snippets may contain email addresses, phone numbers, IBANs, sample names, or other personal-data-like text.

## Final Selection Locations

Important current selections to mirror in Drive:

| Local path | Drive target |
| --- | --- |
| `output/ocr_gain/selected_pdfs/` | `03_approved_sets/ocr_gain_selected_pdfs/` |
| `selected_pradeep_single_pages/` | `03_approved_sets/selected_pradeep_single_pages/` |
| `approved_pdfs/` | `03_approved_sets/approved_pdfs/` |
| `user_provided_documents/` | `02_manual_user_links/` |

## Notes

- Keep raw corpus and generated OCR output in Drive, not GitHub.
- Keep source URLs and validation metrics in GitHub, so the dataset is auditable without downloading every PDF.
- Treat `output/` as generated unless a specific CSV report is intentionally promoted into `manifests/`.

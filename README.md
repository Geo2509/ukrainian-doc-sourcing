# Ukrainian Document Sourcing

Python pipeline for sourcing and quality-checking Ukrainian PDF documents for document-data and OCR workflows.

## What it does

- discovers candidate documents from public web sources;
- downloads and organizes PDF files;
- extracts text with `pdftotext` and uses OCR when required;
- validates document quality using rule-based checks;
- records QA results and rejection reasons;
- detects exact and visual duplicate documents;
- exports approved candidates for manual review.

## Data quality workflow

```
Search -> Download -> Text extraction / OCR -> QA validation
       -> Duplicate checks -> Approved candidates -> Manual review
```

The QA layer records fields such as document category, extracted word count, OCR word count, OCR quality, acceptance status and rejection reason. Documents with insufficient text can be reprocessed with OCR before the final validation step.

## Main tools

Python, Pandas, Requests, DDGS, Poppler (`pdftotext` / `pdfinfo`), OCRmyPDF, Tesseract and PyMuPDF.

## Repository structure

- `scripts/search_ddg.py` - document discovery
- `scripts/download_pdfs.py` - PDF download
- `scripts/qa_check.py` - text/OCR quality validation
- `scripts/export_approved.py` - approved-candidate export
- `scripts/final_validate_documents.py` - final machine validation
- `scripts/cleanup_duplicate_pdfs.py` - exact duplicate detection
- `scripts/cleanup_visual_duplicate_pdfs.py` - visual duplicate detection

Large PDF corpora, generated documents, OCR outputs and local environments are excluded from Git. The repository contains the code and lightweight metadata needed to demonstrate the workflow.

## Notes

Automated QA does not replace manual review. Source quality, readability and possible personal data should be checked before documents are used in a production dataset.

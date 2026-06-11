import re
from pathlib import Path

import pandas as pd

from targeted_pradeep_run import (
    APPROVED_FILE,
    MIN_WORDS,
    OCR_TRIGGER_WORDS,
    OCR_DIR,
    TEXT_DIR,
    get_page_count,
    ocr_quality_label,
    read_text_file,
    run_ocr,
    text_preview,
    write_extracted_text,
)


LINKS_FILE = Path("data/candidate_links.csv")
PDF_DIRS = [Path("downloads"), Path("approved_pdfs"), Path("prepared_pdfs/handfill_ready")]
OUTPUT_FILE = Path("output/existing_inventory_validated.csv")


FORMAT_BY_CATEGORY = {
    "handwritten": "handwritten",
    "contract": "printed",
    "receipt": "printed",
    "certificate_of_analysis": "printed",
    "logistics_financial": "printed",
    "financial_environmental_report": "digital",
    "editable_docs": "digital",
    "patient_form": "printed",
    "medical_doctor_note": "printed",
    "hospital_claim": "printed",
}


def filename_index(path: Path) -> int | None:
    match = re.match(r"!*(\d{3})_", path.name)
    if not match:
        return None
    return int(match.group(1)) - 1


def read_link_map() -> dict[int, dict]:
    if not LINKS_FILE.exists():
        return {}
    df = pd.read_csv(LINKS_FILE).fillna("")
    return {index: row.to_dict() for index, row in df.iterrows()}


def validate_pdf(path: Path, link_row: dict | None) -> dict:
    category = link_row.get("category", path.stem.split("_", 1)[-1]) if link_row else path.stem
    format_guess = FORMAT_BY_CATEGORY.get(category, "printed")
    source_url = link_row.get("link", "") if link_row else ""
    query = link_row.get("query", "") if link_row else ""
    title = link_row.get("title", "") if link_row else ""

    page_count = get_page_count(path)
    if page_count != 1:
        rejection_reason = "not single-page"
        return {
            "accepted": False,
            "local_path": str(path),
            "local_pdf_path": str(path),
            "source_url": source_url,
            "category": category,
            "category_guess": category,
            "format": format_guess,
            "format_guess": format_guess,
            "query": query,
            "title": title,
            "pages": page_count,
            "extracted_word_count": "",
            "pdftotext_word_count": "",
            "ocr_word_count": "",
            "ocr_character_count": "",
            "final_word_count": "",
            "ocr_used": False,
            "ocr_required": False,
            "ocr_quality": "bad",
            "text_extraction_cleanliness": "not_checked",
            "text_preview": "",
            "noise_reason": f"rejected before text extraction: {rejection_reason}",
            "rejection_reason": rejection_reason,
            "text_path": "",
            "ocr_pdf_path": "",
            "errors": "" if page_count else "pdfinfo did not return page count",
        }

    base = f"existing_{path.parent.name}_{path.stem}"
    text_path = TEXT_DIR / f"{base}.txt"
    ocr_pdf_path = OCR_DIR / f"{base}_ocr.pdf"
    ocr_text_path = TEXT_DIR / f"{base}_ocr.txt"

    pdftotext_words, extracted_chars, text_error = write_extracted_text(path, text_path)
    extracted_text = read_text_file(text_path)
    text_quality, noise_reason = ocr_quality_label(extracted_text)
    cleanliness = "clean" if text_quality == "good" else "clean_borderline" if text_quality == "medium" else "noisy"
    ocr_words = ""
    ocr_character_count = ""
    ocr_error = ""
    ocr_used = False
    final_words = pdftotext_words
    final_character_count = extracted_chars
    final_text_path = text_path
    final_text = extracted_text
    final_quality = text_quality
    final_cleanliness = cleanliness
    final_noise_reason = noise_reason

    if pdftotext_words < OCR_TRIGGER_WORDS:
        ocr_used = True
        ok, ocr_error = run_ocr(path, ocr_pdf_path)
        if ok:
            ocr_words_int, ocr_chars_int, ocr_text_error = write_extracted_text(ocr_pdf_path, ocr_text_path)
            ocr_error = ocr_error or ocr_text_error
            ocr_words = ocr_words_int
            ocr_character_count = ocr_chars_int
            ocr_text = read_text_file(ocr_text_path)
            ocr_quality, ocr_noise_reason = ocr_quality_label(ocr_text)
            final_words = ocr_words_int
            final_character_count = ocr_chars_int
            final_text_path = ocr_text_path
            final_text = ocr_text
            final_quality = ocr_quality
            final_cleanliness = (
                "clean" if ocr_quality == "good" else "clean_borderline" if ocr_quality == "medium" else "noisy"
            )
            final_noise_reason = ocr_noise_reason
        else:
            final_quality = "bad"
            final_cleanliness = "noisy"
            final_noise_reason = ocr_error or "OCR failed"

    accepted = bool(source_url) and page_count == 1 and final_words >= MIN_WORDS and final_quality in {"good", "medium"}
    rejection_reasons = []
    if not source_url:
        rejection_reasons.append("missing source URL")
    if final_words < MIN_WORDS:
        rejection_reasons.append(f"word count below {MIN_WORDS}")
    if final_quality == "bad":
        rejection_reasons.append(final_noise_reason or "bad OCR/text quality")

    return {
        "accepted": accepted,
        "local_path": str(path),
        "local_pdf_path": str(path),
        "source_url": source_url,
        "category": category,
        "category_guess": category,
        "format": format_guess,
        "format_guess": format_guess,
        "query": query,
        "title": title,
        "pages": page_count,
        "extracted_word_count": pdftotext_words,
        "pdftotext_word_count": pdftotext_words,
        "ocr_word_count": ocr_words,
        "ocr_character_count": ocr_character_count,
        "final_word_count": final_words,
        "final_character_count": final_character_count,
        "ocr_used": ocr_used,
        "ocr_required": pdftotext_words < OCR_TRIGGER_WORDS,
        "ocr_quality": final_quality,
        "text_extraction_cleanliness": final_cleanliness,
        "text_preview": text_preview(final_text, lines=30),
        "noise_reason": final_noise_reason,
        "rejection_reason": "" if accepted else "; ".join(rejection_reasons),
        "text_path": str(final_text_path),
        "ocr_pdf_path": str(ocr_pdf_path) if ocr_used and ocr_pdf_path.exists() else "",
        "errors": "; ".join(part for part in [text_error, ocr_error] if part),
    }


def main() -> None:
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    OCR_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    link_map = read_link_map()
    seen_paths = set()
    rows = []

    for pdf_dir in PDF_DIRS:
        if not pdf_dir.exists():
            continue
        for path in sorted(pdf_dir.glob("*.pdf")):
            resolved = path.resolve()
            if resolved in seen_paths:
                continue
            seen_paths.add(resolved)
            index = filename_index(path)
            link_row = link_map.get(index) if index is not None else None
            result = validate_pdf(path, link_row)
            rows.append(result)
            print(
                f"Validated: {path} | accepted={result['accepted']} "
                f"pages={result.get('pages')} words={result.get('final_word_count')} "
                f"format={result.get('format_guess')} clean={result.get('text_extraction_cleanliness')}",
                flush=True,
            )

    df = pd.DataFrame(rows)
    df.to_csv(OUTPUT_FILE, index=False)

    existing_approved = df[df["accepted"] == True].copy()
    targeted = pd.read_csv(APPROVED_FILE).fillna("") if APPROVED_FILE.exists() else pd.DataFrame()
    combined = pd.concat([targeted, existing_approved], ignore_index=True)
    if not combined.empty and "local_pdf_path" in combined.columns:
        combined = combined.drop_duplicates(subset=["local_pdf_path", "source_url"])
        ocr_used = combined["ocr_used"] if "ocr_used" in combined.columns else pd.Series(False, index=combined.index)
        quality = combined["ocr_quality"] if "ocr_quality" in combined.columns else pd.Series("", index=combined.index)
        format_guess = (
            combined["format_guess"] if "format_guess" in combined.columns else pd.Series("", index=combined.index)
        )
        combined["_ocr_order"] = ocr_used.map({False: 0, True: 1}).fillna(1)
        combined["_quality_order"] = quality.map({"good": 0, "medium": 1}).fillna(9)
        combined["_format_order"] = format_guess.map(
            {"digital": 0, "printed": 1, "handwritten": 2}
        ).fillna(9)
        combined = combined.sort_values(
            by=["_ocr_order", "_quality_order", "_format_order", "final_word_count"],
            ascending=[True, True, True, False],
        ).drop(columns=["_ocr_order", "_quality_order", "_format_order"])
    combined.to_csv(APPROVED_FILE, index=False)
    print(f"Existing accepted: {len(existing_approved)}", flush=True)
    print(f"Combined approved: {len(combined)}", flush=True)
    print(f"Saved inventory results to: {OUTPUT_FILE}", flush=True)


if __name__ == "__main__":
    main()

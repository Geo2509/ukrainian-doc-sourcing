import re
from pathlib import Path

import pandas as pd

from targeted_pradeep_run import (
    APPROVED_FILE,
    Candidate,
    OCR_DIR,
    TEXT_DIR,
    validate_candidate,
)


PDF_DIR = Path("downloads")
LINKS_FILE = Path("data/candidate_links.csv")
OUTPUT_FILE = Path("output/qa_results.csv")


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


def candidate_for_path(path: Path, link_row: dict | None) -> Candidate:
    category = ""
    format_guess = ""
    if link_row:
        category = link_row.get("category", "") or link_row.get("category_guess", "")
        format_guess = link_row.get("format", "") or link_row.get("format_guess", "")
    if not category:
        category = path.stem.split("_", 1)[-1] if "_" in path.stem else "unknown"
    if not format_guess:
        format_guess = FORMAT_BY_CATEGORY.get(category, "printed")

    return Candidate(
        category_guess=category,
        format_guess=format_guess,
        query=(link_row or {}).get("query", ""),
        title=(link_row or {}).get("title", ""),
        source_url=(link_row or {}).get("link", "") or (link_row or {}).get("source_url", ""),
        snippet=(link_row or {}).get("snippet", ""),
    )


def main() -> None:
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    OCR_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    link_map = read_link_map()
    rows = []

    for pdf_path in sorted(PDF_DIR.glob("*.pdf")):
        index = filename_index(pdf_path)
        link_row = link_map.get(index) if index is not None else None
        candidate = candidate_for_path(pdf_path, link_row)
        try:
            result = validate_candidate(candidate, pdf_path)
        except Exception as exc:
            result = {
                "accepted": False,
                "local_path": str(pdf_path),
                "local_pdf_path": str(pdf_path),
                "source_url": candidate.source_url,
                "category": candidate.category_guess,
                "format": candidate.format_guess,
                "extracted_word_count": "",
                "ocr_word_count": "",
                "ocr_character_count": "",
                "final_word_count": "",
                "final_character_count": "",
                "ocr_used": False,
                "ocr_required": False,
                "ocr_quality": "bad",
                "text_preview": "",
                "rejection_reason": str(exc),
                "errors": str(exc),
            }
        rows.append(result)
        print(
            f"Checked: {pdf_path.name} | accepted={result.get('accepted')} "
            f"words={result.get('final_word_count')} quality={result.get('ocr_quality')}",
            flush=True,
        )

    df = pd.DataFrame(rows)
    df.to_csv(OUTPUT_FILE, index=False)

    approved_df = df[df["accepted"] == True].copy() if not df.empty else df
    if not approved_df.empty:
        approved_df["_ocr_order"] = approved_df["ocr_used"].map({False: 0, True: 1}).fillna(1)
        approved_df["_quality_order"] = approved_df["ocr_quality"].map({"good": 0, "medium": 1}).fillna(9)
        approved_df["_format_order"] = approved_df["format"].map(
            {"digital": 0, "printed": 1, "handwritten": 2}
        ).fillna(9)
        approved_df = approved_df.sort_values(
            by=["_ocr_order", "_quality_order", "_format_order", "final_word_count"],
            ascending=[True, True, True, False],
        ).drop(columns=["_ocr_order", "_quality_order", "_format_order"])

    approved_df.to_csv(APPROVED_FILE, index=False)

    print(f"Approved candidates: {len(approved_df)}")
    print(f"Saved results to: {OUTPUT_FILE}")
    print(f"Saved approved candidates to: {APPROVED_FILE}")


if __name__ == "__main__":
    main()

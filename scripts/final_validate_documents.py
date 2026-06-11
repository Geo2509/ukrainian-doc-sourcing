from pathlib import Path

import pandas as pd

from targeted_pradeep_run import (
    APPROVED_FILE,
    OCR_DIR,
    TEXT_DIR,
    Candidate,
    validate_candidate,
)


RESULTS_FILE = Path("output/final_validation_results.csv")
REPORT_FILE = Path("output/final_validation_report.txt")


def row_value(row: pd.Series, *names: str) -> str:
    for name in names:
        if name in row and pd.notna(row[name]) and str(row[name]).strip():
            return str(row[name])
    return ""


def candidate_from_row(row: pd.Series) -> Candidate:
    return Candidate(
        category_guess=row_value(row, "category", "category_guess") or "unknown",
        format_guess=row_value(row, "format", "format_guess") or "printed",
        query=row_value(row, "query"),
        title=row_value(row, "title"),
        source_url=row_value(row, "source_url"),
        snippet=row_value(row, "snippet"),
    )


def first_lines(text: str, limit: int = 10) -> str:
    lines = text.splitlines()[:limit]
    return "\n".join(f"    {line}" for line in lines) if lines else "    <empty>"


def write_report(df: pd.DataFrame) -> None:
    accepted_count = int((df["accepted"] == True).sum()) if "accepted" in df.columns else 0
    lines = [
        "Final OCR/Text Validation Report",
        "",
        f"Documents checked: {len(df)}",
        f"Accepted: {accepted_count}",
        f"Rejected: {len(df) - accepted_count}",
        "",
    ]

    for _, row in df.iterrows():
        name = Path(row_value(row, "local_path", "local_pdf_path")).name
        source = row_value(row, "source_url") or "<missing>"
        final_words = row_value(row, "final_word_count")
        final_chars = row_value(row, "final_character_count", "ocr_character_count")
        ocr_required = row_value(row, "ocr_required")
        ocr_quality = row_value(row, "ocr_quality")
        accepted = row_value(row, "accepted")
        rejection = row_value(row, "rejection_reason")
        preview = row_value(row, "text_preview")

        lines.extend(
            [
                f"File: {name}",
                f"Source: {source}",
                f"Words: {final_words}",
                f"Characters: {final_chars}",
                f"OCR required: {ocr_required}",
                f"OCR quality: {ocr_quality}",
                f"Accepted: {accepted}",
            ]
        )
        if rejection:
            lines.append(f"Rejection reason: {rejection}")
        lines.append("First 10 text lines:")
        lines.append(first_lines(preview, limit=10))
        lines.append("")

    REPORT_FILE.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    OCR_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not APPROVED_FILE.exists():
        raise FileNotFoundError(f"Missing approved candidates file: {APPROVED_FILE}")

    source_df = pd.read_csv(APPROVED_FILE).fillna("")
    rows = []
    seen_paths = set()

    for _, row in source_df.iterrows():
        local_path = Path(row_value(row, "local_path", "local_pdf_path"))
        if not local_path or str(local_path) == ".":
            continue
        resolved = local_path.resolve()
        if resolved in seen_paths:
            continue
        seen_paths.add(resolved)
        if not local_path.exists():
            rows.append(
                {
                    "accepted": False,
                    "local_path": str(local_path),
                    "local_pdf_path": str(local_path),
                    "source_url": row_value(row, "source_url"),
                    "category": row_value(row, "category", "category_guess"),
                    "format": row_value(row, "format", "format_guess"),
                    "extracted_word_count": "",
                    "ocr_word_count": "",
                    "ocr_character_count": "",
                    "final_word_count": "",
                    "final_character_count": "",
                    "ocr_used": False,
                    "ocr_required": False,
                    "ocr_quality": "bad",
                    "text_preview": "",
                    "rejection_reason": "local file missing",
                    "errors": "local file missing",
                }
            )
            continue

        result = validate_candidate(candidate_from_row(row), local_path)
        rows.append(result)
        print(
            f"Final validated: {local_path.name} | accepted={result['accepted']} "
            f"words={result['final_word_count']} quality={result['ocr_quality']}",
            flush=True,
        )

    df = pd.DataFrame(rows)
    df.to_csv(RESULTS_FILE, index=False)
    write_report(df)
    print(f"Saved final results to: {RESULTS_FILE}", flush=True)
    print(f"Saved final report to: {REPORT_FILE}", flush=True)


if __name__ == "__main__":
    main()

import re
import subprocess
from pathlib import Path

import pandas as pd

from targeted_pradeep_run import (
    APPROVED_FILE,
    MIN_WORDS,
    TEXT_DIR,
    get_page_count,
    ocr_quality_label,
    read_text_file,
    text_preview,
    wc_words,
)


LINKS_FILE = Path("data/pradeep_targeted_candidate_links.csv")
TARGETED_DIR = Path("downloads/pradeep_targeted")
EXTRACT_DIR = Path("downloads/pradeep_targeted_single_pages")
OUTPUT_FILE = Path("output/pradeep_targeted_page_candidates.csv")
SINGLE_PAGE_ALLOWLIST = {
    "016_handwritten-like_p002.pdf",
    "016_handwritten-like_p003.pdf",
    "080_official_dense_p003.pdf",
    "080_official_dense_p005.pdf",
    "080_official_dense_p006.pdf",
}


def run(args: list[str], timeout: int = 90) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )


def load_links() -> dict[int, dict]:
    df = pd.read_csv(LINKS_FILE).fillna("")
    return {index + 1: row.to_dict() for index, row in df.iterrows()}


def file_index(path: Path) -> int | None:
    match = re.match(r"(\d{3})_", path.name)
    if not match:
        return None
    return int(match.group(1))


def extract_text_page(pdf_path: Path, page: int, txt_path: Path) -> int:
    result = run(
        ["pdftotext", "-layout", "-f", str(page), "-l", str(page), str(pdf_path), str(txt_path)]
    )
    if result.returncode != 0:
        return 0
    return wc_words(txt_path)


def extract_pdf_page(pdf_path: Path, page: int, output_path: Path) -> bool:
    pattern = str(output_path)
    result = run(["pdfseparate", "-f", str(page), "-l", str(page), str(pdf_path), pattern])
    return result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0


def main() -> None:
    EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    link_map = load_links()
    rows = []

    for pdf_path in sorted(TARGETED_DIR.glob("*.pdf")):
        index = file_index(pdf_path)
        link_row = link_map.get(index or -1, {})
        format_guess = link_row.get("format_guess", "")
        if format_guess not in {"digital", "handwritten"}:
            continue

        pages = get_page_count(pdf_path) or 0
        max_pages = min(pages, 12)
        for page in range(1, max_pages + 1):
            base = f"{pdf_path.stem}_p{page:03d}"
            txt_path = TEXT_DIR / f"{base}.txt"
            word_count = extract_text_page(pdf_path, page, txt_path)
            page_text = read_text_file(txt_path)
            ocr_quality, noise_reason = ocr_quality_label(page_text)
            cleanliness = "clean" if ocr_quality == "good" else "clean_borderline" if ocr_quality == "medium" else "noisy"
            accepted = word_count >= MIN_WORDS and ocr_quality in {"good", "medium"}
            output_pdf = EXTRACT_DIR / f"{base}.pdf"
            if accepted:
                extract_pdf_page(pdf_path, page, output_pdf)
            rejection_reasons = []
            if word_count < MIN_WORDS:
                rejection_reasons.append(f"word count below {MIN_WORDS}")
            if ocr_quality == "bad":
                rejection_reasons.append(noise_reason or "bad OCR/text quality")
            rows.append(
                {
                    "accepted": accepted and output_pdf.exists(),
                    "local_path": str(output_pdf) if output_pdf.exists() else "",
                    "local_pdf_path": str(output_pdf) if output_pdf.exists() else "",
                    "source_pdf_path": str(pdf_path),
                    "source_url": link_row.get("source_url", ""),
                    "category": link_row.get("category_guess", ""),
                    "category_guess": link_row.get("category_guess", ""),
                    "format": format_guess,
                    "format_guess": format_guess,
                    "query": link_row.get("query", ""),
                    "title": link_row.get("title", ""),
                    "source_page": page,
                    "pages": 1 if output_pdf.exists() else "",
                    "extracted_word_count": word_count,
                    "pdftotext_word_count": word_count,
                    "ocr_word_count": "",
                    "ocr_character_count": "",
                    "final_word_count": word_count,
                    "final_character_count": len(page_text),
                    "ocr_used": False,
                    "ocr_required": False,
                    "ocr_quality": ocr_quality,
                    "text_extraction_cleanliness": cleanliness,
                    "text_preview": text_preview(page_text, lines=30),
                    "noise_reason": noise_reason,
                    "rejection_reason": "" if accepted else "; ".join(rejection_reasons),
                    "text_path": str(txt_path),
                    "ocr_pdf_path": "",
                    "errors": "",
                }
            )
            print(
                f"Checked page: {pdf_path.name} p{page} | accepted={accepted} "
                f"words={word_count} clean={cleanliness}",
                flush=True,
            )

    df = pd.DataFrame(rows)
    df.to_csv(OUTPUT_FILE, index=False)
    if "local_pdf_path" in df.columns:
        page_names = df["local_pdf_path"].astype(str).map(lambda value: Path(value).name)
        df.loc[
            df["local_pdf_path"].astype(str).str.contains("pradeep_targeted_single_pages")
            & ~page_names.isin(SINGLE_PAGE_ALLOWLIST),
            ["accepted", "rejection_reason"],
        ] = [False, "not in approved single-page allowlist"]

    accepted = df[df["accepted"] == True].copy()

    existing = pd.read_csv(APPROVED_FILE).fillna("") if APPROVED_FILE.exists() else pd.DataFrame()
    combined = pd.concat([existing, accepted], ignore_index=True)
    if not combined.empty and "local_pdf_path" in combined.columns:
        combined = combined.drop_duplicates(subset=["local_pdf_path", "source_url"])
    combined.to_csv(APPROVED_FILE, index=False)
    print(f"Accepted page candidates: {len(accepted)}", flush=True)
    print(f"Saved page candidates to: {OUTPUT_FILE}", flush=True)
    print(f"Updated approved candidates: {APPROVED_FILE}", flush=True)


if __name__ == "__main__":
    main()

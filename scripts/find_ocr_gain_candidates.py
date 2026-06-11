import argparse
import re
import shutil
import subprocess
from pathlib import Path

import pandas as pd

from targeted_pradeep_run import ocr_quality_label


SEARCH_DIRS = [
    Path("downloads"),
    Path("approved_pdfs"),
    Path("selected_pradeep_single_pages"),
    Path("user_provided_documents"),
]
OUTPUT_DIR = Path("output/ocr_gain")
TEXT_DIR = OUTPUT_DIR / "text"
OCR_DIR = OUTPUT_DIR / "ocr"
SELECTED_DIR = OUTPUT_DIR / "selected_pdfs"
RESULTS_FILE = OUTPUT_DIR / "ocr_gain_candidates.csv"
REPORT_FILE = OUTPUT_DIR / "ocr_gain_report.txt"
SINGLE_PAGE_ALLOWLIST = {
    "016_handwritten-like_p002.pdf",
    "016_handwritten-like_p003.pdf",
    "080_official_dense_p003.pdf",
    "080_official_dense_p005.pdf",
    "080_official_dense_p006.pdf",
}

MIN_EXTRACTED_WORDS = 250
MIN_OCR_WORDS = 300
OCR_TIMEOUT_SECONDS = 120

PRIORITY_PATTERNS = {
    "contract": ["contract", "dodatkova", "ugoda", "agreement", "069_contract", "075_contract"],
    "medical_consent": ["patient_form", "medical", "doctor", "hospital", "handwritten-like"],
    "official_certificate": ["certificate", "official_dense", "sprav", "dovid", "sert"],
}


def run(args: list[str], timeout: int = 180) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            args,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(
            args=args,
            returncode=124,
            stdout=exc.stdout or "",
            stderr=f"timed out after {timeout} seconds",
        )


def pdf_page_count(path: Path) -> int | None:
    result = run(["pdfinfo", str(path)], timeout=30)
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        if line.startswith("Pages:"):
            try:
                return int(line.split(":", 1)[1].strip())
            except ValueError:
                return None
    return None


def pdftotext(path: Path) -> tuple[str, str]:
    result = run(["pdftotext", str(path), "-"], timeout=90)
    if result.returncode != 0:
        return "", result.stderr.strip()
    return result.stdout, ""


def word_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def category_for_path(path: Path) -> str:
    lowered = path.name.lower()
    for category, patterns in PRIORITY_PATTERNS.items():
        if any(pattern in lowered for pattern in patterns):
            return category
    return ""


def priority_rank(category: str) -> int:
    return {
        "contract": 1,
        "medical_consent": 2,
        "official_certificate": 3,
    }.get(category, 99)


def discover_pdfs() -> list[Path]:
    seen = set()
    seen_names = set()
    paths = []
    for search_dir in SEARCH_DIRS:
        if not search_dir.exists():
            continue
        for path in sorted(search_dir.rglob("*.pdf")):
            if "pradeep_targeted_single_pages" in str(path) and path.name not in SINGLE_PAGE_ALLOWLIST:
                continue
            resolved = path.resolve()
            if resolved in seen or path.name in seen_names:
                continue
            seen.add(resolved)
            seen_names.add(path.name)
            paths.append(path)
    return paths


def ocr_pdf(input_path: Path, output_path: Path) -> tuple[bool, str]:
    if output_path.exists() and output_path.stat().st_size > 0:
        check = run(["pdfinfo", str(output_path)], timeout=30)
        if check.returncode == 0:
            return True, ""
        output_path.unlink()
    result = run(
        [
            "ocrmypdf",
            "--deskew",
            "--clean",
            "--rotate-pages",
            "--force-ocr",
            "-l",
            "ukr",
            str(input_path),
            str(output_path),
        ],
        timeout=OCR_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        if output_path.exists():
            output_path.unlink()
        return False, (result.stderr or result.stdout).strip()
    return True, ""


def safe_output_name(path: Path) -> str:
    prefix = re.sub(r"[^A-Za-z0-9_-]+", "_", str(path.parent))
    return f"{prefix}_{path.name}"


def validate_pdf(path: Path) -> dict:
    category = category_for_path(path)
    if not category:
        return {
            "accepted": False,
            "local_path": str(path),
            "category": "",
            "rejection_reason": "not priority category",
        }

    pages = pdf_page_count(path)
    if pages != 1:
        return {
            "accepted": False,
            "local_path": str(path),
            "category": category,
            "pages": pages,
            "rejection_reason": "not single-page",
        }

    base_name = safe_output_name(path)
    extracted_text, text_error = pdftotext(path)
    extracted_word_count = word_count(extracted_text)
    extracted_text_path = TEXT_DIR / f"{Path(base_name).stem}.txt"
    extracted_text_path.write_text(extracted_text, encoding="utf-8")

    if extracted_word_count < MIN_EXTRACTED_WORDS:
        return {
            "accepted": False,
            "local_path": str(path),
            "category": category,
            "priority_rank": priority_rank(category),
            "pages": pages,
            "extracted_word_count": extracted_word_count,
            "ocr_word_count": "",
            "ocr_character_count": "",
            "ocr_quality": "not_run",
            "text_path": str(extracted_text_path),
            "rejection_reason": f"pdftotext below {MIN_EXTRACTED_WORDS}",
            "errors": text_error,
        }

    ocr_path = OCR_DIR / base_name
    ok, ocr_error = ocr_pdf(path, ocr_path)
    if not ok:
        return {
            "accepted": False,
            "local_path": str(path),
            "category": category,
            "priority_rank": priority_rank(category),
            "pages": pages,
            "extracted_word_count": extracted_word_count,
            "ocr_word_count": "",
            "ocr_character_count": "",
            "ocr_quality": "bad",
            "text_path": str(extracted_text_path),
            "ocr_pdf_path": "",
            "rejection_reason": "OCR failed",
            "errors": "; ".join(part for part in [text_error, ocr_error] if part),
        }

    ocr_text, ocr_text_error = pdftotext(ocr_path)
    ocr_word_count = word_count(ocr_text)
    ocr_character_count = len(ocr_text)
    ocr_text_path = TEXT_DIR / f"{Path(base_name).stem}_ocr.txt"
    ocr_text_path.write_text(ocr_text, encoding="utf-8")
    ocr_quality, ocr_quality_reason = ocr_quality_label(ocr_text)

    accepted = (
        extracted_word_count >= MIN_EXTRACTED_WORDS
        and ocr_word_count > MIN_OCR_WORDS
        and ocr_quality in {"good", "medium"}
    )
    rejection_reasons = []
    if ocr_word_count <= MIN_OCR_WORDS:
        rejection_reasons.append(f"OCR words not above {MIN_OCR_WORDS}")
    if ocr_quality == "bad":
        rejection_reasons.append(ocr_quality_reason or "bad OCR quality")

    if accepted:
        SELECTED_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, SELECTED_DIR / path.name)

    return {
        "accepted": accepted,
        "local_path": str(path),
        "selected_path": str(SELECTED_DIR / path.name) if accepted else "",
        "category": category,
        "priority_rank": priority_rank(category),
        "pages": pages,
        "extracted_word_count": extracted_word_count,
        "ocr_word_count": ocr_word_count,
        "ocr_character_count": ocr_character_count,
        "ocr_quality": ocr_quality,
        "quality_reason": ocr_quality_reason,
        "text_path": str(ocr_text_path),
        "ocr_pdf_path": str(ocr_path),
        "rejection_reason": "" if accepted else "; ".join(rejection_reasons),
        "errors": "; ".join(part for part in [text_error, ocr_error, ocr_text_error] if part),
        "preview": "\n".join(ocr_text.splitlines()[:10]),
    }


def write_report(df: pd.DataFrame) -> None:
    accepted = df[df["accepted"] == True].copy() if "accepted" in df.columns else pd.DataFrame()
    lines = [
        "OCR Gain Candidate Report",
        "",
        f"Criteria: pages=1, extracted_word_count >= {MIN_EXTRACTED_WORDS}, ocr_word_count > {MIN_OCR_WORDS}",
        f"Checked rows: {len(df)}",
        f"Accepted: {len(accepted)}",
        "",
    ]
    sort_columns = [column for column in ["priority_rank", "ocr_word_count"] if column in accepted.columns]
    if sort_columns:
        accepted = accepted.sort_values(
            by=sort_columns,
            ascending=[True, False][: len(sort_columns)],
        )
    for _, row in accepted.iterrows():
        lines.extend(
            [
                f"File: {row.get('local_path', '')}",
                f"Category: {row.get('category', '')}",
                f"Extracted words: {row.get('extracted_word_count', '')}",
                f"OCR words: {row.get('ocr_word_count', '')}",
                f"OCR characters: {row.get('ocr_character_count', '')}",
                f"OCR quality: {row.get('ocr_quality', '')}",
                f"Selected copy: {row.get('selected_path', '')}",
                "Preview:",
                str(row.get("preview", "")),
                "",
            ]
        )
    REPORT_FILE.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-ocr", type=int, default=0, help="Stop after this many OCR runs; 0 means no limit.")
    args = parser.parse_args()

    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    OCR_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    ocr_runs = 0
    for path in discover_pdfs():
        result = validate_pdf(path)
        rows.append(result)
        current_df = pd.DataFrame(rows)
        if not current_df.empty and "priority_rank" in current_df.columns:
            current_df = current_df.sort_values(
                by=["accepted", "priority_rank", "ocr_word_count", "extracted_word_count"],
                ascending=[False, True, False, False],
            )
        current_df.to_csv(RESULTS_FILE, index=False)
        write_report(current_df)
        if result.get("extracted_word_count", 0) >= MIN_EXTRACTED_WORDS and result.get("ocr_quality") != "not_run":
            ocr_runs += 1
        print(
            f"Checked: {path} | accepted={result.get('accepted')} "
            f"extracted={result.get('extracted_word_count', '')} "
            f"ocr={result.get('ocr_word_count', '')} reason={result.get('rejection_reason', '')}",
            flush=True,
        )
        if args.max_ocr and ocr_runs >= args.max_ocr:
            break

    df = pd.DataFrame(rows)
    if not df.empty and "priority_rank" in df.columns:
        df = df.sort_values(
            by=["accepted", "priority_rank", "ocr_word_count", "extracted_word_count"],
            ascending=[False, True, False, False],
        )
    df.to_csv(RESULTS_FILE, index=False)
    write_report(df)
    print(f"Saved results to: {RESULTS_FILE}", flush=True)
    print(f"Saved report to: {REPORT_FILE}", flush=True)
    print(f"Copied accepted PDFs to: {SELECTED_DIR}", flush=True)


if __name__ == "__main__":
    main()

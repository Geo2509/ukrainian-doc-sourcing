import csv
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

import pandas as pd
import requests

try:
    from ddgs import DDGS
except ImportError:
    DDGS = None


RUN_NAME = "pradeep_targeted"
LINKS_FILE = Path("data/pradeep_targeted_candidate_links.csv")
DOWNLOAD_DIR = Path("downloads/pradeep_targeted")
TEXT_DIR = Path("output/pradeep_targeted_text")
OCR_DIR = Path("output/pradeep_targeted_ocr")
ALL_RESULTS_FILE = Path("output/pradeep_targeted_all_results.csv")
APPROVED_FILE = Path("output/approved_candidates.csv")

MAX_RESULTS_PER_QUERY = 20
REQUEST_TIMEOUT_SECONDS = 30
MIN_WORDS = 300
PREFERRED_WORDS = 350
LOW_TEXT_WORDS = 250
OCR_TRIGGER_WORDS = 300


QUERY_GROUPS = [
    (
        "printed_form_handfilled",
        "printed",
        [
            "інформована згода пацієнта бланк PDF українською",
            "анкета пацієнта бланк PDF українською",
            "медична форма пацієнта бланк PDF українською",
            "форма згоди пацієнта підпис дата PDF українською",
            "бланк медичного огляду PDF українською підпис",
            "медична карта пацієнта форма PDF українською",
            "заява пацієнта бланк PDF українською підпис",
            "печатна форма заповнена від руки PDF українською",
        ],
    ),
    (
        "official_dense",
        "digital",
        [
            "site:moz.gov.ua filetype:pdf довідка проєкт постанови медичний огляд",
            "site:kmu.gov.ua filetype:pdf довідка щодо відповідності зобов'язанням України",
            "site:me.gov.ua filetype:pdf фінансовий звіт довідка українською",
            "site:mtu.gov.ua filetype:pdf звіт довідка українською 2024",
            "site:msp.gov.ua filetype:pdf пояснювальна записка українською",
            "site:rada.gov.ua filetype:pdf пояснювальна записка проект постанови",
        ],
    ),
    (
        "printed_dense",
        "printed",
        [
            "договір українською PDF одна сторінка",
            "додаткова угода українською PDF",
            "акт виконаних робіт українською PDF",
            "рахунок фактура українською PDF",
            "квитанція українською PDF 300 слів",
            "товарний чек накладна українською PDF",
            "сертифікат відповідності українською PDF",
            "сертифікат якості продукції українською PDF",
            "протокол випробувань українською PDF",
            "фінансовий звіт українською PDF одна сторінка",
        ],
    ),
]


UKRAINIAN_MARKERS = set("іїєґІЇЄҐ")
CYRILLIC_RE = re.compile(r"[А-Яа-яІіЇїЄєҐґ]")
WORD_RE = re.compile(r"\S+")
TOKEN_RE = re.compile(r"[А-Яа-яІіЇїЄєҐґA-Za-z0-9ʼ'-]+")
ISOLATED_LETTER_RE = re.compile(r"^[А-Яа-яІіЇїЄєҐґA-Za-z]$")
GOOD_UKRAINIAN_PHRASES = [
    "Міністерство",
    "України",
    "Інформована згода",
    "Акт виконаних робіт",
    "Додаткова угода",
    "адреса місця проживання",
]
COMMON_UKRAINIAN_WORDS = {
    "україни",
    "україна",
    "міністерство",
    "договір",
    "додаткова",
    "угода",
    "акт",
    "виконаних",
    "робіт",
    "адреса",
    "місця",
    "проживання",
    "пацієнта",
    "згода",
    "інформована",
    "заява",
    "дата",
    "підпис",
    "прізвище",
    "ім",
    "відповідно",
    "послуги",
    "рахунок",
    "сума",
}


@dataclass
class Candidate:
    category_guess: str
    format_guess: str
    query: str
    title: str
    source_url: str
    snippet: str


def ensure_dirs() -> None:
    for path in [LINKS_FILE.parent, DOWNLOAD_DIR, TEXT_DIR, OCR_DIR, ALL_RESULTS_FILE.parent]:
        path.mkdir(parents=True, exist_ok=True)


def clean_filename(text: str) -> str:
    text = unquote(str(text))
    text = re.sub(r"[^a-zA-Zа-яА-ЯіІїЇєЄґҐ0-9_-]+", "_", text)
    return text.strip("_")[:70] or "document"


def looks_like_pdf_url(url: str) -> bool:
    lower = url.lower()
    parsed_path = urlparse(lower).path
    return ".pdf" in parsed_path or "pdf" in lower


def search_links() -> list[Candidate]:
    if DDGS is None:
        raise RuntimeError("ddgs is required for search_links(); install it or reuse an existing links CSV")

    rows: list[Candidate] = []
    seen: set[str] = set()

    with DDGS() as ddgs:
        for category_guess, format_guess, queries in QUERY_GROUPS:
            for query in queries:
                print(f"Searching: {format_guess} | {query}", flush=True)
                try:
                    results = ddgs.text(
                        query,
                        region="ua-uk",
                        safesearch="off",
                        max_results=MAX_RESULTS_PER_QUERY,
                    )
                except Exception as exc:
                    print(f"Search error: {exc}", flush=True)
                    time.sleep(2)
                    continue

                for item in results:
                    url = item.get("href", "")
                    if not url or url in seen or not looks_like_pdf_url(url):
                        continue
                    seen.add(url)
                    rows.append(
                        Candidate(
                            category_guess=category_guess,
                            format_guess=format_guess,
                            query=query,
                            title=item.get("title", ""),
                            source_url=url,
                            snippet=item.get("body", ""),
                        )
                    )
                time.sleep(2)

    with LINKS_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["category_guess", "format_guess", "query", "title", "source_url", "snippet"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row.__dict__)

    print(f"Saved {len(rows)} candidate links to {LINKS_FILE}", flush=True)
    return rows


def download_pdf(candidate: Candidate, index: int) -> Path | None:
    suffix = clean_filename(candidate.category_guess)
    filename = f"{index:03d}_{suffix}.pdf"
    path = DOWNLOAD_DIR / filename

    if path.exists() and path.stat().st_size > 0:
        return path

    try:
        response = requests.get(
            candidate.source_url,
            timeout=REQUEST_TIMEOUT_SECONDS,
            headers={"User-Agent": "Mozilla/5.0"},
            allow_redirects=True,
        )
    except Exception as exc:
        print(f"Download error: {candidate.source_url} | {exc}", flush=True)
        return None

    content_type = response.headers.get("Content-Type", "").lower()
    content = response.content
    if response.status_code != 200:
        print(f"Skipped status {response.status_code}: {candidate.source_url}", flush=True)
        return None
    if b"%PDF" not in content[:1024] and "pdf" not in content_type:
        print(f"Skipped non-PDF: {candidate.source_url} | {content_type}", flush=True)
        return None

    path.write_bytes(content)
    print(f"Saved: {path}", flush=True)
    return path


def run_command(args: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )


def get_page_count(pdf_path: Path) -> int | None:
    result = run_command(["pdfinfo", str(pdf_path)], timeout=30)
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        if line.startswith("Pages:"):
            try:
                return int(line.split(":", 1)[1].strip())
            except ValueError:
                return None
    return None


def extract_pdftotext(pdf_path: Path, txt_path: Path) -> tuple[int, str]:
    result = run_command(["pdftotext", "-layout", str(pdf_path), str(txt_path)], timeout=90)
    if result.returncode != 0:
        return 0, result.stderr.strip()
    return wc_words(txt_path), ""


def extract_text_stdout(pdf_path: Path) -> tuple[str, str]:
    result = run_command(["pdftotext", str(pdf_path), "-"], timeout=90)
    if result.returncode != 0:
        return "", result.stderr.strip()
    return result.stdout, ""


def write_extracted_text(pdf_path: Path, txt_path: Path) -> tuple[int, int, str]:
    text, error = extract_text_stdout(pdf_path)
    txt_path.write_text(text, encoding="utf-8")
    return count_words(text), len(text), error


def wc_words(txt_path: Path) -> int:
    result = run_command(["wc", "-w", str(txt_path)], timeout=30)
    if result.returncode != 0:
        return 0
    try:
        return int(result.stdout.strip().split()[0])
    except (IndexError, ValueError):
        return 0


def count_words(text: str) -> int:
    return len(WORD_RE.findall(text))


def text_preview(text: str, lines: int = 30) -> str:
    return "\n".join(text.splitlines()[:lines])


def read_text_file(txt_path: Path) -> str:
    return txt_path.read_text(encoding="utf-8", errors="replace") if txt_path.exists() else ""


def max_consecutive_single_letter_lines(lines: list[str]) -> int:
    longest = 0
    current = 0
    for line in lines:
        stripped = line.strip()
        if ISOLATED_LETTER_RE.match(stripped):
            current += 1
            longest = max(longest, current)
        elif stripped:
            current = 0
    return longest


def ocr_quality_label(text: str) -> tuple[str, str]:
    lines = text.splitlines()
    nonempty_lines = [line.strip() for line in lines if line.strip()]
    tokens = TOKEN_RE.findall(text)
    words = [token for token in tokens if any(ch.isalpha() for ch in token)]
    lower_text = text.lower()
    lower_words = [word.lower() for word in words]

    if not words:
        return "bad", "empty text"

    single_letter_lines = sum(1 for line in nonempty_lines if ISOLATED_LETTER_RE.match(line))
    single_letter_words = sum(1 for word in words if ISOLATED_LETTER_RE.match(word))
    cyrillic_chars = len(CYRILLIC_RE.findall(text))
    total_letters = sum(1 for ch in text if ch.isalpha())
    replacement_chars = text.count("\ufffd")
    ukrainian_hits = sum(text.count(ch) for ch in UKRAINIAN_MARKERS)
    phrase_hits = sum(1 for phrase in GOOD_UKRAINIAN_PHRASES if phrase.lower() in lower_text)
    common_word_hits = sum(1 for word in lower_words if word in COMMON_UKRAINIAN_WORDS)
    long_ukrainian_words = [
        word
        for word in lower_words
        if len(word) >= 5 and CYRILLIC_RE.search(word) and not ISOLATED_LETTER_RE.match(word)
    ]

    single_line_ratio = single_letter_lines / max(len(nonempty_lines), 1)
    single_word_ratio = single_letter_words / max(len(words), 1)
    cyrillic_ratio = cyrillic_chars / max(total_letters, 1)
    replacement_ratio = replacement_chars / max(len(text), 1)
    long_word_ratio = len(long_ukrainian_words) / max(len(words), 1)
    vertical_run = max_consecutive_single_letter_lines(nonempty_lines)

    reasons = []
    if vertical_run >= 5:
        reasons.append(f"vertical single-letter run={vertical_run}")
    if single_line_ratio > 0.25 and len(nonempty_lines) >= 12:
        reasons.append(f"many single-letter lines={single_line_ratio:.0%}")
    if single_word_ratio > 0.35 and len(words) >= 30:
        reasons.append(f"many isolated-letter tokens={single_word_ratio:.0%}")
    if cyrillic_ratio < 0.45 and len(words) >= 50:
        reasons.append(f"low Cyrillic ratio={cyrillic_ratio:.0%}")
    if replacement_ratio > 0.02:
        reasons.append("replacement characters")
    if ukrainian_hits == 0 and cyrillic_chars > 100:
        reasons.append("no Ukrainian-specific letters")
    if phrase_hits == 0 and common_word_hits < 3 and long_word_ratio < 0.18:
        reasons.append("no normal Ukrainian words/phrases")

    if reasons:
        return "bad", "; ".join(reasons)

    if phrase_hits >= 1 or common_word_hits >= 5 or long_word_ratio >= 0.28:
        return "good", ""

    return "medium", "limited Ukrainian document markers"


def text_noise_label(txt_path: Path) -> tuple[str, str]:
    quality, reason = ocr_quality_label(read_text_file(txt_path))
    if quality == "bad":
        return "noisy", reason
    if quality == "medium":
        return "clean_borderline", reason
    return "clean", reason


def run_ocr(pdf_path: Path, output_path: Path) -> tuple[bool, str]:
    if output_path.exists() and output_path.stat().st_size > 0:
        return True, ""
    result = run_command(
        [
            "ocrmypdf",
            "--deskew",
            "--clean",
            "--rotate-pages",
            "-l",
            "ukr",
            "--skip-big",
            "50",
            str(pdf_path),
            str(output_path),
        ],
        timeout=240,
    )
    if result.returncode != 0:
        return False, (result.stderr or result.stdout).strip()
    return True, ""


def validate_candidate(candidate: Candidate, pdf_path: Path) -> dict:
    base = pdf_path.stem
    text_path = TEXT_DIR / f"{base}.txt"
    ocr_pdf_path = OCR_DIR / f"{base}_ocr.pdf"
    ocr_text_path = TEXT_DIR / f"{base}_ocr.txt"

    page_count = get_page_count(pdf_path)
    if page_count != 1:
        rejection_reason = "not single-page"
        return {
            "accepted": False,
            "local_path": str(pdf_path),
            "local_pdf_path": str(pdf_path),
            "source_url": candidate.source_url,
            "category": candidate.category_guess,
            "category_guess": candidate.category_guess,
            "format": candidate.format_guess,
            "format_guess": candidate.format_guess,
            "query": candidate.query,
            "title": candidate.title,
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

    pdftotext_words, extracted_chars, text_error = write_extracted_text(pdf_path, text_path)
    extracted_text = read_text_file(text_path)
    text_quality, noise_reason = ocr_quality_label(extracted_text)
    text_cleanliness = "clean" if text_quality == "good" else "clean_borderline" if text_quality == "medium" else "noisy"

    ocr_words = ""
    ocr_character_count = ""
    ocr_error = ""
    ocr_quality = ""
    ocr_used = False
    final_words = pdftotext_words
    final_character_count = extracted_chars
    final_text_path = text_path
    final_text = extracted_text
    final_quality = text_quality
    final_cleanliness = text_cleanliness
    final_noise_reason = noise_reason

    if pdftotext_words < OCR_TRIGGER_WORDS:
        ocr_used = True
        ok, ocr_error = run_ocr(pdf_path, ocr_pdf_path)
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
            ocr_quality = "bad"
            final_quality = "bad"
            final_cleanliness = "noisy"
            final_noise_reason = ocr_error or "OCR failed"

    accepted = (
        page_count == 1
        and final_words >= MIN_WORDS
        and final_quality in {"good", "medium"}
    )

    if accepted and final_words < PREFERRED_WORDS:
        final_cleanliness = "clean_borderline"

    rejection_reasons = []
    if page_count != 1:
        rejection_reasons.append("not single-page")
    if final_words < MIN_WORDS:
        rejection_reasons.append(f"word count below {MIN_WORDS}")
    if final_quality == "bad":
        rejection_reasons.append(final_noise_reason or "bad OCR/text quality")
    if ocr_used and ocr_error and not ocr_pdf_path.exists():
        rejection_reasons.append("OCR failed")
    rejection_reason = "; ".join(rejection_reasons)

    return {
        "accepted": accepted,
        "local_path": str(pdf_path),
        "local_pdf_path": str(pdf_path),
        "source_url": candidate.source_url,
        "category": candidate.category_guess,
        "category_guess": candidate.category_guess,
        "format": candidate.format_guess,
        "format_guess": candidate.format_guess,
        "query": candidate.query,
        "title": candidate.title,
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
        "rejection_reason": "" if accepted else rejection_reason,
        "text_path": str(final_text_path),
        "ocr_pdf_path": str(ocr_pdf_path) if ocr_used and ocr_pdf_path.exists() else "",
        "errors": "; ".join(part for part in [text_error, ocr_error] if part),
    }


def load_existing_links() -> list[Candidate]:
    if not LINKS_FILE.exists():
        return []
    df = pd.read_csv(LINKS_FILE).fillna("")
    rows = []
    for _, row in df.iterrows():
        rows.append(
            Candidate(
                category_guess=row["category_guess"],
                format_guess=row["format_guess"],
                query=row["query"],
                title=row["title"],
                source_url=row["source_url"],
                snippet=row["snippet"],
            )
        )
    return rows


def main() -> None:
    ensure_dirs()
    candidates = load_existing_links()
    if candidates:
        print(f"Reusing {len(candidates)} candidate links from {LINKS_FILE}", flush=True)
    else:
        candidates = search_links()

    results = []
    for index, candidate in enumerate(candidates, start=1):
        pdf_path = download_pdf(candidate, index)
        if not pdf_path:
            continue
        try:
            result = validate_candidate(candidate, pdf_path)
        except Exception as exc:
            result = {
                "accepted": False,
                "local_pdf_path": str(pdf_path),
                "source_url": candidate.source_url,
                "category_guess": candidate.category_guess,
                "format_guess": candidate.format_guess,
                "query": candidate.query,
                "title": candidate.title,
                "errors": str(exc),
            }
        results.append(result)
        print(
            f"Validated: {pdf_path.name} | accepted={result.get('accepted')} "
            f"pages={result.get('pages')} words={result.get('final_word_count')} "
            f"clean={result.get('text_extraction_cleanliness')}",
            flush=True,
        )

    df = pd.DataFrame(results)
    df.to_csv(ALL_RESULTS_FILE, index=False)

    if df.empty:
        df.to_csv(APPROVED_FILE, index=False)
        print("No downloaded PDFs validated.", flush=True)
        return

    approved = df[df["accepted"] == True].copy()
    if not approved.empty:
        approved["_format_order"] = approved["format_guess"].map(
            {"digital": 0, "printed": 1, "handwritten": 2}
        ).fillna(9)
        approved["_ocr_order"] = approved["ocr_used"].map({False: 0, True: 1}).fillna(1)
        approved["_quality_order"] = approved["ocr_quality"].map({"good": 0, "medium": 1}).fillna(9)
        approved = approved.sort_values(
            by=["_ocr_order", "_quality_order", "_format_order", "final_word_count"],
            ascending=[True, True, True, False],
        ).drop(columns=["_format_order", "_ocr_order", "_quality_order"])

    approved.to_csv(APPROVED_FILE, index=False)
    print(f"Approved candidates: {len(approved)}", flush=True)
    print(f"Saved all results to: {ALL_RESULTS_FILE}", flush=True)
    print(f"Saved approved candidates to: {APPROVED_FILE}", flush=True)


if __name__ == "__main__":
    main()

import argparse
import csv
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_ROOTS = [
    "downloads",
    "approved_pdfs",
    "prepared_pdfs",
    "generated_pdfs",
    "duplicates_removed",
    "duplicates_removed_visual",
    "selected_one_page_handfill_candidates",
    "selected_pradeep_single_pages",
    "user_provided_documents",
    "output/ocr_gain/selected_pdfs",
    "output/ocr_gain/ocr",
    "output/pradeep_targeted_ocr",
]

OUTPUT_FILE = Path("manifests/pdf_inventory.csv")

STATUS_BY_ROOT = {
    "approved_pdfs": "approved",
    "selected_pradeep_single_pages": "selected",
    "selected_one_page_handfill_candidates": "selected",
    "user_provided_documents": "user_provided",
    "output/ocr_gain/selected_pdfs": "selected_ocr_gain",
    "output/ocr_gain/ocr": "ocr_generated",
    "output/pradeep_targeted_ocr": "ocr_generated",
    "generated_pdfs": "generated",
    "prepared_pdfs": "prepared",
    "duplicates_removed": "duplicate_working",
    "duplicates_removed_visual": "duplicate_working",
    "downloads": "raw_download",
}


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def normalize_path(path: Path) -> str:
    return path.as_posix()


def infer_category(path: Path) -> str:
    name = path.stem.lower()
    known = [
        "contract",
        "certificate_of_analysis",
        "patient_form",
        "medical_doctor_note",
        "hospital_claim",
        "financial_environmental_report",
        "logistics_financial",
        "receipt",
        "handwritten",
        "official_dense",
        "printed_dense",
        "handwritten-like",
        "editable_docs",
    ]
    for category in known:
        if category in name:
            return category
    match = re.match(r"!*\d{3}_(.+)$", name)
    return match.group(1) if match else ""


def infer_status(path: Path, project_root: Path) -> str:
    rel = path.relative_to(project_root)
    rel_text = normalize_path(rel)
    candidates = sorted(STATUS_BY_ROOT, key=len, reverse=True)
    for root in candidates:
        if rel_text == root or rel_text.startswith(f"{root}/"):
            return STATUS_BY_ROOT[root]
    return "unknown"


def infer_source(path: Path, project_root: Path) -> str:
    rel = path.relative_to(project_root)
    parts = rel.parts
    if not parts:
        return ""
    if parts[0] == "output" and len(parts) > 1:
        return "/".join(parts[:2])
    return parts[0]


def iter_pdfs(project_root: Path, roots: list[str]) -> list[Path]:
    seen = set()
    pdfs = []
    for root in roots:
        search_root = (project_root / root).resolve()
        if not search_root.exists():
            continue
        if search_root.is_file() and search_root.suffix.lower() == ".pdf":
            candidates = [search_root]
        else:
            candidates = sorted(search_root.rglob("*.pdf"))
        for path in candidates:
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            pdfs.append(resolved)
    return pdfs


def build_manifest(project_root: Path, roots: list[str]) -> list[dict]:
    rows = []
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for index, path in enumerate(iter_pdfs(project_root, roots), start=1):
        rel_path = path.relative_to(project_root)
        size_bytes = path.stat().st_size
        rows.append(
            {
                "document_id": f"pdf_{index:06d}",
                "file_name": path.name,
                "relative_path": normalize_path(rel_path),
                "source": infer_source(path, project_root),
                "status": infer_status(path, project_root),
                "category": infer_category(path),
                "size_bytes": size_bytes,
                "size_mb": f"{size_bytes / 1024 / 1024:.3f}",
                "sha256": sha256_file(path),
                "drive_path": "",
                "source_url": "",
                "generated_at": generated_at,
                "notes": "",
            }
        )
    return rows


def write_csv(rows: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "document_id",
        "file_name",
        "relative_path",
        "source",
        "status",
        "category",
        "size_bytes",
        "size_mb",
        "sha256",
        "drive_path",
        "source_url",
        "generated_at",
        "notes",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a PDF inventory manifest.")
    parser.add_argument(
        "--root",
        action="append",
        dest="roots",
        help="Directory or PDF file to scan. Can be passed multiple times.",
    )
    parser.add_argument(
        "--output",
        default=str(OUTPUT_FILE),
        help=f"Output CSV path. Default: {OUTPUT_FILE}",
    )
    args = parser.parse_args()

    project_root = Path.cwd().resolve()
    roots = args.roots or DEFAULT_ROOTS
    rows = build_manifest(project_root, roots)
    write_csv(rows, Path(args.output))
    total_mb = sum(int(row["size_bytes"]) for row in rows) / 1024 / 1024
    print(f"PDF rows: {len(rows)}")
    print(f"Total size: {total_mb:.2f} MB")
    print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()

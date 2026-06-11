import argparse
import csv
import hashlib
from pathlib import Path


DEFAULT_EXCLUDE_DIRS = {
    ".agents",
    ".codex",
    ".git",
    "__pycache__",
    "venv",
}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_pdfs(root, exclude_dirs):
    pdfs_by_dir = {}

    for path in root.rglob("*.pdf"):
        if any(part in exclude_dirs for part in path.parts):
            continue
        if not path.is_file():
            continue

        pdfs_by_dir.setdefault(path.parent, []).append(path)

    return pdfs_by_dir


def find_duplicates(pdfs_by_dir):
    rows = []

    for folder, files in sorted(pdfs_by_dir.items(), key=lambda item: str(item[0])):
        groups = {}

        for path in sorted(files, key=lambda item: item.name):
            groups.setdefault(sha256(path), []).append(path)

        for digest, group in groups.items():
            if len(group) <= 1:
                continue

            kept_file = group[0]

            for duplicate in group[1:]:
                rows.append({
                    "folder": str(folder),
                    "sha256": digest,
                    "kept_file": str(kept_file),
                    "duplicate_file": str(duplicate),
                    "duplicate_size_bytes": duplicate.stat().st_size,
                })

    return rows


def write_report(rows, report_path):
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with report_path.open("w", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "folder",
                "sha256",
                "kept_file",
                "duplicate_file",
                "duplicate_size_bytes",
                "deleted",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(
        description="Find or remove exact duplicate PDFs inside each project folder."
    )
    parser.add_argument("--root", default=".", help="Project root to scan.")
    parser.add_argument(
        "--report",
        default="output/duplicate_cleanup_report.csv",
        help="CSV report path.",
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete duplicates. Without this flag the script only reports them.",
    )
    parser.add_argument(
        "--exclude-dir",
        action="append",
        default=[],
        help="Additional directory name to exclude. Can be passed multiple times.",
    )
    args = parser.parse_args()

    root = Path(args.root)
    exclude_dirs = DEFAULT_EXCLUDE_DIRS | set(args.exclude_dir)

    rows = find_duplicates(collect_pdfs(root, exclude_dirs))

    for row in rows:
        duplicate = Path(row["duplicate_file"])
        row["deleted"] = False

        if args.delete and duplicate.exists():
            duplicate.unlink()
            row["deleted"] = True

    write_report(rows, Path(args.report))

    action = "deleted" if args.delete else "found"
    print(f"{action}: {len(rows)} duplicate PDF files")
    print(f"report: {args.report}")


if __name__ == "__main__":
    main()

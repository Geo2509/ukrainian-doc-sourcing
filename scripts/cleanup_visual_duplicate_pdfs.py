import argparse
import csv
import shutil
from pathlib import Path

import fitz
from PIL import Image


DEFAULT_EXCLUDE_DIRS = {
    ".agents",
    ".codex",
    ".git",
    "__pycache__",
    "duplicates_removed",
    "duplicates_removed_visual",
    "venv",
}


def hamming(left, right):
    return (left ^ right).bit_count()


def dhash(image, hash_size=16):
    image = image.convert("L").resize(
        (hash_size + 1, hash_size),
        Image.Resampling.LANCZOS,
    )
    pixels = list(image.getdata())

    value = 0
    bit = 0
    width = hash_size + 1

    for y in range(hash_size):
        row = y * width
        for x in range(hash_size):
            if pixels[row + x] > pixels[row + x + 1]:
                value |= 1 << bit
            bit += 1

    return value


def page_hashes(path, hash_size=16, max_pages=3):
    doc = fitz.open(path)
    hashes = []

    for page_index in range(min(doc.page_count, max_pages)):
        page = doc[page_index]
        pix = page.get_pixmap(matrix=fitz.Matrix(0.7, 0.7), alpha=False)
        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        hashes.append(dhash(image, hash_size=hash_size))

    page_count = doc.page_count
    doc.close()

    return page_count, hashes


def collect_pdfs(root, exclude_dirs):
    pdfs_by_dir = {}

    for path in root.rglob("*.pdf"):
        if any(part in exclude_dirs for part in path.parts):
            continue
        if not path.is_file():
            continue

        pdfs_by_dir.setdefault(path.parent, []).append(path)

    return pdfs_by_dir


def visual_distance(left, right):
    if left["page_count"] != right["page_count"]:
        return None

    if len(left["hashes"]) != len(right["hashes"]):
        return None

    distances = [
        hamming(left_hash, right_hash)
        for left_hash, right_hash in zip(left["hashes"], right["hashes"])
    ]

    return max(distances) if distances else None


def find_visual_duplicates(pdfs_by_dir, threshold, hash_size, max_pages):
    rows = []

    for folder, files in sorted(pdfs_by_dir.items(), key=lambda item: str(item[0])):
        signatures = []

        for path in sorted(files, key=lambda item: item.name):
            try:
                page_count, hashes = page_hashes(
                    path,
                    hash_size=hash_size,
                    max_pages=max_pages,
                )
            except Exception as error:
                rows.append({
                    "folder": str(folder),
                    "kept_file": "",
                    "duplicate_file": str(path),
                    "page_count": "",
                    "max_hamming_distance": "",
                    "action": "error",
                    "target_file": "",
                    "error": str(error),
                })
                continue

            current = {
                "path": path,
                "page_count": page_count,
                "hashes": hashes,
            }

            duplicate_of = None
            duplicate_distance = None

            for existing in signatures:
                distance = visual_distance(current, existing)

                if distance is not None and distance <= threshold:
                    duplicate_of = existing
                    duplicate_distance = distance
                    break

            if duplicate_of is None:
                signatures.append(current)
                continue

            rows.append({
                "folder": str(folder),
                "kept_file": str(duplicate_of["path"]),
                "duplicate_file": str(path),
                "page_count": page_count,
                "max_hamming_distance": duplicate_distance,
                "action": "found",
                "target_file": "",
                "error": "",
            })

    return rows


def unique_target(path):
    if not path.exists():
        return path

    for index in range(1, 10_000):
        candidate = path.with_name(f"{path.stem}_dup{index}{path.suffix}")
        if not candidate.exists():
            return candidate

    raise RuntimeError(f"Could not create unique target for {path}")


def apply_action(rows, action, root, move_root):
    if action == "report":
        return rows

    for row in rows:
        if row["action"] == "error":
            continue

        duplicate = Path(row["duplicate_file"])

        if not duplicate.exists():
            row["action"] = "missing"
            continue

        if action == "delete":
            duplicate.unlink()
            row["action"] = "deleted"
            continue

        if action == "move":
            relative = duplicate.relative_to(root)
            target = unique_target(move_root / relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(duplicate), str(target))
            row["action"] = "moved"
            row["target_file"] = str(target)

    return rows


def write_report(rows, report_path):
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with report_path.open("w", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "folder",
                "kept_file",
                "duplicate_file",
                "page_count",
                "max_hamming_distance",
                "action",
                "target_file",
                "error",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(
        description="Find visually duplicate PDFs using rendered-page perceptual hashes."
    )
    parser.add_argument("--root", default=".", help="Project root to scan.")
    parser.add_argument(
        "--report",
        default="output/visual_duplicate_report.csv",
        help="CSV report path.",
    )
    parser.add_argument(
        "--action",
        choices=["report", "move", "delete"],
        default="report",
        help="What to do with visual duplicates.",
    )
    parser.add_argument(
        "--move-root",
        default="duplicates_removed_visual",
        help="Where to move duplicates when --action move is used.",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=4,
        help="Maximum per-page dHash Hamming distance to treat files as duplicates.",
    )
    parser.add_argument(
        "--hash-size",
        type=int,
        default=16,
        help="dHash size. 16 means 256 bits per rendered page.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=3,
        help="Maximum number of pages to hash per PDF.",
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

    rows = find_visual_duplicates(
        collect_pdfs(root, exclude_dirs),
        threshold=args.threshold,
        hash_size=args.hash_size,
        max_pages=args.max_pages,
    )
    rows = apply_action(rows, args.action, root, Path(args.move_root))
    write_report(rows, Path(args.report))

    duplicate_rows = [row for row in rows if row["action"] != "error"]
    error_rows = [row for row in rows if row["action"] == "error"]

    print(f"visual duplicate rows: {len(duplicate_rows)}")
    print(f"errors: {len(error_rows)}")
    print(f"action: {args.action}")
    print(f"report: {args.report}")


if __name__ == "__main__":
    main()

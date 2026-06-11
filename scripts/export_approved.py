import os
import shutil
from pathlib import Path
import pandas as pd

CSV_FILE = "output/approved_candidates.csv"
SOURCE_DIR = "downloads"
TARGET_DIR = "approved_pdfs"

os.makedirs(TARGET_DIR, exist_ok=True)

df = pd.read_csv(CSV_FILE)

for _, row in df.iterrows():

    if "local_path" in row and pd.notna(row["local_path"]) and str(row["local_path"]).strip():
        source = Path(str(row["local_path"]))
    elif "local_pdf_path" in row and pd.notna(row["local_pdf_path"]) and str(row["local_pdf_path"]).strip():
        source = Path(str(row["local_pdf_path"]))
    else:
        filename = row["file"]
        source = Path(SOURCE_DIR) / filename

    target = Path(TARGET_DIR) / source.name

    if os.path.exists(source):
        shutil.copy2(source, target)
        print(f"Copied: {source.name}")

print("\nDone.")
print(
    "Next: run `python scripts/cleanup_duplicate_pdfs.py` to check duplicates "
    "or `python scripts/cleanup_duplicate_pdfs.py --delete` to remove exact duplicates."
)

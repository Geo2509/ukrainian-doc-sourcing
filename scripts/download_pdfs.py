import os
import re
import requests
import pandas as pd

INPUT_FILE = "data/candidate_links.csv"
OUTPUT_DIR = "downloads"

os.makedirs(OUTPUT_DIR, exist_ok=True)

df = pd.read_csv(INPUT_FILE)

def clean_filename(text):
    text = str(text)
    text = re.sub(r"[^a-zA-Zа-яА-ЯіІїЇєЄґҐ0-9_-]+", "_", text)
    return text[:60]

for index, row in df.iterrows():
    url = row.get("link", "")
    category = row.get("category", "unknown")
    title = row.get("title", "")

    if not url:
        continue

    filename = f"{index + 1:03d}_{clean_filename(category)}.pdf"
    filepath = os.path.join(OUTPUT_DIR, filename)

    try:
        print(f"Downloading: {url}")

        response = requests.get(
            url,
            timeout=25,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        content_type = response.headers.get("Content-Type", "").lower()

        if response.status_code == 200 and (
            "pdf" in content_type
            or url.lower().endswith(".pdf")
        ):
            with open(filepath, "wb") as f:
                f.write(response.content)

            print(f"Saved: {filepath}")

        else:
            print(f"Skipped not PDF: {url}")
            print(f"Status: {response.status_code}, Content-Type: {content_type}")

    except Exception as e:
        print(f"Error downloading: {url}")
        print(e)
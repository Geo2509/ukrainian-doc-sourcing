import argparse
import re
from pathlib import Path

import pandas as pd


DEFAULT_INPUT_DIR = Path("data")
DEFAULT_OUTPUT_DIR = Path("data/public")
DROP_PUBLIC_COLUMNS = {"title", "snippet", "body", "description"}

REDACTIONS = [
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[EMAIL_REDACTED]"),
    (re.compile(r"UA\d{27}"), "[IBAN_REDACTED]"),
    (re.compile(r"(?<!\d)(?:\+?380|0)\d{9}(?!\d)"), "[PHONE_REDACTED]"),
    (re.compile(r"\b[А-ЯІЇЄҐ]{2}\s?\d{6}\b"), "[PASSPORT_REDACTED]"),
    (re.compile(r"\bРНОКПП:?\s*\d{10}\b", re.IGNORECASE), "РНОКПП: [TAX_ID_REDACTED]"),
    (re.compile(r"\b\d{10}\b"), "[10_DIGIT_ID_REDACTED]"),
]


def sanitize_text(value: object) -> object:
    if not isinstance(value, str):
        return value
    sanitized = value
    for pattern, replacement in REDACTIONS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


def sanitize_csv(input_path: Path, output_path: Path) -> None:
    df = pd.read_csv(input_path).fillna("")
    df = df.drop(columns=[column for column in DROP_PUBLIC_COLUMNS if column in df.columns])
    for column in df.columns:
        if df[column].dtype == object:
            df[column] = df[column].map(sanitize_text)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create PII-sanitized public metadata CSVs.")
    parser.add_argument("--input-dir", default=str(DEFAULT_INPUT_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    count = 0
    for input_path in sorted(input_dir.glob("*.csv")):
        output_path = output_dir / input_path.name
        sanitize_csv(input_path, output_path)
        print(f"Sanitized: {input_path} -> {output_path}")
        count += 1
    print(f"Sanitized CSV files: {count}")


if __name__ == "__main__":
    main()

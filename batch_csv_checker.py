#!/usr/bin/env python3
"""
Consolidates CSV files from csv/ directory into consolidated/consolidated.csv.
Filenames must be datetimestrings; a 'source_epoch' column (Unix timestamp
derived from the filename) is injected into each row before writing.
Validates that column names match before appending.
"""

import csv
import sys
from datetime import timezone
from pathlib import Path

# Datetime formats to try when parsing the filename (stem only, no extension).
# Add or reorder formats here to match your filenames.
DATETIME_FORMATS = [
    "%Y%m%d%H%M%S",        # 20240315143022
    "%Y%m%d_%H%M%S",       # 20240315_143022
    "%Y-%m-%dT%H-%M-%S",   # 2024-03-15T14-30-22
    "%Y-%m-%d_%H-%M-%S",   # 2024-03-15_14-30-22
    "%Y-%m-%dT%H:%M:%S",   # 2024-03-15T14:30:22
    "%Y%m%d",              # 20240315  (date only → midnight UTC)
    "%Y-%m-%d",            # 2024-03-15
]


def parse_epoch_from_filename(filepath: Path) -> int:
    """Parse the file stem as a datetime string and return a UTC Unix epoch."""
    from datetime import datetime

    stem = filepath.stem
    for fmt in DATETIME_FORMATS:
        try:
            dt = datetime.strptime(stem, fmt)
            # Treat naive datetimes as UTC
            return int(dt.replace(tzinfo=timezone.utc).timestamp())
        except ValueError:
            continue

    print(f"Error: Cannot parse '{stem}' as a datetime using any known format.")
    print(f"  Tried: {DATETIME_FORMATS}")
    sys.exit(1)


def get_csv_headers(filepath: Path) -> list[str]:
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        return next(reader, None) or []


def consolidate_csvs(source_dir: str = "csv", output_file: str = "consolidated/consolidated.csv"):
    source_path = Path(source_dir)
    output_path = Path(output_file)

    if not source_path.is_dir():
        print(f"Error: Source directory '{source_dir}' does not exist.")
        sys.exit(1)

    csv_files = sorted(source_path.glob("*.csv"))
    if not csv_files:
        print(f"No CSV files found in '{source_dir}'.")
        sys.exit(0)

    print(f"Found {len(csv_files)} CSV file(s): {[f.name for f in csv_files]}")

    # Parse epoch from every filename up front — fail fast if any are unparseable
    file_epochs: dict[Path, int] = {}
    print("\nParsing epochs from filenames...")
    for csv_file in csv_files:
        epoch = parse_epoch_from_filename(csv_file)
        file_epochs[csv_file] = epoch
        print(f"  {csv_file.name}  →  source_epoch={epoch}")

    # Determine expected headers (source files do NOT yet have source_epoch)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists() and output_path.stat().st_size > 0:
        expected_headers = get_csv_headers(output_path)
        print(f"\nExisting consolidated file detected with headers: {expected_headers}")
        # Strip source_epoch from expected headers when comparing to source files
        expected_source_headers = [h for h in expected_headers if h != "source_epoch"]
    else:
        # Bootstrap from first source file; consolidated will gain source_epoch
        base_headers = get_csv_headers(csv_files[0])
        expected_headers = base_headers + ["source_epoch"]
        expected_source_headers = base_headers
        print(f"\nNo existing consolidated file. "
              f"Headers will be: {expected_headers}")

    if not expected_source_headers:
        print("Error: Could not determine headers.")
        sys.exit(1)

    # Validate all source files before writing anything
    print("\nValidating column headers...")
    for csv_file in csv_files:
        file_headers = get_csv_headers(csv_file)
        if file_headers != expected_source_headers:
            print(f"  ✗ MISMATCH in '{csv_file.name}'")
            print(f"      Expected : {expected_source_headers}")
            print(f"      Found    : {file_headers}")
            sys.exit(1)
        print(f"  ✓ '{csv_file.name}' headers match")

    # Append to consolidated file
    file_exists = output_path.exists() and output_path.stat().st_size > 0
    rows_appended = 0

    with open(output_path, "a", newline="", encoding="utf-8") as out_f:
        writer = csv.writer(out_f)

        for csv_file in csv_files:
            epoch = file_epochs[csv_file]

            with open(csv_file, newline="", encoding="utf-8") as in_f:
                reader = csv.reader(in_f)
                next(reader)  # skip header row

                if not file_exists:
                    writer.writerow(expected_headers)
                    file_exists = True

                file_rows = 0
                for row in reader:
                    writer.writerow([epoch] + row)
                    file_rows += 1
                    rows_appended += 1

            print(f"\n  Appended {file_rows} row(s) from '{csv_file.name}' (source_epoch={epoch})")

    print(f"\n✓ Done. {rows_appended} total row(s) appended to '{output_path}'.")


if __name__ == "__main__":
    consolidate_csvs()

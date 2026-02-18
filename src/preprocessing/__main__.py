"""
CLI entry point for the SEC preprocessing pipeline.

Usage:
    python -m src.preprocessing <file_path> [form_type]

Example:
    python -m src.preprocessing data/raw/AAPL_10K_2025.html
    python -m src.preprocessing data/raw/AFL_10Q_2024.html 10-Q
"""

import logging
import sys

from .pipeline import process_filing

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

print("SEC Preprocessing Pipeline")
print("=" * 50)
print("\nFlow: Parse → Extract → Clean → Segment")
print("\nMetadata preserved throughout:")
print("  - sic_code, sic_name")
print("  - cik, ticker, company_name")
print("  - form_type")

if len(sys.argv) > 1:
    file_path = sys.argv[1]
    form_type = sys.argv[2] if len(sys.argv) > 2 else "10-K"

    result = process_filing(file_path, form_type=form_type)

    if result:
        print(f"\n{'=' * 50}")
        print(f"Company: {result.company_name}")
        print(f"CIK: {result.cik}")
        print(f"SIC Code: {result.sic_code}")
        print(f"SIC Name: {result.sic_name}")
        print(f"Form Type: {result.form_type}")
        print(f"Total Segments: {len(result)}")
        print(f"\nFirst 3 segments:")
        for seg in result.segments[:3]:
            preview = seg.text[:150].replace('\n', ' ')
            print(f"  [{seg.index}] {preview}...")
    else:
        print("Failed to process filing")
else:
    print("\nUsage: python -m src.preprocessing <file_path> [form_type]")
    print("Example: python -m src.preprocessing data/raw/AFL_10K_2025.html")

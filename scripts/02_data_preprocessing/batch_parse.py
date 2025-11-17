"""
Batch parse all SEC filings in data/raw/ directory and save as JSON files

Usage:
    python scripts/batch_parse.py
    python scripts/batch_parse.py --form-type 10-Q
    python scripts/batch_parse.py --overwrite
"""

import argparse
from pathlib import Path
from src.preprocessing.parser import SECFilingParser
from src.config import settings


def batch_parse_filings(
    input_dir: Path = None,
    form_type: str = "10-K",
    pattern: str = "*.html",
    overwrite: bool = False
):
    """
    Parse all HTML filings in a directory and save as JSON files

    Args:
        input_dir: Directory containing HTML files (defaults to settings.paths.raw_data_dir)
        form_type: Type of SEC form (10-K or 10-Q)
        pattern: File pattern to match (default: *.html)
        overwrite: Whether to overwrite existing JSON files
    """
    # Use default if not provided
    if input_dir is None:
        input_dir = settings.paths.raw_data_dir

    # Ensure directories exist
    settings.paths.ensure_directories()

    # Find all HTML files
    html_files = list(input_dir.glob(pattern))

    if not html_files:
        print(f"No files matching '{pattern}' found in: {input_dir}")
        return

    print(f"Found {len(html_files)} file(s) to parse")
    print(f"Output directory: {settings.paths.parsed_data_dir}")
    print("=" * 80)

    # Initialize parser
    parser = SECFilingParser()

    # Parse each file
    success_count = 0
    error_count = 0

    for idx, html_file in enumerate(html_files, 1):
        print(f"\n[{idx}/{len(html_files)}] Processing: {html_file.name}")

        try:
            # Parse and save
            filing = parser.parse_filing(
                html_file,
                form_type=form_type,
                save_output=True,
                overwrite=overwrite
            )

            # Show summary
            print(f"  [OK] Parsed {len(filing)} elements")
            print(f"  [OK] Found {filing.metadata['num_sections']} sections")

            sections = filing.get_section_names()
            if sections:
                print(f"  [OK] First section: {sections[0]}")

            success_count += 1

        except FileExistsError as e:
            print(f"  [SKIP] File already exists (use --overwrite to replace)")
            error_count += 1

        except Exception as e:
            print(f"  [ERROR] {e}")
            error_count += 1

    # Summary
    print("\n" + "=" * 80)
    print(f"Batch processing complete!")
    print(f"  Successful: {success_count}")
    print(f"  Errors/Skipped: {error_count}")
    print(f"  Total: {len(html_files)}")
    print(f"\nParsed files saved to: {PARSED_DATA_DIR}")


def main():
    parser = argparse.ArgumentParser(
        description="Batch parse SEC filings and save as JSON files"
    )
    parser.add_argument(
        '--form-type',
        type=str,
        default='10-K',
        choices=['10-K', '10-Q'],
        help='Type of SEC form (default: 10-K)'
    )
    parser.add_argument(
        '--input-dir',
        type=str,
        help=f'Input directory (default: {RAW_DATA_DIR})'
    )
    parser.add_argument(
        '--pattern',
        type=str,
        default='*.html',
        help='File pattern to match (default: *.html)'
    )
    parser.add_argument(
        '--overwrite',
        action='store_true',
        help='Overwrite existing JSON files'
    )

    args = parser.parse_args()

    input_dir = Path(args.input_dir) if args.input_dir else RAW_DATA_DIR

    batch_parse_filings(
        input_dir=input_dir,
        form_type=args.form_type,
        pattern=args.pattern,
        overwrite=args.overwrite
    )


if __name__ == "__main__":
    main()

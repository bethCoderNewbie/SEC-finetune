"""
Run complete preprocessing pipeline: Parse → Extract → Clean → Segment

Usage:
    python scripts/run_preprocessing_pipeline.py
    python scripts/run_preprocessing_pipeline.py --input data/raw/AAPL_10K.html
"""

import argparse
from pathlib import Path
from src.preprocessing.parser import SECFilingParser, ParsedFiling
from src.preprocessing.extractor import SECSectionExtractor, ExtractedSection
from src.config import RAW_DATA_DIR, PARSED_DATA_DIR, EXTRACTED_DATA_DIR, ensure_directories


def run_pipeline(input_file: Path, save_intermediates: bool = True):
    """
    Run the full preprocessing pipeline on a single filing

    Args:
        input_file: Path to input HTML file
        save_intermediates: Whether to save intermediate results
    """
    print(f"Preprocessing Pipeline for: {input_file.name}")
    print("=" * 80)

    # Step 1: Parse
    print("\n[1/4] Parsing SEC filing...")
    parser = SECFilingParser()
    filing = parser.parse_filing(
        input_file,
        form_type="10-K",
        save_output=save_intermediates
    )
    print(f"  [OK] Parsed {len(filing)} semantic elements")
    print(f"  [OK] Found {filing.metadata['num_sections']} sections")

    # Step 2: Extract
    print("\n[2/4] Extracting risk factors section...")
    extractor = SECSectionExtractor()
    risk_section = extractor.extract_risk_factors(filing)

    if risk_section:
        print(f"  [OK] Extracted '{risk_section.title}'")
        print(f"  [OK] Section length: {len(risk_section):,} characters")
        print(f"  [OK] Found {len(risk_section.subsections)} risk subsections")
        print(f"  [OK] Contains {risk_section.metadata['num_elements']} semantic elements")

        # Save extracted section if requested
        if save_intermediates:
            output_filename = input_file.stem + "_extracted_risks.json"
            output_path = EXTRACTED_DATA_DIR / output_filename
            risk_section.save_to_json(output_path, overwrite=True)
            print(f"  [OK] Saved to: {output_path}")
    else:
        print("  [WARN] Risk Factors section not found in filing")
        risk_section = None

    # Step 3: Clean (example - you would implement this)
    print("\n[3/4] Cleaning extracted text...")
    # TODO: Implement cleaning using src/preprocessing/cleaning.py
    print("  [TODO] Not implemented yet - add cleaning.py logic here")

    # Step 4: Segment (example - you would implement this)
    print("\n[4/4] Segmenting into risk factors...")
    # TODO: Implement segmentation using src/preprocessing/segmenter.py
    print("  [TODO] Not implemented yet - add segmenter.py logic here")

    print("\n" + "=" * 80)
    print("Pipeline complete!")

    return filing, risk_section


def main():
    parser = argparse.ArgumentParser(
        description="Run complete preprocessing pipeline"
    )
    parser.add_argument(
        '--input',
        type=str,
        help='Input HTML file path'
    )
    parser.add_argument(
        '--no-save',
        action='store_true',
        help='Do not save intermediate results'
    )

    args = parser.parse_args()

    ensure_directories()

    if args.input:
        input_file = Path(args.input)
    else:
        # Use first file in RAW_DATA_DIR
        html_files = list(RAW_DATA_DIR.glob("*.html"))
        if not html_files:
            print(f"No HTML files found in {RAW_DATA_DIR}")
            return
        input_file = html_files[0]
        print(f"Using first file found: {input_file.name}\n")

    run_pipeline(input_file, save_intermediates=not args.no_save)


if __name__ == "__main__":
    main()

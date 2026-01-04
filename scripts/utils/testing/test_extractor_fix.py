"""
Test the fixed extractor with Google 10-K
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.preprocessing.parser import SECFilingParser
from src.preprocessing.extractor import SECSectionExtractor
from src.config import settings

# Directory shortcuts from settings (avoids deprecated legacy constants)
RAW_DATA_DIR = settings.paths.raw_data_dir
EXTRACTED_DATA_DIR = settings.paths.extracted_data_dir

def test_fixed_extractor():
    print("=" * 80)
    print("TESTING FIXED EXTRACTOR")
    print("=" * 80)

    # Find HTML file
    html_files = list(RAW_DATA_DIR.glob("*.html"))
    if not html_files:
        print("[ERROR] No HTML files found in data/raw/")
        return

    input_file = html_files[0]
    print(f"\nInput file: {input_file.name}")

    # Parse filing
    print("\n[1/3] Parsing filing...")
    parser = SECFilingParser()
    filing = parser.parse_filing(input_file, form_type="10-K")
    print(f"  [OK] Parsed {len(filing)} elements")

    # Test extraction with FIXED extractor
    print("\n[2/3] Extracting Risk Factors (FIXED)...")
    extractor = SECSectionExtractor()
    risk_section = extractor.extract_risk_factors(filing)

    if risk_section:
        print(f"  [SUCCESS] Risk Factors extracted!")
        print(f"  - Title: {risk_section.title}")
        print(f"  - Length: {len(risk_section):,} characters")
        print(f"  - Subsections: {len(risk_section.subsections)}")
        print(f"  - Elements: {len(risk_section.elements)}")
        print(f"  - Extraction method: {risk_section.metadata.get('extraction_method', 'unknown')}")

        # Show first 500 characters
        print(f"\n  First 500 characters:")
        print(f"  {risk_section.text[:500]}...")

        # Show subsections
        if risk_section.subsections:
            print(f"\n  First 5 subsections:")
            for i, subsec in enumerate(risk_section.subsections[:5], 1):
                print(f"    {i}. {subsec[:80]}")

        # Save to file
        print("\n[3/3] Saving extracted section...")
        output_path = EXTRACTED_DATA_DIR / f"{input_file.stem}_risks_fixed.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        risk_section.save_to_json(output_path, overwrite=True)
        print(f"  [OK] Saved to: {output_path}")

        return True
    else:
        print(f"  [FAIL] Risk Factors NOT found")
        print("\n  Debugging info:")
        print(f"  - Form type: {filing.form_type.value}")
        print(f"  - Total elements: {len(filing)}")

        # Show actual TopSectionTitle texts
        import sec_parser as sp
        print("\n  Checking TopSectionTitle nodes:")
        count = 0
        for i, node in enumerate(filing.tree.nodes):
            if isinstance(node.semantic_element, sp.TopSectionTitle):
                count += 1
                if count <= 15:  # Show first 15
                    print(f"    {count}. Text: {repr(node.text[:100])}")

        return False

if __name__ == "__main__":
    success = test_fixed_extractor()

    print("\n" + "=" * 80)
    if success:
        print("RESULT: SUCCESS - Fixed extractor works!")
    else:
        print("RESULT: FAILED - Issue persists, needs more investigation")
    print("=" * 80)

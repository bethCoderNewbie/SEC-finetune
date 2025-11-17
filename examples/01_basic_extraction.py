"""
Example 1: Basic Section Extraction using sec-parser

This example demonstrates:
- Parsing a 10-K filing
- Extracting Risk Factors section
- Accessing subsections and metadata
"""

from pathlib import Path
from src.preprocessing.parser import SECFilingParser
from src.preprocessing.extractor import RiskFactorExtractor, SectionIdentifier, SECSectionExtractor
from src.config import settings


def main():
    print("="*80)
    print("Example 1: Basic Risk Factors Extraction")
    print("="*80)

    # ============================================
    # Step 1: Parse the HTML filing
    # ============================================
    print("\n[Step 1] Parsing filing...")

    # Find an HTML file in your raw data directory
    html_files = list(settings.paths.raw_data_dir.glob("*.html"))

    if not html_files:
        print(f"ERROR: No HTML files found in {settings.paths.raw_data_dir}")
        print("Please download a 10-K filing using sec-downloader:")
        print("  pip install sec-downloader")
        print("  from sec_downloader import Downloader")
        print('  dl = Downloader("YourCompany", "email@example.com")')
        print('  html = dl.get_filing_html(ticker="AAPL", form="10-K")')
        return

    filing_path = html_files[0]
    print(f"Found filing: {filing_path.name}")

    # Parse the filing
    parser = SECFilingParser()
    filing = parser.parse_filing(filing_path, form_type="10-K")

    print(f"SUCCESS: Parsed {len(filing)} semantic elements")
    print(f"SUCCESS: Found {len(filing.get_section_names())} sections")

    # ============================================
    # Step 2: Extract Risk Factors
    # ============================================
    print("\n[Step 2] Extracting Risk Factors (Item 1A)...")

    extractor = RiskFactorExtractor()
    risk_section = extractor.extract(filing)

    if risk_section is None:
        print("ERROR: Risk Factors section not found!")
        return

    print(f"SUCCESS: Extracted section: {risk_section.title}")
    print(f"Section length: {len(risk_section):,} characters")
    print(f"Subsections found: {len(risk_section.subsections)}")

    # ============================================
    # Step 3: Display subsections
    # ============================================
    print("\n[Step 3] Risk Categories:")

    categories = extractor.get_risk_categories(risk_section)
    for i, category in enumerate(categories[:10], 1):  # Show first 10
        print(f"  {i}. {category[:80]}...")

    if len(categories) > 10:
        print(f"  ... and {len(categories) - 10} more")

    # ============================================
    # Step 4: Display metadata
    # ============================================
    print("\n[Step 4] Metadata:")
    print(f"  Form type: {risk_section.metadata['form_type']}")
    print(f"  Number of elements: {risk_section.metadata['num_elements']}")
    print(f"  Element types:")
    for elem_type, count in risk_section.metadata['element_type_counts'].items():
        print(f"    - {elem_type}: {count}")

    # ============================================
    # Step 5: Extract specific element types
    # ============================================
    print("\n[Step 5] Element Analysis:")

    # Get tables
    tables = risk_section.get_tables()
    print(f"  Tables in Risk Factors: {len(tables)}")

    # Get text paragraphs
    paragraphs = risk_section.get_paragraphs()
    print(f"  Text paragraphs: {len(paragraphs)}")

    # Show first paragraph
    if paragraphs:
        print(f"\n  First paragraph preview:")
        first_para = paragraphs[0]['text'][:300]
        print(f"  {first_para}...")

    # ============================================
    # Step 6: Save extracted text
    # ============================================
    print("\n[Step 6] Saving extracted text...")

    output_file = Path("output") / "risk_factors_extracted.txt"
    output_file.parent.mkdir(exist_ok=True)

    output_file.write_text(risk_section.text, encoding='utf-8')
    print(f"SUCCESS: Saved to: {output_file}")

    print("\n" + "="*80)
    print("SUCCESS: Extraction complete!")
    print("="*80)


if __name__ == "__main__":
    main()

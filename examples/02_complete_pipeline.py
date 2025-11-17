"""
Example 2: Complete Extraction Pipeline

This example demonstrates the complete workflow:
1. Parse HTML filing
2. Extract Risk Factors
3. Clean the text
4. Segment into individual risks
5. Classify risk categories (optional)
"""

from pathlib import Path
from src.preprocessing.parser import SECFilingParser
from src.preprocessing.extractor import RiskFactorExtractor
from src.preprocessing.cleaning import TextCleaner
from src.preprocessing.segmenter import RiskSegmenter
from src.config import settings
import json


def main():
    print("="*80)
    print("Complete Risk Factor Extraction Pipeline")
    print("="*80)

    # ============================================
    # Step 1: Parse Filing
    # ============================================
    print("\n[Step 1] Parsing HTML filing...")

    html_files = list(settings.paths.raw_data_dir.glob("*.html"))
    if not html_files:
        print("ERROR: No HTML files found")
        print(f"Please place HTML filings in: {settings.paths.raw_data_dir}")
        return

    filing_path = html_files[0]
    print(f"  File: {filing_path.name}")

    parser = SECFilingParser()
    filing = parser.parse_filing(filing_path, form_type="10-K")
    print(f"  Parsed: {len(filing)} elements")

    # ============================================
    # Step 2: Extract Risk Factors Section
    # ============================================
    print("\n[Step 2] Extracting Risk Factors section...")

    extractor = RiskFactorExtractor()
    risk_section = extractor.extract(filing)

    if not risk_section:
        print("ERROR: Risk Factors section not found")
        return

    print(f"  Section: {risk_section.title}")
    print(f"  Length: {len(risk_section):,} characters")
    print(f"  Subsections: {len(risk_section.subsections)}")

    # ============================================
    # Step 3: Clean the Extracted Text
    # ============================================
    print("\n[Step 3] Cleaning extracted text...")

    cleaner = TextCleaner()
    clean_text = cleaner.clean_text(risk_section.text)

    print(f"  Original length: {len(risk_section.text):,} chars")
    print(f"  Cleaned length: {len(clean_text):,} chars")
    print(f"  Removed: {len(risk_section.text) - len(clean_text):,} chars")

    # ============================================
    # Step 4: Segment into Individual Risks
    # ============================================
    print("\n[Step 4] Segmenting into individual risks...")

    segmenter = RiskSegmenter()
    segments = segmenter.segment_risks(clean_text)

    print(f"  Total segments: {len(segments)}")
    print(f"  Avg segment length: {sum(len(s) for s in segments) / len(segments):.0f} chars")

    # Show segment length distribution
    lengths = [len(s) for s in segments]
    print(f"  Shortest segment: {min(lengths)} chars")
    print(f"  Longest segment: {max(lengths)} chars")

    # ============================================
    # Step 5: Display Sample Segments
    # ============================================
    print("\n[Step 5] Sample risk segments:")

    for i, segment in enumerate(segments[:3], 1):
        print(f"\n  --- Segment {i} ({len(segment)} chars) ---")
        preview = segment[:200].replace('\n', ' ')
        print(f"  {preview}...")

    # ============================================
    # Step 6: Save Results
    # ============================================
    print("\n[Step 6] Saving results...")

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    # Save raw extracted text
    raw_file = output_dir / "01_raw_risk_factors.txt"
    raw_file.write_text(risk_section.text, encoding='utf-8')
    print(f"  Saved raw text: {raw_file}")

    # Save cleaned text
    clean_file = output_dir / "02_cleaned_risk_factors.txt"
    clean_file.write_text(clean_text, encoding='utf-8')
    print(f"  Saved cleaned text: {clean_file}")

    # Save segments as JSON
    segments_data = {
        'filing': filing_path.name,
        'section': risk_section.title,
        'total_segments': len(segments),
        'segments': [
            {
                'index': i,
                'length': len(seg),
                'text': seg
            }
            for i, seg in enumerate(segments, 1)
        ]
    }

    segments_file = output_dir / "03_risk_segments.json"
    with open(segments_file, 'w', encoding='utf-8') as f:
        json.dump(segments_data, f, indent=2, ensure_ascii=False)
    print(f"  Saved segments: {segments_file}")

    # Save metadata
    metadata = {
        'filing_path': str(filing_path),
        'form_type': '10-K',
        'section_extracted': risk_section.identifier,
        'section_title': risk_section.title,
        'original_length': len(risk_section.text),
        'cleaned_length': len(clean_text),
        'num_subsections': len(risk_section.subsections),
        'subsection_titles': risk_section.subsections,
        'num_segments': len(segments),
        'num_elements': risk_section.metadata['num_elements'],
        'element_types': risk_section.metadata['element_type_counts'],
    }

    metadata_file = output_dir / "00_metadata.json"
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    print(f"  Saved metadata: {metadata_file}")

    # ============================================
    # Step 7: Summary
    # ============================================
    print("\n" + "="*80)
    print("PIPELINE SUMMARY")
    print("="*80)
    print(f"Filing parsed:        {filing_path.name}")
    print(f"Section extracted:    {risk_section.title}")
    print(f"Subsections found:    {len(risk_section.subsections)}")
    print(f"Risk segments:        {len(segments)}")
    print(f"Output directory:     {output_dir.absolute()}")
    print("="*80)
    print("SUCCESS: Pipeline complete!")
    print("="*80)


if __name__ == "__main__":
    main()

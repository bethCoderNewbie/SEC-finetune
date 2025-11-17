"""
Run complete preprocessing pipeline: Parse → Extract → Clean → Segment → Sentiment Analysis

Usage:
    python scripts/run_preprocessing_pipeline.py
    python scripts/run_preprocessing_pipeline.py --input data/raw/AAPL_10K.html
    python scripts/run_preprocessing_pipeline.py --input data/raw/AAPL_10K.html --no-sentiment
"""

import argparse
import json
from pathlib import Path
from src.preprocessing.parser import SECFilingParser, ParsedFiling
from src.preprocessing.extractor import SECSectionExtractor, ExtractedSection
from src.preprocessing.cleaning import TextCleaner
from src.preprocessing.segmenter import RiskSegmenter
from src.features.sentiment import SentimentAnalyzer
from src.config import RAW_DATA_DIR, PARSED_DATA_DIR, EXTRACTED_DATA_DIR, PROCESSED_DATA_DIR, settings, ensure_directories


def run_pipeline(input_file: Path, save_intermediates: bool = True, extract_sentiment: bool = True):
    """
    Run the full preprocessing pipeline on a single filing

    Args:
        input_file: Path to input HTML file
        save_intermediates: Whether to save intermediate results
        extract_sentiment: Whether to extract sentiment features (default: True)
    """
    print(f"Preprocessing Pipeline for: {input_file.name}")
    print("=" * 80)

    # Step 1: Parse
    print("\n[1/5] Parsing SEC filing...")
    parser = SECFilingParser()
    filing = parser.parse_filing(
        input_file,
        form_type="10-K",
        save_output=save_intermediates
    )
    print(f"  [OK] Parsed {len(filing)} semantic elements")
    print(f"  [OK] Found {filing.metadata['num_sections']} sections")

    # Step 2: Extract
    print("\n[2/5] Extracting risk factors section...")
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

    # Step 3: Clean
    print("\n[3/5] Cleaning extracted text...")
    cleaned_section = None
    if risk_section:
        # Initialize text cleaner using config settings
        cleaner = TextCleaner()

        # Clean the extracted text
        cleaned_text = cleaner.clean_text(risk_section.text, deep_clean=False)

        print(f"  [OK] Cleaned text from {len(risk_section.text):,} to {len(cleaned_text):,} characters")

        # Create a new ExtractedSection with cleaned text
        cleaned_section = ExtractedSection(
            text=cleaned_text,
            identifier=risk_section.identifier,
            title=risk_section.title,
            subsections=risk_section.subsections,
            elements=risk_section.elements,
            metadata={
                **risk_section.metadata,
                'cleaned': True,
                'cleaning_settings': {
                    'remove_html_tags': settings.preprocessing.remove_html_tags,
                    'normalize_whitespace': settings.preprocessing.normalize_whitespace,
                    'remove_page_numbers': settings.preprocessing.remove_page_numbers,
                }
            }
        )

        # Save cleaned section if requested
        if save_intermediates:
            output_filename = input_file.stem + "_cleaned_risks.json"
            output_path = EXTRACTED_DATA_DIR / output_filename
            cleaned_section.save_to_json(output_path, overwrite=True)
            print(f"  [OK] Saved cleaned section to: {output_path}")
    else:
        print("  [SKIP] No extracted section to clean")

    # Step 4: Segment
    print("\n[4/5] Segmenting into risk factors...")
    risk_segments = None
    if cleaned_section:
        # Initialize segmenter using config settings
        segmenter = RiskSegmenter(
            min_length=settings.preprocessing.min_segment_length,
            max_length=settings.preprocessing.max_segment_length
        )

        # Segment the cleaned text into individual risks
        risk_segments = segmenter.segment_risks(cleaned_section.text)

        print(f"  [OK] Segmented into {len(risk_segments)} risk factors")
        print(f"  [OK] Average segment length: {sum(len(s) for s in risk_segments) // len(risk_segments):,} characters")

        # Step 5: Sentiment Analysis
        sentiment_features_list = None
        if extract_sentiment:
            print("\n[5/5] Extracting sentiment features...")
            analyzer = SentimentAnalyzer()

            # Extract sentiment features for all segments (batch processing)
            sentiment_features_list = analyzer.extract_features_batch(risk_segments)

            print(f"  [OK] Extracted sentiment features for {len(sentiment_features_list)} segments")

            # Compute aggregate sentiment statistics
            avg_negative = sum(f.negative_ratio for f in sentiment_features_list) / len(sentiment_features_list)
            avg_uncertainty = sum(f.uncertainty_ratio for f in sentiment_features_list) / len(sentiment_features_list)
            avg_positive = sum(f.positive_ratio for f in sentiment_features_list) / len(sentiment_features_list)

            print(f"  [OK] Average sentiment ratios across all segments:")
            print(f"       Negative:    {avg_negative:.4f}")
            print(f"       Uncertainty: {avg_uncertainty:.4f}")
            print(f"       Positive:    {avg_positive:.4f}")
        else:
            print("\n[5/5] Sentiment analysis skipped (use without --no-sentiment to enable)")

        # Save segments if requested
        if save_intermediates:
            output_filename = input_file.stem + "_segmented_risks.json"
            output_path = PROCESSED_DATA_DIR / output_filename
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Create structured output
            segments_data = {
                'filing_name': input_file.name,
                'ticker': input_file.stem.split('_')[0] if '_' in input_file.stem else input_file.stem,
                'section_title': cleaned_section.title,
                'section_identifier': cleaned_section.identifier,
                'num_segments': len(risk_segments),
                'segmentation_settings': {
                    'min_segment_length': settings.preprocessing.min_segment_length,
                    'max_segment_length': settings.preprocessing.max_segment_length,
                },
                'sentiment_analysis_enabled': extract_sentiment,
            }

            # Add aggregate sentiment if available
            if sentiment_features_list:
                segments_data['aggregate_sentiment'] = {
                    'avg_negative_ratio': avg_negative,
                    'avg_uncertainty_ratio': avg_uncertainty,
                    'avg_positive_ratio': avg_positive,
                    'avg_sentiment_word_ratio': sum(f.sentiment_word_ratio for f in sentiment_features_list) / len(sentiment_features_list),
                }

            # Build segments with optional sentiment features
            segments_data['segments'] = []
            for i, segment in enumerate(risk_segments, start=1):
                segment_dict = {
                    'id': i,
                    'text': segment,
                    'length': len(segment),
                    'word_count': len(segment.split())
                }

                # Add sentiment features if available
                if sentiment_features_list:
                    sentiment = sentiment_features_list[i - 1]
                    segment_dict['sentiment'] = {
                        'negative_count': sentiment.negative_count,
                        'positive_count': sentiment.positive_count,
                        'uncertainty_count': sentiment.uncertainty_count,
                        'litigious_count': sentiment.litigious_count,
                        'constraining_count': sentiment.constraining_count,
                        'negative_ratio': sentiment.negative_ratio,
                        'positive_ratio': sentiment.positive_ratio,
                        'uncertainty_ratio': sentiment.uncertainty_ratio,
                        'litigious_ratio': sentiment.litigious_ratio,
                        'constraining_ratio': sentiment.constraining_ratio,
                        'total_sentiment_words': sentiment.total_sentiment_words,
                        'sentiment_word_ratio': sentiment.sentiment_word_ratio,
                    }

                segments_data['segments'].append(segment_dict)

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(segments_data, f, indent=2, ensure_ascii=False)

            print(f"  [OK] Saved segments to: {output_path}")
    else:
        print("  [SKIP] No cleaned section to segment")

    print("\n" + "=" * 80)
    print("Pipeline complete!")

    return filing, risk_section, cleaned_section, risk_segments, sentiment_features_list


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
    parser.add_argument(
        '--no-sentiment',
        action='store_true',
        help='Skip sentiment analysis step'
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

    run_pipeline(input_file, save_intermediates=not args.no_save, extract_sentiment=not args.no_sentiment)


if __name__ == "__main__":
    main()

"""
Example: Sentiment Analysis + Risk Classification Integration

This example demonstrates how to:
1. Load segments with sentiment features from preprocessing pipeline
2. Add risk classification to enriched segments
3. Analyze correlations between sentiment and risk categories
4. Export results for downstream analysis

Usage:
    # First, run the preprocessing pipeline:
    python scripts/02_data_preprocessing/run_preprocessing_pipeline.py

    # Then run this integration example:
    python examples/04_sentiment_risk_classification.py
"""

import sys
import json
from pathlib import Path
from typing import List, Dict
import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.analysis.inference import RiskClassifier
from src.config import PROCESSED_DATA_DIR


def load_segments_with_sentiment(filepath: Path) -> Dict:
    """
    Load segmented risks with sentiment features from JSON file.

    Args:
        filepath: Path to segmented risks JSON file

    Returns:
        Dictionary containing segments with sentiment features
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if not data.get('sentiment_analysis_enabled', False):
        print("WARNING: This file does not contain sentiment features!")
        print("Re-run preprocessing with sentiment analysis enabled.")

    return data


def add_risk_classification(segments_data: Dict, show_progress: bool = True) -> Dict:
    """
    Add risk classification to segments that already have sentiment features.

    Args:
        segments_data: Dictionary with segments and sentiment features
        show_progress: Whether to show progress

    Returns:
        Updated dictionary with risk classification added
    """
    print("\nAdding risk classification to segments...")
    classifier = RiskClassifier()

    segments = segments_data['segments']

    for i, segment in enumerate(segments):
        if show_progress and i % 5 == 0:
            print(f"  Classifying segment {i + 1}/{len(segments)}...")

        # Classify the segment text
        classification = classifier.classify_segment(segment['text'])

        # Add classification to segment
        segment['risk_classification'] = {
            'category': classification['label'],
            'confidence': classification['score'],
            'all_scores': classification['all_scores']
        }

    print(f"✓ Classified {len(segments)} segments")

    # Add metadata
    segments_data['risk_classification_enabled'] = True

    return segments_data


def analyze_sentiment_risk_correlation(segments_data: Dict) -> pd.DataFrame:
    """
    Analyze correlation between sentiment features and risk categories.

    Args:
        segments_data: Dictionary with segments, sentiment, and risk classification

    Returns:
        DataFrame with aggregated statistics by risk category
    """
    segments = segments_data['segments']

    # Convert to DataFrame for easier analysis
    rows = []
    for seg in segments:
        if 'sentiment' in seg and 'risk_classification' in seg:
            row = {
                'segment_id': seg['id'],
                'word_count': seg['word_count'],
                'risk_category': seg['risk_classification']['category'],
                'risk_confidence': seg['risk_classification']['confidence'],
                'negative_ratio': seg['sentiment']['negative_ratio'],
                'positive_ratio': seg['sentiment']['positive_ratio'],
                'uncertainty_ratio': seg['sentiment']['uncertainty_ratio'],
                'litigious_ratio': seg['sentiment']['litigious_ratio'],
                'constraining_ratio': seg['sentiment']['constraining_ratio'],
                'sentiment_word_ratio': seg['sentiment']['sentiment_word_ratio'],
            }
            rows.append(row)

    df = pd.DataFrame(rows)

    # Compute statistics by risk category
    print("\n" + "="*80)
    print("SENTIMENT BY RISK CATEGORY")
    print("="*80)

    stats = df.groupby('risk_category').agg({
        'segment_id': 'count',
        'negative_ratio': 'mean',
        'positive_ratio': 'mean',
        'uncertainty_ratio': 'mean',
        'litigious_ratio': 'mean',
        'constraining_ratio': 'mean',
        'sentiment_word_ratio': 'mean',
        'risk_confidence': 'mean',
    }).round(4)

    stats.rename(columns={'segment_id': 'count'}, inplace=True)

    print(stats.to_string())
    print("="*80)

    return df


def export_for_modeling(
    segments_data: Dict,
    output_path: Path,
    format: str = 'csv'
) -> None:
    """
    Export enriched segments for downstream modeling.

    Args:
        segments_data: Dictionary with all features
        output_path: Path to save exported data
        format: Export format ('csv', 'json', or 'parquet')
    """
    segments = segments_data['segments']

    # Build feature matrix
    rows = []
    for seg in segments:
        row = {
            'segment_id': seg['id'],
            'text': seg['text'],
            'word_count': seg['word_count'],
        }

        # Add sentiment features if available
        if 'sentiment' in seg:
            for key, value in seg['sentiment'].items():
                row[f'sentiment_{key}'] = value

        # Add risk classification if available
        if 'risk_classification' in seg:
            row['risk_category'] = seg['risk_classification']['category']
            row['risk_confidence'] = seg['risk_classification']['confidence']

        rows.append(row)

    df = pd.DataFrame(rows)

    # Export
    if format == 'csv':
        df.to_csv(output_path, index=False)
    elif format == 'json':
        df.to_json(output_path, orient='records', indent=2)
    elif format == 'parquet':
        df.to_parquet(output_path, index=False)

    print(f"\n✓ Exported {len(df)} enriched segments to: {output_path}")
    print(f"  Format: {format}")
    print(f"  Features: {len(df.columns)} columns")


def main():
    """Run the sentiment + risk classification integration example."""
    print("\n" + "="*80)
    print(" " * 20 + "SENTIMENT + RISK CLASSIFICATION EXAMPLE")
    print("="*80)

    # Find latest segmented file
    segmented_files = list(PROCESSED_DATA_DIR.glob("*_segmented_risks.json"))

    if not segmented_files:
        print("\nERROR: No segmented risk files found!")
        print("Please run the preprocessing pipeline first:")
        print("  python scripts/02_data_preprocessing/run_preprocessing_pipeline.py")
        return

    # Use most recent file
    latest_file = max(segmented_files, key=lambda p: p.stat().st_mtime)
    print(f"\nUsing file: {latest_file.name}")

    # Step 1: Load segments with sentiment
    print("\n[1/4] Loading segments with sentiment features...")
    segments_data = load_segments_with_sentiment(latest_file)
    print(f"  ✓ Loaded {segments_data['num_segments']} segments")

    if segments_data.get('sentiment_analysis_enabled'):
        print(f"  ✓ Sentiment features available")
        agg = segments_data.get('aggregate_sentiment', {})
        if agg:
            print(f"  ✓ Avg negative ratio: {agg.get('avg_negative_ratio', 0):.4f}")
            print(f"  ✓ Avg uncertainty ratio: {agg.get('avg_uncertainty_ratio', 0):.4f}")
    else:
        print("  ✗ No sentiment features found")
        return

    # Step 2: Add risk classification
    print("\n[2/4] Adding risk classification...")
    segments_data = add_risk_classification(segments_data)

    # Step 3: Analyze correlations
    print("\n[3/4] Analyzing sentiment-risk correlations...")
    df = analyze_sentiment_risk_correlation(segments_data)

    # Step 4: Export for modeling
    print("\n[4/4] Exporting enriched segments...")

    ticker = segments_data.get('ticker', 'unknown')

    # Export as CSV
    csv_output = PROCESSED_DATA_DIR / f"{ticker}_enriched_segments.csv"
    export_for_modeling(segments_data, csv_output, format='csv')

    # Also save enhanced JSON
    json_output = PROCESSED_DATA_DIR / f"{ticker}_enriched_segments.json"
    with open(json_output, 'w', encoding='utf-8') as f:
        json.dump(segments_data, f, indent=2, ensure_ascii=False)
    print(f"✓ Saved enhanced JSON to: {json_output}")

    # Summary
    print("\n" + "="*80)
    print("INTEGRATION COMPLETE!")
    print("="*80)
    print(f"Total segments processed:  {len(df)}")
    print(f"Unique risk categories:    {df['risk_category'].nunique()}")
    print(f"Average risk confidence:   {df['risk_confidence'].mean():.4f}")
    print("\nOutput files:")
    print(f"  - {csv_output}")
    print(f"  - {json_output}")
    print("\nYou can now use these enriched segments for:")
    print("  • FinBERT fine-tuning with sentiment features")
    print("  • Risk prediction models")
    print("  • Sentiment-based risk analysis")
    print("  • Feature importance studies")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()

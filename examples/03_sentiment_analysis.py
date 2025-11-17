"""
Example: Sentiment Analysis with Loughran-McDonald Dictionary

This example demonstrates how to use the SentimentAnalyzer to extract
sentiment features from financial text.

Usage:
    python examples/03_sentiment_analysis.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.features.sentiment import SentimentAnalyzer
from src.config import settings


def example_basic_sentiment():
    """Basic sentiment analysis example."""
    print("="*60)
    print("Example 1: Basic Sentiment Analysis")
    print("="*60)

    # Initialize analyzer
    analyzer = SentimentAnalyzer()

    # Example financial text
    text = """
    The company faces significant uncertainty regarding future earnings.
    Litigation risks remain elevated, and we may experience substantial losses
    if market conditions deteriorate. However, we are confident that our
    strategic initiatives will yield positive returns despite these constraints.
    """

    # Extract features
    features = analyzer.extract_features(text)

    # Display results
    print(f"\nText analyzed: {features.text_length} characters, {features.word_count} words")
    print(f"\nSentiment Category Counts:")
    print(f"  Negative:    {features.negative_count}")
    print(f"  Positive:    {features.positive_count}")
    print(f"  Uncertainty: {features.uncertainty_count}")
    print(f"  Litigious:   {features.litigious_count}")
    print(f"  Constraining: {features.constraining_count}")

    print(f"\nSentiment Ratios (per word):")
    print(f"  Negative ratio:    {features.negative_ratio:.4f}")
    print(f"  Positive ratio:    {features.positive_ratio:.4f}")
    print(f"  Uncertainty ratio: {features.uncertainty_ratio:.4f}")

    print(f"\nOverall:")
    print(f"  Total sentiment words: {features.total_sentiment_words}")
    print(f"  Sentiment word ratio:  {features.sentiment_word_ratio:.4f}")
    print()


def example_comparing_texts():
    """Compare sentiment across different texts."""
    print("="*60)
    print("Example 2: Comparing Sentiment Across Texts")
    print("="*60)

    analyzer = SentimentAnalyzer()

    texts = {
        "Positive": "The company achieved outstanding results with strong growth and profitability.",
        "Negative": "The company faces severe losses and significant challenges ahead.",
        "Uncertain": "Future outcomes remain unclear and dependent on various uncertain factors.",
    }

    print("\nComparison of different text types:\n")

    for label, text in texts.items():
        features = analyzer.extract_features(text)
        print(f"{label:12s}: Neg={features.negative_ratio:.4f}, "
              f"Pos={features.positive_ratio:.4f}, "
              f"Unc={features.uncertainty_ratio:.4f}")


def example_batch_processing():
    """Batch processing example."""
    print("\n" + "="*60)
    print("Example 3: Batch Processing")
    print("="*60)

    analyzer = SentimentAnalyzer()

    texts = [
        "The company reported substantial losses and faces litigation.",
        "Uncertainty persists regarding regulatory compliance.",
        "Strong performance demonstrates positive momentum.",
    ]

    # Batch processing
    features_list = analyzer.extract_features_batch(texts)

    print(f"\nProcessed {len(features_list)} texts:")
    for i, features in enumerate(features_list, 1):
        print(f"\nText {i}:")
        print(f"  Negative: {features.negative_count}, "
              f"Uncertain: {features.uncertainty_count}, "
              f"Positive: {features.positive_count}")


def example_save_load():
    """Example of saving and loading features."""
    print("\n" + "="*60)
    print("Example 4: Save and Load Features")
    print("="*60)

    analyzer = SentimentAnalyzer()

    text = "The company faces uncertainty and potential litigation risks."
    features = analyzer.extract_features(text)

    # Save to JSON
    output_path = Path("data/processed/features/example_sentiment.json")
    features.save_to_json(output_path)
    print(f"\n[SUCCESS] Saved features to: {output_path}")

    # Load from JSON
    loaded_features = features.__class__.load_from_json(output_path)
    print(f"[SUCCESS] Loaded features from: {output_path}")

    print(f"\nVerification:")
    print(f"  Original negative count: {features.negative_count}")
    print(f"  Loaded negative count:   {loaded_features.negative_count}")
    print(f"  Match: {features.negative_count == loaded_features.negative_count}")


def example_configuration():
    """Show current configuration."""
    print("\n" + "="*60)
    print("Example 5: Configuration")
    print("="*60)

    print(f"\nActive sentiment categories:")
    for i, cat in enumerate(settings.sentiment.active_categories, 1):
        print(f"  {i}. {cat}")

    print(f"\nText processing settings:")
    print(f"  Case sensitive: {settings.sentiment.text_processing.case_sensitive}")
    print(f"  Lemmatize: {settings.sentiment.text_processing.lemmatize}")

    print(f"\nNormalization settings:")
    print(f"  Enabled: {settings.sentiment.normalization.enabled}")
    print(f"  Method: {settings.sentiment.normalization.method}")

    print(f"\nOutput settings:")
    print(f"  Format: {settings.sentiment.output.format}")
    print(f"  Precision: {settings.sentiment.output.precision}")


def main():
    """Run all examples."""
    print("\n" + "="*70)
    print(" " * 15 + "SENTIMENT ANALYSIS EXAMPLES")
    print("="*70)

    # Run examples
    example_basic_sentiment()
    example_comparing_texts()
    example_batch_processing()
    example_save_load()
    example_configuration()

    print("\n" + "="*70)
    print(" " * 20 + "ALL EXAMPLES COMPLETED!")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()

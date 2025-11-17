"""
Feature Engineering Module

This package contains feature extraction and engineering components for SEC filings analysis.

Available features:
- Sentiment analysis using Loughran-McDonald dictionary
- (Future) TF-IDF vectors
- (Future) Named Entity Recognition features
- (Future) Readability metrics

Usage:
    from src.features.sentiment import SentimentAnalyzer

    analyzer = SentimentAnalyzer()
    features = analyzer.extract_features("The company faces uncertainty...")
"""

# Lazy imports to avoid circular dependency
# Use explicit imports: from src.features.sentiment import SentimentAnalyzer

__all__ = [
    "SentimentAnalyzer",
    "SentimentFeatures",
]


def __getattr__(name):
    """Lazy import to avoid circular dependencies."""
    if name == "SentimentAnalyzer":
        from .sentiment import SentimentAnalyzer
        return SentimentAnalyzer
    elif name == "SentimentFeatures":
        from .sentiment import SentimentFeatures
        return SentimentFeatures
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

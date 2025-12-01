"""
Feature Engineering Module

This package contains feature extraction and engineering components for SEC filings analysis.

Available features:
- Sentiment analysis using Loughran-McDonald dictionary
- Readability and text complexity analysis
- Topic modeling using LDA for risk factor analysis
- (Future) TF-IDF vectors
- (Future) Named Entity Recognition features

Usage:
    from src.features import SentimentAnalyzer, ReadabilityAnalyzer, TopicModelingAnalyzer

    # Sentiment analysis
    sentiment_analyzer = SentimentAnalyzer()
    sentiment_features = sentiment_analyzer.extract_features(text)

    # Readability analysis
    readability_analyzer = ReadabilityAnalyzer()
    readability_features = readability_analyzer.extract_features(cleaned_text)

    # Topic modeling
    topic_analyzer = TopicModelingAnalyzer(model_path="models/lda_item1a")
    topic_features = topic_analyzer.extract_features(item1a_text)
"""

# Lazy imports to avoid circular dependency
# Use explicit imports: from src.features.sentiment import SentimentAnalyzer

__all__ = [
    # Sentiment
    "SentimentAnalyzer",
    "SentimentFeatures",
    # Readability
    "ReadabilityAnalyzer",
    "ReadabilityFeatures",
    "ReadabilityAnalysisResult",
    # Topic Modeling
    "TopicModelingAnalyzer",
    "TopicModelingFeatures",
    "TopicModelingResult",
    "LDATrainer",
]


def __getattr__(name):
    """Lazy import to avoid circular dependencies."""
    # Sentiment
    if name == "SentimentAnalyzer":
        from .sentiment import SentimentAnalyzer
        return SentimentAnalyzer
    elif name == "SentimentFeatures":
        from .sentiment import SentimentFeatures
        return SentimentFeatures
    # Readability
    elif name == "ReadabilityAnalyzer":
        from .readability import ReadabilityAnalyzer
        return ReadabilityAnalyzer
    elif name == "ReadabilityFeatures":
        from .readability import ReadabilityFeatures
        return ReadabilityFeatures
    elif name == "ReadabilityAnalysisResult":
        from .readability import ReadabilityAnalysisResult
        return ReadabilityAnalysisResult
    # Topic Modeling
    elif name == "TopicModelingAnalyzer":
        from .topic_modeling import TopicModelingAnalyzer
        return TopicModelingAnalyzer
    elif name == "TopicModelingFeatures":
        from .topic_modeling import TopicModelingFeatures
        return TopicModelingFeatures
    elif name == "TopicModelingResult":
        from .topic_modeling import TopicModelingResult
        return TopicModelingResult
    elif name == "LDATrainer":
        from .topic_modeling import LDATrainer
        return LDATrainer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

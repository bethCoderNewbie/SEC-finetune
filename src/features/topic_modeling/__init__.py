"""
Topic Modeling Feature Extraction Module

This package provides LDA-based topic modeling for SEC risk factor analysis.
It discovers latent risk topics and quantifies each company's exposure to them.

Key Components:
- TopicModelingAnalyzer: Main feature extractor (inference)
- LDATrainer: Model training utilities
- TopicModelingFeatures: Pydantic model for features
- LDAModelInfo: Model metadata

Workflow:
1. Train LDA model on corpus of Item 1A sections (one-time):
    ```python
    from src.features.topic_modeling import LDATrainer

    # Prepare corpus
    documents = [...]  # List of Item 1A texts

    # Train model
    trainer = LDATrainer(num_topics=15)
    model_info = trainer.train(documents, save_path="models/lda_item1a")

    # Inspect topics
    trainer.print_topics(num_words=10)
    ```

2. Extract features from new documents:
    ```python
    from src.features.topic_modeling import TopicModelingAnalyzer

    # Load pre-trained model
    analyzer = TopicModelingAnalyzer(model_path="models/lda_item1a")

    # Extract features
    features = analyzer.extract_features(item1a_text)

    # Use as classifier features
    topic_vector = features.to_feature_vector(analyzer.num_topics)
    # Output: [0.15, 0.08, 0.22, ...]  # Probabilities for each topic
    ```

Features Produced:
- topic_probabilities: Dict[int, float] - Probability distribution over topics
- dominant_topic_id: int - Most prominent topic
- dominant_topic_probability: float - Probability of dominant topic
- topic_entropy: float - Shannon entropy (topic diversity measure)
- num_topics: int - Total number of topics in model
- num_significant_topics: int - Number of topics above threshold

Usage Example:
    ```python
    from src.features.topic_modeling import TopicModelingAnalyzer

    analyzer = TopicModelingAnalyzer(model_path="models/lda_item1a")
    features = analyzer.extract_features(risk_text)

    print(f"Dominant topic: {features.dominant_topic_id}")
    print(f"Topic diversity (entropy): {features.topic_entropy}")
    print(f"Significant topics: {features.num_significant_topics}")

    # Get feature vector for ML model
    X_topics = features.to_feature_vector(analyzer.num_topics)
    ```
"""

from .analyzer import TopicModelingAnalyzer
from .lda_trainer import LDATrainer
from .schemas import (
    TopicModelingFeatures,
    TopicModelingMetadata,
    TopicModelingResult,
    TopicDistribution,
    LDAModelInfo,
)
from .constants import (
    TOPIC_MODELING_MODULE_VERSION,
    DEFAULT_NUM_TOPICS,
    DEFAULT_PASSES,
    DEFAULT_ITERATIONS,
    COMMON_RISK_TOPICS,
    FINANCIAL_STOPWORDS,
)

__all__ = [
    # Main classes
    "TopicModelingAnalyzer",
    "LDATrainer",
    # Schemas
    "TopicModelingFeatures",
    "TopicModelingMetadata",
    "TopicModelingResult",
    "TopicDistribution",
    "LDAModelInfo",
    # Constants
    "TOPIC_MODELING_MODULE_VERSION",
    "DEFAULT_NUM_TOPICS",
    "DEFAULT_PASSES",
    "DEFAULT_ITERATIONS",
    "COMMON_RISK_TOPICS",
    "FINANCIAL_STOPWORDS",
]

__version__ = TOPIC_MODELING_MODULE_VERSION

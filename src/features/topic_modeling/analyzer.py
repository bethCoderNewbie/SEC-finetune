"""
Topic Modeling Feature Analyzer

Main interface for extracting topic modeling features from SEC risk sections.

Usage:
    from src.features.topic_modeling import TopicModelingAnalyzer

    # Load pre-trained model
    analyzer = TopicModelingAnalyzer(model_path="models/lda_item1a")

    # Extract features
    features = analyzer.extract_features(risk_text)
    print(f"Dominant topic: {features.dominant_topic_id}")
    print(f"Topic probabilities: {features.topic_probabilities}")
"""

import logging
import math
from pathlib import Path
from typing import List, Optional, Dict

from src.config import settings
from .lda_trainer import LDATrainer
from .schemas import (
    TopicModelingFeatures,
    TopicModelingMetadata,
    TopicModelingResult,
    TopicDistribution,
)
from .constants import (
    DEFAULT_MIN_PROBABILITY,
    DOMINANT_TOPIC_THRESHOLD,
)

logger = logging.getLogger(__name__)


class TopicModelingAnalyzer:
    """
    Topic Modeling Feature Extractor for SEC Risk Sections.

    This class:
    1. Loads a pre-trained LDA model
    2. Extracts topic exposure features from new documents
    3. Returns features suitable for downstream classification

    The output features quantify a company's exposure to different risk topics,
    which can be used as powerful predictive features.

    Usage:
        # Initialize with pre-trained model
        analyzer = TopicModelingAnalyzer(model_path="models/lda_item1a")

        # Extract features for a new document
        features = analyzer.extract_features(item1a_text)

        # Use as classifier features
        feature_vector = features.to_feature_vector(analyzer.num_topics)
    """

    def __init__(
        self,
        model_path: Optional[Path | str] = None,
        trainer: Optional[LDATrainer] = None,
        min_probability: float = DEFAULT_MIN_PROBABILITY,
    ):
        """
        Initialize topic modeling analyzer.

        Args:
            model_path: Path to pre-trained LDA model directory
            trainer: Optional pre-loaded LDATrainer instance
            min_probability: Minimum probability threshold for topics

        Raises:
            ValueError: If neither model_path nor trainer is provided
            FileNotFoundError: If model_path doesn't exist
        """
        self.min_probability = min_probability

        # Load model
        if trainer is not None:
            self.trainer = trainer
            logger.info("Initialized with provided LDATrainer instance")
        elif model_path is not None:
            model_path = Path(model_path)
            if not model_path.exists():
                raise FileNotFoundError(f"Model path not found: {model_path}")
            self.trainer = LDATrainer.load(model_path)
            logger.info(f"Loaded LDA model from {model_path}")
        else:
            # Try to load from default path
            try:
                default_path = settings.paths.models_dir / "lda_item1a"
                if default_path.exists():
                    self.trainer = LDATrainer.load(default_path)
                    logger.info(f"Loaded default model from {default_path}")
                else:
                    raise ValueError(
                        "No model provided. Either:\n"
                        "1. Provide model_path parameter\n"
                        "2. Provide trainer parameter\n"
                        "3. Ensure default model exists at models/lda_item1a"
                    )
            except Exception as e:
                raise ValueError(
                    f"Failed to load model: {e}\n"
                    "Provide model_path or trainer parameter."
                )

        # Validate model is trained
        if self.trainer.lda_model is None or self.trainer.dictionary is None:
            raise ValueError("Loaded trainer has no trained model")

        self.num_topics = self.trainer.num_topics
        logger.info(
            f"Initialized TopicModelingAnalyzer with {self.num_topics} topics"
        )

    def extract_features(
        self,
        text: str,
        return_metadata: bool = False,
    ) -> TopicModelingFeatures | TopicModelingResult:
        """
        Extract topic modeling features from text.

        Args:
            text: Input text (e.g., Item 1A section)
            return_metadata: If True, return full result with metadata

        Returns:
            TopicModelingFeatures or TopicModelingResult
        """
        if not text or len(text.strip()) == 0:
            return self._empty_features()

        warnings = []

        # Get topic distribution from LDA model
        topic_dist = self.trainer.get_document_topics(
            text,
            minimum_probability=self.min_probability
        )

        if len(topic_dist) == 0:
            warnings.append("No topics found above minimum probability threshold")
            return self._empty_features()

        # Build topic probability dictionary
        topic_probabilities = {topic_id: prob for topic_id, prob in topic_dist}

        # Find dominant topic
        dominant_topic_id, dominant_topic_probability = topic_dist[0]

        # Calculate topic entropy (measure of topic diversity)
        topic_entropy = self._calculate_entropy(topic_probabilities)

        # Count significant topics
        num_significant_topics = sum(
            1 for prob in topic_probabilities.values()
            if prob >= DOMINANT_TOPIC_THRESHOLD
        )

        # Build features
        features = TopicModelingFeatures(
            topic_probabilities=topic_probabilities,
            dominant_topic_id=dominant_topic_id,
            dominant_topic_probability=round(dominant_topic_probability, 4),
            topic_entropy=round(topic_entropy, 4),
            num_topics=self.num_topics,
            num_significant_topics=num_significant_topics,
        )

        if not return_metadata:
            return features

        # Build metadata
        metadata = TopicModelingMetadata(
            model_version=self.trainer.model_info.num_topics if self.trainer.model_info else "unknown",
            num_topics=self.num_topics,
            corpus_size=self.trainer.model_info.num_documents if self.trainer.model_info else 0,
            vocabulary_size=len(self.trainer.dictionary) if self.trainer.dictionary else 0,
            perplexity=self.trainer.model_info.perplexity if self.trainer.model_info else None,
            coherence_score=self.trainer.model_info.coherence_score if self.trainer.model_info else None,
            warnings=warnings,
        )

        # Build detailed topic distributions
        topic_distributions = self._build_topic_distributions(topic_probabilities)

        return TopicModelingResult(
            features=features,
            metadata=metadata,
            topic_distributions=topic_distributions,
        )

    def extract_features_batch(
        self,
        texts: List[str],
        return_metadata: bool = False,
    ) -> List[TopicModelingFeatures] | List[TopicModelingResult]:
        """
        Extract features from multiple texts.

        Args:
            texts: List of text documents
            return_metadata: If True, return results with metadata

        Returns:
            List of TopicModelingFeatures or TopicModelingResult objects
        """
        return [
            self.extract_features(text, return_metadata=return_metadata)
            for text in texts
        ]

    def get_topic_description(self, topic_id: int, num_words: int = 10) -> str:
        """
        Get human-readable description of a topic.

        Args:
            topic_id: Topic ID
            num_words: Number of top words to show

        Returns:
            String description
        """
        if self.trainer.model_info:
            return self.trainer.model_info.get_topic_description(topic_id, num_words)

        # Fallback: use LDA model directly
        if self.trainer.lda_model:
            top_words = self.trainer.lda_model.show_topic(topic_id, topn=num_words)
            words_str = ", ".join([word for word, _ in top_words])
            return f"Topic {topic_id}: {words_str}"

        return f"Topic {topic_id}"

    def print_document_topics(
        self,
        text: str,
        num_words: int = 10,
        min_probability: float = 0.05
    ) -> None:
        """
        Print human-readable topic breakdown for a document.

        Args:
            text: Input document
            num_words: Number of words to show per topic
            min_probability: Minimum probability to display
        """
        features = self.extract_features(text)

        print("\nDocument Topic Breakdown:")
        print("=" * 80)

        for topic_id, prob in sorted(
            features.topic_probabilities.items(),
            key=lambda x: x[1],
            reverse=True
        ):
            if prob < min_probability:
                break

            description = self.get_topic_description(topic_id, num_words)
            print(f"{description}")
            print(f"  Probability: {prob:.4f} ({prob*100:.2f}%)")
            print()

        print(f"Topic Entropy: {features.topic_entropy:.4f}")
        print(f"Dominant Topic: {features.dominant_topic_id} ({features.dominant_topic_probability:.4f})")
        print("=" * 80)

    # ===========================
    # Private Helper Methods
    # ===========================

    def _calculate_entropy(self, topic_probabilities: Dict[int, float]) -> float:
        """
        Calculate Shannon entropy of topic distribution.

        Entropy measures the diversity/uncertainty in the topic distribution:
        - Low entropy: Document focused on few topics
        - High entropy: Document covers many topics equally

        Args:
            topic_probabilities: Dict of topic_id -> probability

        Returns:
            Entropy value (higher = more diverse)
        """
        if not topic_probabilities:
            return 0.0

        entropy = 0.0
        for prob in topic_probabilities.values():
            if prob > 0:
                entropy -= prob * math.log2(prob)

        return entropy

    def _build_topic_distributions(
        self,
        topic_probabilities: Dict[int, float]
    ) -> List[TopicDistribution]:
        """
        Build detailed topic distribution objects.

        Args:
            topic_probabilities: Topic probabilities

        Returns:
            List of TopicDistribution objects
        """
        distributions = []

        for topic_id, prob in sorted(
            topic_probabilities.items(),
            key=lambda x: x[1],
            reverse=True
        ):
            # Get top words for this topic
            top_words = None
            if self.trainer.lda_model:
                words = self.trainer.lda_model.show_topic(topic_id, topn=10)
                top_words = [word for word, _ in words]

            distributions.append(
                TopicDistribution(
                    topic_id=topic_id,
                    probability=prob,
                    top_words=top_words,
                )
            )

        return distributions

    def _empty_features(self) -> TopicModelingFeatures:
        """Return empty features for invalid input."""
        return TopicModelingFeatures(
            topic_probabilities={},
            dominant_topic_id=None,
            dominant_topic_probability=None,
            topic_entropy=0.0,
            num_topics=self.num_topics,
            num_significant_topics=0,
        )

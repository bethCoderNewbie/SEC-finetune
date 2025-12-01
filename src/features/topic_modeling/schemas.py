"""
Topic Modeling Schemas

Pydantic models for LDA topic modeling features and results.
"""

from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field, field_validator


class TopicDistribution(BaseModel):
    """
    Topic probability distribution for a single document.

    Attributes:
        topic_id: Integer topic ID (0 to num_topics - 1)
        probability: Probability of this topic in the document (0.0 to 1.0)
        top_words: Top N most representative words for this topic
    """
    topic_id: int = Field(..., ge=0, description="Topic ID")
    probability: float = Field(..., ge=0.0, le=1.0, description="Topic probability")
    top_words: Optional[List[str]] = Field(default=None, description="Top representative words")

    @field_validator('probability')
    @classmethod
    def validate_probability(cls, v: float) -> float:
        """Ensure probability is in valid range."""
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Probability must be between 0.0 and 1.0, got {v}")
        return v


class TopicModelingFeatures(BaseModel):
    """
    Topic modeling features extracted from a document.

    These features represent the document's exposure to discovered latent topics.
    Each topic represents a distinct type of risk or theme in SEC filings.

    Usage as classifier features:
        - topic_probabilities: Vector of topic probabilities (main features)
        - dominant_topic_id: Categorical feature for most prominent topic
        - topic_entropy: Measure of topic diversity

    Attributes:
        topic_probabilities: Dict mapping topic_id -> probability
        dominant_topic_id: ID of the most prominent topic
        dominant_topic_probability: Probability of the dominant topic
        topic_entropy: Shannon entropy of topic distribution (higher = more diverse)
        num_topics: Total number of topics in the model
        num_significant_topics: Number of topics with probability > threshold
    """
    topic_probabilities: Dict[int, float] = Field(
        default_factory=dict,
        description="Topic ID -> probability mapping"
    )
    dominant_topic_id: Optional[int] = Field(
        default=None,
        description="Most prominent topic ID"
    )
    dominant_topic_probability: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Probability of dominant topic"
    )
    topic_entropy: float = Field(
        default=0.0,
        ge=0.0,
        description="Shannon entropy of topic distribution"
    )
    num_topics: int = Field(
        default=0,
        ge=0,
        description="Total number of topics in model"
    )
    num_significant_topics: int = Field(
        default=0,
        ge=0,
        description="Number of topics above significance threshold"
    )

    @field_validator('topic_probabilities')
    @classmethod
    def validate_probabilities_sum(cls, v: Dict[int, float]) -> Dict[int, float]:
        """Validate that probabilities sum to approximately 1.0."""
        if v:
            total = sum(v.values())
            if not (0.99 <= total <= 1.01):  # Allow small floating-point errors
                raise ValueError(
                    f"Topic probabilities must sum to ~1.0, got {total:.4f}"
                )
        return v

    def to_feature_vector(self, num_topics: int) -> List[float]:
        """
        Convert to dense feature vector for ML models.

        Args:
            num_topics: Number of topics in the model

        Returns:
            List of probabilities ordered by topic ID
        """
        return [
            self.topic_probabilities.get(i, 0.0)
            for i in range(num_topics)
        ]

    def get_top_k_topics(self, k: int = 5) -> List[TopicDistribution]:
        """
        Get top K most prominent topics.

        Args:
            k: Number of top topics to return

        Returns:
            List of TopicDistribution objects sorted by probability (descending)
        """
        sorted_topics = sorted(
            self.topic_probabilities.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return [
            TopicDistribution(topic_id=topic_id, probability=prob)
            for topic_id, prob in sorted_topics[:k]
        ]


class TopicModelingMetadata(BaseModel):
    """
    Metadata about topic modeling analysis.

    Attributes:
        model_version: Version of the LDA model used
        num_topics: Number of topics in the model
        corpus_size: Number of documents the model was trained on
        vocabulary_size: Size of the dictionary/vocabulary
        perplexity: Model perplexity (lower is better)
        coherence_score: Topic coherence score (higher is better)
        training_date: ISO format date when model was trained
        preprocessing_steps: List of preprocessing steps applied
        warnings: Any warnings during feature extraction
    """
    model_version: str = Field(..., description="Model version identifier")
    num_topics: int = Field(..., ge=1, description="Number of topics")
    corpus_size: int = Field(..., ge=0, description="Training corpus size")
    vocabulary_size: int = Field(..., ge=0, description="Vocabulary size")
    perplexity: Optional[float] = Field(default=None, description="Model perplexity")
    coherence_score: Optional[float] = Field(default=None, description="Coherence score")
    training_date: Optional[str] = Field(default=None, description="Training date (ISO format)")
    preprocessing_steps: List[str] = Field(
        default_factory=list,
        description="Preprocessing steps applied"
    )
    warnings: List[str] = Field(default_factory=list, description="Analysis warnings")


class TopicModelingResult(BaseModel):
    """
    Complete topic modeling analysis result with features and metadata.

    Attributes:
        features: Extracted topic modeling features
        metadata: Analysis metadata
        topic_distributions: Full topic distribution with labels
    """
    features: TopicModelingFeatures
    metadata: TopicModelingMetadata
    topic_distributions: Optional[List[TopicDistribution]] = Field(
        default=None,
        description="Detailed topic distributions"
    )


class LDAModelInfo(BaseModel):
    """
    Information about a trained LDA model.

    Attributes:
        num_topics: Number of topics
        num_documents: Number of documents in training corpus
        vocabulary_size: Size of vocabulary
        passes: Number of training passes
        iterations: Number of iterations per pass
        alpha: Document-topic density hyperparameter
        eta: Topic-word density hyperparameter
        perplexity: Model perplexity on corpus
        coherence_score: Topic coherence score
        topic_labels: Human-assigned labels for topics
        topic_top_words: Top words for each topic
    """
    num_topics: int = Field(..., ge=1)
    num_documents: int = Field(..., ge=0)
    vocabulary_size: int = Field(..., ge=0)
    passes: int = Field(..., ge=1)
    iterations: int = Field(..., ge=1)
    alpha: str | float = Field(..., description="Alpha hyperparameter")
    eta: str | float = Field(..., description="Eta hyperparameter")
    perplexity: Optional[float] = Field(default=None)
    coherence_score: Optional[float] = Field(default=None)
    topic_labels: Optional[Dict[int, str]] = Field(
        default=None,
        description="Human-readable topic labels"
    )
    topic_top_words: Optional[Dict[int, List[Tuple[str, float]]]] = Field(
        default=None,
        description="Top words for each topic with probabilities"
    )

    def get_topic_description(self, topic_id: int, num_words: int = 10) -> str:
        """
        Get human-readable description of a topic.

        Args:
            topic_id: Topic ID
            num_words: Number of top words to include

        Returns:
            String description of the topic
        """
        label = self.topic_labels.get(topic_id, f"Topic {topic_id}") if self.topic_labels else f"Topic {topic_id}"

        if self.topic_top_words and topic_id in self.topic_top_words:
            words = self.topic_top_words[topic_id][:num_words]
            word_str = ", ".join([w[0] for w in words])
            return f"{label}: {word_str}"

        return label

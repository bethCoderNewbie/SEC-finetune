"""Topic modeling configuration."""

from typing import Literal, Union

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.config._loader import load_yaml_section


def _get_config() -> dict:
    return load_yaml_section("features/topic_modeling.yaml", "topic_modeling")


class TopicModelingModelConfig(BaseSettings):
    """LDA model architecture settings."""
    model_config = SettingsConfigDict(
        env_prefix='TOPIC_MODELING_MODEL_',
        case_sensitive=False
    )

    num_topics: int = Field(
        default_factory=lambda: _get_config().get('model', {}).get('num_topics', 15)
    )
    passes: int = Field(
        default_factory=lambda: _get_config().get('model', {}).get('passes', 10)
    )
    iterations: int = Field(
        default_factory=lambda: _get_config().get('model', {}).get('iterations', 100)
    )
    random_state: int = Field(
        default_factory=lambda: _get_config().get('model', {}).get('random_state', 42)
    )
    alpha: Union[str, float] = Field(
        default_factory=lambda: _get_config().get('model', {}).get('alpha', 'auto')
    )
    eta: Union[str, float] = Field(
        default_factory=lambda: _get_config().get('model', {}).get('eta', 'auto')
    )


class TopicModelingPreprocessingConfig(BaseSettings):
    """Text preprocessing settings for topic modeling."""
    model_config = SettingsConfigDict(
        env_prefix='TOPIC_MODELING_PREP_',
        case_sensitive=False
    )

    min_word_length: int = Field(
        default_factory=lambda: _get_config().get('preprocessing', {}).get('min_word_length', 3)
    )
    max_word_length: int = Field(
        default_factory=lambda: _get_config().get('preprocessing', {}).get('max_word_length', 30)
    )
    no_below: int = Field(
        default_factory=lambda: _get_config().get('preprocessing', {}).get('no_below', 2)
    )
    no_above: float = Field(
        default_factory=lambda: _get_config().get('preprocessing', {}).get('no_above', 0.7)
    )
    keep_n: int = Field(
        default_factory=lambda: _get_config().get('preprocessing', {}).get('keep_n', 10000)
    )
    use_financial_stopwords: bool = Field(
        default_factory=lambda: _get_config().get('preprocessing', {}).get('use_financial_stopwords', True)
    )


class TopicModelingFeaturesConfig(BaseSettings):
    """Feature extraction settings for topic modeling."""
    model_config = SettingsConfigDict(
        env_prefix='TOPIC_MODELING_FEATURES_',
        case_sensitive=False
    )

    min_probability: float = Field(
        default_factory=lambda: _get_config().get('features', {}).get('min_probability', 0.01)
    )
    dominant_threshold: float = Field(
        default_factory=lambda: _get_config().get('features', {}).get('dominant_threshold', 0.25)
    )
    include_entropy: bool = Field(
        default_factory=lambda: _get_config().get('features', {}).get('include_entropy', True)
    )
    include_dominant_topic: bool = Field(
        default_factory=lambda: _get_config().get('features', {}).get('include_dominant_topic', True)
    )
    return_full_distribution: bool = Field(
        default_factory=lambda: _get_config().get('features', {}).get('return_full_distribution', True)
    )


class TopicModelingEvaluationConfig(BaseSettings):
    """Model evaluation settings."""
    model_config = SettingsConfigDict(
        env_prefix='TOPIC_MODELING_EVAL_',
        case_sensitive=False
    )

    compute_coherence: bool = Field(
        default_factory=lambda: _get_config().get('evaluation', {}).get('compute_coherence', True)
    )
    coherence_metric: str = Field(
        default_factory=lambda: _get_config().get('evaluation', {}).get('coherence_metric', 'c_v')
    )
    compute_perplexity: bool = Field(
        default_factory=lambda: _get_config().get('evaluation', {}).get('compute_perplexity', True)
    )


class TopicModelingOutputConfig(BaseSettings):
    """Output format settings for topic modeling."""
    model_config = SettingsConfigDict(
        env_prefix='TOPIC_MODELING_OUT_',
        case_sensitive=False
    )

    format: Literal["json", "csv", "parquet"] = Field(
        default_factory=lambda: _get_config().get('output', {}).get('format', 'json')
    )
    save_intermediate: bool = Field(
        default_factory=lambda: _get_config().get('output', {}).get('save_intermediate', False)
    )
    precision: int = Field(
        default_factory=lambda: _get_config().get('output', {}).get('precision', 4)
    )
    include_metadata: bool = Field(
        default_factory=lambda: _get_config().get('output', {}).get('include_metadata', True)
    )
    include_topic_words: bool = Field(
        default_factory=lambda: _get_config().get('output', {}).get('include_topic_words', True)
    )
    num_topic_words: int = Field(
        default_factory=lambda: _get_config().get('output', {}).get('num_topic_words', 10)
    )


class TopicModelingProcessingConfig(BaseSettings):
    """Processing performance settings for topic modeling."""
    model_config = SettingsConfigDict(
        env_prefix='TOPIC_MODELING_PROC_',
        case_sensitive=False
    )

    batch_size: int = Field(
        default_factory=lambda: _get_config().get('processing', {}).get('batch_size', 100)
    )
    parallel_workers: int = Field(
        default_factory=lambda: _get_config().get('processing', {}).get('parallel_workers', 4)
    )
    cache_enabled: bool = Field(
        default_factory=lambda: _get_config().get('processing', {}).get('cache_enabled', True)
    )


class TopicModelingPersistenceConfig(BaseSettings):
    """Model persistence settings."""
    model_config = SettingsConfigDict(
        env_prefix='TOPIC_MODELING_PERSIST_',
        case_sensitive=False
    )

    default_model_path: str = Field(
        default_factory=lambda: _get_config().get('persistence', {}).get('default_model_path', 'models/lda_item1a')
    )
    save_dictionary: bool = Field(
        default_factory=lambda: _get_config().get('persistence', {}).get('save_dictionary', True)
    )
    save_corpus: bool = Field(
        default_factory=lambda: _get_config().get('persistence', {}).get('save_corpus', False)
    )
    save_topic_labels: bool = Field(
        default_factory=lambda: _get_config().get('persistence', {}).get('save_topic_labels', True)
    )


class TopicModelingConfig(BaseSettings):
    """
    Topic modeling configuration.
    Loads from configs/features/topic_modeling.yaml with environment variable overrides.
    """
    model_config = SettingsConfigDict(
        env_prefix='TOPIC_MODELING_',
        env_nested_delimiter='__',
        case_sensitive=False
    )

    model: TopicModelingModelConfig = Field(
        default_factory=TopicModelingModelConfig
    )
    preprocessing: TopicModelingPreprocessingConfig = Field(
        default_factory=TopicModelingPreprocessingConfig
    )
    features: TopicModelingFeaturesConfig = Field(
        default_factory=TopicModelingFeaturesConfig
    )
    evaluation: TopicModelingEvaluationConfig = Field(
        default_factory=TopicModelingEvaluationConfig
    )
    output: TopicModelingOutputConfig = Field(
        default_factory=TopicModelingOutputConfig
    )
    processing: TopicModelingProcessingConfig = Field(
        default_factory=TopicModelingProcessingConfig
    )
    persistence: TopicModelingPersistenceConfig = Field(
        default_factory=TopicModelingPersistenceConfig
    )

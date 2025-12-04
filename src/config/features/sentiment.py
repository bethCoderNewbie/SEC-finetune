"""Sentiment analysis configuration."""

from typing import List, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.config._loader import load_yaml_section


def _get_config() -> dict:
    return load_yaml_section("features/sentiment.yaml", "sentiment")


class SentimentTextProcessingConfig(BaseSettings):
    """Text processing settings for sentiment analysis."""
    model_config = SettingsConfigDict(
        env_prefix='SENTIMENT_TEXT_',
        case_sensitive=False
    )

    case_sensitive: bool = Field(
        default_factory=lambda: _get_config().get('text_processing', {}).get('case_sensitive', False)
    )
    lemmatize: bool = Field(
        default_factory=lambda: _get_config().get('text_processing', {}).get('lemmatize', True)
    )
    remove_stopwords: bool = Field(
        default_factory=lambda: _get_config().get('text_processing', {}).get('remove_stopwords', False)
    )


class SentimentNormalizationConfig(BaseSettings):
    """Normalization settings for sentiment features."""
    model_config = SettingsConfigDict(
        env_prefix='SENTIMENT_NORM_',
        case_sensitive=False
    )

    enabled: bool = Field(
        default_factory=lambda: _get_config().get('normalization', {}).get('enabled', True)
    )
    method: Literal["count", "tfidf", "log"] = Field(
        default_factory=lambda: _get_config().get('normalization', {}).get('method', 'tfidf')
    )


class SentimentFeaturesConfig(BaseSettings):
    """Feature extraction settings."""
    model_config = SettingsConfigDict(
        env_prefix='SENTIMENT_FEATURES_',
        case_sensitive=False
    )

    include_counts: bool = Field(
        default_factory=lambda: _get_config().get('features', {}).get('include_counts', True)
    )
    include_ratios: bool = Field(
        default_factory=lambda: _get_config().get('features', {}).get('include_ratios', True)
    )
    include_tfidf: bool = Field(
        default_factory=lambda: _get_config().get('features', {}).get('include_tfidf', True)
    )
    include_proportions: bool = Field(
        default_factory=lambda: _get_config().get('features', {}).get('include_proportions', True)
    )


class SentimentProcessingConfig(BaseSettings):
    """Processing performance settings."""
    model_config = SettingsConfigDict(
        env_prefix='SENTIMENT_PROC_',
        case_sensitive=False
    )

    cache_enabled: bool = Field(
        default_factory=lambda: _get_config().get('processing', {}).get('cache_enabled', True)
    )
    use_preprocessed_dict: bool = Field(
        default_factory=lambda: _get_config().get('processing', {}).get('use_preprocessed_dict', True)
    )
    batch_size: int = Field(
        default_factory=lambda: _get_config().get('processing', {}).get('batch_size', 1000)
    )
    parallel_workers: int = Field(
        default_factory=lambda: _get_config().get('processing', {}).get('parallel_workers', 4)
    )


class SentimentOutputConfig(BaseSettings):
    """Output format settings."""
    model_config = SettingsConfigDict(
        env_prefix='SENTIMENT_OUT_',
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


class SentimentConfig(BaseSettings):
    """
    Sentiment analysis configuration.
    Loads from configs/features/sentiment.yaml with environment variable overrides.
    """
    model_config = SettingsConfigDict(
        env_prefix='SENTIMENT_',
        env_nested_delimiter='__',
        case_sensitive=False
    )

    active_categories: List[str] = Field(
        default_factory=lambda: _get_config().get(
            'active_categories',
            ["Negative", "Positive", "Uncertainty", "Litigious", "Constraining"]
        )
    )
    text_processing: SentimentTextProcessingConfig = Field(
        default_factory=SentimentTextProcessingConfig
    )
    normalization: SentimentNormalizationConfig = Field(
        default_factory=SentimentNormalizationConfig
    )
    features: SentimentFeaturesConfig = Field(
        default_factory=SentimentFeaturesConfig
    )
    processing: SentimentProcessingConfig = Field(
        default_factory=SentimentProcessingConfig
    )
    output: SentimentOutputConfig = Field(
        default_factory=SentimentOutputConfig
    )

    @field_validator('active_categories')
    @classmethod
    def validate_categories(cls, v: List[str]) -> List[str]:
        """Validate that active categories are subset of LM_FEATURE_CATEGORIES."""
        # Import here to avoid circular import
        from src.features.dictionaries.constants import LM_FEATURE_CATEGORIES

        invalid = set(v) - set(LM_FEATURE_CATEGORIES)
        if invalid:
            raise ValueError(
                f"Invalid categories: {invalid}. "
                f"Must be subset of {LM_FEATURE_CATEGORIES}"
            )
        return v

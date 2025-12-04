"""Readability analysis configuration."""

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.config._loader import load_yaml_section


def _get_config() -> dict:
    return load_yaml_section("features/readability.yaml", "readability")


class ReadabilityIndicesConfig(BaseSettings):
    """Readability indices inclusion settings."""
    model_config = SettingsConfigDict(
        env_prefix='READABILITY_INDICES_',
        case_sensitive=False
    )

    include_flesch_kincaid: bool = Field(
        default_factory=lambda: _get_config().get('indices', {}).get('include_flesch_kincaid', True)
    )
    include_gunning_fog: bool = Field(
        default_factory=lambda: _get_config().get('indices', {}).get('include_gunning_fog', True)
    )
    include_flesch_reading_ease: bool = Field(
        default_factory=lambda: _get_config().get('indices', {}).get('include_flesch_reading_ease', True)
    )
    include_smog: bool = Field(
        default_factory=lambda: _get_config().get('indices', {}).get('include_smog', True)
    )
    include_ari: bool = Field(
        default_factory=lambda: _get_config().get('indices', {}).get('include_ari', True)
    )
    include_coleman_liau: bool = Field(
        default_factory=lambda: _get_config().get('indices', {}).get('include_coleman_liau', True)
    )
    include_consensus_grade: bool = Field(
        default_factory=lambda: _get_config().get('indices', {}).get('include_consensus_grade', True)
    )
    include_obfuscation_score: bool = Field(
        default_factory=lambda: _get_config().get('indices', {}).get('include_obfuscation_score', True)
    )


class ReadabilityTextProcessingConfig(BaseSettings):
    """Text processing settings for readability analysis."""
    model_config = SettingsConfigDict(
        env_prefix='READABILITY_TEXT_',
        case_sensitive=False
    )

    preserve_case: bool = Field(
        default_factory=lambda: _get_config().get('text_processing', {}).get('preserve_case', True)
    )
    min_text_length: int = Field(
        default_factory=lambda: _get_config().get('text_processing', {}).get('min_text_length', 100)
    )
    min_word_count: int = Field(
        default_factory=lambda: _get_config().get('text_processing', {}).get('min_word_count', 30)
    )
    min_sentence_count: int = Field(
        default_factory=lambda: _get_config().get('text_processing', {}).get('min_sentence_count', 3)
    )


class ReadabilityAdjustmentsConfig(BaseSettings):
    """Financial domain adjustment settings."""
    model_config = SettingsConfigDict(
        env_prefix='READABILITY_ADJ_',
        case_sensitive=False
    )

    use_financial_adjustments: bool = Field(
        default_factory=lambda: _get_config().get('adjustments', {}).get('use_financial_adjustments', True)
    )


class ReadabilityOutputConfig(BaseSettings):
    """Output format settings for readability features."""
    model_config = SettingsConfigDict(
        env_prefix='READABILITY_OUT_',
        case_sensitive=False
    )

    format: Literal["json", "csv", "parquet"] = Field(
        default_factory=lambda: _get_config().get('output', {}).get('format', 'json')
    )
    save_intermediate: bool = Field(
        default_factory=lambda: _get_config().get('output', {}).get('save_intermediate', False)
    )
    precision: int = Field(
        default_factory=lambda: _get_config().get('output', {}).get('precision', 2)
    )
    include_metadata: bool = Field(
        default_factory=lambda: _get_config().get('output', {}).get('include_metadata', True)
    )
    include_interpretations: bool = Field(
        default_factory=lambda: _get_config().get('output', {}).get('include_interpretations', True)
    )


class ReadabilityProcessingConfig(BaseSettings):
    """Processing performance settings for readability."""
    model_config = SettingsConfigDict(
        env_prefix='READABILITY_PROC_',
        case_sensitive=False
    )

    batch_size: int = Field(
        default_factory=lambda: _get_config().get('processing', {}).get('batch_size', 1000)
    )
    parallel_workers: int = Field(
        default_factory=lambda: _get_config().get('processing', {}).get('parallel_workers', 4)
    )
    cache_enabled: bool = Field(
        default_factory=lambda: _get_config().get('processing', {}).get('cache_enabled', False)
    )


class ReadabilityConfig(BaseSettings):
    """
    Readability analysis configuration.
    Loads from configs/features/readability.yaml with environment variable overrides.
    """
    model_config = SettingsConfigDict(
        env_prefix='READABILITY_',
        env_nested_delimiter='__',
        case_sensitive=False
    )

    indices: ReadabilityIndicesConfig = Field(
        default_factory=ReadabilityIndicesConfig
    )
    text_processing: ReadabilityTextProcessingConfig = Field(
        default_factory=ReadabilityTextProcessingConfig
    )
    adjustments: ReadabilityAdjustmentsConfig = Field(
        default_factory=ReadabilityAdjustmentsConfig
    )
    output: ReadabilityOutputConfig = Field(
        default_factory=ReadabilityOutputConfig
    )
    processing: ReadabilityProcessingConfig = Field(
        default_factory=ReadabilityProcessingConfig
    )

    @property
    def precision(self) -> int:
        """Legacy accessor for output precision."""
        return self.output.precision

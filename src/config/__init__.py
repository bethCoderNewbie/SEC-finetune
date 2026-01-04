"""
SEC Filing Analyzer Configuration Package.

This module uses Pydantic Settings to:
1. Define the schema for all configuration
2. Load defaults from configs/config.yaml
3. Automatically override with environment variables from .env or CI/CD secrets

Usage:
    from src.config import settings

    # Access paths
    data_dir = settings.paths.data_dir

    # Access SEC parser settings
    form_types = settings.sec_parser.supported_form_types

    # Access model settings
    model_name = settings.models.default_model
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Core configs
from src.config.paths import PathsConfig
from src.config.sec_parser import SecParserConfig
from src.config.models import ModelsConfig
from src.config.preprocessing import PreprocessingConfig
from src.config.extraction import ExtractionConfig
from src.config.sec_sections import SecSectionsConfig
from src.config.testing import TestingConfig, ReproducibilityConfig
from src.config.run_context import RunContext
from src.config.naming import NamingConfig
from src.config.qa_validation import (
    QAValidationConfig,
    ThresholdRegistry,
    ValidationResult,
    ThresholdDefinition,
    ValidationStatus,
    GoNoGo,
    MetricType,
    generate_validation_table,
    generate_blocking_summary,
    determine_overall_status,
)

# Feature configs
from src.config.features import (
    SentimentConfig,
    TopicModelingConfig,
    ReadabilityConfig,
    RiskAnalysisConfig,
)


class Settings(BaseSettings):
    """
    Main settings class that combines all configuration sections.

    Usage:
        from src.config import settings

        # Access any configuration
        settings.paths.data_dir
        settings.sec_parser.default_form_type
        settings.models.default_model
    """
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore'
    )

    paths: PathsConfig = Field(default_factory=PathsConfig)
    sec_parser: SecParserConfig = Field(default_factory=SecParserConfig)
    models: ModelsConfig = Field(default_factory=ModelsConfig)
    preprocessing: PreprocessingConfig = Field(default_factory=PreprocessingConfig)
    extraction: ExtractionConfig = Field(default_factory=ExtractionConfig)
    sec_sections: SecSectionsConfig = Field(default_factory=SecSectionsConfig)
    testing: TestingConfig = Field(default_factory=TestingConfig)
    reproducibility: ReproducibilityConfig = Field(default_factory=ReproducibilityConfig)
    sentiment: SentimentConfig = Field(default_factory=SentimentConfig)
    readability: ReadabilityConfig = Field(default_factory=ReadabilityConfig)
    topic_modeling: TopicModelingConfig = Field(default_factory=TopicModelingConfig)
    risk_analysis: RiskAnalysisConfig = Field(default_factory=RiskAnalysisConfig)
    naming: NamingConfig = Field(default_factory=NamingConfig)
    qa_validation: QAValidationConfig = Field(default_factory=QAValidationConfig)


# ===========================
# Global Settings Instance
# ===========================

settings = Settings()


# ===========================
# Utility Functions
# ===========================

ensure_directories = settings.paths.ensure_directories


# ===========================
# Public API
# ===========================

__all__ = [
    # Main settings
    "settings",
    "Settings",
    # Utility
    "ensure_directories",
    "RunContext",
    # Core configs (for direct access if needed)
    "PathsConfig",
    "SecParserConfig",
    "ModelsConfig",
    "PreprocessingConfig",
    "ExtractionConfig",
    "SecSectionsConfig",
    "TestingConfig",
    "ReproducibilityConfig",
    # Feature configs
    "SentimentConfig",
    "TopicModelingConfig",
    "ReadabilityConfig",
    "RiskAnalysisConfig",
    # Naming config
    "NamingConfig",
    # QA Validation
    "QAValidationConfig",
    "ThresholdRegistry",
    "ValidationResult",
    "ThresholdDefinition",
    "ValidationStatus",
    "GoNoGo",
    "MetricType",
    "generate_validation_table",
    "generate_blocking_summary",
    "determine_overall_status",
]


# ===========================
# Legacy Exports (with deprecation warnings)
# ===========================
# Import legacy module to enable deprecated constant access
# This allows: from src.config import DATA_DIR (with warning)
from src.config import legacy as _legacy  # noqa: E402, F401

# Re-export legacy names for backward compatibility
def __getattr__(name: str):
    """Handle deprecated attribute access."""
    return getattr(_legacy, name)

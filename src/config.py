"""
Configuration management for SEC Filing Analyzer

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

from pathlib import Path
from typing import Dict, List, Literal
import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ===========================
# Helper: Load YAML defaults
# ===========================

def load_yaml_config() -> dict:
    """Load default configuration from YAML file"""
    config_path = Path(__file__).parent.parent / "configs" / "config.yaml"
    if config_path.exists():
        with open(config_path, 'r') as f:
            return yaml.safe_load(f) or {}
    return {}


# Load YAML config once
_yaml_config = load_yaml_config()


# ===========================
# Path Configuration
# ===========================

class PathsConfig(BaseSettings):
    """
    Project path configuration
    All paths are computed from PROJECT_ROOT
    """
    model_config = SettingsConfigDict(
        env_prefix='PATHS_',
        case_sensitive=False
    )

    # Project root directory (computed)
    project_root: Path = Field(default_factory=lambda: Path(__file__).parent.parent)

    @property
    def data_dir(self) -> Path:
        return self.project_root / "data"

    @property
    def raw_data_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def interim_data_dir(self) -> Path:
        return self.data_dir / "interim"

    @property
    def parsed_data_dir(self) -> Path:
        """Parsed SEC filings (JSON format)"""
        return self.interim_data_dir / "parsed"

    @property
    def extracted_data_dir(self) -> Path:
        """Extracted sections (JSON format)"""
        return self.interim_data_dir / "extracted"

    @property
    def processed_data_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def models_dir(self) -> Path:
        return self.project_root / "models"

    @property
    def src_dir(self) -> Path:
        return self.project_root / "src"

    @property
    def analysis_dir(self) -> Path:
        return self.src_dir / "analysis"

    @property
    def taxonomies_dir(self) -> Path:
        return self.analysis_dir / "taxonomies"

    @property
    def logs_dir(self) -> Path:
        return self.project_root / "logs"

    @property
    def extraction_logs_dir(self) -> Path:
        return self.logs_dir / "extractions"

    @property
    def risk_taxonomy_path(self) -> Path:
        return self.taxonomies_dir / "risk_taxonomy.yaml"

    @property
    def golden_dataset_path(self) -> Path:
        return self.project_root / "tests" / "fixtures" / "golden_extractions.json"

    @property
    def dictionary_dir(self) -> Path:
        """Directory containing dictionary resources"""
        return self.data_dir / "dictionary"

    @property
    def features_data_dir(self) -> Path:
        """Directory for computed features"""
        return self.processed_data_dir / "features"

    @property
    def lm_dictionary_csv(self) -> Path:
        """Path to LM dictionary source CSV"""
        from src.features.dictionaries.constants import LM_SOURCE_CSV_FILENAME
        return self.dictionary_dir / LM_SOURCE_CSV_FILENAME

    @property
    def lm_dictionary_cache(self) -> Path:
        """Path to preprocessed LM dictionary cache"""
        from src.features.dictionaries.constants import LM_CACHE_FILENAME
        return self.dictionary_dir / LM_CACHE_FILENAME

    def ensure_directories(self):
        """Create necessary directories if they don't exist"""
        directories = [
            self.raw_data_dir,
            self.interim_data_dir,
            self.parsed_data_dir,
            self.extracted_data_dir,
            self.processed_data_dir,
            self.models_dir,
            self.logs_dir,
            self.extraction_logs_dir,
            self.dictionary_dir,
            self.features_data_dir,
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)


# ===========================
# SEC Parser Configuration
# ===========================

class SecParserConfig(BaseSettings):
    """SEC Parser configuration settings"""
    model_config = SettingsConfigDict(
        env_prefix='SEC_PARSER_',
        case_sensitive=False
    )

    supported_form_types: List[str] = Field(
        default_factory=lambda: _yaml_config.get('sec_parser', {}).get('supported_form_types', ["10-K", "10-Q"])
    )
    default_form_type: str = Field(
        default_factory=lambda: _yaml_config.get('sec_parser', {}).get('default_form_type', "10-K")
    )
    input_file_extensions: List[str] = Field(
        default_factory=lambda: _yaml_config.get('sec_parser', {}).get('input_file_extensions', ["html"])
    )
    parse_tables: bool = Field(
        default_factory=lambda: _yaml_config.get('sec_parser', {}).get('parse_tables', True)
    )
    parse_images: bool = Field(
        default_factory=lambda: _yaml_config.get('sec_parser', {}).get('parse_images', False)
    )
    version: str = Field(
        default_factory=lambda: _yaml_config.get('sec_parser', {}).get('version', "0.54.0")
    )


# ===========================
# Model Configuration
# ===========================

class ModelsConfig(BaseSettings):
    """ML model configuration settings"""
    model_config = SettingsConfigDict(
        env_prefix='MODELS_',
        case_sensitive=False
    )

    default_model: str = Field(
        default_factory=lambda: _yaml_config.get('models', {}).get('default_model', "ProsusAI/finbert")
    )
    zero_shot_model: str = Field(
        default_factory=lambda: _yaml_config.get('models', {}).get('zero_shot_model', "facebook/bart-large-mnli")
    )


# ===========================
# Preprocessing Configuration
# ===========================

class PreprocessingConfig(BaseSettings):
    """Text preprocessing configuration settings"""
    model_config = SettingsConfigDict(
        env_prefix='PREPROCESSING_',
        case_sensitive=False
    )

    min_segment_length: int = Field(
        default_factory=lambda: _yaml_config.get('preprocessing', {}).get('min_segment_length', 50)
    )
    max_segment_length: int = Field(
        default_factory=lambda: _yaml_config.get('preprocessing', {}).get('max_segment_length', 2000)
    )
    remove_html_tags: bool = Field(
        default_factory=lambda: _yaml_config.get('preprocessing', {}).get('remove_html_tags', True)
    )
    normalize_whitespace: bool = Field(
        default_factory=lambda: _yaml_config.get('preprocessing', {}).get('normalize_whitespace', True)
    )
    remove_page_numbers: bool = Field(
        default_factory=lambda: _yaml_config.get('preprocessing', {}).get('remove_page_numbers', True)
    )


# ===========================
# Extraction Configuration
# ===========================

class ExtractionConfig(BaseSettings):
    """Section extraction configuration settings"""
    model_config = SettingsConfigDict(
        env_prefix='EXTRACTION_',
        case_sensitive=False
    )

    min_confidence: float = Field(
        default_factory=lambda: _yaml_config.get('extraction', {}).get('min_confidence', 0.7)
    )
    enable_audit_logging: bool = Field(
        default_factory=lambda: _yaml_config.get('extraction', {}).get('enable_audit_logging', True)
    )
    output_format: Literal["json", "parquet", "both"] = Field(
        default_factory=lambda: _yaml_config.get('extraction', {}).get('output_format', "json")
    )
    default_sections: List[str] = Field(
        default_factory=lambda: _yaml_config.get('extraction', {}).get('default_sections', ["part1item1a"])
    )


# ===========================
# SEC Sections Configuration
# ===========================

class SecSectionsConfig(BaseSettings):
    """SEC section identifiers for different form types"""
    model_config = SettingsConfigDict(
        env_prefix='SEC_SECTIONS_',
        case_sensitive=False
    )

    sections_10k: Dict[str, str] = Field(
        default_factory=lambda: _yaml_config.get('sec_sections', {}).get('10-K', {
            "part1item1": "Item 1. Business",
            "part1item1a": "Item 1A. Risk Factors",
            "part1item1b": "Item 1B. Unresolved Staff Comments",
            "part1item1c": "Item 1C. Cybersecurity",
            "part2item7": "Item 7. Management's Discussion and Analysis",
            "part2item7a": "Item 7A. Quantitative and Qualitative Disclosures About Market Risk",
            "part2item8": "Item 8. Financial Statements and Supplementary Data",
        })
    )
    sections_10q: Dict[str, str] = Field(
        default_factory=lambda: _yaml_config.get('sec_sections', {}).get('10-Q', {
            "part1item1": "Item 1. Financial Statements",
            "part1item2": "Item 2. Management's Discussion and Analysis",
            "part2item1a": "Item 1A. Risk Factors",
        })
    )

    @property
    def SEC_10K_SECTIONS(self) -> Dict[str, str]:
        """Legacy property name for backward compatibility"""
        return self.sections_10k

    @property
    def SEC_10Q_SECTIONS(self) -> Dict[str, str]:
        """Legacy property name for backward compatibility"""
        return self.sections_10q


# ===========================
# Testing Configuration
# ===========================

class TestingConfig(BaseSettings):
    """Testing and validation configuration settings"""
    model_config = SettingsConfigDict(
        env_prefix='TESTING_',
        case_sensitive=False
    )

    enable_golden_validation: bool = Field(
        default_factory=lambda: _yaml_config.get('testing', {}).get('enable_golden_validation', False)
    )


# ===========================
# Reproducibility Configuration
# ===========================

class ReproducibilityConfig(BaseSettings):
    """Reproducibility configuration settings"""
    model_config = SettingsConfigDict(
        env_prefix='REPRODUCIBILITY_',
        case_sensitive=False
    )

    random_seed: int = Field(
        default_factory=lambda: _yaml_config.get('reproducibility', {}).get('random_seed', 42)
    )


# ===========================
# Sentiment Features Configuration
# ===========================

def load_sentiment_yaml_config() -> dict:
    """Load sentiment configuration from YAML file"""
    config_path = Path(__file__).parent.parent / "configs" / "features" / "sentiment.yaml"
    if config_path.exists():
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f)
            return data.get('sentiment', {}) if data else {}
    return {}


# Load sentiment YAML config once
_sentiment_yaml_config = load_sentiment_yaml_config()


class SentimentTextProcessingConfig(BaseSettings):
    """Text processing settings for sentiment analysis"""
    model_config = SettingsConfigDict(
        env_prefix='SENTIMENT_TEXT_',
        case_sensitive=False
    )

    case_sensitive: bool = Field(
        default_factory=lambda: _sentiment_yaml_config.get('text_processing', {}).get('case_sensitive', False)
    )
    lemmatize: bool = Field(
        default_factory=lambda: _sentiment_yaml_config.get('text_processing', {}).get('lemmatize', True)
    )
    remove_stopwords: bool = Field(
        default_factory=lambda: _sentiment_yaml_config.get('text_processing', {}).get('remove_stopwords', False)
    )


class SentimentNormalizationConfig(BaseSettings):
    """Normalization settings for sentiment features"""
    model_config = SettingsConfigDict(
        env_prefix='SENTIMENT_NORM_',
        case_sensitive=False
    )

    enabled: bool = Field(
        default_factory=lambda: _sentiment_yaml_config.get('normalization', {}).get('enabled', True)
    )
    method: Literal["count", "tfidf", "log"] = Field(
        default_factory=lambda: _sentiment_yaml_config.get('normalization', {}).get('method', 'tfidf')
    )


class SentimentFeaturesConfig(BaseSettings):
    """Feature extraction settings"""
    model_config = SettingsConfigDict(
        env_prefix='SENTIMENT_FEATURES_',
        case_sensitive=False
    )

    include_counts: bool = Field(
        default_factory=lambda: _sentiment_yaml_config.get('features', {}).get('include_counts', True)
    )
    include_ratios: bool = Field(
        default_factory=lambda: _sentiment_yaml_config.get('features', {}).get('include_ratios', True)
    )
    include_tfidf: bool = Field(
        default_factory=lambda: _sentiment_yaml_config.get('features', {}).get('include_tfidf', True)
    )
    include_proportions: bool = Field(
        default_factory=lambda: _sentiment_yaml_config.get('features', {}).get('include_proportions', True)
    )


class SentimentProcessingConfig(BaseSettings):
    """Processing performance settings"""
    model_config = SettingsConfigDict(
        env_prefix='SENTIMENT_PROC_',
        case_sensitive=False
    )

    cache_enabled: bool = Field(
        default_factory=lambda: _sentiment_yaml_config.get('processing', {}).get('cache_enabled', True)
    )
    use_preprocessed_dict: bool = Field(
        default_factory=lambda: _sentiment_yaml_config.get('processing', {}).get('use_preprocessed_dict', True)
    )
    batch_size: int = Field(
        default_factory=lambda: _sentiment_yaml_config.get('processing', {}).get('batch_size', 1000)
    )
    parallel_workers: int = Field(
        default_factory=lambda: _sentiment_yaml_config.get('processing', {}).get('parallel_workers', 4)
    )


class SentimentOutputConfig(BaseSettings):
    """Output format settings"""
    model_config = SettingsConfigDict(
        env_prefix='SENTIMENT_OUT_',
        case_sensitive=False
    )

    format: Literal["json", "csv", "parquet"] = Field(
        default_factory=lambda: _sentiment_yaml_config.get('output', {}).get('format', 'json')
    )
    save_intermediate: bool = Field(
        default_factory=lambda: _sentiment_yaml_config.get('output', {}).get('save_intermediate', False)
    )
    precision: int = Field(
        default_factory=lambda: _sentiment_yaml_config.get('output', {}).get('precision', 4)
    )


class SentimentConfig(BaseSettings):
    """
    Sentiment analysis configuration
    Loads from configs/features/sentiment.yaml with environment variable overrides
    """
    model_config = SettingsConfigDict(
        env_prefix='SENTIMENT_',
        env_nested_delimiter='__',
        case_sensitive=False
    )

    active_categories: List[str] = Field(
        default_factory=lambda: _sentiment_yaml_config.get(
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
        """Validate that active categories are subset of LM_FEATURE_CATEGORIES"""
        from src.features.dictionaries.constants import LM_FEATURE_CATEGORIES

        invalid = set(v) - set(LM_FEATURE_CATEGORIES)
        if invalid:
            raise ValueError(
                f"Invalid categories: {invalid}. "
                f"Must be subset of {LM_FEATURE_CATEGORIES}"
            )
        return v


# ===========================
# Main Settings Class
# ===========================

class Settings(BaseSettings):
    """
    Main settings class that combines all configuration sections

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


# ===========================
# Global Settings Instance
# ===========================

settings = Settings()


# ===========================
# Legacy Exports (for easier migration)
# ===========================
# These allow existing code to continue using simple imports
# Example: from src.config import RAW_DATA_DIR

# Paths
PROJECT_ROOT = settings.paths.project_root
DATA_DIR = settings.paths.data_dir
RAW_DATA_DIR = settings.paths.raw_data_dir
INTERIM_DATA_DIR = settings.paths.interim_data_dir
PARSED_DATA_DIR = settings.paths.parsed_data_dir
EXTRACTED_DATA_DIR = settings.paths.extracted_data_dir
PROCESSED_DATA_DIR = settings.paths.processed_data_dir
MODELS_DIR = settings.paths.models_dir
SRC_DIR = settings.paths.src_dir
ANALYSIS_DIR = settings.paths.analysis_dir
TAXONOMIES_DIR = settings.paths.taxonomies_dir
LOGS_DIR = settings.paths.logs_dir
EXTRACTION_LOGS_DIR = settings.paths.extraction_logs_dir
RISK_TAXONOMY_PATH = settings.paths.risk_taxonomy_path
GOLDEN_DATASET_PATH = settings.paths.golden_dataset_path

# SEC Parser
SUPPORTED_FORM_TYPES = settings.sec_parser.supported_form_types
DEFAULT_FORM_TYPE = settings.sec_parser.default_form_type
INPUT_FILE_EXTENSIONS = settings.sec_parser.input_file_extensions
PARSE_TABLES = settings.sec_parser.parse_tables
PARSE_IMAGES = settings.sec_parser.parse_images
SEC_PARSER_VERSION = settings.sec_parser.version

# Models
DEFAULT_MODEL = settings.models.default_model
ZERO_SHOT_MODEL = settings.models.zero_shot_model

# Preprocessing
MIN_SEGMENT_LENGTH = settings.preprocessing.min_segment_length
MAX_SEGMENT_LENGTH = settings.preprocessing.max_segment_length
REMOVE_HTML_TAGS = settings.preprocessing.remove_html_tags
NORMALIZE_WHITESPACE = settings.preprocessing.normalize_whitespace
REMOVE_PAGE_NUMBERS = settings.preprocessing.remove_page_numbers

# Extraction
MIN_EXTRACTION_CONFIDENCE = settings.extraction.min_confidence
ENABLE_AUDIT_LOGGING = settings.extraction.enable_audit_logging
EXTRACTION_OUTPUT_FORMAT = settings.extraction.output_format
DEFAULT_SECTIONS_TO_EXTRACT = settings.extraction.default_sections

# SEC Sections
SEC_10K_SECTIONS = settings.sec_sections.sections_10k
SEC_10Q_SECTIONS = settings.sec_sections.sections_10q

# Testing
ENABLE_GOLDEN_VALIDATION = settings.testing.enable_golden_validation

# Reproducibility
RANDOM_SEED = settings.reproducibility.random_seed

# Utility function
ensure_directories = settings.paths.ensure_directories


# ===========================
# CLI Support
# ===========================

if __name__ == "__main__":
    """
    Run this module to:
    1. Create necessary directories
    2. Display current configuration
    """
    ensure_directories()
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Data directory: {DATA_DIR}")
    print(f"Risk taxonomy: {RISK_TAXONOMY_PATH}")
    print(f"\nConfiguration loaded successfully!")
    print(f"SEC Parser version: {SEC_PARSER_VERSION}")
    print(f"Default model: {DEFAULT_MODEL}")
    print(f"Supported form types: {SUPPORTED_FORM_TYPES}")

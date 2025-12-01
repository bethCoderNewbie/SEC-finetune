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
from typing import Dict, List, Literal, Optional, Union
from datetime import datetime
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
    def labeled_data_dir(self) -> Path:
        return self.processed_data_dir / "labeled"

    @property
    def features_data_dir(self) -> Path:
        """Directory for computed features"""
        return self.processed_data_dir / "features"

    @property
    def models_dir(self) -> Path:
        return self.project_root / "models"

    @property
    def experiments_dir(self) -> Path:
        """Directory for training experiments"""
        return self.models_dir / "experiments"
        
    @property
    def model_registry_dir(self) -> Path:
        """Directory for production-ready models"""
        return self.models_dir / "registry"

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
            self.labeled_data_dir,
            self.features_data_dir,
            self.models_dir,
            self.experiments_dir,
            self.model_registry_dir,
            self.logs_dir,
            self.extraction_logs_dir,
            self.dictionary_dir,
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)


# ===========================
# Run Context & Versioning (Pydantic V2)
# ===========================

class RunContext(BaseSettings):
    """
    Manages versioning and output paths for data processing runs.
    Ensures all artifacts from a run are saved together.

    Pydantic V2 compliant model with computed properties.

    Usage:
        run = RunContext(name="auto_label_bart")
        run.create()
        output_path = run.output_dir  # e.g., data/processed/labeled/20231201_143022_auto_label_bart/
        run.save_config({"model": "bart-large-mnli"})
    """
    model_config = SettingsConfigDict(
        arbitrary_types_allowed=True,
        validate_default=True
    )

    name: str = Field(..., description="Name identifier for this run")
    base_dir: Optional[Path] = Field(
        default=None,
        description="Base directory for run outputs. Defaults to labeled_data_dir"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp for this run"
    )

    def model_post_init(self, __context) -> None:
        """Set default base_dir after settings are available"""
        if self.base_dir is None:
            # Use object.__setattr__ since Pydantic models are frozen by default
            object.__setattr__(self, 'base_dir', settings.paths.labeled_data_dir)

    @property
    def run_id(self) -> str:
        """Generate run ID from timestamp"""
        return self.timestamp.strftime("%Y%m%d_%H%M%S")

    @property
    def output_dir(self) -> Path:
        """Construct unique output directory path"""
        return self.base_dir / f"{self.run_id}_{self.name}"

    def create(self) -> "RunContext":
        """Create the run directory"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        return self

    def save_config(self, config: Dict) -> Path:
        """
        Save the configuration used for this run.

        Returns:
            Path to the saved config file
        """
        self.create()
        config_path = self.output_dir / "run_config.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        return config_path


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
# Topic Modeling Features Configuration
# ===========================

def load_topic_modeling_yaml_config() -> dict:
    """Load topic modeling configuration from YAML file"""
    config_path = Path(__file__).parent.parent / "configs" / "features" / "topic_modeling.yaml"
    if config_path.exists():
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f)
            return data.get('topic_modeling', {}) if data else {}
    return {}


# Load topic modeling YAML config once
_topic_modeling_yaml_config = load_topic_modeling_yaml_config()


class TopicModelingModelConfig(BaseSettings):
    """LDA model architecture settings"""
    model_config = SettingsConfigDict(
        env_prefix='TOPIC_MODELING_MODEL_',
        case_sensitive=False
    )

    num_topics: int = Field(
        default_factory=lambda: _topic_modeling_yaml_config.get('model', {}).get('num_topics', 15)
    )
    passes: int = Field(
        default_factory=lambda: _topic_modeling_yaml_config.get('model', {}).get('passes', 10)
    )
    iterations: int = Field(
        default_factory=lambda: _topic_modeling_yaml_config.get('model', {}).get('iterations', 100)
    )
    random_state: int = Field(
        default_factory=lambda: _topic_modeling_yaml_config.get('model', {}).get('random_state', 42)
    )
    alpha: str | float = Field(
        default_factory=lambda: _topic_modeling_yaml_config.get('model', {}).get('alpha', 'auto')
    )
    eta: str | float = Field(
        default_factory=lambda: _topic_modeling_yaml_config.get('model', {}).get('eta', 'auto')
    )


class TopicModelingPreprocessingConfig(BaseSettings):
    """Text preprocessing settings for topic modeling"""
    model_config = SettingsConfigDict(
        env_prefix='TOPIC_MODELING_PREP_',
        case_sensitive=False
    )

    min_word_length: int = Field(
        default_factory=lambda: _topic_modeling_yaml_config.get('preprocessing', {}).get('min_word_length', 3)
    )
    max_word_length: int = Field(
        default_factory=lambda: _topic_modeling_yaml_config.get('preprocessing', {}).get('max_word_length', 30)
    )
    no_below: int = Field(
        default_factory=lambda: _topic_modeling_yaml_config.get('preprocessing', {}).get('no_below', 2)
    )
    no_above: float = Field(
        default_factory=lambda: _topic_modeling_yaml_config.get('preprocessing', {}).get('no_above', 0.7)
    )
    keep_n: int = Field(
        default_factory=lambda: _topic_modeling_yaml_config.get('preprocessing', {}).get('keep_n', 10000)
    )
    use_financial_stopwords: bool = Field(
        default_factory=lambda: _topic_modeling_yaml_config.get('preprocessing', {}).get('use_financial_stopwords', True)
    )


class TopicModelingFeaturesConfig(BaseSettings):
    """Feature extraction settings for topic modeling"""
    model_config = SettingsConfigDict(
        env_prefix='TOPIC_MODELING_FEATURES_',
        case_sensitive=False
    )

    min_probability: float = Field(
        default_factory=lambda: _topic_modeling_yaml_config.get('features', {}).get('min_probability', 0.01)
    )
    dominant_threshold: float = Field(
        default_factory=lambda: _topic_modeling_yaml_config.get('features', {}).get('dominant_threshold', 0.25)
    )
    include_entropy: bool = Field(
        default_factory=lambda: _topic_modeling_yaml_config.get('features', {}).get('include_entropy', True)
    )
    include_dominant_topic: bool = Field(
        default_factory=lambda: _topic_modeling_yaml_config.get('features', {}).get('include_dominant_topic', True)
    )
    return_full_distribution: bool = Field(
        default_factory=lambda: _topic_modeling_yaml_config.get('features', {}).get('return_full_distribution', True)
    )


class TopicModelingEvaluationConfig(BaseSettings):
    """Model evaluation settings"""
    model_config = SettingsConfigDict(
        env_prefix='TOPIC_MODELING_EVAL_',
        case_sensitive=False
    )

    compute_coherence: bool = Field(
        default_factory=lambda: _topic_modeling_yaml_config.get('evaluation', {}).get('compute_coherence', True)
    )
    coherence_metric: str = Field(
        default_factory=lambda: _topic_modeling_yaml_config.get('evaluation', {}).get('coherence_metric', 'c_v')
    )
    compute_perplexity: bool = Field(
        default_factory=lambda: _topic_modeling_yaml_config.get('evaluation', {}).get('compute_perplexity', True)
    )


class TopicModelingOutputConfig(BaseSettings):
    """Output format settings for topic modeling"""
    model_config = SettingsConfigDict(
        env_prefix='TOPIC_MODELING_OUT_',
        case_sensitive=False
    )

    format: Literal["json", "csv", "parquet"] = Field(
        default_factory=lambda: _topic_modeling_yaml_config.get('output', {}).get('format', 'json')
    )
    save_intermediate: bool = Field(
        default_factory=lambda: _topic_modeling_yaml_config.get('output', {}).get('save_intermediate', False)
    )
    precision: int = Field(
        default_factory=lambda: _topic_modeling_yaml_config.get('output', {}).get('precision', 4)
    )
    include_metadata: bool = Field(
        default_factory=lambda: _topic_modeling_yaml_config.get('output', {}).get('include_metadata', True)
    )
    include_topic_words: bool = Field(
        default_factory=lambda: _topic_modeling_yaml_config.get('output', {}).get('include_topic_words', True)
    )
    num_topic_words: int = Field(
        default_factory=lambda: _topic_modeling_yaml_config.get('output', {}).get('num_topic_words', 10)
    )


class TopicModelingProcessingConfig(BaseSettings):
    """Processing performance settings for topic modeling"""
    model_config = SettingsConfigDict(
        env_prefix='TOPIC_MODELING_PROC_',
        case_sensitive=False
    )

    batch_size: int = Field(
        default_factory=lambda: _topic_modeling_yaml_config.get('processing', {}).get('batch_size', 100)
    )
    parallel_workers: int = Field(
        default_factory=lambda: _topic_modeling_yaml_config.get('processing', {}).get('parallel_workers', 4)
    )
    cache_enabled: bool = Field(
        default_factory=lambda: _topic_modeling_yaml_config.get('processing', {}).get('cache_enabled', True)
    )


class TopicModelingPersistenceConfig(BaseSettings):
    """Model persistence settings"""
    model_config = SettingsConfigDict(
        env_prefix='TOPIC_MODELING_PERSIST_',
        case_sensitive=False
    )

    default_model_path: str = Field(
        default_factory=lambda: _topic_modeling_yaml_config.get('persistence', {}).get('default_model_path', 'models/lda_item1a')
    )
    save_dictionary: bool = Field(
        default_factory=lambda: _topic_modeling_yaml_config.get('persistence', {}).get('save_dictionary', True)
    )
    save_corpus: bool = Field(
        default_factory=lambda: _topic_modeling_yaml_config.get('persistence', {}).get('save_corpus', False)
    )
    save_topic_labels: bool = Field(
        default_factory=lambda: _topic_modeling_yaml_config.get('persistence', {}).get('save_topic_labels', True)
    )


class TopicModelingConfig(BaseSettings):
    """
    Topic modeling configuration
    Loads from configs/features/topic_modeling.yaml with environment variable overrides
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


# ===========================
# Readability Features Configuration
# ===========================

def load_readability_yaml_config() -> dict:
    """Load readability configuration from YAML file"""
    config_path = Path(__file__).parent.parent / "configs" / "features" / "readability.yaml"
    if config_path.exists():
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f)
            return data.get('readability', {}) if data else {}
    return {}


# Load readability YAML config once
_readability_yaml_config = load_readability_yaml_config()


class ReadabilityIndicesConfig(BaseSettings):
    """Readability indices inclusion settings"""
    model_config = SettingsConfigDict(
        env_prefix='READABILITY_INDICES_',
        case_sensitive=False
    )

    include_flesch_kincaid: bool = Field(
        default_factory=lambda: _readability_yaml_config.get('indices', {}).get('include_flesch_kincaid', True)
    )
    include_gunning_fog: bool = Field(
        default_factory=lambda: _readability_yaml_config.get('indices', {}).get('include_gunning_fog', True)
    )
    include_flesch_reading_ease: bool = Field(
        default_factory=lambda: _readability_yaml_config.get('indices', {}).get('include_flesch_reading_ease', True)
    )
    include_smog: bool = Field(
        default_factory=lambda: _readability_yaml_config.get('indices', {}).get('include_smog', True)
    )
    include_ari: bool = Field(
        default_factory=lambda: _readability_yaml_config.get('indices', {}).get('include_ari', True)
    )
    include_coleman_liau: bool = Field(
        default_factory=lambda: _readability_yaml_config.get('indices', {}).get('include_coleman_liau', True)
    )
    include_consensus_grade: bool = Field(
        default_factory=lambda: _readability_yaml_config.get('indices', {}).get('include_consensus_grade', True)
    )
    include_obfuscation_score: bool = Field(
        default_factory=lambda: _readability_yaml_config.get('indices', {}).get('include_obfuscation_score', True)
    )


class ReadabilityTextProcessingConfig(BaseSettings):
    """Text processing settings for readability analysis"""
    model_config = SettingsConfigDict(
        env_prefix='READABILITY_TEXT_',
        case_sensitive=False
    )

    preserve_case: bool = Field(
        default_factory=lambda: _readability_yaml_config.get('text_processing', {}).get('preserve_case', True)
    )
    min_text_length: int = Field(
        default_factory=lambda: _readability_yaml_config.get('text_processing', {}).get('min_text_length', 100)
    )
    min_word_count: int = Field(
        default_factory=lambda: _readability_yaml_config.get('text_processing', {}).get('min_word_count', 30)
    )
    min_sentence_count: int = Field(
        default_factory=lambda: _readability_yaml_config.get('text_processing', {}).get('min_sentence_count', 3)
    )


class ReadabilityAdjustmentsConfig(BaseSettings):
    """Financial domain adjustment settings"""
    model_config = SettingsConfigDict(
        env_prefix='READABILITY_ADJ_',
        case_sensitive=False
    )

    use_financial_adjustments: bool = Field(
        default_factory=lambda: _readability_yaml_config.get('adjustments', {}).get('use_financial_adjustments', True)
    )


class ReadabilityOutputConfig(BaseSettings):
    """Output format settings for readability features"""
    model_config = SettingsConfigDict(
        env_prefix='READABILITY_OUT_',
        case_sensitive=False
    )

    format: Literal["json", "csv", "parquet"] = Field(
        default_factory=lambda: _readability_yaml_config.get('output', {}).get('format', 'json')
    )
    save_intermediate: bool = Field(
        default_factory=lambda: _readability_yaml_config.get('output', {}).get('save_intermediate', False)
    )
    precision: int = Field(
        default_factory=lambda: _readability_yaml_config.get('output', {}).get('precision', 2)
    )
    include_metadata: bool = Field(
        default_factory=lambda: _readability_yaml_config.get('output', {}).get('include_metadata', True)
    )
    include_interpretations: bool = Field(
        default_factory=lambda: _readability_yaml_config.get('output', {}).get('include_interpretations', True)
    )


class ReadabilityProcessingConfig(BaseSettings):
    """Processing performance settings for readability"""
    model_config = SettingsConfigDict(
        env_prefix='READABILITY_PROC_',
        case_sensitive=False
    )

    batch_size: int = Field(
        default_factory=lambda: _readability_yaml_config.get('processing', {}).get('batch_size', 1000)
    )
    parallel_workers: int = Field(
        default_factory=lambda: _readability_yaml_config.get('processing', {}).get('parallel_workers', 4)
    )
    cache_enabled: bool = Field(
        default_factory=lambda: _readability_yaml_config.get('processing', {}).get('cache_enabled', False)
    )


class ReadabilityConfig(BaseSettings):
    """
    Readability analysis configuration
    Loads from configs/features/readability.yaml with environment variable overrides
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
        """Legacy accessor for output precision"""
        return self.output.precision


# ===========================
# Risk Analysis Configuration
# ===========================

def load_risk_analysis_yaml_config() -> dict:
    """Load risk analysis configuration from YAML file"""
    config_path = Path(__file__).parent.parent / "configs" / "features" / "risk_analysis.yaml"
    if config_path.exists():
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f)
            return data.get('model', {}) if data else {}
    return {}

# Load risk analysis YAML config once
_risk_analysis_yaml_config = load_risk_analysis_yaml_config()

class RiskAnalysisConfig(BaseSettings):
    """
    Risk analysis configuration (Drift Detection & Auto-Labeling)
    Loads from configs/features/risk_analysis.yaml with environment variable overrides
    """
    model_config = SettingsConfigDict(
        env_prefix='RISK_ANALYSIS_',
        case_sensitive=False
    )

    drift_threshold: float = Field(
        default_factory=lambda: _risk_analysis_yaml_config.get('drift_threshold', 0.15)
    )
    labeling_model: str = Field(
        default_factory=lambda: _risk_analysis_yaml_config.get('labeling_model', "facebook/bart-large-mnli")
    )
    labeling_batch_size: int = Field(
        default_factory=lambda: _risk_analysis_yaml_config.get('labeling_batch_size', 16)
    )
    labeling_multi_label: bool = Field(
        default_factory=lambda: _risk_analysis_yaml_config.get('labeling_multi_label', True)
    )
    device: str = Field(
        default_factory=lambda: _risk_analysis_yaml_config.get('device', "auto")
    )


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
    readability: ReadabilityConfig = Field(default_factory=ReadabilityConfig)
    topic_modeling: TopicModelingConfig = Field(default_factory=TopicModelingConfig)
    risk_analysis: RiskAnalysisConfig = Field(default_factory=RiskAnalysisConfig)


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
LABELED_DATA_DIR = settings.paths.labeled_data_dir
MODELS_DIR = settings.paths.models_dir
SRC_DIR = settings.paths.src_dir
ANALYSIS_DIR = settings.paths.analysis_dir
TAXONOMIES_DIR = settings.paths.taxonomies_dir
LOGS_DIR = settings.paths.logs_dir
EXTRACTION_LOGS_DIR = settings.paths.extraction_logs_dir
RISK_TAXONOMY_PATH = settings.paths.risk_taxonomy_path
GOLDEN_DATASET_PATH = settings.paths.golden_dataset_path
MODEL_REGISTRY_DIR = settings.paths.model_registry_dir
EXPERIMENTS_DIR = settings.paths.experiments_dir

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

# Classes (already defined at module level, explicitly listed for clarity)
# RunContext - defined at line 183, available for import


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
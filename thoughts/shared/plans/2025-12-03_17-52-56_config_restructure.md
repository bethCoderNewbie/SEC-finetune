---
date: 2025-12-03T17:52:56-06:00
researcher: bethCoderNewbie
git_commit: f599254
branch: main
repository: SEC finetune
topic: "src/config.py Modularization Plan"
tags: [plan, config, refactoring, pydantic, architecture]
status: ready_for_review
last_updated: 2025-12-03
last_updated_by: bethCoderNewbie
related_research: thoughts/shared/research/2025-12-03_17-51-31_config_restructure.md
---

# Plan: src/config.py Modularization

## Desired End State

After this plan is complete, the user will have:

* **Modular config package** at `src/config/` with domain-specific modules
* **Single cached YAML loader** replacing 5 duplicate functions
* **Zero import-time side effects** - all YAML loading is lazy/cached
* **Backward compatibility** - existing `from src.config import settings` works unchanged
* **Deprecation path** - legacy constant imports emit warnings
* **Testable configuration** - easy to mock/override in tests

### Key Discoveries (from Research)

* `src/config.py:34-44, 426-437, 583-594, 797-808, 956-967` - 5 duplicate YAML loaders
* `src/config.py:149-156, 568-575` - Deferred imports indicate circular dependency risk
* `src/config.py:1046-1105` - 60 legacy exports need deprecation path
* All 5 YAML files exist under `configs/` and `configs/features/`

## What We're NOT Doing

* **Breaking the public API** - `from src.config import settings` remains unchanged
* **Removing legacy exports immediately** - deprecation warnings only
* **Changing YAML file locations** - `configs/` structure stays the same
* **Modifying YAML file contents** - only Python code changes
* **Adding new features** - pure refactoring, no functional changes

## Implementation Approach

Start with infrastructure (`_loader.py`), then extract configs bottom-up (leaf configs first), then wire up the main `Settings` class, and finally add deprecation warnings to legacy exports.

---

## Phase 1: Infrastructure - Cached YAML Loader

**Overview:** Create a single, cached YAML loading utility to replace 5 duplicate functions.

### Changes Required:

**1. Create `_loader.py`**
**File:** `src/config/_loader.py` (new file)
**Purpose:** Generic cached YAML loader

```python
"""
Cached YAML configuration loader.

Usage:
    from src.config._loader import load_yaml_section

    # Load entire file
    config = load_yaml_section("config.yaml")

    # Load specific section
    sentiment = load_yaml_section("features/sentiment.yaml", "sentiment")
"""

from functools import lru_cache
from pathlib import Path
from typing import Any
import yaml


def _get_configs_dir() -> Path:
    """Get the configs directory path."""
    return Path(__file__).parent.parent.parent / "configs"


@lru_cache(maxsize=16)
def load_yaml_section(config_file: str, section: str | None = None) -> dict[str, Any]:
    """
    Load and cache YAML configuration.

    Args:
        config_file: Path relative to configs/ directory (e.g., "config.yaml" or "features/sentiment.yaml")
        section: Optional top-level key to extract (e.g., "sentiment")

    Returns:
        Configuration dictionary (empty dict if file not found)

    Note:
        Results are cached. Use load_yaml_section.cache_clear() to reload.
    """
    config_path = _get_configs_dir() / config_file

    if not config_path.exists():
        return {}

    with open(config_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}

    return data.get(section, {}) if section else data


def clear_config_cache() -> None:
    """Clear all cached configurations. Useful for testing."""
    load_yaml_section.cache_clear()
```

**2. Create package `__init__.py` stub**
**File:** `src/config/__init__.py` (new file, minimal)
**Purpose:** Package marker (will be expanded in Phase 4)

```python
"""
SEC Filing Analyzer Configuration Package.

Usage:
    from src.config import settings

    data_dir = settings.paths.data_dir
    model = settings.models.default_model
"""

# Will be populated in Phase 4
```

---

## Phase 2: Extract Core Configs

**Overview:** Extract non-feature configs into separate modules.

### Changes Required:

**1. PathsConfig**
**File:** `src/config/paths.py` (new file)
**Source:** `src/config.py:51-177`

```python
"""Project path configuration."""

from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from src.config._loader import load_yaml_section


class PathsConfig(BaseSettings):
    """
    Project path configuration.
    All paths are computed from project_root.
    """
    model_config = SettingsConfigDict(
        env_prefix='PATHS_',
        case_sensitive=False
    )

    project_root: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent)

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
        return self.interim_data_dir / "parsed"

    @property
    def extracted_data_dir(self) -> Path:
        return self.interim_data_dir / "extracted"

    @property
    def processed_data_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def labeled_data_dir(self) -> Path:
        return self.processed_data_dir / "labeled"

    @property
    def features_data_dir(self) -> Path:
        return self.processed_data_dir / "features"

    @property
    def models_dir(self) -> Path:
        return self.project_root / "models"

    @property
    def experiments_dir(self) -> Path:
        return self.models_dir / "experiments"

    @property
    def model_registry_dir(self) -> Path:
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
        return self.data_dir / "dictionary"

    @property
    def lm_dictionary_csv(self) -> Path:
        """Path to LM dictionary source CSV."""
        # Inline constant to avoid circular import
        return self.dictionary_dir / "Loughran-McDonald_MasterDictionary_1993-2021.csv"

    @property
    def lm_dictionary_cache(self) -> Path:
        """Path to preprocessed LM dictionary cache."""
        # Inline constant to avoid circular import
        return self.dictionary_dir / "lm_dictionary_cache.pkl"

    def ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
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
```

**2. SecParserConfig**
**File:** `src/config/sec_parser.py` (new file)
**Source:** `src/config.py:250-274`

```python
"""SEC Parser configuration."""

from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.config._loader import load_yaml_section


def _get_config() -> dict:
    return load_yaml_section("config.yaml").get("sec_parser", {})


class SecParserConfig(BaseSettings):
    """SEC Parser configuration settings."""
    model_config = SettingsConfigDict(
        env_prefix='SEC_PARSER_',
        case_sensitive=False
    )

    supported_form_types: List[str] = Field(
        default_factory=lambda: _get_config().get('supported_form_types', ["10-K", "10-Q"])
    )
    default_form_type: str = Field(
        default_factory=lambda: _get_config().get('default_form_type', "10-K")
    )
    input_file_extensions: List[str] = Field(
        default_factory=lambda: _get_config().get('input_file_extensions', ["html"])
    )
    parse_tables: bool = Field(
        default_factory=lambda: _get_config().get('parse_tables', True)
    )
    parse_images: bool = Field(
        default_factory=lambda: _get_config().get('parse_images', False)
    )
    version: str = Field(
        default_factory=lambda: _get_config().get('version', "0.54.0")
    )
```

**3. ModelsConfig**
**File:** `src/config/models.py` (new file)
**Source:** `src/config.py:281-293`

```python
"""ML model configuration."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.config._loader import load_yaml_section


def _get_config() -> dict:
    return load_yaml_section("config.yaml").get("models", {})


class ModelsConfig(BaseSettings):
    """ML model configuration settings."""
    model_config = SettingsConfigDict(
        env_prefix='MODELS_',
        case_sensitive=False
    )

    default_model: str = Field(
        default_factory=lambda: _get_config().get('default_model', "ProsusAI/finbert")
    )
    zero_shot_model: str = Field(
        default_factory=lambda: _get_config().get('zero_shot_model', "facebook/bart-large-mnli")
    )
```

**4. PreprocessingConfig**
**File:** `src/config/preprocessing.py` (new file)
**Source:** `src/config.py:300-321`

```python
"""Text preprocessing configuration."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.config._loader import load_yaml_section


def _get_config() -> dict:
    return load_yaml_section("config.yaml").get("preprocessing", {})


class PreprocessingConfig(BaseSettings):
    """Text preprocessing configuration settings."""
    model_config = SettingsConfigDict(
        env_prefix='PREPROCESSING_',
        case_sensitive=False
    )

    min_segment_length: int = Field(
        default_factory=lambda: _get_config().get('min_segment_length', 50)
    )
    max_segment_length: int = Field(
        default_factory=lambda: _get_config().get('max_segment_length', 2000)
    )
    remove_html_tags: bool = Field(
        default_factory=lambda: _get_config().get('remove_html_tags', True)
    )
    normalize_whitespace: bool = Field(
        default_factory=lambda: _get_config().get('normalize_whitespace', True)
    )
    remove_page_numbers: bool = Field(
        default_factory=lambda: _get_config().get('remove_page_numbers', True)
    )
```

**5. ExtractionConfig**
**File:** `src/config/extraction.py` (new file)
**Source:** `src/config.py:328-346`

```python
"""Section extraction configuration."""

from typing import List, Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.config._loader import load_yaml_section


def _get_config() -> dict:
    return load_yaml_section("config.yaml").get("extraction", {})


class ExtractionConfig(BaseSettings):
    """Section extraction configuration settings."""
    model_config = SettingsConfigDict(
        env_prefix='EXTRACTION_',
        case_sensitive=False
    )

    min_confidence: float = Field(
        default_factory=lambda: _get_config().get('min_confidence', 0.7)
    )
    enable_audit_logging: bool = Field(
        default_factory=lambda: _get_config().get('enable_audit_logging', True)
    )
    output_format: Literal["json", "parquet", "both"] = Field(
        default_factory=lambda: _get_config().get('output_format', "json")
    )
    default_sections: List[str] = Field(
        default_factory=lambda: _get_config().get('default_sections', ["part1item1a"])
    )
```

**6. SecSectionsConfig**
**File:** `src/config/sec_sections.py` (new file)
**Source:** `src/config.py:353-387`

```python
"""SEC section identifiers configuration."""

from typing import Dict

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.config._loader import load_yaml_section


def _get_config() -> dict:
    return load_yaml_section("config.yaml").get("sec_sections", {})


class SecSectionsConfig(BaseSettings):
    """SEC section identifiers for different form types."""
    model_config = SettingsConfigDict(
        env_prefix='SEC_SECTIONS_',
        case_sensitive=False
    )

    sections_10k: Dict[str, str] = Field(
        default_factory=lambda: _get_config().get('10-K', {
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
        default_factory=lambda: _get_config().get('10-Q', {
            "part1item1": "Item 1. Financial Statements",
            "part1item2": "Item 2. Management's Discussion and Analysis",
            "part2item1a": "Item 1A. Risk Factors",
        })
    )

    @property
    def SEC_10K_SECTIONS(self) -> Dict[str, str]:
        """Legacy property name for backward compatibility."""
        return self.sections_10k

    @property
    def SEC_10Q_SECTIONS(self) -> Dict[str, str]:
        """Legacy property name for backward compatibility."""
        return self.sections_10q
```

**7. TestingConfig & ReproducibilityConfig**
**File:** `src/config/testing.py` (new file)
**Source:** `src/config.py:394-419`

```python
"""Testing and reproducibility configuration."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.config._loader import load_yaml_section


def _get_testing_config() -> dict:
    return load_yaml_section("config.yaml").get("testing", {})


def _get_reproducibility_config() -> dict:
    return load_yaml_section("config.yaml").get("reproducibility", {})


class TestingConfig(BaseSettings):
    """Testing and validation configuration settings."""
    model_config = SettingsConfigDict(
        env_prefix='TESTING_',
        case_sensitive=False
    )

    enable_golden_validation: bool = Field(
        default_factory=lambda: _get_testing_config().get('enable_golden_validation', False)
    )


class ReproducibilityConfig(BaseSettings):
    """Reproducibility configuration settings."""
    model_config = SettingsConfigDict(
        env_prefix='REPRODUCIBILITY_',
        case_sensitive=False
    )

    random_seed: int = Field(
        default_factory=lambda: _get_reproducibility_config().get('random_seed', 42)
    )
```

**8. RunContext**
**File:** `src/config/run_context.py` (new file)
**Source:** `src/config.py:183-243`

```python
"""Run context and versioning management."""

from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RunContext(BaseSettings):
    """
    Manages versioning and output paths for data processing runs.

    Usage:
        run = RunContext(name="auto_label_bart")
        run.create()
        output_path = run.output_dir
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
        """Set default base_dir after settings are available."""
        if self.base_dir is None:
            # Import here to avoid circular dependency
            from src.config import settings
            object.__setattr__(self, 'base_dir', settings.paths.labeled_data_dir)

    @property
    def run_id(self) -> str:
        """Generate run ID from timestamp."""
        return self.timestamp.strftime("%Y%m%d_%H%M%S")

    @property
    def output_dir(self) -> Path:
        """Construct unique output directory path."""
        return self.base_dir / f"{self.run_id}_{self.name}"

    def create(self) -> "RunContext":
        """Create the run directory."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        return self

    def save_config(self, config: Dict) -> Path:
        """Save the configuration used for this run."""
        self.create()
        config_path = self.output_dir / "run_config.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        return config_path
```

---

## Phase 3: Extract Feature Configs

**Overview:** Extract complex feature configs (sentiment, topic modeling, readability, risk analysis) into `src/config/features/`.

### Changes Required:

**1. Create features package**
**File:** `src/config/features/__init__.py` (new file)

```python
"""Feature extraction configuration modules."""

from src.config.features.sentiment import SentimentConfig
from src.config.features.topic_modeling import TopicModelingConfig
from src.config.features.readability import ReadabilityConfig
from src.config.features.risk_analysis import RiskAnalysisConfig

__all__ = [
    "SentimentConfig",
    "TopicModelingConfig",
    "ReadabilityConfig",
    "RiskAnalysisConfig",
]
```

**2. SentimentConfig**
**File:** `src/config/features/sentiment.py` (new file)
**Source:** `src/config.py:426-577`
**Note:** Extract all 6 sub-configs (TextProcessing, Normalization, Features, Processing, Output) + main SentimentConfig

**3. TopicModelingConfig**
**File:** `src/config/features/topic_modeling.py` (new file)
**Source:** `src/config.py:583-790`
**Note:** Extract all 7 sub-configs + main TopicModelingConfig

**4. ReadabilityConfig**
**File:** `src/config/features/readability.py` (new file)
**Source:** `src/config.py:797-950`
**Note:** Extract all 5 sub-configs + main ReadabilityConfig

**5. RiskAnalysisConfig**
**File:** `src/config/features/risk_analysis.py` (new file)
**Source:** `src/config.py:956-993`

---

## Phase 4: Wire Up Main Settings

**Overview:** Update `src/config/__init__.py` to assemble all configs into the main Settings class.

### Changes Required:

**File:** `src/config/__init__.py` (update)

```python
"""
SEC Filing Analyzer Configuration Package.

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


# Global settings instance
settings = Settings()

# Utility function
ensure_directories = settings.paths.ensure_directories

# Re-export RunContext for direct import
__all__ = [
    "settings",
    "Settings",
    "RunContext",
    "ensure_directories",
    # Sub-configs for direct access if needed
    "PathsConfig",
    "SecParserConfig",
    "ModelsConfig",
    "PreprocessingConfig",
    "ExtractionConfig",
    "SecSectionsConfig",
    "TestingConfig",
    "ReproducibilityConfig",
    "SentimentConfig",
    "TopicModelingConfig",
    "ReadabilityConfig",
    "RiskAnalysisConfig",
]

# Legacy exports (with deprecation warnings)
from src.config.legacy import *  # noqa: F401, F403, E402
```

---

## Phase 5: Legacy Deprecation Layer

**Overview:** Create deprecation warnings for legacy constant imports.

### Changes Required:

**File:** `src/config/legacy.py` (new file)

```python
"""
Legacy exports with deprecation warnings.

These constants are deprecated. Use settings.* instead:
    # Old (deprecated)
    from src.config import DATA_DIR

    # New (preferred)
    from src.config import settings
    data_dir = settings.paths.data_dir
"""

import warnings
from typing import Any

# Import settings for access
from src.config import settings as _settings


def _deprecated(name: str, new_path: str) -> Any:
    """Emit deprecation warning and return the value."""
    warnings.warn(
        f"{name} is deprecated. Use settings.{new_path} instead.",
        DeprecationWarning,
        stacklevel=3
    )
    # Navigate the settings object
    obj = _settings
    for part in new_path.split('.'):
        obj = getattr(obj, part)
    return obj


# Path constants
PROJECT_ROOT = property(lambda self: _deprecated('PROJECT_ROOT', 'paths.project_root'))
DATA_DIR = property(lambda self: _deprecated('DATA_DIR', 'paths.data_dir'))
# ... (full list in implementation)

# For module-level attribute access
def __getattr__(name: str) -> Any:
    """Handle deprecated attribute access."""
    mappings = {
        # Paths
        'PROJECT_ROOT': 'paths.project_root',
        'DATA_DIR': 'paths.data_dir',
        'RAW_DATA_DIR': 'paths.raw_data_dir',
        'INTERIM_DATA_DIR': 'paths.interim_data_dir',
        'PARSED_DATA_DIR': 'paths.parsed_data_dir',
        'EXTRACTED_DATA_DIR': 'paths.extracted_data_dir',
        'PROCESSED_DATA_DIR': 'paths.processed_data_dir',
        'LABELED_DATA_DIR': 'paths.labeled_data_dir',
        'MODELS_DIR': 'paths.models_dir',
        'SRC_DIR': 'paths.src_dir',
        'ANALYSIS_DIR': 'paths.analysis_dir',
        'TAXONOMIES_DIR': 'paths.taxonomies_dir',
        'LOGS_DIR': 'paths.logs_dir',
        'EXTRACTION_LOGS_DIR': 'paths.extraction_logs_dir',
        'RISK_TAXONOMY_PATH': 'paths.risk_taxonomy_path',
        'GOLDEN_DATASET_PATH': 'paths.golden_dataset_path',
        'MODEL_REGISTRY_DIR': 'paths.model_registry_dir',
        'EXPERIMENTS_DIR': 'paths.experiments_dir',
        # SEC Parser
        'SUPPORTED_FORM_TYPES': 'sec_parser.supported_form_types',
        'DEFAULT_FORM_TYPE': 'sec_parser.default_form_type',
        'INPUT_FILE_EXTENSIONS': 'sec_parser.input_file_extensions',
        'PARSE_TABLES': 'sec_parser.parse_tables',
        'PARSE_IMAGES': 'sec_parser.parse_images',
        'SEC_PARSER_VERSION': 'sec_parser.version',
        # Models
        'DEFAULT_MODEL': 'models.default_model',
        'ZERO_SHOT_MODEL': 'models.zero_shot_model',
        # Preprocessing
        'MIN_SEGMENT_LENGTH': 'preprocessing.min_segment_length',
        'MAX_SEGMENT_LENGTH': 'preprocessing.max_segment_length',
        'REMOVE_HTML_TAGS': 'preprocessing.remove_html_tags',
        'NORMALIZE_WHITESPACE': 'preprocessing.normalize_whitespace',
        'REMOVE_PAGE_NUMBERS': 'preprocessing.remove_page_numbers',
        # Extraction
        'MIN_EXTRACTION_CONFIDENCE': 'extraction.min_confidence',
        'ENABLE_AUDIT_LOGGING': 'extraction.enable_audit_logging',
        'EXTRACTION_OUTPUT_FORMAT': 'extraction.output_format',
        'DEFAULT_SECTIONS_TO_EXTRACT': 'extraction.default_sections',
        # SEC Sections
        'SEC_10K_SECTIONS': 'sec_sections.sections_10k',
        'SEC_10Q_SECTIONS': 'sec_sections.sections_10q',
        # Testing
        'ENABLE_GOLDEN_VALIDATION': 'testing.enable_golden_validation',
        # Reproducibility
        'RANDOM_SEED': 'reproducibility.random_seed',
    }

    if name in mappings:
        return _deprecated(name, mappings[name])

    raise AttributeError(f"module 'src.config.legacy' has no attribute '{name}'")


__all__ = list(mappings.keys())
```

---

## Phase 6: Cleanup and Verification

**Overview:** Remove old `src/config.py`, update imports if needed.

### Changes Required:

**1. Delete old config.py**
**File:** `src/config.py` (delete)
**Action:** Remove after all tests pass

**2. Verify no direct imports**
**Command:** `grep -r "from src.config import" --include="*.py" | grep -v "settings"`

---

## Success Criteria

### Automated Verification:

- [ ] All tests pass: `pytest tests/ -v`
- [ ] Import works: `python -c "from src.config import settings; print(settings.paths.data_dir)"`
- [ ] Legacy imports work with warning: `python -c "from src.config import DATA_DIR" 2>&1 | grep DeprecationWarning`
- [ ] No circular imports: `python -c "from src.config import settings"`
- [ ] Type checking passes: `mypy src/config/`

### Manual Verification:

- [ ] `settings.paths.data_dir` returns correct path
- [ ] `settings.sentiment.active_categories` loads from YAML
- [ ] Legacy `DATA_DIR` emits deprecation warning
- [ ] `RunContext(name="test").output_dir` works correctly

---

## File Summary

| File | Action | Lines (approx) |
|------|--------|----------------|
| `src/config/__init__.py` | New | 80 |
| `src/config/_loader.py` | New | 45 |
| `src/config/paths.py` | New | 120 |
| `src/config/sec_parser.py` | New | 40 |
| `src/config/models.py` | New | 30 |
| `src/config/preprocessing.py` | New | 40 |
| `src/config/extraction.py` | New | 40 |
| `src/config/sec_sections.py` | New | 50 |
| `src/config/testing.py` | New | 45 |
| `src/config/run_context.py` | New | 60 |
| `src/config/features/__init__.py` | New | 15 |
| `src/config/features/sentiment.py` | New | 150 |
| `src/config/features/topic_modeling.py` | New | 200 |
| `src/config/features/readability.py` | New | 150 |
| `src/config/features/risk_analysis.py` | New | 40 |
| `src/config/legacy.py` | New | 80 |
| `src/config.py` | Delete | -1126 |
| **Total** | | ~1,185 (well-organized) |

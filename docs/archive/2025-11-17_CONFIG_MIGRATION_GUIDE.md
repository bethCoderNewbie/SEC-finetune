# Configuration Migration Guide

## Overview

The configuration system has been refactored to use **Pydantic Settings** with YAML-based defaults and environment variable support. This provides:

- ✅ Type safety and validation
- ✅ YAML configuration for defaults
- ✅ Environment variable overrides
- ✅ Better separation of concerns
- ✅ Structured, organized settings

## New Structure

```
configs/
  └── config.yaml          # All default configuration values

src/
  └── config.py           # Pydantic Settings classes
```

## Configuration Files

### `configs/config.yaml`

Contains all default values organized by domain:

```yaml
sec_parser:
  supported_form_types: ["10-K", "10-Q"]
  default_form_type: "10-K"
  input_file_extensions: ["html"]
  parse_tables: true
  parse_images: false

models:
  default_model: "ProsusAI/finbert"
  zero_shot_model: "facebook/bart-large-mnli"

preprocessing:
  min_segment_length: 50
  max_segment_length: 2000
  remove_html_tags: true
  normalize_whitespace: true

extraction:
  min_confidence: 0.7
  enable_audit_logging: true
  output_format: "json"
  default_sections: ["part1item1a"]

# ... and more
```

### `src/config.py`

Pydantic Settings classes that:
1. Load defaults from `configs/config.yaml`
2. Allow overrides via environment variables
3. Provide type validation and documentation

## Usage

### Modern Approach (Recommended)

```python
from src.config import settings

# Access paths
data_dir = settings.paths.data_dir
raw_data = settings.paths.raw_data_dir
parsed_data = settings.paths.parsed_data_dir

# Access SEC parser settings
form_types = settings.sec_parser.supported_form_types
default_form = settings.sec_parser.default_form_type
extensions = settings.sec_parser.input_file_extensions

# Access model settings
model_name = settings.models.default_model
zero_shot = settings.models.zero_shot_model

# Access preprocessing settings
min_length = settings.preprocessing.min_segment_length
max_length = settings.preprocessing.max_segment_length

# Access extraction settings
min_conf = settings.extraction.min_confidence
output_fmt = settings.extraction.output_format

# Access SEC sections
sections_10k = settings.sec_sections.sections_10k
sections_10q = settings.sec_sections.sections_10q

# Utility functions
settings.paths.ensure_directories()
```

### Legacy Approach (Still Supported)

For backward compatibility, the old constant-style imports still work:

```python
from src.config import (
    RAW_DATA_DIR,
    PARSED_DATA_DIR,
    EXTRACTED_DATA_DIR,
    PROCESSED_DATA_DIR,
    MODELS_DIR,
    LOGS_DIR,
    RISK_TAXONOMY_PATH,

    SUPPORTED_FORM_TYPES,
    DEFAULT_FORM_TYPE,
    INPUT_FILE_EXTENSIONS,

    DEFAULT_MODEL,
    ZERO_SHOT_MODEL,

    MIN_SEGMENT_LENGTH,
    MAX_SEGMENT_LENGTH,

    MIN_EXTRACTION_CONFIDENCE,
    EXTRACTION_OUTPUT_FORMAT,

    SEC_10K_SECTIONS,
    SEC_10Q_SECTIONS,

    ensure_directories,
)
```

However, we recommend migrating to the modern approach for better organization.

## Environment Variable Overrides

You can override any setting using environment variables in your `.env` file:

### Path Settings

```bash
# Paths (prefix: PATHS_)
PATHS_PROJECT_ROOT=/custom/path
```

### SEC Parser Settings

```bash
# SEC Parser (prefix: SEC_PARSER_)
SEC_PARSER_DEFAULT_FORM_TYPE=10-Q
SEC_PARSER_INPUT_FILE_EXTENSIONS=["html","txt"]
SEC_PARSER_PARSE_TABLES=false
SEC_PARSER_VERSION=0.55.0
```

### Model Settings

```bash
# Models (prefix: MODELS_)
MODELS_DEFAULT_MODEL=custom/finbert-model
MODELS_ZERO_SHOT_MODEL=custom/bart-model
```

### Preprocessing Settings

```bash
# Preprocessing (prefix: PREPROCESSING_)
PREPROCESSING_MIN_SEGMENT_LENGTH=100
PREPROCESSING_MAX_SEGMENT_LENGTH=1500
PREPROCESSING_REMOVE_HTML_TAGS=true
```

### Extraction Settings

```bash
# Extraction (prefix: EXTRACTION_)
EXTRACTION_MIN_CONFIDENCE=0.8
EXTRACTION_ENABLE_AUDIT_LOGGING=true
EXTRACTION_OUTPUT_FORMAT=parquet
```

### Testing Settings

```bash
# Testing (prefix: TESTING_)
TESTING_ENABLE_GOLDEN_VALIDATION=true
```

### Reproducibility Settings

```bash
# Reproducibility (prefix: REPRODUCIBILITY_)
REPRODUCIBILITY_RANDOM_SEED=123
```

## Configuration Classes

The new config system is organized into the following classes:

### `PathsConfig`

All directory and file paths:
- `project_root`: Project root directory
- `data_dir`: Main data directory
- `raw_data_dir`: Raw SEC filings
- `parsed_data_dir`: Parsed filings
- `extracted_data_dir`: Extracted sections
- `processed_data_dir`: Processed data
- `models_dir`: Model storage
- `logs_dir`: Log files
- `risk_taxonomy_path`: Risk taxonomy YAML
- `ensure_directories()`: Create all directories

### `SecParserConfig`

SEC parsing configuration:
- `supported_form_types`: List of supported forms
- `default_form_type`: Default form type
- `input_file_extensions`: Accepted file extensions
- `parse_tables`: Enable table parsing
- `parse_images`: Enable image extraction
- `version`: SEC parser version

### `ModelsConfig`

ML model configuration:
- `default_model`: Default financial model
- `zero_shot_model`: Zero-shot classification model

### `PreprocessingConfig`

Text preprocessing settings:
- `min_segment_length`: Minimum segment length
- `max_segment_length`: Maximum segment length
- `remove_html_tags`: Remove HTML tags
- `normalize_whitespace`: Normalize whitespace
- `remove_page_numbers`: Remove page numbers

### `ExtractionConfig`

Section extraction settings:
- `min_confidence`: Minimum extraction confidence
- `enable_audit_logging`: Enable audit logs
- `output_format`: Output format (json/parquet/both)
- `default_sections`: Default sections to extract

### `SecSectionsConfig`

SEC section identifiers:
- `sections_10k`: 10-K section mappings
- `sections_10q`: 10-Q section mappings

### `TestingConfig`

Testing and validation:
- `enable_golden_validation`: Enable golden dataset validation

### `ReproducibilityConfig`

Reproducibility settings:
- `random_seed`: Random seed for reproducibility

## Migration Examples

### Before (Old Style)

```python
from src.config import RAW_DATA_DIR, INPUT_FILE_EXTENSIONS

raw_dir = RAW_DATA_DIR
extensions = INPUT_FILE_EXTENSIONS

for ext in extensions:
    files = raw_dir.glob(f"*.{ext}")
```

### After (New Style)

```python
from src.config import settings

raw_dir = settings.paths.raw_data_dir
extensions = settings.sec_parser.input_file_extensions

for ext in extensions:
    files = raw_dir.glob(f"*.{ext}")
```

### Benefits of New Style

1. **Clear organization**: Settings are grouped by domain
2. **Type safety**: Pydantic validates types
3. **Autocomplete**: Better IDE support
4. **Documentation**: Self-documenting structure
5. **Flexibility**: Easy to add new settings

## Testing the Configuration

Run the config module directly to test:

```bash
python -m src.config
```

This will:
1. Create all necessary directories
2. Display current configuration values
3. Verify everything loads correctly

## Best Practices

1. **Use the settings object**: `from src.config import settings`
2. **Group related settings**: Access via domain (paths, models, etc.)
3. **Override via environment**: Use `.env` for environment-specific values
4. **Document changes**: Update `configs/config.yaml` for new defaults
5. **Type hints**: Leverage Pydantic's type validation

## Additional Configuration

### Adding New Settings

1. **Update `configs/config.yaml`**:
   ```yaml
   new_section:
     new_setting: value
   ```

2. **Add Pydantic class in `src/config.py`**:
   ```python
   class NewSectionConfig(BaseSettings):
       model_config = SettingsConfigDict(
           env_prefix='NEW_SECTION_',
           case_sensitive=False
       )

       new_setting: str = Field(
           default_factory=lambda: _yaml_config.get('new_section', {}).get('new_setting', 'default')
       )
   ```

3. **Add to Settings class**:
   ```python
   class Settings(BaseSettings):
       # ... existing settings
       new_section: NewSectionConfig = Field(default_factory=NewSectionConfig)
   ```

## Dependencies

The new configuration system requires:

```bash
pip install pydantic-settings pyyaml
```

These are already installed in the project.

---

**Note**: While legacy imports are still supported for backward compatibility, we recommend migrating to the new `settings` object approach for cleaner, more maintainable code.

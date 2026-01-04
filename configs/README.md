# Configuration Directory

This directory contains YAML configuration files that define default values for the SEC Filing Analyzer application.

## Structure

```
configs/
├── README.md              # This file
├── config.yaml            # Main application configuration
└── qa_validation/         # QA validation thresholds
    ├── README.md          # QA validation documentation
    ├── extraction.yaml    # Extractor thresholds
    ├── parsing.yaml       # Parser thresholds
    ├── cleaning.yaml      # Cleaner/segmenter thresholds
    └── features.yaml      # Sentiment/readability thresholds
```

## Files

### `config.yaml`

Main configuration file containing all application defaults, organized by domain:

- **`sec_parser`**: SEC filing parser settings (form types, extensions, parsing options)
- **`models`**: Machine learning model configurations
- **`preprocessing`**: Text preprocessing parameters
- **`extraction`**: Section extraction settings
- **`sec_sections`**: Section identifiers for 10-K and 10-Q forms
- **`testing`**: Testing and validation settings
- **`reproducibility`**: Reproducibility settings (random seed, versions)
- **`naming`**: Naming conventions for output files and directories

### `qa_validation/`

QA validation thresholds for Go/No-Go test criteria. See [qa_validation/README.md](qa_validation/README.md) for details.

## How It Works

1. **Default Values**: All defaults are defined in `config.yaml`
2. **Loading**: `src/config.py` loads these values using Pydantic Settings
3. **Overrides**: Environment variables can override any setting
4. **Type Safety**: Pydantic validates all configuration values

## Environment Variable Overrides

Any setting can be overridden using environment variables with the appropriate prefix:

```bash
# Override SEC parser settings
SEC_PARSER_DEFAULT_FORM_TYPE=10-Q

# Override model settings
MODELS_DEFAULT_MODEL=custom/model-name

# Override preprocessing settings
PREPROCESSING_MIN_SEGMENT_LENGTH=100

# Override extraction settings
EXTRACTION_MIN_CONFIDENCE=0.8
```

## Editing Configuration

To change default values:

1. Edit `config.yaml`
2. Restart your application
3. Values will be automatically loaded

Example:
```yaml
sec_parser:
  default_form_type: "10-Q"  # Changed from 10-K
  input_file_extensions:
    - "html"
    - "txt"  # Added txt support
```

## Configuration Precedence

Settings are loaded in this order (later values override earlier ones):

1. **YAML defaults** (`config.yaml`)
2. **Environment variables** (`.env` file or system environment)
3. **Explicit overrides** (passed to Pydantic Settings constructors)

## See Also

- **[Configuration Migration Guide](../docs/CONFIG_MIGRATION_GUIDE.md)**: Detailed usage and migration instructions
- **[src/config.py](../src/config.py)**: Pydantic Settings implementation

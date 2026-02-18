# Config

Documentation for `src/config/`: Pydantic v2 settings, enums, and the YAML configuration system.

## Documents

| File | Purpose |
|------|---------|
| [PYDANTIC_V2_ENFORCEMENT.md](PYDANTIC_V2_ENFORCEMENT.md) | **Start here.** Rules for Pydantic v2 usage and common migration pitfalls |
| [ENUM_CONFIG_PATTERNS.md](ENUM_CONFIG_PATTERNS.md) | How enums are defined and used across config modules |
| [FILE_TYPE_CONFIGURATION.md](FILE_TYPE_CONFIGURATION.md) | Per-file-type config structure and override patterns |

## Config Modules

```
src/config/
├── __init__.py         → settings singleton + legacy constants
├── paths.py            → PathsConfig (all data dirs)
├── preprocessing.py    → PreprocessingConfig
├── models.py           → ModelConfig
├── sec_parser.py       → SecParserConfig
├── sec_sections.py     → Section enums and targets
├── qa_validation.py    → QA thresholds
├── naming.py           → Run directory naming conventions
└── run_context.py      → Per-run metadata
```

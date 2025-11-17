# Enum & Configuration Management Patterns

## Overview
Best practices for managing enums and configurations in a scalable, maintainable Python project.

---

## 🔒 Pydantic v2 Enforcement Policy

### **MANDATORY REQUIREMENT: Pydantic 2.12.4+**

This project **REQUIRES** Pydantic v2 (version 2.12.4 or later). Pydantic v1 is deprecated and **NOT SUPPORTED**.

### Version Requirements

**pyproject.toml must specify:**
```toml
[project]
dependencies = [
    "pydantic>=2.12.4",
    "pydantic-settings>=2.0.0",
]
```

### Pre-Commit Validation

All Pydantic code must follow v2 patterns. The following patterns are **FORBIDDEN**:

❌ **NEVER USE (Pydantic v1 - Deprecated):**
```python
# ❌ OLD - Do not use
from pydantic import BaseSettings  # Wrong import
from pydantic import validator      # Deprecated

class Config:                        # Old style configuration
    env_file = '.env'

@validator('field')                  # Old validator decorator
def validate_field(cls, v):
    return v

config.dict()                        # Old serialization method
config.json()                        # Old JSON method
Config.parse_obj(data)               # Old parsing method
```

✅ **ALWAYS USE (Pydantic v2 - Current):**
```python
# ✅ CORRECT - Use these
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict

model_config = ConfigDict(...)               # New style configuration
model_config = SettingsConfigDict(...)       # For BaseSettings

@field_validator('field')                    # New validator decorator
@classmethod
def validate_field(cls, v):
    return v

@model_validator(mode='after')               # New model validator
@classmethod
def validate_model(cls, model):
    return model

config.model_dump()                          # New serialization method
config.model_dump_json()                     # New JSON method
Config.model_validate(data)                  # New parsing method
Field(..., pattern='regex')                  # pattern instead of regex
```

### Code Review Checklist

Before committing any Pydantic code, verify:

- [ ] Using Pydantic v2.12.4 or later
- [ ] All imports are from correct v2 modules (`pydantic` and `pydantic_settings`)
- [ ] All models use `model_config = ConfigDict(...)` or `SettingsConfigDict(...)`
- [ ] All validators use `@field_validator` or `@model_validator` with `@classmethod`
- [ ] All serialization uses `.model_dump()` and `.model_dump_json()`
- [ ] All parsing uses `.model_validate()` and `.model_validate_json()`
- [ ] No deprecated v1 patterns in code

### Enforcement

- **CI/CD**: Add linting to check for deprecated patterns
- **Code Reviews**: Reject any PRs containing Pydantic v1 patterns
- **Documentation**: All examples must show v2 patterns only
- **Dependencies**: Pin `pydantic>=2.12.4` to prevent downgrades

---

## Pattern 1: Config-Driven Enums (Current Implementation)

### ✅ Recommended for: Business logic that changes frequently

**Structure:**
```
src/
├── config.py              # Source of truth
└── preprocessing/
    └── extractor.py       # References config
```

**Implementation:**

```python
# src/config.py - Single source of truth
SEC_10K_SECTIONS = {
    "part1item1": "Item 1. Business",
    "part1item1a": "Item 1A. Risk Factors",
    "part1item1b": "Item 1B. Unresolved Staff Comments",
    # Add more sections here as needed
}

SEC_10Q_SECTIONS = {
    "part1item1": "Item 1. Financial Statements",
    "part1item2": "Item 2. Management's Discussion and Analysis",
}

# src/preprocessing/extractor.py
from ..config import SEC_10K_SECTIONS, SEC_10Q_SECTIONS

class SectionIdentifier(Enum):
    """Type-safe enum for IDE autocomplete"""
    ITEM_1A_RISK_FACTORS = "part1item1a"
    # Keep enum for type safety

class SECSectionExtractor:
    # Reference config instead of hardcoding
    SECTION_TITLES_10K = SEC_10K_SECTIONS
    SECTION_TITLES_10Q = SEC_10Q_SECTIONS
```

**Benefits:**
- ✅ Single source of truth
- ✅ Easy to add new sections without code changes
- ✅ Can be overridden via environment variables
- ✅ Type safety with Enum for critical paths

## Pattern 2: YAML-Based Configuration

### ✅ Recommended for: Complex, hierarchical configs

**Structure:**
```
config/
├── sections.yaml          # Section definitions
├── models.yaml            # Model configs
└── taxonomy.yaml          # Risk taxonomy
```

**Implementation:**

```yaml
# config/sections.yaml
sec_forms:
  10-K:
    sections:
      - id: part1item1
        title: "Item 1. Business"
        extract_by_default: false
        priority: 2

      - id: part1item1a
        title: "Item 1A. Risk Factors"
        extract_by_default: true
        priority: 1
        subsections_required: true

      - id: part2item7
        title: "Item 7. Management's Discussion and Analysis"
        extract_by_default: true
        priority: 1

  10-Q:
    sections:
      - id: part1item1
        title: "Item 1. Financial Statements"
        extract_by_default: false
```

```python
# src/config.py
import yaml
from pathlib import Path

CONFIG_DIR = PROJECT_ROOT / "config"

def load_section_config():
    """Load section configuration from YAML"""
    with open(CONFIG_DIR / "sections.yaml") as f:
        return yaml.safe_load(f)

SECTION_CONFIG = load_section_config()

# Convenience accessors
SEC_10K_SECTIONS = {
    s['id']: s['title']
    for s in SECTION_CONFIG['sec_forms']['10-K']['sections']
}

DEFAULT_SECTIONS_TO_EXTRACT = [
    s['id']
    for s in SECTION_CONFIG['sec_forms']['10-K']['sections']
    if s.get('extract_by_default', False)
]
```

**Benefits:**
- ✅ Non-technical users can update configs
- ✅ Version control for configuration changes
- ✅ Supports complex hierarchies
- ✅ Easy validation with JSON Schema

## Pattern 3: Database-Driven Configuration

### ✅ Recommended for: Multi-tenant or frequently changing configs

**Implementation:**

```python
# src/config_db.py
from sqlalchemy import create_engine, Column, String, Boolean, Integer
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class SECSection(Base):
    __tablename__ = 'sec_sections'

    id = Column(String, primary_key=True)
    form_type = Column(String, nullable=False)
    title = Column(String, nullable=False)
    extract_by_default = Column(Boolean, default=False)
    priority = Column(Integer, default=0)

# Usage
def get_sections_for_form(form_type: str):
    session = get_db_session()
    sections = session.query(SECSection).filter_by(form_type=form_type).all()
    return {s.id: s.title for s in sections}
```

**Benefits:**
- ✅ Runtime configuration changes
- ✅ No deployment needed for updates
- ✅ Audit trail for changes
- ✅ Multi-tenant support

## Pattern 4: Environment-Specific Overrides

### ✅ Recommended for: Different configs per environment

**Structure:**
```
config/
├── base.py              # Default configs
├── development.py       # Dev overrides
├── staging.py           # Staging overrides
└── production.py        # Production configs
```

**Implementation:**

```python
# config/base.py
class BaseConfig:
    SEC_10K_SECTIONS = {
        "part1item1": "Item 1. Business",
        "part1item1a": "Item 1A. Risk Factors",
    }
    EXTRACTION_OUTPUT_FORMAT = "json"
    MIN_EXTRACTION_CONFIDENCE = 0.7

# config/development.py
from .base import BaseConfig

class DevelopmentConfig(BaseConfig):
    # Override for faster development
    MIN_EXTRACTION_CONFIDENCE = 0.5
    DEBUG = True

# config/production.py
from .base import BaseConfig

class ProductionConfig(BaseConfig):
    MIN_EXTRACTION_CONFIDENCE = 0.9
    EXTRACTION_OUTPUT_FORMAT = "parquet"  # Faster for production

# src/config.py
import os
from config.base import BaseConfig
from config.development import DevelopmentConfig
from config.production import ProductionConfig

ENV = os.getenv('ENVIRONMENT', 'development')

config_map = {
    'development': DevelopmentConfig,
    'staging': BaseConfig,
    'production': ProductionConfig,
}

Config = config_map[ENV]

# Usage
SEC_10K_SECTIONS = Config.SEC_10K_SECTIONS
MIN_EXTRACTION_CONFIDENCE = Config.MIN_EXTRACTION_CONFIDENCE
```

**Benefits:**
- ✅ Clear separation of concerns
- ✅ Environment-specific optimizations
- ✅ Easy testing with different configs

## Pattern 5: Pydantic v2 for Validation

### ✅ Recommended for: Type-safe, validated configs

### 🔒 **ENFORCED: Pydantic v2.12.4+ Required**

**This project MUST use Pydantic v2 (2.12.4 or later). Pydantic v1 is deprecated and not supported.**

**Implementation (Pydantic v2 Style):**

```python
# src/config_models.py
from pydantic import BaseModel, Field, field_validator, ConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Dict, List, Literal
from pathlib import Path

class SECSectionConfig(BaseModel):
    """Configuration for individual SEC filing sections"""
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(..., pattern=r'^part\d+item\d+[a-z]?$')
    title: str
    extract_by_default: bool = False
    priority: int = Field(default=0, ge=0, le=10)

class FormConfig(BaseModel):
    """Configuration for SEC form types"""
    form_type: Literal['10-K', '10-Q', '8-K']
    sections: List[SECSectionConfig]

    @field_validator('sections')
    @classmethod
    def validate_sections(cls, sections: List[SECSectionConfig]) -> List[SECSectionConfig]:
        """Ensure no duplicate section IDs"""
        ids = [s.id for s in sections]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate section IDs found")
        return sections

class ExtractionConfig(BaseSettings):
    """Main extraction configuration with environment variable support"""
    model_config = SettingsConfigDict(
        env_prefix='EXTRACTION_',
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore'
    )

    sec_forms: Dict[str, FormConfig] = Field(default_factory=dict)
    output_format: Literal['json', 'parquet', 'both'] = 'json'
    min_confidence: float = Field(default=0.7, ge=0.0, le=1.0)

    @field_validator('output_format')
    @classmethod
    def validate_output_format(cls, v: str) -> str:
        """Validate output format is supported"""
        valid = ['json', 'parquet', 'both']
        if v not in valid:
            raise ValueError(f"output_format must be one of {valid}")
        return v

# Usage (Pydantic v2 methods)
import yaml
with open('config/extraction.yaml') as f:
    yaml_data = yaml.safe_load(f)

config = ExtractionConfig.model_validate(yaml_data)  # v2: model_validate instead of parse_obj
SEC_10K_SECTIONS = {
    s.id: s.title
    for s in config.sec_forms['10-K'].sections
}

# Serialization (v2 methods)
config_dict = config.model_dump()  # v2: model_dump instead of .dict()
config_json = config.model_dump_json(indent=2)  # v2: model_dump_json instead of .json()
```

**Benefits:**
- ✅ Automatic validation with better error messages
- ✅ Type safety with full IDE autocomplete
- ✅ Environment variable integration via BaseSettings
- ✅ JSON Schema generation via `.model_json_schema()`
- ✅ Clear separation: BaseSettings for configs, BaseModel for data schemas
- ✅ Modern ConfigDict pattern for better maintainability

### 🚨 Pydantic v2 Migration Checklist

**REQUIRED Changes from v1 to v2:**

| Old (v1) ❌ | New (v2) ✅ |
|------------|-----------|
| `@validator` | `@field_validator` with `@classmethod` |
| `@root_validator` | `@model_validator` with `@classmethod` |
| `class Config:` | `model_config = ConfigDict(...)` |
| `.dict()` | `.model_dump()` |
| `.json()` | `.model_dump_json()` |
| `.parse_obj(data)` | `.model_validate(data)` |
| `.parse_raw(json_str)` | `.model_validate_json(json_str)` |
| `.parse_file(path)` | Use with open + `.model_validate()` |
| `.schema()` | `.model_json_schema()` |
| `.construct()` | `.model_construct()` |
| `Field(..., regex='...')` | `Field(..., pattern='...')` |

**Example v2 Validator:**
```python
# ✅ CORRECT - Pydantic v2
@field_validator('field_name')
@classmethod
def validate_field(cls, v: str) -> str:
    if not v:
        raise ValueError('Field cannot be empty')
    return v.upper()

# ✅ CORRECT - Pydantic v2 model validator (for cross-field validation)
@model_validator(mode='after')
@classmethod
def validate_model(cls, model):
    if model.start_date > model.end_date:
        raise ValueError('start_date must be before end_date')
    return model
```

## Hybrid Approach (Recommended)

Combine patterns for maximum flexibility using **Pydantic v2**:

```python
# src/config.py
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Dict, Optional
import yaml

def load_yaml_config(path: str) -> dict:
    """Load configuration from YAML file"""
    with open(path) as f:
        return yaml.safe_load(f)

class Settings(BaseSettings):
    """
    Hierarchical configuration (Pydantic v2):
    1. YAML files (base configuration)
    2. Environment variables (overrides)
    3. .env file (local development)
    """
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
        env_nested_delimiter='__'  # Allows SECTION__SUBSECTION__VALUE
    )

    # Base configs from YAML
    sec_10k_sections: Optional[Dict[str, str]] = Field(default_factory=dict)
    sec_10q_sections: Optional[Dict[str, str]] = Field(default_factory=dict)

    # Can be overridden by environment (env_prefix in model_config)
    extraction_output_format: str = Field(
        default='json',
        description='Output format for extraction results'
    )
    min_extraction_confidence: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description='Minimum confidence threshold for extraction'
    )

    @classmethod
    def load(cls) -> 'Settings':
        """Load settings from YAML + environment variables"""
        # Load base from YAML
        base_config = load_yaml_config('config/sections.yaml')

        # Create settings with YAML base + env overrides
        # Environment variables will automatically override YAML values
        return cls(
            sec_10k_sections=base_config.get('10-K', {}),
            sec_10q_sections=base_config.get('10-Q', {}),
        )

# Initialize settings
settings = Settings.load()

# Export for backwards compatibility
SEC_10K_SECTIONS = settings.sec_10k_sections
SEC_10Q_SECTIONS = settings.sec_10q_sections
EXTRACTION_OUTPUT_FORMAT = settings.extraction_output_format

# Example: Override via environment variable
# EXTRACTION_OUTPUT_FORMAT=parquet python script.py
# MIN_EXTRACTION_CONFIDENCE=0.9 python script.py
```

## Migration Strategy

### From Hardcoded → Config-Driven (Current Project)

**Phase 1: Centralize** ✅ (COMPLETED)
- Move hardcoded values to `config.py`
- Update imports to use config

**Phase 2: Environment Variables** (Optional)
```python
# config.py
SEC_10K_SECTIONS = os.getenv('SEC_10K_SECTIONS_JSON', None)
if SEC_10K_SECTIONS:
    SEC_10K_SECTIONS = json.loads(SEC_10K_SECTIONS)
else:
    SEC_10K_SECTIONS = {
        # defaults
    }
```

**Phase 3: YAML (For complex configs)**
- Move to YAML when config grows beyond 50 lines
- Add validation layer

**Phase 4: Validation (For production)**
- Add Pydantic models for type safety
- Validate on startup

## Best Practices Summary

| Scenario | Recommended Pattern |
|----------|-------------------|
| Small project (<5 configs) | Config-driven enums (current) ✅ |
| Medium project (5-20 configs) | YAML + Pydantic validation |
| Large project (20+ configs) | Environment-specific configs |
| Multi-tenant SaaS | Database-driven |
| Frequently changing | YAML or database |
| Type safety critical | Pydantic models |

## Common Pitfalls

❌ **DON'T:**
- Scatter configuration across multiple files
- Mix configuration with business logic
- Hardcode values in classes
- Use mutable defaults (e.g., `def func(config={})`)
- Skip validation

✅ **DO:**
- Use a single source of truth
- Version control your configs
- Validate configuration on startup
- Document configuration options
- Provide sensible defaults
- Use type hints and validation

## Example: Adding a New Section Type

### Current Project (Config-Driven Approach)

```python
# Step 1: Update config.py
SEC_10K_SECTIONS = {
    # ... existing sections
    "part2item9a": "Item 9A. Controls and Procedures",  # NEW
}

# Step 2: (Optional) Add enum for type safety
class SectionIdentifier(Enum):
    # ... existing
    ITEM_9A_CONTROLS = "part2item9a"  # NEW

# Step 3: Use immediately
extractor = SECSectionExtractor()
controls = extractor.extract_section(
    filing,
    SectionIdentifier.ITEM_9A_CONTROLS
)
```

**Time to implement: 2 minutes** ✅

### Without Config Pattern (Hardcoded)

```python
# Step 1: Update extractor.py SECTION_TITLES_10K
# Step 2: Update any other files that reference sections
# Step 3: Update documentation
# Step 4: Update tests
# Step 5: Restart application
```

**Time to implement: 15-30 minutes** ❌

## Conclusion

The current project uses **Pattern 1: Config-Driven Enums**, which is perfect for the current scale. As the project grows, consider migrating to **Pattern 5: Pydantic for Validation** for additional type safety and validation.

**Next steps:**
1. ✅ Continue using centralized config
2. Add environment variable overrides if needed
3. Consider YAML migration when config exceeds 100 lines
4. Add Pydantic validation before production deployment

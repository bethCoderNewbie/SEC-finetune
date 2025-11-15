# Enum & Configuration Management Patterns

## Overview
Best practices for managing enums and configurations in a scalable, maintainable Python project.

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

## Pattern 5: Pydantic for Validation

### ✅ Recommended for: Type-safe, validated configs

**Implementation:**

```python
# src/config_models.py
from pydantic import BaseModel, Field, validator
from typing import Dict, List, Literal
from pathlib import Path

class SECSectionConfig(BaseModel):
    id: str = Field(..., regex=r'^part\d+item\d+[a-z]?$')
    title: str
    extract_by_default: bool = False
    priority: int = Field(default=0, ge=0, le=10)

class FormConfig(BaseModel):
    form_type: Literal['10-K', '10-Q', '8-K']
    sections: List[SECSectionConfig]

    @validator('sections')
    def validate_sections(cls, sections):
        ids = [s.id for s in sections]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate section IDs found")
        return sections

class ExtractionConfig(BaseModel):
    sec_forms: Dict[str, FormConfig]
    output_format: Literal['json', 'parquet', 'both'] = 'json'
    min_confidence: float = Field(default=0.7, ge=0.0, le=1.0)

    @validator('output_format')
    def validate_output_format(cls, v):
        valid = ['json', 'parquet', 'both']
        if v not in valid:
            raise ValueError(f"output_format must be one of {valid}")
        return v

# Usage
config = ExtractionConfig.parse_file('config/extraction.yaml')
SEC_10K_SECTIONS = {
    s.id: s.title
    for s in config.sec_forms['10-K'].sections
}
```

**Benefits:**
- ✅ Automatic validation
- ✅ Type safety
- ✅ IDE autocomplete
- ✅ Clear error messages
- ✅ JSON Schema generation

## Hybrid Approach (Recommended)

Combine patterns for maximum flexibility:

```python
# src/config.py
from pathlib import Path
from pydantic import BaseSettings
import os

class Settings(BaseSettings):
    """
    Hierarchical configuration:
    1. YAML files (base configuration)
    2. Environment variables (overrides)
    3. .env file (local development)
    """

    # Base configs from YAML
    sec_10k_sections: Dict[str, str] = None
    sec_10q_sections: Dict[str, str] = None

    # Can be overridden by environment
    extraction_output_format: str = Field(
        default='json',
        env='EXTRACTION_OUTPUT_FORMAT'
    )
    min_extraction_confidence: float = Field(
        default=0.7,
        env='MIN_EXTRACTION_CONFIDENCE'
    )

    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'

    @classmethod
    def load(cls):
        # Load base from YAML
        base_config = load_yaml_config('config/sections.yaml')

        # Create settings with YAML base + env overrides
        return cls(
            sec_10k_sections=base_config['10-K'],
            sec_10q_sections=base_config['10-Q'],
        )

# Initialize
settings = Settings.load()

# Export for backwards compatibility
SEC_10K_SECTIONS = settings.sec_10k_sections
SEC_10Q_SECTIONS = settings.sec_10q_sections
EXTRACTION_OUTPUT_FORMAT = settings.extraction_output_format
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

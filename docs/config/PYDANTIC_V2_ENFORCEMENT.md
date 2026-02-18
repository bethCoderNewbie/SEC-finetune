# Pydantic v2 Enforcement Guide

## 🔒 Policy: Pydantic 2.12.4+ Mandatory

**This project REQUIRES Pydantic v2 (version 2.12.4 or later).**

All new and existing code must use Pydantic v2 patterns. Pydantic v1 is deprecated and not supported.

---

## Quick Reference: v1 → v2 Migration

| Category | Pydantic v1 ❌ | Pydantic v2 ✅ |
|----------|---------------|---------------|
| **Imports** | `from pydantic import BaseSettings` | `from pydantic_settings import BaseSettings` |
| | `from pydantic import validator` | `from pydantic import field_validator` |
| | | `from pydantic import model_validator` |
| **Configuration** | `class Config:` inside model | `model_config = ConfigDict(...)` |
| | | `model_config = SettingsConfigDict(...)` |
| **Validators** | `@validator('field')` | `@field_validator('field')` + `@classmethod` |
| | `@root_validator` | `@model_validator(mode='after')` + `@classmethod` |
| **Serialization** | `.dict()` | `.model_dump()` |
| | `.dict(exclude_unset=True)` | `.model_dump(exclude_unset=True)` |
| | `.json()` | `.model_dump_json()` |
| | `.json(indent=2)` | `.model_dump_json(indent=2)` |
| **Parsing** | `.parse_obj(data)` | `.model_validate(data)` |
| | `.parse_raw(json_str)` | `.model_validate_json(json_str)` |
| | `.parse_file(path)` | Use `with open()` + `.model_validate()` |
| **Schema** | `.schema()` | `.model_json_schema()` |
| | `.schema_json()` | `json.dumps(model.model_json_schema())` |
| **Construction** | `.construct()` | `.model_construct()` |
| **Field Validation** | `Field(..., regex='...')` | `Field(..., pattern='...')` |
| | `Field(..., min_length=1)` | `Field(..., min_length=1)` ✅ Same |
| | `Field(..., ge=0, le=100)` | `Field(..., ge=0, le=100)` ✅ Same |

---

## Installation Requirements

### pyproject.toml

Ensure your `pyproject.toml` specifies the correct versions:

```toml
[project]
name = "sec-filing-analyzer"
dependencies = [
    "pydantic>=2.12.4",
    "pydantic-settings>=2.0.0",
    # ... other dependencies
]

[project.optional-dependencies]
dev = [
    "ruff>=0.1.0",  # For linting Pydantic patterns
    "mypy>=1.0.0",  # For type checking
    # ... other dev dependencies
]
```

### Version Verification

Check your installed version:

```bash
python -c "import pydantic; print(f'Pydantic version: {pydantic.__version__}')"
```

Expected output:
```
Pydantic version: 2.12.4 (or higher)
```

---

## Code Examples

### Example 1: Basic Model (BaseModel)

```python
# ✅ CORRECT - Pydantic v2
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import List

class User(BaseModel):
    """User data model"""
    model_config = ConfigDict(str_strip_whitespace=True, frozen=False)

    username: str = Field(..., min_length=3, max_length=50)
    email: str
    age: int = Field(..., ge=0, le=120)
    tags: List[str] = Field(default_factory=list)

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Validate email format"""
        if '@' not in v:
            raise ValueError('Invalid email format')
        return v.lower()

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username is alphanumeric"""
        if not v.isalnum():
            raise ValueError('Username must be alphanumeric')
        return v

# Usage
user = User(username='john123', email='JOHN@EXAMPLE.COM', age=25)
print(user.model_dump())  # ✅ v2 method
print(user.model_dump_json(indent=2))  # ✅ v2 method
```

### Example 2: Settings with Environment Variables

```python
# ✅ CORRECT - Pydantic v2
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal, List

class AppSettings(BaseSettings):
    """Application settings with environment variable support"""
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        env_prefix='APP_',
        case_sensitive=False,
        extra='ignore',
        env_nested_delimiter='__'
    )

    # Basic settings
    app_name: str = Field(default='SEC Filing Analyzer')
    debug: bool = Field(default=False)

    # Database settings (nested)
    database_url: str = Field(default='sqlite:///./data.db')
    database_pool_size: int = Field(default=5, ge=1, le=100)

    # Extraction settings
    output_format: Literal['json', 'parquet', 'both'] = 'json'
    min_confidence: float = Field(default=0.7, ge=0.0, le=1.0)

    # Feature flags
    active_features: List[str] = Field(default_factory=list)

    @field_validator('database_url')
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Validate database URL format"""
        if not v.startswith(('sqlite://', 'postgresql://', 'mysql://')):
            raise ValueError('Invalid database URL scheme')
        return v

# Usage
settings = AppSettings()  # Automatically loads from .env

# Environment variables can override:
# APP_DEBUG=true
# APP_OUTPUT_FORMAT=parquet
# APP_DATABASE__POOL_SIZE=10  # Note: __ for nested delimiter
```

### Example 3: Model Validator (Cross-Field Validation)

```python
# ✅ CORRECT - Pydantic v2
from pydantic import BaseModel, Field, model_validator
from datetime import datetime
from typing import Optional

class DateRange(BaseModel):
    """Date range with validation"""
    start_date: datetime
    end_date: datetime
    description: Optional[str] = None

    @model_validator(mode='after')
    @classmethod
    def validate_date_range(cls, model):
        """Ensure start_date is before end_date"""
        if model.start_date >= model.end_date:
            raise ValueError('start_date must be before end_date')
        return model

    @model_validator(mode='after')
    @classmethod
    def add_default_description(cls, model):
        """Add default description if not provided"""
        if model.description is None:
            days = (model.end_date - model.start_date).days
            model.description = f'{days}-day range'
        return model

# Usage
date_range = DateRange(
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 12, 31)
)
print(date_range.description)  # "365-day range"
```

### Example 4: Complex Nested Configuration

```python
# ✅ CORRECT - Pydantic v2
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Dict, List, Literal

class DatabaseConfig(BaseModel):
    """Database configuration section"""
    url: str
    pool_size: int = Field(default=5, ge=1)
    echo: bool = False

class CacheConfig(BaseModel):
    """Cache configuration section"""
    backend: Literal['redis', 'memory'] = 'memory'
    ttl_seconds: int = Field(default=3600, ge=0)
    max_size: int = Field(default=1000, ge=1)

class Settings(BaseSettings):
    """Main application settings"""
    model_config = SettingsConfigDict(
        env_file='.env',
        env_prefix='APP_',
        env_nested_delimiter='__',
        case_sensitive=False
    )

    # Nested configurations
    database: DatabaseConfig = Field(default_factory=lambda: DatabaseConfig(url='sqlite:///./app.db'))
    cache: CacheConfig = Field(default_factory=CacheConfig)

    # Top-level settings
    workers: int = Field(default=4, ge=1, le=16)
    log_level: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR'] = 'INFO'

# Usage
settings = Settings()

# Can override with environment variables:
# APP_DATABASE__URL=postgresql://localhost/mydb
# APP_DATABASE__POOL_SIZE=10
# APP_CACHE__BACKEND=redis
# APP_WORKERS=8
```

---

## Automated Validation

### 1. Ruff Configuration

Add to `pyproject.toml`:

```toml
[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "UP",  # pyupgrade
]

# Custom rules to detect deprecated Pydantic patterns
extend-select = ["RUF"]  # Ruff-specific rules
```

Run ruff:
```bash
ruff check src/ scripts/ --fix
```

### 2. MyPy Type Checking

Add to `pyproject.toml`:

```toml
[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true

# Pydantic plugin for better type checking
plugins = ["pydantic.mypy"]

[tool.pydantic-mypy]
init_forbid_extra = true
init_typed = true
warn_required_dynamic_aliases = true
```

Run mypy:
```bash
mypy src/ scripts/
```

### 3. Pre-Commit Hook

Create `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.8
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: [pydantic>=2.12.4, pydantic-settings>=2.0.0]

  - repo: local
    hooks:
      - id: check-pydantic-v2
        name: Check for deprecated Pydantic v1 patterns
        entry: python scripts/utils/validation/validate_pydantic_v2.py
        language: system
        types: [python]
        pass_filenames: true
```

### 4. Custom Validation Script

Create `scripts/utils/validation/validate_pydantic_v2.py`:

```python
#!/usr/bin/env python3
"""
Validate that code uses Pydantic v2 patterns only.
Checks for deprecated v1 patterns and fails if found.
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple

# Deprecated patterns to detect
DEPRECATED_PATTERNS = [
    (r'from pydantic import BaseSettings', 'Use: from pydantic_settings import BaseSettings'),
    (r'from pydantic import validator\b', 'Use: from pydantic import field_validator'),
    (r'@validator\(', 'Use: @field_validator() with @classmethod'),
    (r'@root_validator\(', 'Use: @model_validator(mode="after") with @classmethod'),
    (r'class Config:', 'Use: model_config = ConfigDict(...) or SettingsConfigDict(...)'),
    (r'\.dict\(\)', 'Use: .model_dump()'),
    (r'\.json\(\)', 'Use: .model_dump_json()'),
    (r'\.parse_obj\(', 'Use: .model_validate('),
    (r'\.parse_raw\(', 'Use: .model_validate_json('),
    (r'\.parse_file\(', 'Use: with open() + .model_validate()'),
    (r'\.schema\(\)', 'Use: .model_json_schema()'),
    (r'\.construct\(', 'Use: .model_construct()'),
    (r'Field\([^)]*regex=', 'Use: Field(..., pattern=...) instead of regex='),
]

def check_file(file_path: Path) -> List[Tuple[int, str, str]]:
    """Check a single file for deprecated patterns."""
    errors = []

    try:
        content = file_path.read_text(encoding='utf-8')
        lines = content.splitlines()

        for line_num, line in enumerate(lines, start=1):
            for pattern, suggestion in DEPRECATED_PATTERNS:
                if re.search(pattern, line):
                    errors.append((line_num, pattern, suggestion))

    except Exception as e:
        print(f"Error reading {file_path}: {e}", file=sys.stderr)

    return errors

def main():
    """Main validation function."""
    if len(sys.argv) < 2:
        print("Usage: validate_pydantic_v2.py <file1> <file2> ...", file=sys.stderr)
        sys.exit(1)

    files_to_check = [Path(f) for f in sys.argv[1:]]
    all_errors = []

    for file_path in files_to_check:
        if not file_path.exists():
            continue

        errors = check_file(file_path)
        if errors:
            all_errors.append((file_path, errors))

    if all_errors:
        print("\n❌ Deprecated Pydantic v1 patterns found:\n", file=sys.stderr)

        for file_path, errors in all_errors:
            print(f"\n{file_path}:", file=sys.stderr)
            for line_num, pattern, suggestion in errors:
                print(f"  Line {line_num}: Found '{pattern}'", file=sys.stderr)
                print(f"    → {suggestion}", file=sys.stderr)

        print("\n⚠️  All code must use Pydantic v2 patterns.", file=sys.stderr)
        print("📖 See docs/PYDANTIC_V2_ENFORCEMENT.md for migration guide.\n", file=sys.stderr)
        sys.exit(1)

    print("✅ All files use Pydantic v2 patterns correctly.", file=sys.stderr)
    sys.exit(0)

if __name__ == '__main__':
    main()
```

Make it executable:
```bash
chmod +x scripts/utils/validation/validate_pydantic_v2.py
```

### 5. CI/CD Integration

Add to `.github/workflows/validate.yml`:

```yaml
name: Validate Code Quality

on: [push, pull_request]

jobs:
  validate-pydantic:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install pydantic>=2.12.4 pydantic-settings>=2.0.0
          pip install ruff mypy

      - name: Check Pydantic version
        run: |
          python -c "import pydantic; print(f'Pydantic: {pydantic.__version__}')"
          python -c "import pydantic; assert pydantic.__version__ >= '2.12.4', 'Pydantic must be >= 2.12.4'"

      - name: Validate Pydantic v2 patterns
        run: |
          python scripts/utils/validation/validate_pydantic_v2.py $(find src scripts -name "*.py")

      - name: Run ruff
        run: ruff check src/ scripts/

      - name: Run mypy
        run: mypy src/ scripts/
```

---

## Migration Checklist

When updating existing code or writing new code:

### For New Code

- [ ] Import from correct modules (`pydantic`, `pydantic_settings`)
- [ ] Use `model_config = ConfigDict(...)` or `SettingsConfigDict(...)`
- [ ] Use `@field_validator` with `@classmethod` for field validation
- [ ] Use `@model_validator(mode='after')` with `@classmethod` for model validation
- [ ] Use `.model_dump()` for dictionary serialization
- [ ] Use `.model_dump_json()` for JSON serialization
- [ ] Use `.model_validate()` for object parsing
- [ ] Use `Field(..., pattern='...')` not `regex='...'`
- [ ] Add type hints to all validators
- [ ] Document with docstrings

### For Existing Code

- [ ] Check Pydantic version: `python -c "import pydantic; print(pydantic.__version__)"`
- [ ] Update imports
- [ ] Replace `class Config:` with `model_config`
- [ ] Replace `@validator` with `@field_validator`
- [ ] Replace `@root_validator` with `@model_validator`
- [ ] Replace all deprecated methods (`.dict()`, `.json()`, etc.)
- [ ] Replace `regex=` with `pattern=`
- [ ] Add `@classmethod` to all validators
- [ ] Run validation script
- [ ] Run tests to ensure behavior unchanged

---

## Testing

### Test Pydantic Models

```python
# tests/test_models.py
import pytest
from pydantic import ValidationError
from src.config import Settings

def test_settings_default_values():
    """Test that settings have correct defaults"""
    settings = Settings()
    assert settings.extraction_output_format == 'json'
    assert settings.min_extraction_confidence == 0.7

def test_settings_validation():
    """Test that settings validate correctly"""
    with pytest.raises(ValidationError) as exc_info:
        Settings(min_extraction_confidence=1.5)  # Invalid: > 1.0

    assert 'min_extraction_confidence' in str(exc_info.value)

def test_settings_serialization():
    """Test v2 serialization methods"""
    settings = Settings()

    # Test model_dump
    data = settings.model_dump()
    assert isinstance(data, dict)

    # Test model_dump_json
    json_str = settings.model_dump_json()
    assert isinstance(json_str, str)

    # Test model_validate
    settings_copy = Settings.model_validate(data)
    assert settings_copy.extraction_output_format == settings.extraction_output_format
```

Run tests:
```bash
pytest tests/ -v
```

---

## Resources

- **Official Pydantic v2 Docs**: https://docs.pydantic.dev/latest/
- **Migration Guide**: https://docs.pydantic.dev/latest/migration/
- **Pydantic Settings**: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- **Validators**: https://docs.pydantic.dev/latest/concepts/validators/
- **Configuration**: https://docs.pydantic.dev/latest/api/config/

---

## Support

If you encounter issues with Pydantic v2 migration:

1. Check the official migration guide: https://docs.pydantic.dev/latest/migration/
2. Review examples in `src/config.py` and `src/features/dictionaries/schemas.py`
3. Run the validation script: `python scripts/validate_pydantic_v2.py <file>`
4. Check the project's `docs/ENUM_CONFIG_PATTERNS.md` for patterns

---

## Summary

✅ **DO:**
- Use Pydantic v2.12.4+
- Use `model_config = ConfigDict(...)` or `SettingsConfigDict(...)`
- Use `@field_validator` and `@model_validator` with `@classmethod`
- Use `.model_dump()`, `.model_dump_json()`, `.model_validate()`
- Run automated validation before committing
- Add type hints to all validators

❌ **DON'T:**
- Use any Pydantic v1 patterns
- Import `BaseSettings` from `pydantic` (use `pydantic_settings`)
- Use `@validator` or `@root_validator`
- Use `.dict()`, `.json()`, `.parse_obj()`, etc.
- Skip validation checks
- Commit code without running tests

**Remember**: This project enforces Pydantic v2 standards. All code must comply.

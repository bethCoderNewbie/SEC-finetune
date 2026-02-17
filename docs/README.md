# Documentation Index

This directory contains comprehensive documentation for the SEC Filing Analyzer project.

## 📚 Available Documentation

### 🚀 Implementation Reports

**[implementation/](implementation/)** - Pipeline optimization implementation reports
- **[PHASE1_IMPLEMENTATION_REPORT.md](implementation/PHASE1_IMPLEMENTATION_REPORT.md)** - Memory-aware resource allocation
- **[PHASE2_TEST_REPORT.md](implementation/PHASE2_TEST_REPORT.md)** - Global worker pattern testing
- **[PHASE1_IMPLEMENTATION_SUMMARY.md](implementation/PHASE1_IMPLEMENTATION_SUMMARY.md)** - Phase 1 summary

### 🔧 Setup & Operations

**[setup/](setup/)** - Installation and operational documentation
- **[SETUP_COMPLETE.md](setup/SETUP_COMPLETE.md)** - Setup completion checklist
- **[RUN_SCRIPTS.md](setup/RUN_SCRIPTS.md)** - Script execution guide

### 📝 Project Documentation

- **[CHANGES.md](CHANGES.md)** - Project changelog
- **[PREPROCESSING_TIMEOUT_SUMMARY.md](PREPROCESSING_TIMEOUT_SUMMARY.md)** - Preprocessing pipeline analysis

### Configuration & Best Practices

1. **[PYDANTIC_V2_ENFORCEMENT.md](PYDANTIC_V2_ENFORCEMENT.md)** 🔒 **REQUIRED READING**
   - **Mandatory Pydantic v2.12.4+ enforcement policy**
   - Complete v1 → v2 migration guide with examples
   - Automated validation tools and scripts
   - Pre-commit hooks and CI/CD integration
   - Code review checklist

2. **[ENUM_CONFIG_PATTERNS.md](ENUM_CONFIG_PATTERNS.md)**
   - Best practices for configuration management
   - Multiple configuration patterns (config-driven, YAML-based, database-driven)
   - Updated with Pydantic v2 patterns only
   - Hybrid approaches combining multiple strategies

3. **[CONFIG_MIGRATION_GUIDE.md](CONFIG_MIGRATION_GUIDE.md)**
   - Guide for migrating configuration systems
   - Step-by-step migration instructions
   - Backward compatibility strategies

## 🔒 Pydantic v2 Enforcement

### Quick Start

**All code in this project MUST use Pydantic v2.12.4+**

#### Verify Your Installation
```bash
python -c "import pydantic; print(f'Pydantic: {pydantic.__version__}')"
# Expected: Pydantic: 2.12.4 (or higher)
```

#### Validate Your Code
```bash
# Check specific files
python scripts/utils/validation/validate_pydantic_v2.py src/config.py

# Check all Python files
python scripts/utils/validation/validate_pydantic_v2.py $(find src -name "*.py")
```

#### Quick Reference: v1 → v2

| Old (v1) ❌ | New (v2) ✅ |
|------------|-----------|
| `from pydantic import BaseSettings` | `from pydantic_settings import BaseSettings` |
| `@validator` | `@field_validator` + `@classmethod` |
| `class Config:` | `model_config = ConfigDict(...)` |
| `.dict()` | `.model_dump()` |
| `.json()` | `.model_dump_json()` |
| `.parse_obj()` | `.model_validate()` |

**See [PYDANTIC_V2_ENFORCEMENT.md](PYDANTIC_V2_ENFORCEMENT.md) for complete details.**

## 📖 Usage Examples

### Example 1: Basic Pydantic v2 Model

```python
from pydantic import BaseModel, Field, field_validator, ConfigDict

class User(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=1)
    email: str
    age: int = Field(..., ge=0, le=120)

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        if '@' not in v:
            raise ValueError('Invalid email')
        return v.lower()
```

### Example 2: Settings with Environment Variables

```python
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        env_prefix='APP_',
        case_sensitive=False
    )

    database_url: str = Field(default='sqlite:///./app.db')
    debug: bool = False
```

**See [PYDANTIC_V2_ENFORCEMENT.md](PYDANTIC_V2_ENFORCEMENT.md) for more examples.**

## 🛠️ Development Tools

### Validation Script

Located at: `scripts/utils/validation/validate_pydantic_v2.py`

**Usage:**
```bash
# Validate specific files
python scripts/utils/validation/validate_pydantic_v2.py src/config.py src/models.py

# Validate with verbose output
python scripts/utils/validation/validate_pydantic_v2.py src/*.py --verbose

# Quiet mode (only show errors)
python scripts/utils/validation/validate_pydantic_v2.py src/*.py --quiet
```

### Pre-Commit Hooks

To enable automated validation before commits:

1. Install pre-commit:
   ```bash
   pip install pre-commit
   ```

2. Create `.pre-commit-config.yaml` (see [PYDANTIC_V2_ENFORCEMENT.md](PYDANTIC_V2_ENFORCEMENT.md#3-pre-commit-hook))

3. Install hooks:
   ```bash
   pre-commit install
   ```

### Linting and Type Checking

```bash
# Run ruff linter
ruff check src/ scripts/ --fix

# Run mypy type checker (with Pydantic plugin)
mypy src/ scripts/

# Run both
ruff check src/ && mypy src/
```

## ✅ Code Review Checklist

Before submitting code for review, ensure:

- [ ] Using Pydantic v2.12.4 or later
- [ ] All imports from correct v2 modules (`pydantic`, `pydantic_settings`)
- [ ] All models use `model_config = ConfigDict(...)` or `SettingsConfigDict(...)`
- [ ] All validators use `@field_validator` or `@model_validator` with `@classmethod`
- [ ] All serialization uses `.model_dump()` and `.model_dump_json()`
- [ ] All parsing uses `.model_validate()` and `.model_validate_json()`
- [ ] No deprecated v1 patterns in code
- [ ] Validation script passes: `python scripts/utils/validation/validate_pydantic_v2.py <your_files>`
- [ ] Type checking passes: `mypy <your_files>`
- [ ] Linting passes: `ruff check <your_files>`

## 📊 Project Configuration Architecture

The project uses a sophisticated multi-layer configuration system:

```
Layer 1: YAML Defaults
    ↓ (configs/config.yaml, configs/features/sentiment.yaml)
Layer 2: Pydantic Settings Models
    ↓ (src/config.py with model_config = SettingsConfigDict)
Layer 3: Environment Variables
    ↓ (.env file or system environment variables)
Layer 4: Legacy Exports
    ↓ (Backward compatibility at module level)
```

**Key Files:**
- `src/config.py` - Main configuration module (15 Pydantic models)
- `src/features/dictionaries/schemas.py` - Data models (3 Pydantic models)
- `configs/config.yaml` - Default configuration values
- `configs/features/sentiment.yaml` - Sentiment analysis configuration

## 🚀 Getting Started

### For New Developers

1. **Read the enforcement guide:**
   - [PYDANTIC_V2_ENFORCEMENT.md](PYDANTIC_V2_ENFORCEMENT.md)

2. **Review existing code examples:**
   - `src/config.py` - Settings models with environment variable support
   - `src/features/dictionaries/schemas.py` - Data models with validators

3. **Set up development environment:**
   ```bash
   # Install with dev dependencies
   pip install -e ".[dev]"

   # Verify Pydantic version
   python -c "import pydantic; print(pydantic.__version__)"

   # Run validation on existing code
   python scripts/utils/validation/validate_pydantic_v2.py src/config.py
   ```

4. **Configure your editor:**
   - Enable mypy for type checking
   - Install Pydantic extension (if available for your IDE)
   - Enable automatic formatting with Black/Ruff

### For Code Reviewers

1. **Check Pydantic version compliance:**
   ```bash
   python scripts/utils/validation/validate_pydantic_v2.py <changed_files>
   ```

2. **Verify type checking:**
   ```bash
   mypy <changed_files>
   ```

3. **Review against checklist:**
   - See "Code Review Checklist" above

## 📝 Contributing

When adding new configuration or data models:

1. **Always use Pydantic v2 patterns** - See [PYDANTIC_V2_ENFORCEMENT.md](PYDANTIC_V2_ENFORCEMENT.md)
2. **Add type hints** - All fields and validators must be typed
3. **Add docstrings** - Document models and validators
4. **Add validation** - Use `@field_validator` for field-level validation
5. **Add tests** - Test model validation and serialization
6. **Run validation** - `python scripts/utils/validation/validate_pydantic_v2.py <your_file>`

## 🔗 Additional Resources

- **Pydantic v2 Documentation:** https://docs.pydantic.dev/latest/
- **Migration Guide:** https://docs.pydantic.dev/latest/migration/
- **Pydantic Settings:** https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- **Validators:** https://docs.pydantic.dev/latest/concepts/validators/

## ❓ FAQ

### Q: Why is Pydantic v2 mandatory?
**A:** Pydantic v2 provides better performance, improved type safety, clearer configuration patterns, and is the actively maintained version. v1 is deprecated and will not receive updates.

### Q: Can I use Pydantic v1 for legacy code?
**A:** No. All code must be migrated to v2. Use the migration guide in [PYDANTIC_V2_ENFORCEMENT.md](PYDANTIC_V2_ENFORCEMENT.md).

### Q: How do I migrate existing v1 code?
**A:** Follow the comprehensive migration guide in [PYDANTIC_V2_ENFORCEMENT.md](PYDANTIC_V2_ENFORCEMENT.md), which includes automated detection and step-by-step instructions.

### Q: What if the validation script fails on my code?
**A:** The script will show exactly which deprecated patterns were found and suggest replacements. Fix each issue according to the suggestions.

### Q: How do I add environment variable support to my model?
**A:** Use `BaseSettings` with `model_config = SettingsConfigDict(env_prefix='YOUR_PREFIX_')`. See examples in `src/config.py`.

## 📧 Support

For questions or issues:
1. Check this documentation first
2. Review examples in `src/config.py` and `src/features/dictionaries/schemas.py`
3. Run validation script to identify specific issues
4. Review the official Pydantic v2 documentation

---

**Last Updated:** 2025-11-17
**Pydantic Version Required:** 2.12.4+
**Status:** ✅ All project code compliant with Pydantic v2

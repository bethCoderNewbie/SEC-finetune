# Validation Tools

This directory contains code quality validation tools to enforce project standards.

## 🔒 Pydantic v2 Enforcement

### validate_pydantic_v2.py

Automated validation tool to enforce Pydantic v2.12.4+ patterns across the codebase.

**Purpose:**
- Detect deprecated Pydantic v1 patterns in Python code
- Enforce Pydantic v2.12.4+ standards
- Prevent introduction of legacy code patterns
- Can be integrated with pre-commit hooks and CI/CD pipelines

**Usage:**

```bash
# Validate specific files
python scripts/utils/validation/validate_pydantic_v2.py src/config.py

# Validate multiple files
python scripts/utils/validation/validate_pydantic_v2.py src/config.py src/models.py

# Validate all Python files in a directory
python scripts/utils/validation/validate_pydantic_v2.py $(find src -name "*.py")

# Verbose mode (shows all files being checked)
python scripts/utils/validation/validate_pydantic_v2.py src/*.py --verbose

# Quiet mode (only show errors)
python scripts/utils/validation/validate_pydantic_v2.py src/*.py --quiet
```

**Exit Codes:**
- `0`: All files pass validation
- `1`: Deprecated patterns found

**Detected Patterns:**

The script detects these deprecated Pydantic v1 patterns:

| Deprecated Pattern (v1) | Required Pattern (v2) |
|------------------------|----------------------|
| `from pydantic import BaseSettings` | `from pydantic_settings import BaseSettings` |
| `@validator(...)` | `@field_validator(...)` with `@classmethod` |
| `@root_validator(...)` | `@model_validator(mode='after')` with `@classmethod` |
| `class Config:` | `model_config = ConfigDict(...)` |
| `.dict()` | `.model_dump()` |
| `.json()` | `.model_dump_json()` |
| `.parse_obj()` | `.model_validate()` |
| `.parse_raw()` | `.model_validate_json()` |
| `.parse_file()` | Use `with open()` + `.model_validate()` |
| `.schema()` | `.model_json_schema()` |
| `Field(..., regex=...)` | `Field(..., pattern=...)` |

**Example Output:**

```bash
$ python scripts/utils/validation/validate_pydantic_v2.py src/old_code.py

================================================================================
❌ DEPRECATED PYDANTIC v1 PATTERNS FOUND
================================================================================

📄 src/old_code.py:
  Line 5:
    Code: from pydantic import BaseSettings
    ❌ Found deprecated pattern
    ✅ Use: from pydantic_settings import BaseSettings

  Line 15:
    Code: @validator('email')
    ❌ Found deprecated pattern
    ✅ Use: @field_validator() with @classmethod decorator

================================================================================
📊 Summary:
   Files checked: 1
   Files with errors: 1
   Total errors: 2
================================================================================

⚠️  All code must use Pydantic v2 patterns.
📖 See docs/PYDANTIC_V2_ENFORCEMENT.md for migration guide.
```

**Integration:**

See `docs/PYDANTIC_V2_ENFORCEMENT.md` for:
- Pre-commit hook setup
- CI/CD integration examples
- Complete migration guide
- Code review checklist

## Adding New Validation Tools

When adding new validation scripts:

1. **Naming Convention**: Use descriptive names like `validate_<aspect>.py`
2. **Documentation**: Include comprehensive docstrings and usage examples
3. **Exit Codes**: Use `0` for success, `1` for failures
4. **Output**: Provide clear, actionable error messages
5. **CLI**: Support command-line arguments with `argparse`
6. **Testing**: Test validation script on known good/bad examples

## Best Practices

- Run validation tools before committing code
- Integrate validation into your IDE/editor workflow
- Use pre-commit hooks for automatic validation
- Include validation in CI/CD pipelines
- Keep validation scripts fast and focused

## Related Documentation

- **docs/PYDANTIC_V2_ENFORCEMENT.md** - Complete Pydantic v2 enforcement guide
- **docs/ENUM_CONFIG_PATTERNS.md** - Configuration patterns with v2 examples
- **docs/README.md** - Documentation index with quick reference

## Future Validation Tools

Planned additions:
- `validate_config_schema.py` - Validate configuration file schemas
- `validate_data_schema.py` - Validate data file formats
- `validate_imports.py` - Check import organization and dependencies
- `validate_docstrings.py` - Ensure comprehensive documentation
- `validate_type_hints.py` - Verify type annotation coverage

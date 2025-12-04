# Code Quality: Pylint & Flake8 Fixes

**Date:** 2025-12-03
**Files:** `parser.py`, `segmenter.py`, `test_parser_section_recall.py`

## Takeaways

### parser.py (8.47 -> 9.80)
- **Broad exceptions** - Changed `except Exception` to specific types (`AttributeError, TypeError, ValueError`)
- **Pydantic false positives** - `no-member` errors for `settings.paths.*` are false positives; use `# pylint: disable=no-member`
- **Unnecessary else** - Remove `else`/`elif` after `return` statements
- **Redundant imports** - Don't re-import `re` inside functions when already at module level

### segmenter.py (8.76 -> 9.93)
- **Unused imports** - Removed `import numpy as np` (not used)
- **Line length** - Split long lines, especially default parameter assignments
- **Comment spacing** - Two spaces before inline `#` comments

### test_parser_section_recall.py (9.34 -> 9.65)
- **Import order** - Standard library first, then third-party, then local
- **Late imports** - Use `# noqa: E402` when imports must come after `sys.path` modification
- **Encoding** - Always specify `encoding='utf-8'` in `open()` calls

## Acceptable Suppressions

| Pattern | Reason |
|---------|--------|
| `too-few-public-methods` | Single-purpose classes are valid design |
| `too-many-arguments` | Clear signatures > config objects for simple cases |
| `broad-exception-caught` in tests | Tests need to catch all failures for reporting |
| `redefined-outer-name` in `__main__` | Standard pattern, renaming reduces clarity |

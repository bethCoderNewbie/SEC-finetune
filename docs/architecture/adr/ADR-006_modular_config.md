# ADR-006: Decompose Monolithic `src/config.py` into 16 Domain Modules

**Status:** Accepted
**Date:** 2025-12-03
**Author:** @bethCoderNewbie

---

## Context

`src/config.py` had grown to **1,126 lines** covering paths, model names, preprocessing parameters,
extraction config, feature engineering settings, and test fixtures — all in one file.

Problems:
- Every module that needed one setting imported the entire file, loading all config (including
  heavy `yaml.load` calls) even when only `paths.raw_data_dir` was needed
- Module-level I/O (5 `yaml.load` calls at import time) slowed test collection by ~1.5 seconds
- The YAML loader was duplicated 5 times across the file
- Circular import risk: `src/features/` and `src/config.py` imported each other

## Decision

Decompose into **16 domain-specific modules** under `src/config/`:

```
src/config/
├── __init__.py          # Settings aggregate + global `settings` instance
├── _loader.py           # Single cached YAML loader (replaces 5 duplicates)
├── paths.py             # PathsConfig — all project paths
├── models.py            # ModelsConfig — model names
├── preprocessing.py     # PreprocessingConfig
├── extraction.py        # ExtractionConfig
├── sec_parser.py        # SecParserConfig
├── sec_sections.py      # Section identifiers
├── run_context.py       # RunContext (git SHA, timestamps)
├── naming.py            # File naming conventions
├── qa_validation.py     # HealthCheckValidator + ThresholdRegistry
├── testing.py           # TestingConfig
├── legacy.py            # DeprecationWarning shims for old import paths
└── features/
    ├── sentiment.py
    ├── topic_modeling.py
    ├── readability.py
    └── risk_analysis.py
```

Each module uses `pydantic-settings` `BaseSettings` with a unique `env_prefix`
(e.g., `PATHS_`, `MODELS_`) so any setting can be overridden by environment variable.

The `legacy.py` module re-exports old names with `DeprecationWarning` — no breaking changes
for existing scripts.

## Consequences

**Positive:**
- Average module: ~65 lines (vs. 1,126 lines before)
- YAML loaded once and cached via `functools.lru_cache` in `_loader.py` — 5 → 1 I/O calls
- Module-level I/O eliminated — all config is lazy-loaded on first access
- Each config module is independently testable

**Negative:**
- 16 files to navigate instead of 1 — new contributors must learn the module map
- `legacy.py` shims add a permanent maintenance burden (must track all old import paths)

## Supersedes

Monolithic `src/config.py` (archived; removed from active codebase).

## References

- `src/config/` — all 16 modules
- `src/config/legacy.py` — backward-compat shims
- CHANGELOG: 2025-12-03

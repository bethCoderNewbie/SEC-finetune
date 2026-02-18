# ADR-001: Enforce Pydantic V2 for All Data Schemas

**Status:** Accepted
**Date:** 2025-11-17 (strengthened 2025-12-03)
**Author:** @bethCoderNewbie

---

## Context

The original pipeline used raw Python `dict` objects and `@dataclass` for passing data between
pipeline stages (`ParsedFiling`, `ExtractedSection`, `SegmentedRisks`). This caused:

- Silent `KeyError` and `AttributeError` failures when EDGAR HTML contained unexpected metadata layouts
- No validation at stage boundaries — corrupt data propagated through the full pipeline before
  surfacing as an error in the segmenter
- No IDE autocompletion or type safety on consumed fields
- A monolithic 1,126-line `src/config.py` with no enforced structure

## Decision

All data models and configuration objects will use **Pydantic V2** (`pydantic>=2.12.4`).

Specific rules:

- `ConfigDict(validate_assignment=True)` on all pipeline models (`ParsedFiling`, `ExtractedSection`,
  `SegmentedRisks`, `RiskSegment`, `PipelineConfig`)
- `ConfigDict(extra='forbid')` on `PipelineConfig` — unknown fields raise `ValidationError`
- Configuration uses `pydantic-settings` `BaseSettings` with per-module `env_prefix` for all 16
  config modules (`src/config/`)
- Validation occurs at the **Interim stage** (pipeline stage boundaries), not on raw HTML

## Consequences

**Positive:**
- Rust-based V2 core is ~5–50× faster than V1 for large model validation
- `model_dump()` / `model_validate()` provide clean serialization for JSON output and checkpoint loading
- IDE autocompletion on all pipeline objects reduces development errors
- `extra='forbid'` on `PipelineConfig` prevents silent misconfiguration

**Negative:**
- Strict types mean dirty EDGAR metadata (missing CIK, null SIC code) raises `ValidationError`
  instead of silently defaulting — requires robust `DeadLetterQueue` handling
- Pydantic V2 API is not backward-compatible with V1; all V1 patterns (`validator`, `@root_validator`,
  `.dict()`) are deprecated and flagged by `ruff`

## Supersedes

Nothing — first ADR on this topic.

## References

- `src/config/` — 16 modular `BaseSettings` subclasses
- `src/preprocessing/models/` — `ParsedFiling`, `ExtractedSection`, `SegmentedRisks`, `RiskSegment`
- `docs/config/PYDANTIC_V2_ENFORCEMENT.md` — migration guide
- CHANGELOG: 2025-11-17, 2025-12-03

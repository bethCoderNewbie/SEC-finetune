---
title: "Pipeline Inconsistencies & Single Source of Truth Design"
date: "2026-02-22T20:14:46-06:00"
commit: 15670ba
branch: main
author: claude-sonnet-4-6
scope: src/preprocessing/, scripts/data_preprocessing/, src/utils/, src/config/
---

# Pipeline Inconsistencies & Single Source of Truth Design

## Problem Statement

The preprocessing pipeline has four categories of hardcoded strings scattered across 15+ files.
There is no single authoritative location for output filename suffixes, pipeline step names,
the embedding model name, or form type literals. This causes silent bugs (wrong suffix in
`pipeline.py`), inconsistent telemetry (tracker step names differ between the two pipeline
implementations), and fragile maintenance (renaming a suffix requires a grep-and-replace).

---

## Inconsistency 1 — Output Filename Suffixes (P0)

### Current state: 3 different suffix sets across 2 pipeline implementations

| Suffix | Used in | Correct? |
|--------|---------|----------|
| `_segmented_risks.json` | `run_preprocessing_pipeline.py`, `__main__.py`, `batch_extract.py`, `src/config/testing.py` | **Yes** |
| `_segmented.json` | `src/preprocessing/pipeline.py:249`, `src/utils/resume.py` default, `pipeline.py:619` | **No** — diverges from the rest |
| `_extracted_risks.json` | both pipeline implementations | Yes |
| `_cleaned_risks.json` | `run_preprocessing_pipeline.py` only | Yes |
| `_parsed.json` | `parser.py`, `batch_parse.py`, `pipeline.py:407` | Yes |

**Active bug:** `SECPreprocessingPipeline.process_batch()` (`pipeline.py:249`) writes
`{stem}_segmented.json`, so `ResumeFilter` in the same class (`pipeline.py:619`) checks for
`_segmented.json`. But everything else in the codebase expects `_segmented_risks.json`.
This means `pipeline.py`'s resume logic would never match files written by other pipeline paths.

### Where suffixes are defined today

Nowhere. They are inline f-strings everywhere:
- `pipeline.py:183`: `f"{file_path.stem}_extracted_risks.json"` (×2 in same file)
- `pipeline.py:249`: `f"{file_path.stem}_segmented.json"` ← wrong
- `run_preprocessing_pipeline.py:271`: `f"{input_file.stem}_segmented_risks.json"` (×4)
- `src/utils/resume.py:15,53`: default parameter `"_segmented.json"` ← wrong default

---

## Inconsistency 2 — ResourceTracker Step Names (P1)

### Current state: two naming conventions in parallel

| Step | `src/preprocessing/pipeline.py` | `scripts/.../run_preprocessing_pipeline.py` |
|------|----------------------------------|---------------------------------------------|
| Parsing | `"parser"` (line 151) | `"parse"` (line 400) |
| Extraction | `"extractor"` (line 166) | `"extract"` (line 408) |
| Cleaning | `"cleaner"` (line 189) | `"clean"` (line 433) |
| Segmentation | `"segmenter"` (line 203) | `"segment"` (line 464) |
| Sentiment | *(not used)* | `"sentiment"` (line 490) |

Any downstream consumer of `resource_usage` dicts (reports, dashboards, tests) must
hard-code whichever name it expects, with no guarantee it matches the producer.

---

## Inconsistency 3 — Embedding Model Name (P2)

`"all-MiniLM-L6-v2"` appears in two places as a default string literal:
- `src/preprocessing/segmenter.py:52` — `RiskSegmenter.__init__` parameter default
- `src/preprocessing/pipeline.py:95` — `PipelineConfig.semantic_model_name` default

`src/config/preprocessing.py` already holds `min_segment_length` and `max_segment_length`
(lines 74–78) but has no `semantic_model_name` field. This is the natural home for the model name.

---

## Inconsistency 4 — Form Type String Literals (P2)

`FormType` enum (`src/preprocessing/models/parsing.py:21-24`) already provides canonical values:
```python
class FormType(Enum):
    FORM_10K = "10-K"
    FORM_10Q = "10-Q"
```

Despite this, 40+ call sites compare against raw strings `"10-K"`, `"10-Q"`, `"10K"`.
Notable: `parser.py:342` checks `if form_type == "10K"` (no dash) — a legacy variant that
differs from all other comparisons. If the enum ever changes its `.value`, all raw string
comparisons silently break.

---

## Single Source of Truth Design

### Principle

All pipeline-level string constants live in **one place** that every module imports.
No module should hardcode a suffix, step name, or model name inline.

### Proposed: extend `src/preprocessing/constants.py`

`constants.py` already owns `SectionIdentifier` and all regex patterns. It is the natural
home for two new namespaces:

```python
# src/preprocessing/constants.py (additions)

class OutputSuffix:
    """Canonical file suffixes for every pipeline stage output."""
    PARSED          = "_parsed.json"
    EXTRACTED       = "_extracted_risks.json"
    CLEANED         = "_cleaned_risks.json"
    SEGMENTED       = "_segmented_risks.json"   # was "_segmented.json" in pipeline.py — fix here


class PipelineStep:
    """Canonical ResourceTracker step names (noun form, no -er suffix)."""
    PARSE     = "parse"
    EXTRACT   = "extract"
    CLEAN     = "clean"
    SEGMENT   = "segment"
    SENTIMENT = "sentiment"
```

### Proposed: add model name to `src/config/preprocessing.py`

```python
# src/config/preprocessing.py (addition)
semantic_model_name: str = Field(
    default_factory=lambda: _get_config().get('semantic_model_name', 'all-MiniLM-L6-v2'),
    description="SentenceTransformer model used for semantic segmentation"
)
```

`RiskSegmenter` and `PipelineConfig` both read from `settings.preprocessing.semantic_model_name`
instead of duplicating the string.

### Form types: enforce enum at boundary, not inside

`FormType` already exists. The fix is to normalize `form_type: str` to `FormType` at each
public entry point (`parse_filing`, `process_filing`, `process_batch`) once, then pass the
enum internally. No module below the entry point should compare against a raw string.

---

## Files Requiring Changes

| File | Change |
|------|--------|
| `src/preprocessing/constants.py` | Add `OutputSuffix` and `PipelineStep` classes |
| `src/config/preprocessing.py` | Add `semantic_model_name` field |
| `src/preprocessing/pipeline.py` | Replace all suffix strings with `OutputSuffix.*`; replace step strings with `PipelineStep.*`; fix `_segmented.json` → `OutputSuffix.SEGMENTED`; read model name from `settings.preprocessing` |
| `src/preprocessing/segmenter.py` | Replace `"all-MiniLM-L6-v2"` default with `settings.preprocessing.semantic_model_name` |
| `scripts/data_preprocessing/run_preprocessing_pipeline.py` | Replace suffix f-strings with `OutputSuffix.*`; replace step strings with `PipelineStep.*` |
| `src/utils/resume.py` | Change default `output_suffix="_segmented.json"` to `OutputSuffix.SEGMENTED` (import from constants) |
| `src/preprocessing/__main__.py` | Replace suffix strings with `OutputSuffix.*` |
| `scripts/data_preprocessing/batch_extract.py` | Replace `_extracted_risks.json` strings with `OutputSuffix.EXTRACTED` |

---

## What This Does NOT Change

- `SectionIdentifier` enum — already correct single source of truth
- `FormType` enum — already correct; only call-site normalization needed
- `PAGE_HEADER_PATTERN` and other regex constants — already in `constants.py`
- Actual file content or pipeline logic — no behavioral changes, only constant substitution

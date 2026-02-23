---
date: 2026-02-23T15:11:55-06:00
researcher: bethCoderNewbie
git_commit: 8c9b470
branch: main
repository: SEC-finetune
status: completed
last_updated: 2026-02-23
last_updated_by: bethCoderNewbie
---

# Multi-Section Extraction — Implementation Plan

## Problem Statement

The pipeline hardcodes **Item 1A (Risk Factors)** at every entry point despite the config
already defining 7 10-K and 3 10-Q sections in `settings.sec_sections`, and the extractor
and segmenter being fully generic. The `extraction.default_sections` config key exists but
is never read.

Each filing is parsed once per run, but only a single section is extracted, cleaned, and
segmented. Training data coverage is therefore limited to one section type regardless of
what the config defines.

---

## Desired End State

Every filing is parsed **once**. All sections defined in `settings.sec_sections` are
extracted in a single pass. Sections not present in the filing are silently skipped.

```
run_dir/
├── parsed/
│   └── AAPL_10K_2021_parsed.json
├── extracted/
│   ├── AAPL_10K_2021_part1item1_extracted.json
│   ├── AAPL_10K_2021_part1item1_cleaned.json
│   ├── AAPL_10K_2021_part1item1a_extracted.json
│   ├── AAPL_10K_2021_part1item1a_cleaned.json
│   └── ...  (one pair per section found)
├── AAPL_10K_2021_part1item1_segmented.json
├── AAPL_10K_2021_part1item1a_segmented.json
├── AAPL_10K_2021_part2item7_segmented.json
└── ...  (one per section found)
```

---

## Anti-Scope

- No changes to `batch_extract.py` or `batch_parse.py`
- No changes to `extractor.py` or `segmenter.py` (already generic)
- No changes to `configs/config.yaml` or `src/config/extraction.py`
- No test file changes
- No changes to `SectionIdentifier` enum values or `SECTION_PATTERNS`

---

## Key Insight: Section List from Config

`settings.sec_sections.sections_10k` is a `Dict[str, str]` whose keys are valid
`SectionIdentifier` values:

```python
# Effective defaults loaded from config.yaml sec_sections.10-K:
{
    "part1item1":  "Item 1. Business",
    "part1item1a": "Item 1A. Risk Factors",
    "part1item1b": "Item 1B. Unresolved Staff Comments",
    "part1item1c": "Item 1C. Cybersecurity",
    "part2item7":  "Item 7. Management's Discussion and Analysis",
    "part2item7a": "Item 7A. Quantitative and Qualitative Disclosures About Market Risk",
    "part2item8":  "Item 8. Financial Statements and Supplementary Data",
}

# Effective defaults for 10-Q:
{
    "part1item1":  "Item 1. Financial Statements",
    "part1item2":  "Item 2. Management's Discussion and Analysis",
    "part2item1a": "Item 1A. Risk Factors",
}
```

These keys are passed directly to `SectionIdentifier(section_id)`. No new config is
needed — the existing `sec_sections` config block is the authority for which sections
to extract.

**Helper function** (added to both `pipeline.py` and `run_preprocessing_pipeline.py`):

```python
def _sections_for_form_type(form_type: str) -> List[str]:
    from src.config import settings as _cfg
    if form_type.upper() in ("10-K", "10K"):
        return list(_cfg.sec_sections.sections_10k.keys())
    elif form_type.upper() in ("10-Q", "10Q"):
        return list(_cfg.sec_sections.sections_10q.keys())
    return ["part1item1a"]   # fallback for unknown form types
```

---

## Phase 1 — `src/preprocessing/constants.py`

**Goal:** Add section-ID-stamped filename generators to `OutputSuffix`.

Keep old constants (`EXTRACTED`, `CLEANED`, `SEGMENTED`) intact for backward
compatibility. Add three static methods:

```python
class OutputSuffix:
    PARSED    = "_parsed.json"
    EXTRACTED = "_extracted_risks.json"   # legacy (Risk Factors only)
    CLEANED   = "_cleaned_risks.json"     # legacy
    SEGMENTED = "_segmented_risks.json"   # legacy

    @staticmethod
    def section_extracted(section_id: str) -> str:
        return f"_{section_id}_extracted.json"

    @staticmethod
    def section_cleaned(section_id: str) -> str:
        return f"_{section_id}_cleaned.json"

    @staticmethod
    def section_segmented(section_id: str) -> str:
        return f"_{section_id}_segmented.json"
```

**Rationale:** Static methods rather than f-string literals at call sites so every
output path is derivable from a single import. `section_segmented("part1item1a")`
→ `"_part1item1a_segmented.json"`.

---

## Phase 2 — `src/preprocessing/pipeline.py`

### 2a — Module-level helper

Add `_sections_for_form_type()` after the `logger =` line. Uses a lazy import
(`from src.config import settings as _cfg`) inside the function body to avoid
circular imports at module level.

### 2b — `_process_filing_with_global_workers()`: multi-section loop

**Signature change:**

| Old | New |
|-----|-----|
| `save_output: Optional[Path]` | `output_dir: Optional[Path]` |
| Returns `Optional[SegmentedRisks]` | Returns `Dict[str, Optional[SegmentedRisks]]` |
| `sections` param absent | `sections: Optional[List[str]] = None` |

**Body structure:**

```
if sections is None:
    sections = _sections_for_form_type(form_type)

# Step 1: Parse (once — tracker wraps PipelineStep.PARSE)
parsed = get_worker_parser().parse_filing(...)

# Steps 2-4: Per-section loop
results = {}
for section_id in sections:
    try:
        section_enum = SectionIdentifier(section_id)
    except ValueError:
        logger.warning(...)
        continue

    # 2: Extract
    extracted = get_worker_extractor().extract_section(parsed, section_enum)
    if extracted is None:
        results[section_id] = None
        continue                 # ← silent skip; NOT an error

    # Save extracted intermediate (if intermediates_dir or save_intermediates)
    if ext_dir:
        extracted.save_to_json(ext_dir / (stem + OutputSuffix.section_extracted(section_id)))

    # 3: Clean
    cleaned_text = get_worker_cleaner().clean_text(...)

    # Save cleaned intermediate (if intermediates_dir only)
    if intermediates_dir:
        cleaned_section.save_to_json(ext_dir / (stem + OutputSuffix.section_cleaned(section_id)))

    # 4: Segment
    result = get_worker_segmenter().segment_extracted_section(extracted, cleaned_text=cleaned_text)

    # Save segmented output
    if output_dir:
        result.save_to_json(output_dir / (stem + OutputSuffix.section_segmented(section_id)))

    results[section_id] = result

return results
```

**Key decision — `ext_dir` determination:**
Mirrors the existing pattern: `intermediates_dir / "extracted"` takes precedence;
falls back to `settings.paths.extracted_data_dir` when `save_intermediates=True`
and no `intermediates_dir` is given; `None` otherwise. Cleaned intermediates
are only saved when `intermediates_dir` is set (same as old behaviour).

### 2c — `_process_single_filing_worker()`: aggregate dict result

Old code computed a single `save_output` path and returned a flat `SegmentedRisks`.
New code calls `_process_filing_with_global_workers(output_dir=..., sections=...)` and
aggregates:

```python
successful = {sid: r for sid, r in results.items() if r is not None}
total_segments = sum(len(r) for r in successful.values())

if successful:
    first = next(iter(successful.values()))
    primary_section = next(iter(successful))
    primary_path = output_dir / (stem + OutputSuffix.section_segmented(primary_section))
    return {
        'status': 'success',
        'result': successful,           # Dict[str, SegmentedRisks]
        'num_segments': total_segments,
        'sections_extracted': list(successful.keys()),
        'output_path': str(primary_path),
        'sic_code': first.sic_code,
        'company_name': first.company_name,
        ...
    }
else:
    return {'status': 'warning', 'error': 'No sections extracted from filing', ...}
```

`primary_path` is the path of the first successfully extracted section. It is used by
callers (manifest, progress log) as the canonical output reference.

### 2d — `SECPreprocessingPipeline.process_filing()`: new signature + section loop

**Old signature:**
```python
def process_filing(self, file_path, form_type="10-K",
                   section=SectionIdentifier.ITEM_1A_RISK_FACTORS,
                   save_output=None, overwrite=False,
                   save_intermediates=False, intermediates_dir=None
                   ) -> Optional[SegmentedRisks]:
```

**New signature:**
```python
def process_filing(self, file_path, form_type="10-K",
                   sections: Optional[List[SectionIdentifier]] = None,
                   save_output_dir: Optional[Union[str, Path]] = None,
                   overwrite=False, save_intermediates=False,
                   intermediates_dir=None
                   ) -> Dict[str, Optional[SegmentedRisks]]:
```

Internal: if `sections is None`, call `_sections_for_form_type(form_type)` and map
strings to `SectionIdentifier` enums (skip on `ValueError`). Parse once with
`self.parser`. Loop identical to `_process_filing_with_global_workers` but uses
`self.extractor`, `self.cleaner`, `self.segmenter` instead of worker-pool accessors.

### 2e — `process_risk_factors()`: backward-compat wrapper

Keeps the old signature byte-for-byte. Maps to `process_filing(sections=[section])`.
Saves to the exact legacy path `save_output` if provided (section_segmented would
produce a different name).

```python
def process_risk_factors(self, file_path, form_type="10-K",
                         save_output=None, overwrite=False,
                         save_intermediates=False, intermediates_dir=None
                         ) -> Optional[SegmentedRisks]:
    section = (SectionIdentifier.ITEM_1A_RISK_FACTORS
               if form_type.upper() in ("10-K", "10K")
               else SectionIdentifier.ITEM_1A_RISK_FACTORS_10Q)
    results = self.process_filing(
        file_path, form_type=form_type, sections=[section],
        save_output_dir=Path(save_output).parent if save_output else None,
        overwrite=overwrite, save_intermediates=save_intermediates,
        intermediates_dir=intermediates_dir,
    )
    result = results.get(section.value)
    if result and save_output:
        result.save_to_json(save_output, overwrite=overwrite)   # honour exact path
    return result
```

**Rationale for double-save:** `save_output_dir` writes to
`parent / stem_part1item1a_segmented.json`. The caller may have passed
`out_path = run_dir / "AAPL_10K_2021_segmented_risks.json"` — a different name.
The second `save_to_json` writes to the exact legacy path so no caller breaks.

### 2f — `process_and_validate()`: adapted

```python
# Before
result = self.process_filing(file_path=..., section=section, save_output=None)
if result is None: return None, "FAIL", ...

# After
results = self.process_filing(file_path=..., sections=[section], save_output_dir=None)
result = results.get(section.value)
if result is None: return None, "FAIL", ...
# remainder unchanged — validator still receives a single SegmentedRisks
```

### 2g — `process_batch()`: resume suffix + result flattening

```python
# Resume suffix (was "_segmented.json" — matched old SEGMENTED constant)
resume_filter = ResumeFilter(
    output_dir=Path(output_dir),
    output_suffix=OutputSuffix.section_segmented("part1item1a"),  # "_part1item1a_segmented.json"
)

# Result extraction (was: [r['result'] for r in successful])
# New: flatten per-section dicts into flat List[SegmentedRisks]
results: List[SegmentedRisks] = []
for r in successful:
    if r.get('result'):
        results.extend(r['result'].values())
return results
```

**Rationale for `part1item1a` in resume suffix:** Risk Factors is the highest-priority
section and the one most likely to have been extracted in a previous run. Using it as
the resume sentinel preserves backward compatibility with runs that produced
`*_segmented_risks.json` files only if `process_risk_factors` is also called — but more
importantly, any run that successfully extracted Item 1A will have this file and will be
correctly skipped on resume.

---

## Phase 3 — `scripts/data_preprocessing/run_preprocessing_pipeline.py`

### 3a — `_sections_for_form_type()` at module level

Same implementation as pipeline.py, but uses `settings` directly (already imported at
module level — no lazy import needed).

### 3b — `run_pipeline()`: parse once, section loop

**Return type change:**
```
Old: Tuple[Optional[ParsedFiling], Optional[ExtractedSection],
          Optional[SegmentedRisks], Optional[List]]
New: Tuple[Optional[ParsedFiling], Dict[str, Optional[SegmentedRisks]]]
```

The caller `main()` does not capture the return value, so no downstream breakage.

**Internal structure:**
```
1. Parse once (SECFilingParser) — save to parsed/ if save_intermediates
2. Instantiate extractor, cleaner, segmenter, analyzer once (not per-section)
3. Loop over _sections_for_form_type("10-K"):
   a. extract_section() — skip+record None if not found
   b. Save extracted intermediate to extracted/ if save_intermediates
   c. clean_text() — build cleaned_section ExtractedSection
   d. Save cleaned intermediate to extracted/ if save_intermediates
   e. segment_extracted_section() — skip if 0 segments
   f. extract_features_batch() if analyzer
   g. _build_output_data() — save to dest_dir/{stem}_{section_id}_segmented.json
   h. all_results[section_id] = segmented_risks
4. Print summary: "{found}/{total} sections processed"
5. return (filing, all_results)
```

**Note on form_type:** `run_pipeline()` currently hardcodes `form_type="10-K"` in the
parse call. `_sections_for_form_type("10-K")` is called consistently. No `form_type`
parameter is added to the function; this is in-scope for a future ticket.

### 3c — `process_single_file_fast()`: parse once, section loop

Pattern identical to `run_pipeline()` but uses global workers and ResourceTracker steps.
Early-return-on-single-miss is replaced with continue:

```
# Before: if not risk_section: return {'status': 'warning', ...}
# After:  if not section_result: continue  ← process remaining sections
```

Aggregate after the loop:
```python
if not all_segmented:
    return {'status': 'warning', 'error': 'No sections extracted from filing', ...}

first_result = next(iter(all_segmented.values()))
total_segments = sum(len(r) for r in all_segmented.values())
return {
    'status': 'success',
    'num_segments': total_segments,
    'sections_extracted': list(all_segmented.keys()),
    'output_path': str(first_output_path),
    ...
}
```

### 3d — `run_batch_pipeline()`: resume suffix

```python
# Before
resume_filter = ResumeFilter(output_dir=run_dir, output_suffix="_segmented_risks.json")
# After
resume_filter = ResumeFilter(
    output_dir=run_dir,
    output_suffix=OutputSuffix.section_segmented("part1item1a"),
)
```

---

## Phase 4 — `src/preprocessing/__main__.py`

### 4a — Add `OutputSuffix` import

```python
from .pipeline import SECPreprocessingPipeline
from .constants import OutputSuffix         # ← added
```

### 4b — `_process_one()`: call `process_filing()` multi-section

```python
# Before
out_path = run_dir / f"{file_path.stem}_segmented_risks.json"
result = SECPreprocessingPipeline().process_risk_factors(
    file_path, save_output=out_path, overwrite=True, intermediates_dir=run_dir)
if result:
    return {'status': 'success', 'output_path': str(out_path), ...}

# After
results = SECPreprocessingPipeline().process_filing(
    file_path, save_output_dir=run_dir, overwrite=True, intermediates_dir=run_dir)
successful = {sid: r for sid, r in results.items() if r is not None}
if successful:
    primary_sid = next(iter(successful))
    out_path = run_dir / (file_path.stem + OutputSuffix.section_segmented(primary_sid))
    return {'status': 'success', 'output_path': str(out_path),
            'sections_extracted': list(successful.keys()), ...}
```

### 4c — `_run_single()`: same pattern + updated console output

Console output now shows sections list and total segments instead of single segment
count and single output path:

```
Sections:    ['part1item1', 'part1item1a', 'part2item7']
Segments:    247
Output dir:  data/processed/20260223_151155_preprocessing_8c9b470
```

---

## Invariants Preserved

| Invariant | How preserved |
|-----------|---------------|
| **Rule 1 (ADR-010): never modify HTML before sec-parser** | Unchanged — no HTML manipulation added |
| **Parse-once per filing** | Single `parse_filing()` call before the section loop at all four call sites |
| **Silent skip on missing section** | `extracted is None` → `results[section_id] = None` + `continue`; no exception, no warning (only debug log) |
| **`process_risk_factors()` backward compat** | Identical public signature; re-saves to exact `save_output` path |
| **`process_and_validate()` still returns `SegmentedRisks`** | Extracts single result from dict via `results.get(section.value)` |
| **`process_batch()` return type is `List[SegmentedRisks]`** | Flattens `r['result'].values()` into a flat list |

---

## Files Changed

| File | Lines changed (approx.) | Nature |
|------|------------------------|--------|
| `src/preprocessing/constants.py` | +12 | Add 3 static methods to `OutputSuffix` |
| `src/preprocessing/pipeline.py` | ~825 → ~730 (net) | Refactor — remove dead single-section paths |
| `scripts/data_preprocessing/run_preprocessing_pipeline.py` | ~978 → ~960 | Refactor — section loop replaces single-extract flow |
| `src/preprocessing/__main__.py` | +8 | Import + two function updates |

---

## Verification

```bash
# Single file — library entry point
python -m src.preprocessing data/raw/AAPL_10K_2021.html

RUN=$(ls -t data/processed | grep preprocessing | head -1)

# Expect: one *_segmented.json per section found
ls data/processed/$RUN/*.json | grep segmented

# Expect: extracted/ contains extracted + cleaned files for each section found
ls data/processed/$RUN/extracted/ | head -10

# Expect: parsed/ contains the single parsed JSON
ls data/processed/$RUN/parsed/

# Script entry point
python scripts/data_preprocessing/run_preprocessing_pipeline.py \
  --input data/raw/AAPL_10K_2021.html --no-sentiment

# Confirm backward compat: process_risk_factors still works
python -c "
from src.preprocessing.pipeline import SECPreprocessingPipeline
r = SECPreprocessingPipeline().process_risk_factors('data/raw/AAPL_10K_2021.html')
assert r is not None
print('process_risk_factors OK —', len(r), 'segments')
"
```

**Expected output structure for AAPL_10K_2021.html (10-K, 7 sections attempted):**

| File | Present? |
|------|----------|
| `AAPL_10K_2021_part1item1_segmented.json` | Yes (Business section found) |
| `AAPL_10K_2021_part1item1a_segmented.json` | Yes (Risk Factors found) |
| `AAPL_10K_2021_part1item1b_segmented.json` | Maybe (Unresolved Staff Comments — may be empty) |
| `AAPL_10K_2021_part1item1c_segmented.json` | Maybe (Cybersecurity — added 2023; absent in 2021) |
| `AAPL_10K_2021_part2item7_segmented.json` | Yes (MD&A found) |
| `AAPL_10K_2021_part2item7a_segmented.json` | Maybe |
| `AAPL_10K_2021_part2item8_segmented.json` | Maybe (Financial Statements — may exceed max_length) |

Sections absent from the filing produce no file and no log warning (debug log only).

---

## Test Coverage

No new test files were created (in anti-scope). All 284 existing unit tests pass:

```
tests/unit/preprocessing/   284 passed in 27.32s
```

The existing `test_extractor_unit.py` exercises `extract_section()` generically against
all `SectionIdentifier` values; `test_segmenter_unit.py` tests `segment_extracted_section()`
independent of section type. No regression in existing behaviour.

---

## References

- `src/config/sec_sections.py` — `SecSectionsConfig.sections_10k/sections_10q`
- `src/preprocessing/constants.py:SectionIdentifier` — enum of valid section IDs
- `docs/general/CHANGELOG.md` — 2026-02-23 entry
- ADR-010 — pre-seek architecture (no change from this work)

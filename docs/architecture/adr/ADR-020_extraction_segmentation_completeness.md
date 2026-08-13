# ADR-020: Extraction & Segmentation Completeness Observability

| Field | Value |
|-------|-------|
| **Status** | Accepted |
| **Date** | 2026-08-13 |
| **Author** | bethCoderNewbie (Claude-assisted) |
| **Commit** | 994cc2b (base) |

---

## Context

Six confirmed gaps in the extraction/segmentation pipeline allowed content loss to go undetected. A seventh was a config gap. The gaps were:

1. **No section manifest** — missing sections silently skipped (`pipeline.py:198-200`)
2. **Tables dropped before measurement** — `raw_section_char_count` measured after table exclusion (`extractor.py:467-474`, `pipeline.py:237`)
3. **Segment filtering unaccounted** — `_filter_segments()`, `_merge_short_segments()`, `_split_long_segments()` had zero logging (`segmenter.py:148-156`)
4. **No text coverage ratio** — no code compared `sum(segment.char_count)` vs `cleaned_section_char_count`
5. **"No material change" undetected** — DB column existed (`database.py:58`) but was never set
6. **Cross-ref drops silent** — `_CROSS_REF_DROP_PAT` (`segmenter.py:15-19`) dropped at line 386 with no log
7. **Incomplete 10-K section config** — `configs/config.yaml` listed only 7 of 15 `SectionIdentifier` enum values for 10-K

Without observability at each stage, the G-02 content loss threshold was unenforceable and boilerplate 10-Q filings (those stating "no material changes to risk factors") were indistinguishable from substantive ones.

## Decision

Add additive observability at each pipeline stage using existing infrastructure (metadata dicts, `HealthCheckValidator`, `ThresholdRegistry`, Pydantic models). No new frameworks introduced.

### Changes

| Component | Change |
|-----------|--------|
| `configs/config.yaml` | Expand `sec_sections["10-K"]` from 7 to 15 sections |
| `src/preprocessing/segmenter.py` | `SegmentationStats` frozen Pydantic model; counters in `_filter_segments()` for `filtered_too_short`, `filtered_too_few_words`, `filtered_non_risk`, `cross_ref_drops`; counters in `segment_risks()` for `segments_split`, `segments_merged`; `_NO_MATERIAL_CHANGE_PAT` regex; boilerplate detection in `segment_extracted_section()` |
| `src/preprocessing/extractor.py` | `table_char_count` and `pre_exclusion_char_count` computed from `elements` list before table exclusion |
| `src/preprocessing/pipeline.py` | Extraction manifest (sections attempted/found/missing) stored on each `SegmentedRisks.metadata`; text coverage ratio computed after segmentation |
| `src/preprocessing/models/segmentation.py` | `no_material_change: bool` field; updated `save_to_json()` and `load_from_json()` for new stats fields |
| `scripts/.../run_preprocessing_pipeline.py` | New stats fields in `_build_output_data()` stats block; `sections_attempted` in worker return dict |
| `src/storage/database.py` | Wire `no_material_change` from `section_metadata` in `_import_segmented_json()` |
| `src/config/qa_validation.py` | `_check_completeness()` method on `HealthCheckValidator` |
| `configs/qa_validation/health_check.yaml` | `text_coverage_ratio` (target 0.85, warn 0.70) and `section_found_rate` (target 0.80, warn 0.60) thresholds |

### Governing Rules

1. `SegmentationStats` is frozen (immutable) — counters accumulated in a mutable dict during processing, frozen at end of `segment_risks()`.
2. The `no_material_change` guard requires `<= 3 segments` AND `< 2000 chars` to prevent false positives on substantive sections.
3. Both new completeness thresholds (`text_coverage_ratio`, `section_found_rate`) are non-blocking — they produce warnings, not quarantine.
4. The 10-K section config expansion is purely additive — `_sections_for_form_type()` reads config keys directly, so no code change was needed.

## Consequences

### Positive

- Full visibility into content loss at every pipeline stage via `segmentation_stats`, `extraction_manifest`, and `text_coverage` metadata fields.
- G-02 content loss threshold is now enforceable through `text_coverage_ratio` in `HealthCheckValidator`.
- Boilerplate 10-Q filings detectable via `no_material_change` flag — can be excluded from training data or weighted differently.
- 10-K extraction expanded to all 15 standard sections, enabling downstream analysis of Item 2 (Properties), Item 5 (Market), etc.

### Negative

- JSON output grows by ~200 bytes per filing due to new stats fields.
- Debug-level logging increases in `segment_risks()` — controlled by logger level, no impact in production.
- `_filter_segments()` signature gains an optional `sa` parameter — backward compatible (default `None`).

## References

- PRD-002 §3 (G-02 content loss threshold)
- `src/preprocessing/segmenter.py` — `SegmentationStats`, `_NO_MATERIAL_CHANGE_PAT`
- `src/config/qa_validation.py:_check_completeness()` — completeness validation
- `configs/qa_validation/health_check.yaml` — threshold definitions
- `tests/preprocessing/test_completeness.py` — 23 tests

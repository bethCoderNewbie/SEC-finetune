---
id: US-032
epic: EP-6 ML Readiness
priority: P0
status: not_started
source_prd: PRD-002
estimation: 8 points
---

# US-032: Segment Annotator — JSONL Transform from SegmentedRisks to Training Record

## The Story

> **As an** `ML Engineer`,
> **I want** a `SegmentAnnotator` module that reads `*_segmented.json` files from a preprocessing run directory, merges short segments by ancestor breadcrumb, classifies each merged segment using zero-shot NLI, and writes a flat JSONL file matching the PRD-002 §8 Phase 2 schema,
> **So that** the annotation corpus build (US-031) has a reproducible, quality-gated input source with all 14 required fields populated.

## Acceptance Criteria

### Scenario A: All 14 target fields present per record
```gherkin
Given a preprocessing run directory containing *_segmented.json files
  And section_include defaults to ["part1item1a", "part2item7a", "part1item1c"]
When I run segment_annotator_cli.py --run-dir <dir> --output labeled.jsonl
Then labeled.jsonl contains one JSON object per line
  And every record contains exactly these fields:
      index, text, word_count, char_count, label, risk_label,
      sasb_topic, sasb_industry, sic_code, ticker, cik,
      filing_date, confidence, label_source
  And sasb_topic and sasb_industry are null when taxonomy files are absent (not a crash)
  And label is an integer in range 0–8
```

### Scenario B: filed_as_of_date round-trips and formats correctly
```gherkin
Given a *_segmented.json file written by save_to_json() with filed_as_of_date "20211029"
When load_from_json() reads the file
Then segmented.filed_as_of_date == "20211029" (B-5 fix — not None)
  And the annotator emits filing_date == "2021-10-29" (ISO 8601 reformat)
  And no record has filing_date == null for filings where the field was originally present
```

### Scenario C: No merged segment exceeds 379 words
```gherkin
Given a SegmentedRisks with multiple short segments sharing identical ancestors
When _merge_by_ancestors() is called with merge_hi=379
Then every emitted merged segment has word_count <= 379
  And no merge crosses an ancestors boundary (consecutive identical-ancestors groups only)
  And segments with ancestors == [] are never merged with neighbours
  And the merged chunk_id has format "{first_id}+{last_id}" for multi-segment groups
```

### Scenario D: label_source values are from the locked namespace only
```gherkin
Given labeled.jsonl produced by any annotator run
When I read every record's label_source field
Then every value is one of:
    "nli_zero_shot", "heuristic", "ancestor_prior", "llm_silver",
    "classifier", "human", "llm_synthetic"
  And no record has label_source == "classifier" (reserved for Stage B fine-tuned model only)
  And records classified by BART with confidence >= section threshold have label_source == "nli_zero_shot"
  And records falling back to keyword heuristic have label_source == "heuristic"
  And records resolved by ancestor heading prior have label_source == "ancestor_prior"
```

### Scenario E: Output is loadable by HuggingFace datasets without modification
```gherkin
Given data/processed/annotation/labeled.jsonl produced by this module
When I run: ds = datasets.load_dataset("json", data_files="labeled.jsonl")
Then no exception is raised
  And ds["train"].features includes text (Value("string")) and label (Value("int64"))
  And no record has null text or out-of-range label integer
```

## Technical Notes

- **New module:** `src/analysis/segment_annotator.py` — `SegmentAnnotator` class
- **New CLI:** `scripts/feature_engineering/segment_annotator_cli.py`
- **Config:** `src/config/features/annotation.py` (`AnnotationConfig`, env prefix `SEC_ANNOTATION__`)
  registered in `src/config/__init__.py` `Settings` class
- **YAML defaults:** `configs/features/annotation.yaml`
- **Prereq B-5 fix:** `src/preprocessing/models/segmentation.py:load_from_json` lines 204–224
  must be patched to restore `filed_as_of_date` and `accession_number` before this story
- **label_source namespace:** Defined by ADR-015 — locked constants in `segment_annotator.py`
- **Ancestor merge:** Runs in the annotator only; does NOT mutate `*_segmented.json` files
- **Section policy (hard-excludes):** `part1item1b` and `part2item8` never annotated
- **Blocked by:** US-030 (taxonomy files) for non-null `sasb_industry` / `sasb_topic`
- **Blocks:** US-031 (corpus build) and US-029 (Stage A pipeline integration)
- **Stage A only:** Pipeline integration into `process_batch()` (US-029) is a separate story
- **Research reference:** `thoughts/shared/research/2026-03-03_17-30-00_segment_annotator_jsonl_transform.md`
- Status: ❌ Not implemented

---
id: RFC-005
title: Multi-Section Full-Document Parse Dispatch (ADR-011 Implementation)
status: ACCEPTED
author: beth
created: 2026-02-23
last_updated: 2026-02-23
git_sha: 8f08d4b
superseded_by: null
related_prd: docs/requirements/PRD-002_SEC_Finetune_Pipeline_v2.md
related_adr: docs/architecture/adr/ADR-011_preseeker_single_section_constraint.md
---

# RFC-005: Multi-Section Full-Document Parse Dispatch

## Status

**ACCEPTED** — Architecture decided in ADR-011 (Rule 9). This RFC documents the
implementation strategy for the three-file fix and the alternatives that were
rejected.

---

## Context

ADR-010 introduced a three-stage pre-seek architecture where Stage 1
(`AnchorPreSeeker.seek()`) returns a ~50–200 KB HTML slice spanning exactly one
section. sec-parser operates on this fragment and produces a flat node list
(`filing.tree.nodes`) containing only elements from that slice.

Commit `8f08d4b` added multi-section extraction: `_process_filing_with_global_workers()`
and `SECPreprocessingPipeline.process_filing()` now resolve all sections for a form type
and loop over them against a single `ParsedFiling`. This loop was written on the
assumption that `parse_filing()` would return a full-document parse. At runtime it does
not: `parse_filing()` contains

```python
fragment = AnchorPreSeeker().seek(
    file_path, manifest,
    section_id=section_id or "part1item1a",   # always "part1item1a" when unset
    form_type=form_type,
)
html_for_parser = fragment if fragment is not None else full_doc1_html
```

Neither `_process_filing_with_global_workers()` (`pipeline.py:169`) nor the script
worker `process_single_file_fast` (`run_preprocessing_pipeline.py:412`) passes a
`section_id`, so `section_id or "part1item1a"` always evaluates to `"part1item1a"`.
sec-parser builds its tree from the 1A slice only. All subsequent calls to
`extractor.extract_section(filing, section_enum)` for `part1item1b`, `part2item7`, etc.
return `None` — those nodes were never in the tree.

Full root-cause analysis: `thoughts/shared/research/2026-02-23_15-20-10_preseeker_multisection_skip_bug.md`.

---

## Design Question

**How should `parse_filing()` and its callers dispatch between the Stage 1 pre-seek
(fragment) path and the full Document 1 path for multi-section extraction?**

---

## Rejected Alternatives

### Alt A — N sequential pre-seeks, one per section

Run `AnchorPreSeeker.seek()` once per section ID, build N separate `ParsedFiling`
objects, and extract from each.

**Rejected.** This violates the parse-once-per-filing principle established in the
multi-section plan. For a 7-section 10-K it means 7 calls to `AnchorPreSeeker.seek()`
(each decoding and scanning the full Document 1 HTML string) plus 7 calls to
`Edgar10QParser.parse()`. Total parse latency: ~7 × 5.85s ≈ 41s — worse than the
18.44s pre-ADR-010 baseline. No design benefit over the status quo.

### Alt B — Composite pre-seek: first section anchor to last section end

Locate the first section's start anchor and the last section's end anchor, then pass
`doc_html[start_first : end_last]` as a single composite fragment.

**Rejected for two reasons:**

1. **Non-contiguity.** EDGAR 10-K sections are not contiguous blocks separated only by
   headings. Item 2 (Properties), Item 3 (Legal), Item 4 (Mine Safety), Exhibits, and
   other sections that are not in the extraction target set appear between
   `part1item1b` → `part2item7`. A composite slice spanning 1B through Item 8 would
   include thousands of nodes from sections the extractor never needs. Parse time
   approaches the full-document baseline.

2. **Node list pollution.** Even if parse time were acceptable, `filing.tree.nodes`
   would contain `TopSectionTitle` and `TitleElement` nodes from the intervening
   unwanted sections. `_find_section_node()` uses text-pattern matching against
   `tree.nodes`; false-positive matches against out-of-scope section headings are
   possible. The flat node list has no scope fence.

### Alt C — Parallel section-scoped pre-seeks (one worker per section)

Spawn one parse task per section, each worker calling `parse_filing(section_id=sid)`,
and merge results. Parallelism would hide per-section latency.

**Rejected.** The worker pool (`worker_pool.py`) is already parallelised at the
*filing* level (one worker per file). Introducing intra-filing section parallelism
adds inter-worker coordination complexity, increases per-filing peak memory (N
simultaneous DOM allocations for the same document), and creates contention on the
single `SGMLManifest.container_path` file handle used by `extract_document()`. The
rule from ADR-010 is parse-once per filing, not parse-once per section.

---

## Chosen Design — Intent-Based Dispatch at the Call Site

The correct fix separates two distinct caller intents:

| Caller intent | Pre-seek? | `section_id` arg | Result |
|---|---|---|---|
| Extract one section only | Yes — Stage 1 | `section_id=<sid>` | ~50–200 KB fragment |
| Extract multiple sections | No — Rule 7 path | omitted / `None` | Full Document 1 HTML |

**`parse_filing()` change** (`src/preprocessing/parser.py:165-172`)

The `or "part1item1a"` fallback is the sole defect. Replace it with an explicit
conditional:

```python
# Before
fragment = AnchorPreSeeker().seek(
    file_path, manifest,
    section_id=section_id or "part1item1a",
    form_type=form_type,
)

# After
if section_id is not None:
    from .pre_seeker import AnchorPreSeeker
    fragment = AnchorPreSeeker().seek(
        file_path, manifest, section_id=section_id, form_type=form_type
    )
else:
    fragment = None   # full-document parse — caller extracts multiple sections
html_for_parser = fragment if fragment is not None else full_doc1_html
```

This makes `section_id=None` (the existing default) explicitly mean "skip Stage 1",
which is already how Rule 7 works. No new code path is introduced; the fallback
branch already exists and is already tested.

**`pipeline.py` changes** — two call sites

`_process_filing_with_global_workers()` and `SECPreprocessingPipeline.process_filing()`
each resolve the section list before calling `parse_filing()`. Both must compute
`preseek_id` before the parse call:

```python
# In _process_filing_with_global_workers() (pipeline.py ~line 154)
if sections is None:
    sections = _sections_for_form_type(form_type)

# Stage 1 pre-seek valid only for single-section extraction (ADR-011 Rule 9)
preseek_id = sections[0] if len(sections) == 1 else None

parsed = get_worker_parser().parse_filing(
    file_path, form_type,
    save_output=parser_save,
    section_id=preseek_id,
)
```

Apply the same pattern in `SECPreprocessingPipeline.process_filing()` (~line 472):

```python
preseek_id = section_list[0].value if len(section_list) == 1 else None
parsed = self.parser.parse_filing(file_path, form_type,
                                  save_output=parser_save,
                                  section_id=preseek_id)
```

**Script worker** (`run_preprocessing_pipeline.py:process_single_file_fast`)

`process_single_file_fast` always iterates all sections (line 419:
`sections = _sections_for_form_type("10-K")`). After the `parser.py` fix, the existing
call at line 412 passes no `section_id` and therefore already takes the full-document
path. **No change required.**

### Why `_find_section_node()` does not need to change

`_find_section_node()` (`extractor.py:207-254`) uses three strategies, all iterating
`tree.nodes`:

1. **`TopSectionTitle`** nodes — matched by identifier or SECTION_PATTERNS regex. Used
   for `part1item1` (Item 1. Business), `part2item7` (MD&A), etc.
2. **`TitleElement`** nodes — matched by identifier or regex. Used for sub-items: 1A,
   1B, 1C, 7A.
3. **Flexible text-key matching** — last resort; same `tree.nodes` set.

When the full Document 1 HTML is parsed, sec-parser produces `TopSectionTitle` nodes
for every top-level section heading and `TitleElement` nodes for every sub-item
heading in the document. All 7 target section types are represented in `tree.nodes`.
The three-strategy approach handles both node types correctly for the full-document case;
the only reason it failed was that the relevant nodes were absent from the fragment-based
tree.

---

## Backward Compatibility

| Caller | Before fix | After fix |
|--------|-----------|-----------|
| `process_single_file_fast` (batch, all sections) | Pre-seeks 1A → silently skips 5 sections | Full document → all sections extracted |
| `_process_filing_with_global_workers` (multi) | Pre-seeks 1A → silently skips 5 sections | Full document → all sections extracted |
| `_process_filing_with_global_workers` (single) | Pre-seeks 1A (accidentally correct for 1A-only callers) | Pre-seeks the requested section (explicit) |
| `SECPreprocessingPipeline.process_filing` (multi) | Pre-seeks 1A → silently skips 5 sections | Full document → all sections extracted |
| `SECPreprocessingPipeline.process_filing` (single) | Pre-seeks 1A (accidentally correct for 1A-only callers) | Pre-seeks the requested section (explicit) |
| `process_risk_factors()` | Calls `process_filing([section_1a])` → single-element list → `preseek_id = section_1a.value` → Stage 1 fires | Unchanged |

`process_risk_factors()` (`pipeline.py:648`) calls `self.process_filing(sections=[section])`.
After the fix, `len(section_list) == 1` → `preseek_id = section.value` → Stage 1 fires
as before. No regression.

---

## Performance Impact

Multi-section batch runs will be slower than single-section runs:

| Mode | sec-parser input | Approx. per-file latency |
|------|-----------------|--------------------------|
| Single-section (pre-seek) | ~91 KB fragment | ~5.85s (AAPL measured) |
| Multi-section (full doc) | ~5.2 MB Document 1 | ~18–20s (pre-ADR-010 baseline) |

This is unavoidable: non-contiguous sections cannot share a single HTML byte range
(see Alt B rejection). The multi-section path was previously non-functional (all sections
silently skipped), so any working latency is an improvement over the status quo.

The `recursion_limit` auto-scaling at `parser.py:159-161` already accounts for full
Document 1 size:

```python
file_size_mb = len(full_doc1_html) / (1024 * 1024)
recursion_limit = min(50000, 10000 + int(file_size_mb * 2000))
```

No change needed. `MemorySemaphore` adaptive timeout scaling (`run_preprocessing_pipeline.py:674-685`)
already provisions 20–40 minutes per file based on container size. Multi-section full-document
parsing fits within these bounds for AAPL-class filings.

---

## Governing Rules Affected

| Rule | Status | Change |
|------|--------|--------|
| ADR-010 Rule 1 (never modify HTML before sec-parser) | Unchanged | Fix passes full Document 1 HTML — still unmodified |
| ADR-010 Rule 7 (fallback to full doc if Stage 1 returns None) | Extended | Rule 7 path is now the *expected* path for multi-section callers, not only the error path |
| ADR-011 Rule 9 (Stage 1 is single-section only) | New | Codifies the dispatch logic above |

---

## Verification

```bash
# Run single file; confirm all non-absent sections produce *_segmented.json
python scripts/data_preprocessing/run_preprocessing_pipeline.py \
  --input data/raw/AAPL_10K_2021.html --no-sentiment

# Confirm multi-section output files are present
RUN=$(ls -t data/processed | grep preprocessing | head -1)
ls data/processed/$RUN/*.json | grep segmented

# Confirm backward compat: process_risk_factors still returns results
python -c "
from src.preprocessing.pipeline import SECPreprocessingPipeline
r = SECPreprocessingPipeline().process_risk_factors('data/raw/AAPL_10K_2021.html')
assert r is not None
print('process_risk_factors OK —', len(r.segments), 'segments')
"

# No regressions in unit-test suite
pytest tests/unit/preprocessing/ -q
```

Expected: all 7 configured 10-K sections either produce a segmented output or emit a
meaningful "not found in filing" skip (not a silent None). `process_risk_factors`
returns the same segment count as before.

---

## References

- `thoughts/shared/research/2026-02-23_15-20-10_preseeker_multisection_skip_bug.md`
  — root-cause analysis; evidence trail; before/after code diffs
- `docs/architecture/adr/ADR-011_preseeker_single_section_constraint.md` — Rule 9 (the decision)
- `docs/architecture/adr/ADR-010_hybrid_pre_seek_parser_corrected.md` — base architecture;
  Rules 1, 7 (amended by Rule 9)
- `src/preprocessing/parser.py:165-172` — pre-seek condition (the bug)
- `src/preprocessing/pipeline.py:154-169` — `_process_filing_with_global_workers()` parse call
- `src/preprocessing/pipeline.py:453-472` — `SECPreprocessingPipeline.process_filing()` parse call
- `src/preprocessing/extractor.py:207-254` — `_find_section_node()` three strategies
- `scripts/data_preprocessing/run_preprocessing_pipeline.py:412` — `process_single_file_fast` parse call

# ADR-011: Pre-Seeker is Single-Section Only — Multi-Section Must Parse Full Document

**Status:** Accepted — Amends ADR-010
**Date:** 2026-02-23
**Author:** beth
**git SHA:** 8f08d4b
**Research document:** `thoughts/shared/research/2026-02-23_15-20-10_preseeker_multisection_skip_bug.md`

---

## Context

ADR-010 Stage 1 pre-seek was designed for single-section extraction: it returns a
raw HTML substring spanning exactly one section (e.g., `doc_html[start_1A : start_1B]`).
The multi-section extraction plan
(`thoughts/shared/research/2026-02-23_15-11-55_multi_section_extraction_plan.md`,
implemented in commit `8f08d4b`) correctly introduced a parse-once → loop-over-sections
pipeline but did not account for this constraint.

### What went wrong

`SECFilingParser.parse_filing()` (`src/preprocessing/parser.py:165-172`) contains:

```python
fragment = AnchorPreSeeker().seek(
    file_path,
    manifest,
    section_id=section_id or "part1item1a",   # ← always "part1item1a" when unset
    form_type=form_type,
)
html_for_parser = fragment if fragment is not None else full_doc1_html
```

The `section_id` parameter defaults to `None`. Neither the pipeline worker
(`pipeline.py:169`) nor the script runner
(`run_preprocessing_pipeline.py:173`) passes a `section_id`, so
`section_id or "part1item1a"` always evaluates to `"part1item1a"`.

`AnchorPreSeeker.seek()` constructs `end_patterns` from every section after the
target in config order (`part1item1b`, `part1item1c`, `part2item7`, …) and returns
`doc_html[start_of_1A : start_of_1B]`. sec-parser builds a flat tree from this
~50–200 KB fragment; `filing.tree.nodes` contains only nodes from that slice.

When the multi-section loop later calls `extractor.extract_section(filing, section_enum)`
for `part1item1b`, `part2item7`, etc., `_find_section_node()` iterates `tree.nodes`
and finds nothing — those sections were never parsed.

**Observed symptom:**

```
Extracting section 'part1item1'...   [OK]   (heading is just above 1A anchor — in slice)
Extracting section 'part1item1a'...  [OK]   (sought by pre-seeker)
Extracting section 'part1item1b'...
  [SKIP] Section 'part1item1b' not found in filing
Extracting section 'part2item7'...
  [SKIP] Section 'part2item7' not found in filing
...
```

---

## Decision

### Rule 9 — Stage 1 pre-seek is single-section only

**The pre-seeker MUST NOT be used when more than one section will be extracted
from the same `ParsedFiling` object.**

When `parse_filing()` is called for multi-section extraction, `section_id` must be
`None` (the default), and the `parse_filing()` implementation must treat `None` as
"skip Stage 1, parse the full Document 1 HTML". This is the existing Rule 7 fallback
path — it is not new code, only a change in when it is triggered.

When `parse_filing()` is called for single-section extraction, the caller SHOULD
pass the target `section_id` explicitly to enable the Stage 1 speed benefit.

### Required code changes (three files)

**`src/preprocessing/parser.py:165-172`**

Change the pre-seek condition so that `section_id=None` (the default) skips Stage 1:

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
    fragment = None   # full-document parse; caller will extract multiple sections
html_for_parser = fragment if fragment is not None else full_doc1_html
```

**`src/preprocessing/pipeline.py` — `_process_filing_with_global_workers()`**

Resolve `sections` before the parse call; pass `section_id` only for single-section requests:

```python
if sections is None:
    sections = _sections_for_form_type(form_type)

# Pre-seek only valid for single-section extraction
preseek_id = sections[0] if len(sections) == 1 else None

parsed = get_worker_parser().parse_filing(
    file_path, form_type,
    save_output=parser_save,
    section_id=preseek_id,
)
```

Apply the same pattern to `SECPreprocessingPipeline.process_filing()`: resolve
`section_list` first, then pass
`section_id=section_list[0].value if len(section_list) == 1 else None`.

**`scripts/data_preprocessing/run_preprocessing_pipeline.py` — `run_pipeline()`**

`run_pipeline()` always iterates all sections; it must never pre-seek. After the
`parser.py` fix, the existing call with no `section_id` argument already achieves
this — no code change required in this file.

---

## Consequences

**Positive:**
- Multi-section extraction (`part1item1b`, `part1item1c`, `part2item7`, `part2item7a`,
  `part2item8`) works correctly — all sections are present in `filing.tree.nodes`.
- Rule 7 fallback path (full Document 1 parse) is the natural mechanism; no new code path.
- Single-section callers (`process_risk_factors`, `process_and_validate`) retain the
  ADR-010 Stage 1 speed benefit by passing `section_id` explicitly.

**Negative:**
- Multi-section extraction loses the Stage 1 speed benefit: sec-parser processes the
  full Document 1 (~5.2 MB for AAPL) rather than a ~91 KB slice. Per-filing latency
  increases from ~5.85s (single-section) to the pre-ADR-010 baseline of ~18s for a
  10 MB filing. Batch throughput for multi-section runs will be proportionally lower.
- The performance regression is unavoidable: non-contiguous sections cannot be sliced
  from a single HTML byte range. Acceptable given that multi-section extraction was
  previously non-functional (all sections silently skipped).

**Invariants preserved:**
- Rule 1 (never modify HTML before sec-parser) — unchanged.
- Rule 7 (fallback to full document if Stage 1 returns None) — now the expected path
  for multi-section callers, not just the error path.
- `process_risk_factors()` — calls `process_filing([section])`, a single-element list;
  `preseek_id = section.value`; Stage 1 fires as before. No regression.
- All other ADR-010 governing rules (2–8) are unchanged.

---

## Supersedes

Does not supersede ADR-010. All ADR-010 decisions, rules, and consequences remain
in effect. This ADR adds **Rule 9** and records the post-implementation limitation
discovered in commit `8f08d4b`.

---

## References

- `thoughts/shared/research/2026-02-23_15-20-10_preseeker_multisection_skip_bug.md`
  — full root-cause analysis, evidence trail, and before/after diffs
- `src/preprocessing/parser.py:165-172` — the `section_id or "part1item1a"` expression (the bug)
- `src/preprocessing/pre_seeker.py:70-98` — `AnchorPreSeeker.seek()` slice logic
- `src/preprocessing/pipeline.py:154-169` — `parse_filing()` call site (worker path)
- `src/preprocessing/pipeline.py:453-472` — `parse_filing()` call site (class path)
- `scripts/data_preprocessing/run_preprocessing_pipeline.py:173` — script call site
- ADR-010 — hybrid pre-seek architecture (amended by this document)

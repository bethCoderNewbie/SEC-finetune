---
date: 2026-02-23T15:20:10-0600
researcher: beth
git_commit: 8f08d4b
branch: main
repository: SEC-finetune
status: completed
topic: pre-seeker fragment causes multi-section extraction skips
---

# Root Cause: Multi-Section Extraction Skips (part1item1b … part2item8)

## Symptom

After implementing the multi-section extraction plan
(`2026-02-23_15-11-55_multi_section_extraction_plan.md`), `run_pipeline()` and
`_process_filing_with_global_workers()` successfully extract `part1item1` and
`part1item1a` but silently skip every other section:

```
Extracting section 'part1item1'...   [OK]
Extracting section 'part1item1a'...  [OK]
Extracting section 'part1item1b'...
  [SKIP] Section 'part1item1b' not found in filing
Extracting section 'part1item1c'...
  [SKIP] Section 'part1item1c' not found in filing
Extracting section 'part2item7'...
  [SKIP] Section 'part2item7' not found in filing
Extracting section 'part2item7a'...
  [SKIP] Section 'part2item7a' not found in filing
Extracting section 'part2item8'...
  [SKIP] Section 'part2item8' not found in filing
```

The `[SKIP]` message originates at
`scripts/data_preprocessing/run_preprocessing_pipeline.py:211`:
```python
if extracted is None:
    print(f"  [SKIP] Section '{section_id}' not found in filing")
```
which is reached when `SECSectionExtractor.extract_section()` returns `None`,
which happens when `_find_section_node()` returns `None`.

---

## Root Cause

### The pre-seeker always runs for `part1item1a`

`SECFilingParser.parse_filing()` (`src/preprocessing/parser.py:165-172`)
contains the ADR-010 pre-seek path:

```python
fragment = AnchorPreSeeker().seek(
    file_path,
    manifest,
    section_id=section_id or "part1item1a",   # ← bug
    form_type=form_type,
)
html_for_parser = fragment if fragment is not None else full_doc1_html
```

The `section_id` parameter of `parse_filing()` defaults to `None`.  Neither
the pipeline (`pipeline.py:169`) nor the script (`run_preprocessing_pipeline.py:173`)
passes a `section_id` argument, so `section_id or "part1item1a"` always
evaluates to `"part1item1a"`.

### The pre-seeker returns a fragment, not the full document

`AnchorPreSeeker.seek()` (`src/preprocessing/pre_seeker.py:70-98`) builds:
- `target_patterns` — regex patterns for `part1item1a`
- `end_patterns` — regex patterns for every section that comes **after**
  `part1item1a` in the config-ordered list (`part1item1b`, `part1item1c`,
  `part2item7`, `part2item7a`, `part2item8`, …)

Strategy A (ToC anchor resolution) and Strategy B (direct text scan) both
return `doc_html[start_of_1A : start_of_1B]` — a substring covering only the
Item 1A region, typically 50–200 KB of the 5–10 MB full document.

`html_for_parser` therefore contains **only Item 1A's content**. sec-parser
builds a flat tree from this fragment. `filing.tree.nodes` has elements only
from that slice.

### `_find_section_node` cannot find sections outside the fragment

`SECSectionExtractor._find_section_node()` (`src/preprocessing/extractor.py:204-251`)
iterates `tree.nodes` in three strategies:

1. Search `TopSectionTitle` nodes by identifier / regex
2. Search `TitleElement` nodes by identifier / regex
3. Flexible text-key matching

All three iterate the same `tree.nodes`. Because the tree was built from the
1A fragment, none of `part1item1b`, `part1item1c`, `part2item7`, `part2item7a`,
`part2item8` have any representation in the node list.  Every search returns
`None`.

### Why `part1item1` is found

The pre-seeker's start position for Item 1A backs up to the opening `<` of the
surrounding HTML tag (`pre_seeker.py:183` for Strategy B,
`pre_seeker.py:141` for Strategy A). In practice the **Item 1. Business**
heading sits just above the Item 1A anchor in the filing HTML. It falls inside
the fragment's byte range, so sec-parser produces a `TopSectionTitle` node for
it. Strategy 1 of `_find_section_node` matches it via
`SECTION_PATTERNS["part1item1"]`.

---

## Evidence Trail

| File | Line | What it does | Why it's causal |
|------|------|-------------|----------------|
| `src/preprocessing/parser.py` | 165–172 | `AnchorPreSeeker().seek(section_id or "part1item1a")` | Always pre-seeks 1A regardless of which sections will be extracted |
| `src/preprocessing/parser.py` | 172 | `html_for_parser = fragment or full_doc1_html` | Parser receives only the 1A slice |
| `src/preprocessing/pre_seeker.py` | 81–86 | `end_patterns` built from all sections after 1A | Fragment ends at start of 1B |
| `src/preprocessing/pipeline.py` | 169 | `parse_filing(file_path, form_type, save_output=…)` | No `section_id` arg → defaults to `None` → maps to `"part1item1a"` |
| `scripts/…/run_preprocessing_pipeline.py` | 173 | `parser.parse_filing(input_file, form_type="10-K", …)` | Same: no `section_id` |
| `src/preprocessing/extractor.py` | 204–251 | `_find_section_node` iterates `tree.nodes` | Flat node list only contains fragment elements |

---

## What the Research Plan Missed

The multi-section extraction implementation plan
(`2026-02-23_15-11-55_multi_section_extraction_plan.md`) correctly identified
the need to parse once and loop over sections, but it did not account for the
ADR-010 pre-seek path. The plan's "parse once" step assumed `parse_filing()`
would return a full document. At runtime, the SGML manifest is valid for any
real filing, so the ADR-010 branch is always taken — and the pre-seeker always
clips to the 1A slice.

---

## How It Should Work vs. How It Does Work

| Aspect | Should work | Actually works |
|--------|------------|----------------|
| `parse_filing()` for multi-section | Parses full Document 1 HTML | Parses only the `part1item1a` fragment |
| `section_id` default in `parse_filing()` | `None` → no pre-seek | `None or "part1item1a"` → always pre-seeks |
| Sections in `filing.tree.nodes` | All 7 10-K sections | Only elements from the 1A slice |
| `_find_section_node` for `part2item7` | Finds the Item 7 node | Returns `None` (node not in tree) |

---

## Fix (Three Files)

### 1. `src/preprocessing/parser.py:165-172`

Change the pre-seek condition to only fire when `section_id` is explicitly
provided by the caller:

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
    fragment = None   # full-document parse; caller handles all sections
html_for_parser = fragment if fragment is not None else full_doc1_html
```

**No other change to `parse_filing()` is needed.** Its signature already
accepts `section_id=None`; the `or "part1item1a"` expression was the sole bug.

### 2. `src/preprocessing/pipeline.py` — `_process_filing_with_global_workers()` (~line 154-169)

Resolve `sections` before the parse call, then pass `section_id` only when
a single section is requested (preserves ADR-010 performance for
single-section callers such as `process_risk_factors`):

```python
if sections is None:
    sections = _sections_for_form_type(form_type)

# Pre-seek optimisation only valid for single-section extraction.
# Multi-section requires the full document.
preseek_id = sections[0] if len(sections) == 1 else None

parsed = get_worker_parser().parse_filing(
    file_path, form_type,
    save_output=parser_save,
    section_id=preseek_id,
)
```

Apply the same pattern to `SECPreprocessingPipeline.process_filing()` (~line
453-472): resolve `section_list` before the parse call and pass
`section_id=section_list[0].value if len(section_list) == 1 else None`.

### 3. `scripts/data_preprocessing/run_preprocessing_pipeline.py` — `run_pipeline()` (~line 173)

`run_pipeline()` always iterates all sections for the filing's form type.
It must never pre-seek. After fix #1, the existing call with no `section_id`
argument already achieves this:

```python
# No change required — section_id defaults to None → full-document parse
filing = parser.parse_filing(
    input_file, form_type="10-K",
    save_output=parsed_path if parsed_path else save_intermediates,
)
```

---

## Invariants Preserved

| Invariant | How preserved |
|-----------|---------------|
| ADR-010: pre-seek for single-section callers | `process_risk_factors()` → `process_filing([section])` → `preseek_id = section.value` |
| Rule 1: never modify HTML before sec-parser | Unchanged; fix only controls which HTML slice is passed |
| Parse-once per filing | Unchanged; the single `parse_filing()` call remains before the section loop |
| Backward compat: `process_risk_factors()` | Unaffected; it calls `process_filing` with a single-element `sections` list |

---

## Affected Call Sites

| Call site | Current | After fix |
|-----------|---------|-----------|
| `_process_filing_with_global_workers()` multi-section | Pre-seeks 1A only | Full document |
| `_process_filing_with_global_workers()` single-section | Pre-seeks 1A only | Pre-seeks the requested section |
| `SECPreprocessingPipeline.process_filing()` multi | Pre-seeks 1A only | Full document |
| `SECPreprocessingPipeline.process_filing()` single | Pre-seeks 1A only | Pre-seeks the requested section |
| `run_pipeline()` (script) | Pre-seeks 1A only | Full document |
| `process_risk_factors()` (via above) | Pre-seeks 1A ✓ | Pre-seeks 1A ✓ (unchanged) |

---

## Verification

```bash
# Run single file; expect all non-absent sections to produce *_segmented.json
python scripts/data_preprocessing/run_preprocessing_pipeline.py \
  --input data/raw/AAPL_10K_2021.html --no-sentiment

# Confirm multi-section output files exist
RUN=$(ls -t data/processed | grep preprocessing | head -1)
ls data/processed/$RUN/*.json | grep segmented

# Confirm backward compat: process_risk_factors still works
python -c "
from src.preprocessing.pipeline import SECPreprocessingPipeline
r = SECPreprocessingPipeline().process_risk_factors('data/raw/AAPL_10K_2021.html')
assert r is not None
print('process_risk_factors OK —', len(r), 'segments')
"

# Run full unit-test suite; no regressions expected
pytest tests/unit/preprocessing/ -q
```

---

## References

- `src/preprocessing/parser.py:165-172` — pre-seek condition (the bug)
- `src/preprocessing/pre_seeker.py:70-98` — `AnchorPreSeeker.seek()` slice logic
- `src/preprocessing/extractor.py:204-251` — `_find_section_node()` iteration
- `src/preprocessing/pipeline.py:154-169` — `parse_filing()` call site
- `scripts/data_preprocessing/run_preprocessing_pipeline.py:173` — script call site
- `thoughts/shared/research/2026-02-23_15-11-55_multi_section_extraction_plan.md` — prior implementation plan (did not account for pre-seeker)
- ADR-010 — hybrid pre-seek architecture

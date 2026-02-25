---
date: 2026-02-24T17:05:36-06:00
author: bethCoderNewbie
git_commit: 96801e6
branch: main
topic: "Fix char_count field alias and add char_count at all five pipeline levels"
tags: [plan, schema, g-02, g-03, char_count, loss_measurement, segmentation, parsed, extracted, elements]
status: ready_for_review
related_prd: PRD-002 G-02, G-03
---

# Plan: Fix `char_count` Field Alias and Add `char_count` at All Five Pipeline Levels

## Five-Level Char Count Waterfall (AAPL 10-K 2021, part1item1a)

```
Stage                      chars       delta        exists today?
──────────────────────────────────────────────────────────────────
Raw HTML    (parsed)     2,051,191   baseline      metadata.html_size ✓
Parsed elements (all)      211,751   −89.7%  tags  metadata.text_char_count ✗  ← Phase 3
Extracted text (section)    66,278   −68.7%  scope stats.text_length ✓ (not forwarded)
Extracted elements sum      66,122   −156    joins  elements[].char_count ✗     ← Phase 4
Cleaned text                66,278   −0.00%  clean  stats.text_length ✓ (not forwarded)
Segmented sum               66,087   −0.29%  split  segments[].length ✗ (alias bug) ← Phase 1/2
```

Note: `extracted_elements_sum` (66,122) ≠ `stats.text_length` (66,278) — a consistent
156-char gap caused by joining whitespace added between elements during text concatenation.
`stats.text_length` measures the concatenated `text` field and is the authoritative baseline.

## Desired End State

After implementation:

1. **Single canonical field name** — `char_count` is used consistently in every
   on-disk JSON schema and every model load path. `length` disappears as an output key.
   Any code that loads batch output via `load_from_json()` gets correct `char_count`
   values (not 0).

2. **Three-tier loss measurement from one file** — every `*_segmented.json` carries
   `raw_section_char_count` and `cleaned_section_char_count` in
   `section_metadata.stats`. The G-02 full-pipeline loss formula is computable without
   joining to the `extracted/` directory:
   ```
   pipeline_loss = (raw_section_char_count − Σ segment.char_count) / raw_section_char_count
   cleaning_loss = (raw_section_char_count − cleaned_section_char_count) / raw_section_char_count
   segment_loss  = (cleaned_section_char_count − Σ segment.char_count) / cleaned_section_char_count
   ```

3. **`HealthCheckValidator` and `diagnose_short_segments.py`** read `char_count`
   with no fallback required.

4. **Document-level text char count** — `_parsed.json → metadata.text_char_count`
   records the sum of all element text chars after sec-parser strips HTML tags. Enables
   detection of filings where sec-parser under-extracted (large `html_size` but low
   `text_char_count`).

5. **Element-level char count** — every element dict in `_extracted.json` and
   `_cleaned.json` carries `char_count: len(text)`. Enables downstream analytics to
   identify unusually long paragraphs and measure per-element TextCleaner impact without
   re-reading the text field.

---

## What We're NOT Doing

- **Not merging the two serialisers** (`save_to_json` v1.0 + `_build_output_data` v2.1).
  That is a separate refactoring concern. Both serialisers will be fixed independently.
- **Not migrating existing on-disk files** — the `load_from_json` migration fallback
  handles all v2.1 files already on disk.
- **Not changing the `section_metadata.stats` key names** for `total_chunks` or
  `num_tables` — only new keys are added.
- **Not touching `word_count`** — it is consistent across both serialisers already.
- **Not adding `raw_section_char_count` to the annotation JSONL schema** (§2.1.2)
  — it is a pipeline-internal diagnostic field, not a training feature.
- **Not adding node/subsection-level char counts** — `node_subsections` is a flat
  per-element `List[List[str]]`, not grouped by subsection. Aggregating per-subsection
  requires grouping logic in `SECSectionExtractor` and a schema decision on whether to
  add a new `subsection_char_counts: Dict[str, int]` field or restructure
  `node_subsections` into typed objects. Deferred to a separate story; the element-level
  `char_count` (Phase 4) provides the raw data needed to compute subsection sums.

---

## Key Discoveries

| Location | Finding |
|---|---|
| `run_preprocessing_pipeline.py:410` | `'length': seg.char_count` — correct value, wrong key; v2.1 schema |
| `segmentation.py:155` | `'char_count': seg.char_count` — correct; v1.0 schema (`save_to_json`) |
| `segmentation.py:230` | `char_count=s.get('char_count', 0)` — reads `char_count`; silently gets 0 for all v2.1 files |
| `qa_validation.py:846` | `seg.get("length", len(seg.get("text", "")))` — correct for v2.1 but needs update |
| `pipeline.py:228,232,236` | `extracted.text` (raw) and `cleaned_text` available back-to-back; neither char count is captured |
| `run_preprocessing_pipeline.py:263-281` | Same dual-text availability in single-file path |
| `run_preprocessing_pipeline.py:515-598` | Same dual-text availability in batch path |
| `segmentation.py:32-62` | `SegmentedRisks` model has no char count fields for the section |
| `_parsed.json` `metadata` | Has `html_size` (raw HTML bytes) but no `text_char_count` (sum of element text after tag stripping). For AAPL 10-K 2021: html_size=2,051,191 vs text_char_count=211,751 — 89.7% is HTML markup. |
| `_extracted.json` `elements[]` | Each element has `type`, `text`, optionally `level` — no `char_count`. Adding is a one-liner in serialization. |
| `_cleaned.json` `elements[]` | Same gap as extracted. TextCleaner currently preserves the elements list unchanged; element-level char_count enables per-element cleaning impact measurement. |
| `extracted_elements_sum` vs `stats.text_length` | 66,122 vs 66,278 for AAPL 10-K 2021 — 156-char gap from joining whitespace in concatenated `text` field. `stats.text_length` is authoritative; element sum is not a valid proxy for section char count. |

---

## Phase 1 — Fix the `length` → `char_count` alias

**Scope:** 4 file changes, no new fields, no schema version bump required.

### 1a. Batch CLI serialiser (`run_preprocessing_pipeline.py:406-412`)

Rename the output key. `seg.char_count` is already the correct value.

```python
# BEFORE (line 406-412)
segment_dict = {
    'id':               seg.chunk_id,
    'parent_subsection': seg.parent_subsection,
    'text':             seg.text,
    'length':           seg.char_count,   # ← wrong key
    'word_count':       seg.word_count,
}

# AFTER
segment_dict = {
    'id':               seg.chunk_id,
    'parent_subsection': seg.parent_subsection,
    'text':             seg.text,
    'char_count':       seg.char_count,   # ← correct
    'word_count':       seg.word_count,
}
```

### 1b. `load_from_json` migration fallback (`segmentation.py:229-230`)

The old-schema path already reads `char_count`. Add `length` as a fallback so any
v2.1 file already on disk loads correctly after this fix ships.

```python
# BEFORE (line 230)
char_count=s.get('char_count', 0),

# AFTER
char_count=s.get('char_count') or s.get('length', 0),
```

The `or` short-circuits: if `char_count` is present and non-zero it wins; if absent
or 0 (legacy file), fall back to `length`. After the fix ships, all new files will
have `char_count`, so the fallback is a read-only migration path.

### 1c. QA validator (`qa_validation.py:846`)

Update the dict read to match the new canonical key.

```python
# BEFORE (line 846)
length = seg.get("length", len(seg.get("text", "")))

# AFTER
length = seg.get("char_count", len(seg.get("text", "")))
```

Variable name `length` is local and unchanged — only the dict key changes here.

### 1d. `diagnose_short_segments.py` (if applicable)

`diagnose_short_segments.py` reads `word_count` and `text` from raw dicts; it does
not read `length` or `char_count` directly. No change needed.
Verify with: `grep -n "length\|char_count" scripts/validation/data_quality/diagnose_short_segments.py`

---

## Phase 2 — Add `raw_section_char_count` / `cleaned_section_char_count`

**Scope:** 6 file changes. Additive only — no existing fields removed or renamed.

### 2a. `SegmentedRisks` model — two new optional fields (`segmentation.py:56-61`)

Insert after the existing `ein` field:

```python
# New fields — set by the pipeline after Step 3 (cleaning), before Step 4 (segmenting)
raw_section_char_count: Optional[int] = None     # len(extracted.text) pre-TextCleaner
cleaned_section_char_count: Optional[int] = None  # len(cleaned_text) post-TextCleaner
```

Both are `Optional[int]` so existing callers that don't set them get `None` rather
than a validation error. `None` is written to JSON as `null` and is distinguishable
from 0.

### 2b. Pipeline worker path — capture char counts (`pipeline.py:224-265`)

After cleaning (line 236) and after segmentation (line 254), set both fields on
the `result` object:

```python
# After line 236 (logger.info cleaned text)
raw_chars     = len(extracted.text)
cleaned_chars = len(cleaned_text)

# After line 255 (logger.info segment count)
result.raw_section_char_count     = raw_chars
result.cleaned_section_char_count = cleaned_chars
```

`extracted` and `cleaned_text` are both in scope at this point.

### 2c. Batch CLI single-file path — capture char counts (`run_preprocessing_pipeline.py:~263-282`)

The single-file path also has `extracted.text` and `cleaned_text` in scope.
Capture immediately after cleaning and pass to `_build_output_data`:

```python
raw_chars     = len(extracted.text)
cleaned_chars = len(cleaned_text)
# … segmentation …
output_data = _build_output_data(
    input_file=input_file,
    segmented_risks=segmented_risks,
    sentiment_features_list=sentiment_features_list,
    extract_sentiment=extract_sentiment,
    raw_section_char_count=raw_chars,        # new kwarg
    cleaned_section_char_count=cleaned_chars, # new kwarg
)
```

### 2d. Batch CLI batch path — capture char counts (`run_preprocessing_pipeline.py:~515-598`)

Same pattern as 2c. Capture after cleaning (around line 550), pass to
`_build_output_data` at line 591.

### 2e. `_build_output_data` signature and `section_metadata.stats` (`run_preprocessing_pipeline.py:319-390`)

Add parameters and write into stats:

```python
def _build_output_data(
    input_file: Path,
    segmented_risks: SegmentedRisks,
    sentiment_features_list: Optional[List] = None,
    extract_sentiment: bool = True,
    raw_section_char_count: Optional[int] = None,      # new
    cleaned_section_char_count: Optional[int] = None,  # new
) -> Dict[str, Any]:

# In section_metadata.stats block (line 386-390):
'stats': {
    'total_chunks':              segmented_risks.total_segments,
    'num_tables':                num_tables,
    'raw_section_char_count':    raw_section_char_count,    # new
    'cleaned_section_char_count': cleaned_section_char_count, # new
},
```

### 2f. `save_to_json` stats block and `load_from_json` round-trip (`segmentation.py:144-148`, `segmentation.py:184-213`)

In `save_to_json` stats block:

```python
'stats': {
    'total_chunks':              self.total_segments,
    'num_tables':                num_tables,
    'raw_section_char_count':    self.raw_section_char_count,    # new
    'cleaned_section_char_count': self.cleaned_section_char_count, # new
},
```

In `load_from_json` new-schema path (after line 210):

```python
total_segments=stats.get('total_chunks', len(segments)),
raw_section_char_count=stats.get('raw_section_char_count'),      # new
cleaned_section_char_count=stats.get('cleaned_section_char_count'), # new
```

---

## Phase 3 — Add `text_char_count` to parsed document metadata

**Scope:** 1 file change. Additive only. No downstream consumers need updating.

**Complexity: Low.** The parsed elements list is already in memory when the parsed
file is serialized. `text_char_count` is a one-pass sum over the existing list.

### 3a. `SECFilingParser` — add `text_char_count` to `metadata` (`parser.py`)

Find the metadata dict construction in the parser serialization path and add:

```python
# In parsed metadata block — after existing 'html_size' field
'text_char_count': sum(len(e.get('text', '') or '') for e in elements),
```

This yields the total readable chars after sec-parser strips HTML — the true
document-level baseline for extraction efficiency measurement. For AAPL 10-K 2021:
`text_char_count = 211,751` vs `html_size = 2,051,191` (89.7% was markup).

**Do not use `text_char_count` as the G-02 baseline.** The G-02 baseline is
`raw_section_char_count` from Phase 2 — the section-scoped extracted text, not the
whole document.

---

## Phase 4 — Add `char_count` to each element in extracted / cleaned output

**Scope:** 1 file change (`SECSectionExtractor`). Additive only. Both `_extracted.json`
and `_cleaned.json` share the same element serialization path.

**Complexity: Very Low.** Elements are serialized in a loop; adding `char_count` is
a one-liner per element. No schema restructuring.

### 4a. `SECSectionExtractor` — add `char_count` to element dicts (`extractor.py`)

Find the element serialization loop and extend each element dict:

```python
# BEFORE
{'type': e.type, 'text': e.text_str, 'level': getattr(e, 'level', None)}

# AFTER
{
    'type':       e.type,
    'text':       e.text_str,
    'char_count': len(e.text_str or ''),   # ← new
    'level':      getattr(e, 'level', None),
}
```

This enables:
- Per-element loss measurement between `_extracted.json` and `_cleaned.json`
  (though TextCleaner currently passes elements through unchanged)
- Downstream analytics that need element-level weight without re-reading text
- Detecting outlier-length elements that may drive the segment split heuristics

**Note on element sum vs section text:** `Σ element.char_count` ≠ `stats.text_length`
due to the 156-char joining-whitespace gap. Never use element sum as a proxy for
section char count. Use `stats.text_length` (Phase 2) for G-02 measurement.

---

## Implementation Order

```
Phase 1 first — the alias fix is a pure correction with no new surface area.
Phase 2 second — new fields build on the corrected serialiser.
Phases 3 and 4 are independent of each other and of Phases 1/2; run in parallel or after.

1a  run_preprocessing_pipeline.py:410       'length' → 'char_count'
1b  segmentation.py:230                     load_from_json fallback
1c  qa_validation.py:846                    dict key update
    ── run tests; confirm no regressions ──
2a  segmentation.py:56-61                   new SegmentedRisks fields
2b  pipeline.py:236,255                     capture + set in worker path
2c  run_preprocessing_pipeline.py:~282      capture + pass in single-file path
2d  run_preprocessing_pipeline.py:~550      capture + pass in batch path
2e  run_preprocessing_pipeline.py:319-390   _build_output_data signature + stats
2f  segmentation.py:144-148, 184-213        save_to_json + load_from_json
    ── run tests; confirm section char counts round-trip ──
3a  parser.py                               text_char_count to parsed metadata
4a  extractor.py                            char_count to each element dict
    ── run tests; confirm new fields in parsed and extracted output ──
```

---

## Success Criteria

### Phase 1 — automated

```bash
# 1. No 'length' key in any new segmented output
python3 -c "
import json, glob, sys
files = glob.glob('data/processed/latest/**/*_segmented.json', recursive=True)[:20]
bad = [f for f in files if any('length' in seg for seg in json.load(open(f)).get('segments', []))]
sys.exit(1 if bad else 0) or print('PASS: no length key found')
"

# 2. load_from_json round-trip gives correct char_count
python3 -c "
from src.preprocessing.models.segmentation import SegmentedRisks
sr = SegmentedRisks.load_from_json('data/processed/20260223_182806_preprocessing_3ef72af/AAPL_10K_2021_part1item1a_segmented.json')
assert all(seg.char_count > 0 for seg in sr.segments), 'char_count is 0 — migration fallback failed'
print('PASS: char_count round-trip correct')
"

# 3. All existing tests pass
python3 -m pytest tests/ -q --tb=short 2>&1 | tail -5
```

### Phase 2 — automated

```bash
# 4. New fields present in segmented output after a fresh run
python3 -c "
import json
d = json.load(open('PATH_TO_NEW_SEGMENTED_FILE'))
stats = d['section_metadata']['stats']
assert stats.get('raw_section_char_count') is not None, 'raw_section_char_count missing'
assert stats.get('cleaned_section_char_count') is not None, 'cleaned_section_char_count missing'
print(f'PASS: raw={stats[\"raw_section_char_count\"]} cleaned={stats[\"cleaned_section_char_count\"]}')
"

# 5. Three-tier G-02 measurement (replace PATH with a fresh run dir)
python3 -c "
import json
from pathlib import Path
run_dir = Path('PATH_TO_NEW_RUN')
losses = []
for f in run_dir.glob('*_part1item1a_segmented.json'):
    d = json.load(open(f))
    stats = d['section_metadata']['stats']
    raw = stats.get('raw_section_char_count') or 0
    seg_sum = sum(s.get('char_count', 0) for s in d.get('segments', []))
    if raw: losses.append((raw - seg_sum) / raw)
print(f'Filings: {len(losses)}, median: {sorted(losses)[len(losses)//2]*100:.2f}%, max: {max(losses)*100:.2f}%')
assert max(losses) < 0.05, f'G-02 FAIL: max loss {max(losses)*100:.2f}% >= 5%'
print('PASS: G-02 gate < 5%')
"
```

### Phase 1 — manual

- Open a fresh `*_segmented.json` from the next run and confirm `segments[0]` has
  `char_count` (not `length`).
- Load the same file via `SegmentedRisks.load_from_json()` and confirm
  `sr.segments[0].char_count == len(sr.segments[0].text)`.

### Phase 2 — manual

- Open a fresh `*_segmented.json` and confirm `section_metadata.stats` contains
  `raw_section_char_count` and `cleaned_section_char_count` as integers.
- Confirm `cleaned_section_char_count ≤ raw_section_char_count` (cleaning never
  adds chars).
- Confirm `Σ segment.char_count ≤ cleaned_section_char_count` (segmentation never
  adds chars).

### Phases 3 & 4 — automated

```bash
# 6. parsed metadata.text_char_count present and sane
python3 -c "
import json
from pathlib import Path
f = next(Path('data/processed').rglob('*_parsed.json'))
d = json.load(open(f))
tcc = d['metadata'].get('text_char_count')
assert tcc is not None, 'text_char_count missing from parsed metadata'
assert tcc < d['metadata']['html_size'], 'text_char_count should be < html_size'
print(f'PASS: text_char_count={tcc:,}, html_size={d[\"metadata\"][\"html_size\"]:,}')
"

# 7. element char_count present in extracted output and matches len(text)
python3 -c "
import json
from pathlib import Path
f = next(Path('data/processed').rglob('*_part1item1a_extracted.json'))
d = json.load(open(f))
elems = d.get('elements', [])
bad = [e for e in elems if e.get('char_count') != len(e.get('text') or '')]
assert not bad, f'{len(bad)} elements have wrong char_count'
print(f'PASS: {len(elems)} elements all have correct char_count')
"
```

### Phases 3 & 4 — manual

- Open a fresh `*_parsed.json` and confirm `metadata.text_char_count` is present
  and substantially smaller than `metadata.html_size` (expect ~10–30% ratio for
  typical 10-K filings).
- Open a fresh `*_extracted.json` and confirm `elements[0]` has `char_count` equal
  to `len(elements[0]["text"])`.
- Confirm `Σ element.char_count` ≠ `stats.text_length` (the joining-whitespace gap
  is expected — see Key Discoveries).

---

## Files Changed Summary

| File | Phase | Change |
|---|---|---|
| `scripts/data_preprocessing/run_preprocessing_pipeline.py` | 1a, 2c, 2d, 2e | `length`→`char_count`; capture raw/cleaned chars; extend `_build_output_data` |
| `src/preprocessing/models/segmentation.py` | 1b, 2a, 2f | `load_from_json` fallback; new `SegmentedRisks` fields; `save_to_json` stats; `load_from_json` stats |
| `src/config/qa_validation.py` | 1c | Dict key `length`→`char_count` at line 846 |
| `src/preprocessing/pipeline.py` | 2b | Capture raw/cleaned char counts in worker path |
| `src/preprocessing/parser.py` | 3a | Add `text_char_count` to parsed `metadata` dict |
| `src/preprocessing/extractor.py` | 4a | Add `char_count` to each element dict in serialization loop |

**No new files.** Tests that assert specific JSON output keys will need `'length'`
updated to `'char_count'` — search: `grep -rn "'length'" tests/`. Phase 3 and 4
changes are purely additive — no existing test assertions are invalidated.

## Deferred

- **Node/subsection-level char counts** — `node_subsections` is flat per-element,
  not grouped. Grouping by parent `TitleElement` requires schema restructuring in
  `SECSectionExtractor`. The element-level `char_count` from Phase 4 provides the
  raw data; aggregation can be done in a diagnostic script without a schema change.
  Track as a separate story if subsection-level loss reporting becomes a requirement.

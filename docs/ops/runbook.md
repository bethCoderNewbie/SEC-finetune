# SEC Pipeline — Operational Runbook

**Audience:** Engineers running or debugging the batch preprocessing pipeline.
**Scope:** `scripts/data_preprocessing/run_preprocessing_pipeline.py` and all `src/utils/` components.

Symptoms are organized by observable signal. Do not read the PRD when the pipeline is on fire.

---

## Quick-Reference Commands

```bash
# Start a fresh batch run
python scripts/data_preprocessing/run_preprocessing_pipeline.py --batch --workers 4

# Resume after crash (skips already-written output files)
python scripts/data_preprocessing/run_preprocessing_pipeline.py --batch --resume

# Process single file (debugging)
python scripts/data_preprocessing/run_preprocessing_pipeline.py --input data/raw/AAPL_10K.html

# Inspect the DLQ
cat logs/failed_files.json | python -m json.tool | head -60

# Inspect the latest run report
ls -lt data/processed/ | head -5
cat data/processed/<latest_run_dir>/RUN_REPORT.md

# Check checkpoint state
cat data/processed/<latest_run_dir>/_checkpoint.json | python -m json.tool
```

---

## Symptom: `_progress.log` Has Stalled

**Severity:** High
**Trigger:** No new log lines in `_progress.log` for > 15 minutes.

### Diagnosis

```bash
# 1. Is the process still alive?
pgrep -f run_preprocessing_pipeline

# 2. Check CPU
top -p $(pgrep -f preprocessing | head -1)
```

| CPU reading | Interpretation |
|:------------|:---------------|
| ~0% | Process is hung on a lock or blocking I/O |
| ~100% (single core) | Stuck in a tight loop — likely a large regex or infinite segmentation loop |
| High across multiple cores | Workers running normally; progress log may have a flush delay |

### Resolution

1. **Kill the run:**
   ```bash
   pkill -f run_preprocessing_pipeline
   ```

2. **Identify the stuck file** from the last line of `_progress.log`:
   ```bash
   tail -20 data/processed/<run_dir>/_progress.log
   ```

3. **Move the stuck file to DLQ manually** (add to `logs/failed_files.json`) or exclude it:
   ```bash
   # Exclude by moving out of data/raw/ temporarily
   mv data/raw/<stuck_file>.html /tmp/
   ```

4. **Resume the run:**
   ```bash
   python scripts/data_preprocessing/run_preprocessing_pipeline.py --batch --resume
   ```
   `CheckpointManager` will skip all files already written to the run directory.

5. **Restore the excluded file** after the batch completes, then retry it alone:
   ```bash
   mv /tmp/<stuck_file>.html data/raw/
   python scripts/data_preprocessing/run_preprocessing_pipeline.py --input data/raw/<stuck_file>.html
   ```

---

## Symptom: High Failure Rate in RUN_REPORT.md

**Severity:** High
**Trigger:** `RUN_REPORT.md` shows success rate < 80%, or DLQ has > 200 entries.

### Diagnosis

```bash
# 1. Check DLQ for common error patterns
python -c "
import json
data = json.load(open('logs/failed_files.json'))
from collections import Counter
errors = Counter(r.get('error', 'unknown')[:80] for r in data)
for err, count in errors.most_common(10):
    print(f'{count:4d}  {err}')
"

# 2. Check if failures are clustered (same SIC, same company)
python -c "
import json
data = json.load(open('logs/failed_files.json'))
print([r['file'] for r in data[:20]])
"
```

### Common Causes

| DLQ error pattern | Cause | Fix |
|:------------------|:------|:----|
| `Section 'part1item1a' not found` | Filing uses non-standard Item 1A label | Check `src/preprocessing/constants.py`; add label variant |
| `FileNotFoundError` | File moved or corrupt download | Re-download from EDGAR |
| `timeout` / `TimeoutError` | File too large for current timeout | Increase `--chunk-size` or add file to large-file list |
| `ValidationError` | Pydantic rejected the parsed output | Inspect raw file for missing CIK/SIC in EDGAR header |
| `KeyError: 'sic_code'` | Old output schema loaded from checkpoint | Delete `_checkpoint.json` and re-run without `--resume` |

### Resolution

1. Fix the root cause (code change or re-download).
2. Run the retry script against the DLQ:
   ```bash
   python scripts/utils/retry_failed_files.py
   ```
3. If retry succeeds, the DLQ removes those entries automatically.

---

## Symptom: `ZeroDivisionError` During Test Collection

**Severity:** Medium (blocks CI; known bug)
**Trigger:** `pytest --collect-only` fails with `ZeroDivisionError` in `test_validator_fix.py`.

### Diagnosis

This is a known collection error documented in PRD-002 OQ-7.

```bash
pytest tests/validation/test_validator_fix.py -x 2>&1 | tail -20
```

### Resolution (Temporary)

Exclude the broken file from CI runs:
```bash
pytest tests/ --ignore=tests/validation/test_validator_fix.py --ignore=tests/unit/test_pipeline_global_workers.py
```

Track fix in OQ-7 (PRD-002).

---

## Symptom: Workers Exit Silently (No Output, No Error)

**Severity:** High
**Trigger:** Batch run completes immediately with 0 successes, no DLQ entries, no error logs.

### Diagnosis

```bash
# Check if workers initialized
grep -i "worker" data/processed/<run_dir>/_progress.log | head -10

# Run a single file with verbose output
python scripts/data_preprocessing/run_preprocessing_pipeline.py \
  --input data/raw/<any_file>.html 2>&1 | tee /tmp/debug.log
```

### Common Causes

| Cause | Resolution |
|:------|:-----------|
| `init_preprocessing_worker()` crashed (import error, missing model) | Check `logs/` for import error; re-install `sentence-transformers` and `spacy` |
| `en_core_web_sm` not downloaded | `python -m spacy download en_core_web_sm` |
| `data/raw/` is empty | Verify input directory |
| `--resume` with no valid checkpoint | Delete `_checkpoint.json` and run fresh |

---

## Symptom: Output JSON Missing `sic_code` / `cik`

**Severity:** Medium
**Trigger:** Output `{stem}_segmented_risks.json` has `"sic_code": null` for many filings.

### Diagnosis

`sic_code` is extracted from the EDGAR `<SEC-HEADER>` block by `sec-parser`. It is absent when:

1. The filing was downloaded without the full EDGAR wrapper (just the document body)
2. The filing is an exhibit, not a primary 10-K/10-Q document

```bash
# Check EDGAR header presence in raw file
head -50 data/raw/<suspect_file>.html | grep -i "SEC-HEADER\|SIC\|CIK"
```

### Resolution

- If header is missing: re-download the full filing from EDGAR (not just the document URL)
- If header is present but not parsed: open a bug against `sec-parser==0.54.0`
- Validate after a run: `sic_code_present_rate` threshold in `configs/qa_validation/health_check.yaml`
  requires ≥ 95%; failures will appear in `RUN_REPORT.md`

---

## Symptom: Only `part1item1` and `part1item1a` Extracted — All Other Sections Silently Skipped

**Severity:** High (silent data quality failure — no error is raised)
**Trigger:** Run directory contains only `*_part1item1_segmented.json` and
`*_part1item1a_segmented.json`. No `part1item1b`, `part2item7`, `part2item7a`,
`part2item8` files appear, despite no `[SKIP]` entries in `_progress.log`.

### Cause

This is the ADR-011 pre-seeker regression. It occurs when `SECFilingParser.parse_filing()`
reverts to the `section_id or "part1item1a"` expression, causing Stage 1 to always
pre-seek Item 1A and return a ~50–200 KB fragment. sec-parser builds its tree only
from that fragment. All subsequent `extract_section()` calls for other sections return
`None` because their nodes are not in `filing.tree.nodes`.

### Diagnosis

```bash
# Confirm only 2 sections in output
ls data/processed/<run_dir>/*segmented.json

# Check parser.py Stage 1 condition — should be "if section_id is not None:"
grep -n "section_id" src/preprocessing/parser.py | grep -i "seek\|fragment\|or \""
```

Expected (correct): `if section_id is not None:`
Broken (regression): `section_id=section_id or "part1item1a"`

### Resolution

```bash
# Restore the ADR-011 fix in parser.py (src/preprocessing/parser.py ~line 168):
#   Replace:  section_id=section_id or "part1item1a"
#   With:     if section_id is not None: ... fragment = AnchorPreSeeker().seek(...)

# Verify both pipeline call sites pass preseek_id correctly:
grep -n "preseek_id" src/preprocessing/pipeline.py
# Expect two hits: one in _process_filing_with_global_workers, one in process_filing

# Re-run after fix:
python scripts/data_preprocessing/run_preprocessing_pipeline.py --input data/raw/<file>.html
ls data/processed/<new_run_dir>/*segmented.json  # should show 3–7 files
```

**Reference:** ADR-011 Rule 9 (`docs/architecture/adr/ADR-011_preseeker_single_section_constraint.md`),
RFC-005 (`docs/architecture/rfc/RFC-005_multisection_full_document_dispatch.md`).

---

## Symptom: `data/processed/.manifest.json` Is Corrupt

**Severity:** Medium
**Trigger:** `StateManager` raises `json.JSONDecodeError` on startup.

### Cause

`StateManager` uses atomic writes (temp file + rename), but a `SIGKILL` mid-rename can leave a
zero-byte temp file. The manifest file itself should not be corrupt; a temp file (`*.tmp`) may
be present alongside it.

### Resolution

```bash
# Check for orphaned temp files
ls -la data/processed/.manifest*.tmp 2>/dev/null

# If manifest is actually corrupt, delete it (state will be rebuilt from output files on next run)
mv data/processed/.manifest.json data/processed/.manifest.json.bak
# Re-run; StateManager creates a fresh manifest
```

---

## Symptom: `accession_number`, `filed_as_of_date`, `amendment_flag`, `ein` Are `null` in Segmented Output

**Severity:** Medium (silent data quality failure — pipeline succeeds, metadata is incomplete)
**Trigger:** `*_segmented.json` files have correct `company_name`, `cik`, `sic_code` but
`"accession_number": null`, `"filed_as_of_date": null`, `"amendment_flag": null`,
`"entity_filer_category": null`, `"ein": null` under `document_info`.

### Cause

`run_preprocessing_pipeline.py` (`run_pipeline` and `process_single_file_fast`) constructed
`cleaned_section` by manually listing fields in `ExtractedSection(...)`. This manual
construction only carried `sic_code`, `cik`, `ticker`, `company_name`, `form_type` —
it silently dropped the ADR-010/DEI fields added later:
`accession_number`, `filed_as_of_date`, `amendment_flag`, `entity_filer_category`, `ein`,
and `node_subsections`.

Both `--input` (single-file) and `--batch` modes used this code path.

`src/preprocessing/pipeline.py`'s `_process_filing_with_global_workers` was **not** affected —
it passes `extracted` directly to the segmenter without an intermediate `cleaned_section`.

**Fixed in:** commit `a659277` — replaced manual construction with `model_copy(update={...})`.
Any run produced before that commit may have null fields.

### Diagnosis

```bash
# 1. Spot-check a segmented output from the suspect run
python3 -c "
import json, glob, sys
files = sorted(glob.glob('data/processed/<run_dir>/*_segmented.json'))[:3]
for f in files:
    d = json.load(open(f))
    di = d.get('document_info', {})
    print(f.split('/')[-1], '|',
          'accession:', di.get('accession_number'),
          '| amendment:', di.get('amendment_flag'),
          '| ein:', di.get('ein'))
"

# 2. Confirm the corresponding extracted JSON HAS the fields (parsed correctly)
python3 -c "
import json
d = json.load(open('data/processed/<run_dir>/extracted/<stem>_<section>_extracted.json'))
print('accession_number:', d.get('accession_number'))
print('filed_as_of_date:', d.get('filed_as_of_date'))
print('amendment_flag:',   d.get('amendment_flag'))
print('ein:',              d.get('ein'))
"
```

If step 1 shows `null` and step 2 shows real values, the extracted data is intact
and the run is recoverable without re-parsing.

```bash
# 3. Verify the fix is in the current codebase (should NOT find the old pattern)
grep -n "ExtractedSection(" scripts/data_preprocessing/run_preprocessing_pipeline.py \
  | grep -v "load_from_json\|#\|import"
# Expected: no output (manual constructions are gone)
```

### Resolution: Regenerate from existing extracted JSONs (no re-parse)

Use `--from-intermediates` to load each section from the already-saved `extracted/` JSONs
and re-run only the Clean + Segment steps. The expensive HTML parse is skipped entirely.

```bash
python scripts/data_preprocessing/run_preprocessing_pipeline.py \
  --batch --no-sentiment \
  --from-intermediates data/processed/<suspect_run_dir>
```

This creates a **new** stamped run directory. Verify the output:

```bash
python3 -c "
import json, glob
files = sorted(glob.glob('data/processed/<new_run_dir>/*_segmented.json'))[:3]
for f in files:
    d = json.load(open(f))
    di = d.get('document_info', {})
    print(f.split('/')[-1], '|',
          'accession:', di.get('accession_number'),
          '| amendment:', di.get('amendment_flag'),
          '| ein:', di.get('ein'))
"
# All three fields should now be non-null
```

### Resolution: If extracted JSONs are missing

If `<suspect_run_dir>/extracted/` is absent or empty, the parse step must be re-run:

```bash
# Re-run from scratch with intermediates enabled (default)
python scripts/data_preprocessing/run_preprocessing_pipeline.py --batch
```

### Known Limitations

- `--from-intermediates` reads from `<DIR>/extracted/`. If a section's extracted JSON
  is missing, that section falls back to normal parse + extract from the source HTML.
  The source HTML must still exist in `data/raw/`.
- `amendment_flag`, `entity_filer_category`, `ein` can legitimately be `null` for
  legacy filings that pre-date XBRL inline tagging. Null in those fields is expected,
  not a pipeline bug. Distinguish by checking `filed_as_of_date`: if it is also null,
  the run was affected by this bug; if it is present, the DEI fields are genuinely absent.

---

## Symptom: Text Coverage Ratio Below 70%

**Severity:** Medium (silent content loss — pipeline succeeds but segments are incomplete)
**Trigger:** `HealthCheckValidator` reports `text_coverage_ratio` as FAIL (< 0.70) or
WARN (< 0.85) in `RUN_REPORT.md` or `check_single()` output.

### Cause

The text coverage ratio measures `sum(segment.char_count) / cleaned_section_char_count`.
Values below 70% indicate that a significant portion of the cleaned section text did not
survive segmentation. Common causes:

1. **Aggressive filtering** — many segments dropped by `_filter_segments()` as non-risk content
2. **Cross-reference drops** — `_CROSS_REF_DROP_PAT` removing substantive paragraphs
3. **Merge absorption** — `_merge_short_segments()` combining too aggressively
4. **Table-heavy section** — most content was in tables (excluded from segmentation)

### Diagnosis

```bash
# 1. Check the segmentation_stats in the affected output file
python -c "
import json, sys
d = json.load(open(sys.argv[1]))
stats = d.get('section_metadata', {}).get('stats', {})
print('text_coverage:', json.dumps(stats.get('text_coverage'), indent=2))
print('segmentation_stats:', json.dumps(stats.get('segmentation_stats'), indent=2))
print('table_char_count:', stats.get('table_char_count'))
print('pre_exclusion_char_count:', stats.get('pre_exclusion_char_count'))
" data/processed/<run_dir>/<file>_segmented.json

# 2. Check if tables account for the missing content
# If table_char_count is high relative to pre_exclusion_char_count, the content
# is in tables (expected — tables are excluded from risk segmentation).

# 3. Check filter breakdown
# If filtered_non_risk or cross_ref_drops are high, review the section content
# to determine if the filter patterns are too aggressive.
```

### Resolution

| Finding | Resolution |
|:--------|:-----------|
| High `table_char_count` | Expected for financial statements sections. Consider if this section should be excluded from the extraction config. |
| High `filtered_non_risk` | Review `_is_non_risk_content()` patterns in `src/preprocessing/segmenter.py` — they may be too aggressive for this filing type. |
| High `cross_ref_drops` | The cross-ref pattern (`_CROSS_REF_DROP_PAT`) may be dropping substantive paragraphs. Check `segmenter.py:15-19`. |
| High `segments_merged` | `_merge_short_segments()` is absorbing too much. Review `min_length` threshold in `configs/config.yaml`. |
| All stats look normal | The coverage loss may be in whitespace normalization or Unicode cleaning. Compare `raw_section_char_count` vs `cleaned_section_char_count`. |

**Reference:** ADR-020 (extraction/segmentation completeness), `src/config/qa_validation.py:_check_completeness()`

---

## Routine Maintenance

### Prune old run directories

```bash
# List run dirs older than 30 days
find data/processed -maxdepth 1 -type d -mtime +30 -name "*_preprocessing_*"

# Delete (review before running)
find data/processed -maxdepth 1 -type d -mtime +30 -name "*_preprocessing_*" -exec rm -rf {} +
```

### Verify test suite after any `src/` change

```bash
pytest tests/ \
  --ignore=tests/validation/test_validator_fix.py \
  --ignore=tests/unit/test_pipeline_global_workers.py \
  -q
```

---

## Feature Engineering / Annotation

### Symptom: `segment_annotator_cli.py` exits 0 but `labeled.jsonl` is empty or has far fewer records than expected

**Severity:** Medium
**Trigger:** All `*_segmented.json` files in `--run-dir` have a `section_identifier` that is not
in the `--include-sections` list (default: `part1item1a`, `part2item7a`, `part1item1c`), or the
run directory contains an old schema version that lacks the `section_metadata.identifier` field.

**Diagnosis:**

```bash
# 1. Check what section identifiers are actually in the run directory
python -c "
import json, glob, sys
run_dir = sys.argv[1]
ids = set()
for f in glob.glob(run_dir + '/*_segmented.json'):
    d = json.load(open(f))
    ids.add(d.get('section_metadata', {}).get('identifier', '<missing>'))
print(sorted(ids))
" data/processed/<run_dir>

# 2. Confirm the run used v2-schema (post-ADR-014 run dirs have 'section_metadata' key)
python -c "
import json; d = json.load(open('data/processed/<run_dir>/<any>_segmented.json'))
print('version:', d.get('version'), 'has section_metadata:', 'section_metadata' in d)
"
```

**Resolution:**

```bash
# Pass --include-sections matching the identifiers found above
python scripts/feature_engineering/segment_annotator_cli.py \
    --run-dir data/processed/<run_dir> \
    --output /tmp/labeled.jsonl \
    --include-sections part1item1a part2item7a  # use identifiers found in diagnosis step

# If run dir is pre-ADR-014 (no section_metadata), re-run preprocessing with current pipeline
# and annotate the new run directory.
```

**Known limitations:** The annotator only reads v2-schema files (`"version": "2.1"` with
`section_metadata` key). Files written before the ADR-014 `ancestors` field was introduced
will not produce any records.

---

### Symptom: `segment_annotator_cli.py` raises `RuntimeError: filed_as_of_date is None`

**Severity:** Medium
**Trigger:** A `*_segmented.json` file was written before the B-5 fix
(`segmentation.py:load_from_json` lines 204–224). `filed_as_of_date` is absent from the
constructor call, so `segmented.filed_as_of_date` is `None` after `load_from_json()`.

**Diagnosis:**

```bash
python -c "
from src.preprocessing.models.segmentation import SegmentedRisks
import json
d = json.load(open('data/processed/<run_dir>/<file>_segmented.json'))
sr = SegmentedRisks.load_from_json(json.dumps(d))
print('filed_as_of_date:', sr.filed_as_of_date)
"
```

**Resolution:** Verify that `src/preprocessing/models/segmentation.py` contains the B-5 fix
(lines 204–224 include `filed_as_of_date=di.get('filed_as_of_date')`). If the fix is absent,
apply the patch from US-032 and re-run the annotator. The annotator emits `filing_date: null`
for records with `filed_as_of_date is None` — it does not raise; the `RuntimeError` above is
for illustration only.

Expected: ≥ 658 passed, 0 errors (excludes 2 known broken collection files).

---

---

# Analysis Layer Runbook (PRD-005 / ADR-017)

**Audience:** Engineers running or debugging `python -m src.analysis.cli`.
**Scope:** `src/analysis/` — orchestrator, skills, agents.

## Quick-Reference Commands

```bash
# Run a full single-company analysis
python -m src.analysis.cli analyze company AAPL --year 2024

# Run without LLM narration (narration is skipped automatically when key is absent)
ANTHROPIC_API_KEY="" python -m src.analysis.cli analyze company AAPL --year 2024

# Explicit run-dir (skip auto-discovery)
python -m src.analysis.cli analyze company AAPL --run-dir data/processed/20260220_185647_preprocessing_b9fb777

# Compare two companies
python -m src.analysis.cli compare AAPL MSFT --year 2024

# Sector report
python -m src.analysis.cli analyze sector 3571 --year 2024

# YoY trend (3-year window)
python -m src.analysis.cli trend AAPL --years 3

# Shorthand alias (US-041)
python -m src.analysis.cli report AAPL --format json

# Inspect trace
cat data/reports/<run_id>/agent_trace.jsonl | python -m json.tool | head -40

# Validate report schema
python -c "
from src.analysis.models.analysis import AnalysisResult
import json
AnalysisResult.model_validate(json.load(open('data/reports/<run_id>/report.json')))
print('schema OK')
"
```

---

## Symptom: `FilingNotFoundError` — no segmented JSON found

**Severity:** Medium
**Trigger:** `python -m src.analysis.cli analyze company AAPL` raises or exits 2 with:
```
[load_filing] No segmented JSON found for ticker='AAPL' fiscal_year='2024' in run_dir=...
```

**Diagnosis:**

```bash
# 1. Confirm the run directory exists and contains *_segmented.json files
ls data/processed/ | tail -5
ls data/processed/<latest_run_dir>/ | grep segmented | head -10

# 2. Check the ticker field in the candidate files
python -c "
import json, pathlib
for f in pathlib.Path('data/processed/<run_dir>').rglob('*_segmented.json'):
    d = json.load(open(f))
    di = d.get('document_info', d)
    print(di.get('ticker'), di.get('fiscal_year'), f.name)
" | grep -i aapl
```

**Resolution:**

| Finding | Resolution |
|---------|------------|
| No `*_segmented.json` files at all | The preprocessing pipeline has not been run yet. Run it first: `python scripts/data_preprocessing/run_preprocessing_pipeline.py --batch` |
| Files exist but wrong ticker capitalization | The lookup is case-insensitive; this is a code bug — open an issue. |
| Correct ticker found but wrong `fiscal_year` | Pass `--year` matching the fiscal_year in `document_info.fiscal_year`. |
| Correct ticker+year but different `--run-dir` | Pass `--run-dir <path>` explicitly to the correct stamped directory. |

---

## Symptom: `SkillTimeoutError` — skill timed out

**Severity:** Medium
**Trigger:** Exit code 2 with:
```
[classify_filing] Timed out after 30s
```

**Diagnosis:**

The NLI model (`facebook/bart-large-mnli`) can be slow on CPU for large filings.
```bash
# Check how many segments the filing has
python -c "
from src.analysis.skills.filing_loader import load_filing
s = load_filing('AAPL', '2024')
print(len(s.segments), 'segments')
"
```

**Resolution:**

```bash
# Increase timeout via env var
SEC_ANALYSIS__SKILL_TIMEOUT_SECONDS=120 python -m src.analysis.cli analyze company AAPL

# Or use GPU if available (set CUDA device)
SEC_ANNOTATION__DEVICE=0 SEC_ANALYSIS__SKILL_TIMEOUT_SECONDS=60 python -m src.analysis.cli analyze company AAPL
```

---

## Symptom: Phase C narration skipped — `ANTHROPIC_API_KEY not set`

**Severity:** Low (informational)
**Trigger:** Log line:
```
INFO  src.analysis.orchestrator  ANTHROPIC_API_KEY not set — skipping narrative summaries (Phase C).
```

**This is not an error.** The report is still written; `narrative_summary` fields in `report.json`
will be `null`.

**Resolution:**
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
python -m src.analysis.cli analyze company AAPL
```

---

## Symptom: `ImportError: No module named 'anthropic'`

**Severity:** High
**Trigger:** Phase C narration raises `ImportError` at `src/analysis/skills/narrator.py`.

**Resolution:**
```bash
pip install anthropic>=0.40.0
# Or reinstall all project deps:
pip install -e ".[dev]"
```

---

## Symptom: `analyze sector` exits 2 — fewer than minimum filings

**Severity:** Medium
**Trigger:**
```
[analyze_sector] Found only 1 filing(s) for SIC 3571; minimum required is 2.
```

**Diagnosis:**
```bash
python -c "
import json, pathlib
for f in pathlib.Path('data/processed').rglob('*_segmented.json'):
    d = json.load(open(f))
    di = d.get('document_info', d)
    if di.get('sic_code') == '3571':
        print(di.get('ticker'), di.get('fiscal_year'))
"
```

**Resolution:** Either preprocess more filings for the SIC code, or lower the minimum:
```bash
SEC_ANALYSIS__SECTOR_MIN_FILINGS=1 python -m src.analysis.cli analyze sector 3571
```

---

## Symptom: `report.json` fails Pydantic schema validation

**Severity:** High
**Trigger:** The `AnalysisResult` model raises a `ValidationError` when loading an existing
`report.json`. Usually indicates a schema version mismatch.

**Diagnosis:**
```bash
python -c "
import json
from src.analysis.models.analysis import AnalysisResult
r = json.load(open('data/reports/<run_id>/report.json'))
print('schema_version:', r.get('schema_version'))
AnalysisResult.model_validate(r)
"
```

**Resolution:** If `schema_version` is absent or `< 1.0`, the file was written by a pre-release
version of the analysis layer. Re-run the command against the same `--run-dir` to regenerate
a valid `report.json`.

---

## Symptom: `agent_trace.jsonl` is empty or missing

**Severity:** Low
**Trigger:** `agent_trace.jsonl` is absent from `data/reports/<run_id>/` after a successful run.

**Diagnosis:**
```bash
grep "trace_logging" src/config/analysis.py
# Check if it was disabled via env var:
echo $SEC_ANALYSIS__TRACE_LOGGING
```

**Resolution:**
```bash
# Ensure trace logging is enabled (default: true)
SEC_ANALYSIS__TRACE_LOGGING=true python -m src.analysis.cli analyze company AAPL
```

---

## Symptom: Downstream analysis produces unexpected results (missing labels, zero scores, empty text)

**Severity:** Medium
**Trigger:** Reports contain empty text segments, labels not matching SASB archetypes, confidence values outside [0, 1], or zero risk scores for filings that should have risk content.

**Diagnosis:**
```bash
# Run the quality audit on the database
python -m src.storage.cli status --quality

# Example output:
#   Quality Audit:
#   ========================================
#     [  OK] Missing CIK: 0
#     [FAIL] Missing Company Name: 3
#     [  OK] Zero Segments: 0
#     [  OK] Missing SIC Code: 0
#     [  OK] Empty Classification Text: 0
#     [FAIL] Invalid Risk Labels: 2
#     [  OK] Out-of-Range Confidence: 0
#     [  OK] Invalid Label Sources: 0
#   ========================================
#   Total issues: 5
```

**Resolution:**

If issues are found in filings (missing CIK, zero segments, missing company name):
```bash
# Re-backfill from the latest run directory — validation gates now filter bad files
python -m src.storage.cli backfill-latest
```

If issues are found in classifications (invalid labels, out-of-range confidence):
```bash
# Re-classify all filings (forces re-annotation with validation gates active)
python -m src.storage.cli classify-all --force
```

If the source data is bad (HTML artifacts, missing ticker), fix the preprocessing input
and re-run the pipeline:
```bash
python scripts/data_preprocessing/run_preprocessing_pipeline.py --batch --workers 4
python -m src.storage.cli backfill-latest
python -m src.storage.cli classify-all
```

**References:** ADR-019 (boundary quality gates), `src/validation/quality_gates.py`, `src/storage/cli.py:_run_quality_audit()`

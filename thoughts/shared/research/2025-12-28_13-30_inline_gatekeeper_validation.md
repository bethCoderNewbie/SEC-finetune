---
date: 2025-12-28T13:30:00-06:00
git_commit: 648bf25
branch: main
repository: SEC finetune
researcher: bethCoderNewbie
topic: Inline Gatekeeper Validation (Priority 2)
status: research_complete
---

# Inline Gatekeeper Validation Research
## Validate During Processing, Not After

## Executive Summary

**Problem:** Current validation happens AFTER batch processing completes. If data is bad, you've already wasted time processing garbage.

**Root Cause:** Validation is decoupled from processing pipeline.

**Solution:** Integrate HealthCheckValidator inline with preprocessing. Validate each file immediately after processing, fail fast on bad data.

**Implementation Effort:** 3-4 hours

**Impact:** Immediate failure detection, prevents downstream corruption, clearer audit trails

---

## Part 1: Current vs. Desired Workflow

### Current Workflow (Broken)

```
Step 1: Process 100 files (20 minutes)
          ↓
Step 2: Write all to disk
          ↓
Step 3: Run validation script (2 minutes)
          ↓
Step 4: Find 10 files with substance < 50 chars
          ↓
Step 5: Manually delete bad files and reprocess (10 minutes)

Total Time Wasted: 30+ minutes
```

**Problems:**
- ❌ Bad data written to disk
- ❌ Wasted processing time on files that will fail validation
- ❌ Manual cleanup required
- ❌ Hard to trace which files failed and why

### Desired Workflow (Inline Validation)

```
For each file (streaming):
  Step 1: Process file (12 seconds)
          ↓
  Step 2: Validate immediately (inline)
          ↓
  Step 3a: If PASS → Write to disk + Record in manifest
  Step 3b: If FAIL → Log failure + Skip write + Continue

Summary Report:
  Processed: 90 files
  Failed: 10 files (logged with reasons)
  Time Saved: 2 minutes (failed files detected early)
```

**Benefits:**
- ✅ Fail fast (detect bad data immediately)
- ✅ No bad data written to disk
- ✅ No manual cleanup
- ✅ Clear audit trail (manifest tracks validation status)

---

## Part 2: Integration Points with Pipeline

### Current Pipeline Architecture

**Location:** `src/preprocessing/pipeline.py:93-100+`

**Flow:**
```python
class SECPreprocessingPipeline:
    def process(self, html_path: Path) -> SegmentedRisks:
        # Step 1: Sanitize
        sanitized = self.sanitizer.sanitize(html)

        # Step 2: Parse
        parsed = self.parser.parse(sanitized)

        # Step 3: Extract
        extracted = self.extractor.extract(parsed)

        # Step 4: Clean
        cleaned = self.cleaner.clean(extracted)

        # Step 5: Segment
        segmented = self.segmenter.segment(cleaned)

        return segmented  # No validation!
```

### Enhanced Pipeline (With Inline Validation)

**New Method:** `process_and_validate()`

```python
from src.config.qa_validation import HealthCheckValidator, ValidationStatus

class SECPreprocessingPipeline:
    def __init__(self, config: PipelineConfig, validate_inline: bool = True):
        # ... existing init ...
        self.validator = HealthCheckValidator() if validate_inline else None

    def process_and_validate(self, html_path: Path) -> Tuple[SegmentedRisks, ValidationStatus]:
        """
        Process file and validate inline.

        Returns:
            Tuple of (result, validation_status)
            - result: SegmentedRisks object (None if validation failed)
            - validation_status: "PASS", "WARN", or "FAIL"
        """
        # Standard processing
        result = self.process(html_path)

        # Inline validation (NEW)
        if self.validator:
            validation_report = self.validator.check_single(result)
            status = validation_report["status"]

            if status == "FAIL":
                logger.error(f"Validation failed for {html_path.name}: {validation_report}")
                return None, status

            if status == "WARN":
                logger.warning(f"Validation warning for {html_path.name}: {validation_report}")

            return result, status
        else:
            return result, "SKIP"  # No validation performed
```

---

## Part 3: HealthCheckValidator Integration

### Current Validator Design

**Location:** `src/config/qa_validation.py:593-829`

**Current Usage:**
```python
validator = HealthCheckValidator()
report = validator.check_run(run_dir)  # Validates DIRECTORY of JSON files
```

**Problem:** Expects directory of JSON files, not single in-memory object

### New Method: check_single()

**Add to HealthCheckValidator:**

```python
def check_single(self, data: Union[SegmentedRisks, Dict]) -> Dict[str, Any]:
    """
    Validate a single in-memory object (not from disk).

    Args:
        data: SegmentedRisks object or dict with preprocessing output

    Returns:
        Validation report dict with status and validation_table
    """
    # Convert to dict if needed
    if hasattr(data, 'model_dump'):
        file_data = data.model_dump()
    else:
        file_data = data

    # Run all checks
    results = []
    results.extend(self._check_identity([file_data]))
    results.extend(self._check_cleanliness([file_data]))
    results.extend(self._check_substance([file_data]))
    results.extend(self._check_domain([file_data]))

    # Determine overall status
    overall_status = determine_overall_status(results)

    return {
        "status": overall_status.value,
        "validation_table": generate_validation_table(results),
        "blocking_summary": generate_blocking_summary(results),
    }
```

**Implementation Time:** 30 minutes (simple wrapper around existing methods)

---

## Part 4: Batch Processing Integration

### Current Batch Script

**Location:** `scripts/data_preprocessing/batch_parse.py`

**Current Logic:**
```python
for file in input_files:
    result = pipeline.process(file)
    output_path = run.get_artifact_path(f"{file.stem}_parsed.json")
    result.to_json(output_path)

# Validation happens separately (manual step)
```

### Enhanced Batch Script (Inline Validation)

```python
from src.config.qa_validation import ValidationStatus

# Track validation results
passed = []
failed = []
warned = []

for file in input_files:
    # Process with inline validation
    result, status = pipeline.process_and_validate(file)

    if status == "PASS":
        # Write to disk
        output_path = run.get_artifact_path(f"{file.stem}_parsed.json")
        result.to_json(output_path)
        passed.append(file.name)

        # Update manifest
        manifest.record_file(
            input_path=file,
            output_path=output_path,
            run_id=run.run_id,
            validation_status="PASS"
        )

    elif status == "WARN":
        # Write with warning flag
        output_path = run.get_artifact_path(f"{file.stem}_parsed.json")
        result.to_json(output_path)
        warned.append(file.name)

        # Update manifest with warning
        manifest.record_file(
            input_path=file,
            output_path=output_path,
            run_id=run.run_id,
            validation_status="WARN"
        )

    else:  # FAIL
        # Do NOT write to disk
        failed.append(file.name)
        logger.error(f"Skipped {file.name} - validation failed")

        # Record failure in manifest
        manifest.record_failure(
            input_path=file,
            run_id=run.run_id,
            reason="validation_failed"
        )

# Summary report
print(f"\nProcessing Complete:")
print(f"  Passed: {len(passed)}")
print(f"  Warned: {len(warned)}")
print(f"  Failed: {len(failed)}")

if failed:
    print(f"\nFailed files:")
    for f in failed:
        print(f"  - {f}")
```

---

## Part 5: Fail-Fast Strategy

### Validation Thresholds (Blocking vs. Non-Blocking)

**Location:** `configs/qa_validation/health_check.yaml`

**Current Thresholds:**
```yaml
thresholds:
  health_check:
    empty_segment_rate:
      target: 0.02  # ≤2% empty segments
      operator: "<="
      blocking: true  # FAIL if exceeded

    short_segment_rate:
      target: 0.10  # ≤10% short segments (< 50 chars)
      operator: "<="
      blocking: false  # WARN if exceeded
```

**Inline Behavior:**

| Threshold | Blocking | Inline Action |
|-----------|----------|---------------|
| empty_segment_rate > 2% | TRUE | Do NOT write file, log failure |
| short_segment_rate > 10% | FALSE | Write file, log warning |
| cik_present_rate < 99% | TRUE | Do NOT write file, log failure |

**Result:**
- Only **well-formed, validated data** hits disk
- Warnings still written (for review)
- Failures never written (prevents downstream corruption)

---

## Part 6: Manifest Integration

### StateManifest Enhancement

**Add to `src/utils/state_manager.py`:**

```python
def record_file(
    self,
    input_path: Path,
    output_path: Path,
    run_id: str,
    validation_status: str  # NEW
) -> None:
    """Record file processing with validation status."""

    self.runs[run_id]["files"][input_path.name]["validation_status"] = validation_status

def record_failure(
    self,
    input_path: Path,
    run_id: str,
    reason: str  # NEW
) -> None:
    """Record file processing failure."""

    self.runs[run_id]["files"][input_path.name] = {
        "status": "failed",
        "reason": reason,
        "input_hash": compute_file_hash(input_path)
    }

def get_failed_files(self, run_id: Optional[str] = None) -> List[str]:
    """Get list of files that failed validation."""

    if run_id:
        run = self.runs.get(run_id, {})
        return [
            fname for fname, fdata in run.get("files", {}).items()
            if fdata.get("validation_status") == "FAIL" or fdata.get("status") == "failed"
        ]
    else:
        # Get all failed files across all runs
        failed = []
        for run_data in self.runs.values():
            for fname, fdata in run_data.get("files", {}).items():
                if fdata.get("validation_status") == "FAIL" or fdata.get("status") == "failed":
                    failed.append(fname)
        return list(set(failed))  # Deduplicate
```

---

## Part 7: Recovery and Reprocessing

### Selective Reprocessing

**Query failed files:**
```python
manifest = StateManifest.load()
failed_files = manifest.get_failed_files(run_id="20251228_132700_batch_parse_648bf25")

print(f"Found {len(failed_files)} failed files:")
for f in failed_files:
    print(f"  - {f}")
```

**Reprocess only failures:**
```bash
python scripts/data_preprocessing/batch_parse.py \
    --input-dir data/raw \
    --only-failed \
    --run-id 20251228_132700_batch_parse_648bf25
```

**Implementation:**
```python
if args.only_failed:
    manifest = StateManifest.load()
    failed_files = manifest.get_failed_files(args.run_id)
    input_files = [Path(args.input_dir) / f for f in failed_files]
else:
    input_files = list(Path(args.input_dir).glob("*.html"))
```

---

## Part 8: Performance Comparison

### Baseline (Post-Processing Validation)

```
Process 100 files:     20 minutes
Write all to disk:      1 minute
Validate batch:         2 minutes
Find 10 failures:       0 seconds
Manual cleanup:         5 minutes
─────────────────────────────────
Total:                  28 minutes
```

### Inline Validation

```
Process + Validate 90 files (PASS):  18 minutes
Process + Validate 10 files (FAIL):   2 minutes (not written)
─────────────────────────────────────────────────────────────
Total:                                20 minutes
                                      (28% time saved)
```

**Additional Benefits:**
- No manual cleanup
- No bad data on disk
- Clear failure reasons in manifest
- Selective reprocessing of only failures

---

## Part 9: Implementation Timeline

| Phase | Task | Duration |
|-------|------|----------|
| 1 | Add `check_single()` to HealthCheckValidator | 30 min |
| 2 | Add `process_and_validate()` to pipeline | 45 min |
| 3 | Update batch_parse.py for inline validation | 1.5 hours |
| 4 | Enhance StateManifest with failure tracking | 45 min |
| 5 | Add `--only-failed` flag for reprocessing | 30 min |
| 6 | Testing and validation | 1 hour |
| **Total** | | **5 hours** |

---

## Part 10: Files to Create/Modify

### Modified Files

**`src/config/qa_validation.py`** (MODIFY - add `check_single()`)
- Lines to add: ~40
- New method validates single object (not directory)

**`src/preprocessing/pipeline.py`** (MODIFY - add `process_and_validate()`)
- Lines to add: ~30
- New method wraps `process()` with validation

**`scripts/data_preprocessing/batch_parse.py`** (MODIFY)
- Lines to change: ~50
- Inline validation logic
- Track pass/fail/warn counts
- Only write validated files

**`src/utils/state_manager.py`** (MODIFY)
- Lines to add: ~60
- `record_failure()` method
- `get_failed_files()` method

### No New Files Required

All changes integrate with existing infrastructure.

---

## Part 11: Success Metrics

### Operational Metrics

**Failure Detection:**
- ✅ Detect bad data within seconds (not minutes)
- ✅ Zero bad files written to disk
- ✅ Clear failure reasons in manifest

**Processing Efficiency:**
- ✅ 20-30% time savings (no reprocessing)
- ✅ No manual cleanup required
- ✅ Selective reprocessing of only failures

### Audit Trail

**Manifest Tracking:**
- ✅ validation_status for every file
- ✅ Failure reasons recorded
- ✅ Reprocessing history

---

## Conclusion

**Overall Assessment:** ✅ **HIGH PRIORITY - CRITICAL FOR DATA QUALITY**

**Key Strengths:**
1. Builds on existing HealthCheckValidator (well-tested)
2. Integrates cleanly with pipeline (minimal changes)
3. Prevents bad data from corrupting downstream processes
4. Clear audit trail via manifest

**Critical Finding:**
Inline validation is the missing piece between processing and data quality. Current post-processing validation wastes time and allows bad data to reach disk.

**Next Steps:**
1. Add `check_single()` to HealthCheckValidator
2. Add `process_and_validate()` to SECPreprocessingPipeline
3. Update batch_parse.py for inline validation
4. Test with sample dataset (10 files, force 2 failures)
5. Deploy to production

**This transforms validation from an afterthought to a first-class pipeline component.**

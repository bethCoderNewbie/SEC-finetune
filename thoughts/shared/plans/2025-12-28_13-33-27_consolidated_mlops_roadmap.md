---
date: 2025-12-28T13:52:06-06:00
git_commit: 648bf25
branch: main
repository: SEC finetune
researcher: bethCoderNewbie
topic: Consolidated MLOps Implementation Roadmap (Priorities 1-3) - Production-Ready Edition
status: ready_for_implementation
revision: 2.0
---

# Consolidated MLOps Implementation Roadmap
## From "Scripts That Run" to "Pipeline That Is Production-Ready"

## Executive Summary

**Total Implementation Effort:** 17.5 hours active development + 2 hours testing/deployment

**Priorities:**
1. **State Management & Incremental Processing** (6.5 hours) - Foundation + Production Hardening
2. **Inline Gatekeeper Validation** (6.5 hours) - Data Quality + Quarantine Pattern
3. **Auto-Documentation System** (4.5 hours) - Audit Trail + Interactive Reports

**Expected Impact:**
- 60-90% reduction in preprocessing time (subsequent runs)
- Zero bad data written to production directories
- Complete audit trail for compliance (FDA 21 CFR Part 11 ready)
- Production-ready preprocessing pipeline with failure recovery

**Key Enhancements (Rev 2.0):**
- ✅ Atomic writes to prevent manifest corruption
- ✅ Quarantine pattern for failed files (no silent drops)
- ✅ Config snapshot for full reproducibility
- ✅ Interactive markdown reports with clickable links
- ✅ Deleted file cleanup in manifest

---

## Part 1: Strategic Context

### Hierarchy of Needs for ML

```
     [Drift Detection]         ← DEFERRED (monitoring garbage is still garbage)
     [Model Monitoring]
     ───────────────────
     [Audit Trails]            ← Priority 3 (CLEANING_SUMMARY.md + Config Snapshot)
     [Data Validation]         ← Priority 2 (Inline Gatekeeper + Quarantine)
     [State Management]        ← Priority 1 (DVC-lite + Atomic Writes)
```

### Why This Order?

**Priority 1 enables Priority 2:**
- State management tracks which files to process
- Inline validation determines which files pass/fail
- Manifest records validation status for each file
- **NEW:** Atomic writes prevent corruption, config snapshot enables reproducibility

**Priority 2 enables Priority 3:**
- Validation results feed into documentation
- Pass/fail counts populate summary reports
- Failure details included in audit trail
- **NEW:** Quarantined files available for inspection and debugging

**All 3 enable future priorities:**
- Clean data foundation → reliable model training
- Complete audit trail → drift detection makes sense
- Resilient pipeline → automated CI/CD deployment
- **NEW:** Production-ready infrastructure → compliance and regulatory approval

---

## Part 2: Dependency Graph

```
┌─────────────────────────────────────────────────────────────────┐
│ Priority 1: State Management (Week 1)                          │
│ ┌───────────────────────────────────────────────────────────┐   │
│ │ StateManifest class                                       │   │
│ │ ├─ File hash tracking (SHA-256)                          │   │
│ │ ├─ Atomic writes (temp + rename)                  [NEW]  │   │
│ │ ├─ Config snapshot capture                        [NEW]  │   │
│ │ ├─ Prune deleted files                            [NEW]  │   │
│ │ ├─ Incremental processing logic                          │   │
│ │ └─ Integration with batch_parse.py                       │   │
│ └───────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                            │
                            │ Enables
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ Priority 2: Inline Validation (Week 2)                         │
│ ┌───────────────────────────────────────────────────────────┐   │
│ │ HealthCheckValidator.check_single()                       │   │
│ │ ├─ Validate in-memory objects                            │   │
│ │ ├─ Pipeline.process_and_validate()                       │   │
│ │ ├─ Quarantine pattern (not silent drop)          [NEW]  │   │
│ │ └─ Manifest integration (validation + quarantine)        │   │
│ └───────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                            │
                            │ Enables
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ Priority 3: Auto-Documentation (Week 2)                        │
│ ┌───────────────────────────────────────────────────────────┐   │
│ │ ReportFormatter.generate_markdown_report()                │   │
│ │ ├─ Section generators (header, overview, results)        │   │
│ │ ├─ Interactive links to files                     [NEW]  │   │
│ │ ├─ Integration with batch processing                     │   │
│ │ └─ reports/preprocessing_validation_summary_{run_id}.md   │   │
│ └───────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Part 3: Production-Ready Best Practices

### 1. Atomic Writes

**Problem:** Manifest corruption if process crashes mid-write
**Solution:** Write to temp file + atomic rename
**Implementation:** `StateManifest.save()` with platform-specific handling

```python
def save(self) -> None:
    """Save manifest with atomic write to prevent corruption."""
    temp_fd, temp_path = tempfile.mkstemp(
        dir=self.manifest_path.parent,
        prefix='.manifest_',
        suffix='.tmp'
    )

    try:
        with os.fdopen(temp_fd, 'w') as f:
            json.dump(self.data, f, indent=2, default=str)

        # Platform-specific atomic rename
        if platform.system() == 'Windows':
            backup = self.manifest_path.with_suffix('.json.bak')
            shutil.copy2(self.manifest_path, backup)
            self.manifest_path.unlink()

        shutil.move(temp_path, self.manifest_path)
    except Exception:
        Path(temp_path).unlink(missing_ok=True)
        raise
```

### 2. Quarantine Pattern

**Problem:** Silent drops hide root causes (validator bugs, edge cases)
**Solution:** Quarantine failed files with detailed reports

**Directory Structure:**
```
data/
├── interim/parsed/20251228_133000_batch_parse_648bf25/
│   ├── AAPL_10K_2024_parsed.json  (PASS)
│   └── validation_report.json
└── quarantine_20251228_133000_batch_parse_648bf25/
    ├── TSLA_10K_2024_FAILED.json
    └── TSLA_10K_2024_FAILURE_REPORT.md

reports/
└── preprocessing_validation_summary_20251228_133000_batch_parse_648bf25.md
```

**Benefits:**
- ✅ Engineers can inspect WHY validation failed
- ✅ Catch validator false positives
- ✅ Recovery path: fix → reprocess quarantined files
- ✅ Complete audit trail (nothing disappears)

### 3. Config Snapshot

**Problem:** Can't reproduce old runs without exact config + environment
**Solution:** Capture config snapshot in manifest

**Captured Data:**
- Pipeline configuration (all settings)
- Python version + platform
- Key dependency versions
- Git commit + branch + researcher

**Auditability:** FDA 21 CFR Part 11 compliance-ready

### 4. Interactive Documentation

**Problem:** Static markdown reports not actionable
**Solution:** Relative links to files (clickable in IDE/GitHub)

```markdown
### ⚠️ Warnings (5 files)

**[TSLA_10K_2024.json](./TSLA_10K_2024.json)**  ← Click to open
- Short Segment Rate: 12% (threshold: ≤10%)
```

### 5. Naming Convention for Generated Reports

**Convention:** `reports/preprocessing_validation_summary_{run_id}.md`

**Filename Structure:**
```
preprocessing_validation_summary_{timestamp}_{stage}_{git_sha}.md
                 │                    │         │        │
                 │                    │         │        └─ Code version (reproducibility)
                 │                    │         └────────── Pipeline stage
                 │                    └──────────────────── When (chronological sorting)
                 └───────────────────────────────────────── What (pipeline + operation)
```

**Rationale:**
- **Descriptive** - Clearly states: preprocessing pipeline + validation operation + summary type
- **Centralization** - All reports in `reports/` directory (established pattern)
- **Auditability** - Unique filename per run prevents overwriting
- **Reproducibility** - Includes git commit for exact code version
- **Discoverability** - Easy to locate all validation reports
- **Sortable** - Timestamp-first enables chronological listing

**Example:**
```
reports/
├── preprocessing_validation_summary_20251228_133000_batch_parse_648bf25.md
├── preprocessing_validation_summary_20251228_150000_batch_parse_648bf25.md
└── validation_report_2025-12-15.md  (existing pattern - less descriptive)
```

**Comparison with Alternatives:**
- ❌ `cleaning_summary_{run_id}.md` - Less clear what "cleaning" means
- ❌ `CLEANING_SUMMARY.md` - Gets overwritten, no run tracking
- ❌ `data/interim/.../summary.md` - Scattered across output directories
- ✅ `preprocessing_validation_summary_{run_id}.md` - **Clear, descriptive, reproducible**

**Reference:** `thoughts/shared/research/2025-12-28_13-45-00_naming_and_reporting_rules.md:136` (enhanced for clarity)

### 6. Concurrency Planning

**Current:** Single-threaded (safe for JSON manifest)
**Future:** When parallelizing, use:
1. File-level locking (`filelock` library)
2. SQLite backend (ACID guarantees)
3. Append-only log + periodic compaction

**Migration Trigger:** When `batch_parse.py` adds `ProcessPoolExecutor`

---

## Part 4: Phased Implementation

### Week 1: Priority 1 - State Management (6.5 hours)

#### Phase 1.1: StateManifest Infrastructure (3 hours)

**File:** `src/utils/state_manager.py` (~300 lines)

**Key Components:**
- `StateManifest` class with atomic writes
- `compute_file_hash()` - SHA-256 with 64KB chunks
- `prune_deleted_files()` - Manifest cleanup
- `_capture_run_config()` - Config snapshot
- Concurrency assumption documentation

**Testing:**
- Atomic write verification (simulate crash mid-save)
- Hash computation correctness
- Prune deleted files (remove 3, verify manifest updated)
- Config snapshot serialization

#### Phase 1.2: RunContext Integration (1 hour)

**File:** `src/config/run_context.py`

**Enhancement:**
```python
class RunContext:
    def __init__(self, name: str, capture_config: bool = True):
        if capture_config:
            self.config_snapshot = self._capture_config_snapshot()
```

#### Phase 1.3: Batch Integration (1.5 hours)

**File:** `scripts/data_preprocessing/batch_parse.py`

**Add flags:**
- `--incremental` - Skip unchanged files
- `--prune-deleted` - Clean manifest

#### Phase 1.4: Documentation (1 hour)

---

### Week 2: Priority 2 - Inline Validation (6.5 hours)

#### Phase 2.1: HealthCheckValidator (30 min)

**File:** `src/config/qa_validation.py`

**Add:** `check_single()` method for in-memory validation

#### Phase 2.2: Pipeline Integration (1 hour)

**File:** `src/preprocessing/pipeline.py`

**Add:** `process_and_validate()` with dependency injection

```python
def process_and_validate(
    self, html_path: Path
) -> Tuple[Optional[SegmentedRisks], str, Optional[Dict]]:
    """Returns (result, status, validation_report) for quarantine"""
```

#### Phase 2.3: Quarantine Pattern (2.5 hours)

**File:** `scripts/data_preprocessing/batch_parse.py`

**Implementation:**
```python
if status == "FAIL":
    # Quarantine instead of silent drop
    quarantine_dir.mkdir(exist_ok=True)
    quarantine_path = quarantine_dir / f"{file.stem}_FAILED.json"
    result.to_json(quarantine_path)

    # Write failure report
    failure_report_path = quarantine_dir / f"{file.stem}_FAILURE_REPORT.md"
    failure_report_path.write_text(f"# Validation Failure\n\n{validation_report}")

    # Track in manifest
    manifest.record_failure(
        input_path=file,
        run_id=run.run_id,
        reason="validation_failed",
        quarantine_path=quarantine_path
    )
```

#### Phase 2.4: Manifest Failure Tracking (1 hour)

**File:** `src/utils/state_manager.py`

**Enhance:** `record_failure()` to track quarantine locations

#### Phase 2.5: Selective Reprocessing (1.5 hours)

**Add flags:**
- `--only-failed` - Reprocess failures
- `--inspect-quarantine` - Show quarantined files

---

### Week 2: Priority 3 - Auto-Documentation (4.5 hours)

#### Phase 3.1: Interactive Markdown Generator (2 hours)

**File:** `src/utils/reporting.py`

**Key features:**
- Interactive links: `[file.json](./file.json)`
- Quarantine links for failed files
- Config snapshot section
- Collapsible sections

#### Phase 3.2: Batch Integration (1.5 hours)

**Modified Files:**
- `scripts/data_preprocessing/batch_parse.py`
- `scripts/validation/data_quality/check_preprocessing_batch.py`

**Auto-generate after processing:**
```python
from pathlib import Path
from src.utils.reporting import ReportFormatter

# Generate report in centralized reports/ directory (established convention)
reports_dir = Path("reports")
reports_dir.mkdir(exist_ok=True)

markdown_path = reports_dir / f"preprocessing_validation_summary_{run.run_id}.md"
ReportFormatter.generate_markdown_report(
    report=validation_report,
    manifest=manifest,
    output_path=markdown_path
)

logger.info(f"✅ Markdown report: {markdown_path}")
logger.info(f"📊 JSON report: {run.output_dir / 'validation_report.json'}")

if failed:
    logger.warning(f"⚠️  Quarantine: {quarantine_dir}")
```

**Naming Convention:**
- Format: `preprocessing_validation_summary_{run_id}.md`
- Location: `reports/` (centralized, not in output directory)
- Rationale: Descriptive (pipeline + operation + type), reproducible (includes git commit)
- Auditability: Unique per run, never overwritten
- Sortable: Timestamp-first for chronological listing

#### Phase 3.3: Documentation & Testing (1 hour)

---

## Part 5: Testing Strategy

### Unit Tests

**Priority 1:**
- `test_atomic_save()` - Kill mid-save, verify backup
- `test_prune_deleted()` - Manifest cleanup
- `test_config_snapshot()` - Reproducibility

**Priority 2:**
- `test_quarantine_pattern()` - Failed files quarantined
- `test_manifest_quarantine_tracking()` - Paths recorded

**Priority 3:**
- `test_interactive_links()` - Relative link generation
- `test_config_snapshot_rendering()` - Reproducibility section

### Integration Tests

**Scenario 1:** Fresh batch → manifest created, reports/preprocessing_validation_summary_{run_id}.md generated
**Scenario 2:** Incremental → 0 processed, 10 skipped
**Scenario 3:** Failures → PASS to production, FAIL quarantined
**Scenario 4:** Inspect quarantine → List failures with reasons
**Scenario 5:** Reprocess failures → Only failed files processed
**Scenario 6:** Corruption recovery → Use .bak file

---

## Part 6: Success Metrics

### Performance
- First run: 20 minutes
- Subsequent (90% unchanged): 2.5 minutes (87.5% reduction)
- **Total savings: 22.5 minutes per run**

### Quality
- ✅ Zero bad files in production
- ✅ All failures quarantined with reports
- ✅ Complete audit trail (file → hash → config → commit)
- ✅ Interactive reports for debugging

### Compliance
- ✅ Config snapshot for reproducibility
- ✅ Timestamped records
- ✅ Researcher tracking
- ✅ FDA 21 CFR Part 11 ready

---

## Part 7: Timeline Summary

| Week | Priority | Tasks | Hours |
|------|----------|-------|-------|
| **Week 1** | **Priority 1** | State Management + Production Hardening | **6.5** |
| **Week 2** | **Priority 2** | Inline Validation + Quarantine | **6.5** |
| **Week 2** | **Priority 3** | Auto-Documentation + Interactive Reports | **4.5** |
| **Testing** | | Integration testing & deployment | **2.0** |
| **Total** | | | **19.5 hours** |

**Note:** Production-ready enhancements add 4 hours vs original 15.5 hour estimate.

---

## Part 8: Immediate Next Steps

### Step 1: Approval
- [ ] Review production-ready enhancements
- [ ] Confirm revised timeline (19.5 hours)
- [ ] Identify additional requirements

### Step 2: Environment Setup
- [ ] Create branch: `feature/mlops-production-ready`
- [ ] Set up test data (10 good, 3 bad files)
- [ ] Review existing components

### Step 3: Begin Priority 1
1. Create `src/utils/state_manager.py` with atomic writes
2. Implement `compute_file_hash()`
3. Implement `StateManifest` with all enhancements
4. Add unit tests (including atomic write verification)
5. Integrate with `batch_parse.py`
6. Test end-to-end

---

## Part 9: Deferred Items

**Drift Detection** (5.5 hours - fully researched but deferred)
- **Why:** "Monitoring garbage is still garbage" - need clean data first
- **Research:** `thoughts/shared/research/2025-12-28_14-30_scheduled_drift_detection_github_actions.md`

**Multi-channel Alerting** (1 hour - deferred)
- **Why:** PR comments sufficient for now

**Parallel Processing** (3 hours - deferred)
- **Why:** Single-threaded sufficient for current scale
- **Trigger:** When adding `ProcessPoolExecutor`

### When to Revisit
After:
- ✅ State management operational (Priority 1)
- ✅ Inline validation prevents bad data (Priority 2)
- ✅ Automated documentation in place (Priority 3)
- ✅ Production model deployed

---

## Conclusion

**Overall Assessment:** ✅ **PRODUCTION-READY FOR IMPLEMENTATION**

**Key Strengths:**
1. Production-ready patterns: Atomic writes, quarantine, config snapshot
2. Realistic timeline: 19.5 hours (4 hours for production hardening)
3. Measurable impact: 60-90% time savings, zero bad data
4. Compliance-ready: FDA 21 CFR Part 11 audit trail
5. Low risk: Builds on existing infrastructure

**Production Enhancements (Rev 2.0):**
- ✅ Atomic writes prevent corruption
- ✅ Quarantine eliminates silent drops
- ✅ Config snapshot enables reproducibility
- ✅ Interactive reports improve debugging
- ✅ Deleted file cleanup prevents bloat

**This transforms the pipeline from "scripts that run" to a "production-ready, compliance-ready system" with complete audit trails, failure recovery, and data quality guarantees.**

**Next Action:** Begin Priority 1 - StateManifest with production-ready features

---

## Appendix: File Change Summary

### New Files
- `src/utils/state_manager.py` (~300 lines)

### Modified Files
- `src/config/run_context.py` (+40 lines)
- `src/config/qa_validation.py` (+40 lines)
- `src/preprocessing/pipeline.py` (+50 lines)
- `src/utils/reporting.py` (+200 lines)
- `scripts/data_preprocessing/batch_parse.py` (~100 lines modified)
- `scripts/validation/data_quality/check_preprocessing_batch.py` (+20 lines)

### Total Code Changes
- **New:** ~730 lines
- **Modified:** ~120 lines
- **Total:** ~850 lines

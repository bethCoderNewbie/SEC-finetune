---
date: 2025-12-28T13:27:11-06:00
git_commit: 648bf25
branch: main
repository: SEC finetune
researcher: bethCoderNewbie
topic: State Management & Incremental Processing (Priority 1)
status: research_complete
---

# State Management & Incremental Processing Research
## The "DVC-lite" Approach for Pipeline Resilience

## Executive Summary

**Problem:** Preprocessing pipeline reprocesses all files on every run, wasting time and compute.

**Root Cause:** No state tracking between runs. Pipeline doesn't know which files have already been processed or if source files have changed.

**Solution:** Implement manifest-based state management that tracks file hashes (input → output) and enables incremental processing.

**Implementation Effort:** 4-5 hours

**Impact:** 60-90% reduction in preprocessing time for subsequent runs

---

## Part 1: Current State Analysis

### What Already Exists (Well-Designed)

**1. RunContext** (`src/config/run_context.py:28-188`)
- ✅ Tracks git SHA for data-code linkage
- ✅ Creates timestamped output directories
- ✅ Saves run configuration and metrics
- ✅ **Working Path:** `run.output_dir` → `data/processed/{run_id}_{name}_{git_sha}/`

**2. CheckpointManager** (`src/utils/checkpoint.py:9-101`)
- ✅ Crash recovery for batch operations
- ✅ Saves/loads processed file lists
- ✅ **Working Path:** Resumes interrupted batch processing

**3. RunMetadata** (`src/utils/metadata.py:11-80`)
- ✅ Collects environment metadata
- ✅ Git commit, branch, researcher tracking
- ✅ **Working Path:** Comprehensive audit trail

**4. SECPreprocessingPipeline** (`src/preprocessing/pipeline.py:93-100+`)
- ✅ Five-stage pipeline: Sanitize → Parse → Extract → Clean → Segment
- ✅ Metadata preservation (CIK, SIC, ticker)
- ✅ **Working Path:** Processes single files correctly

### What's Missing (Broken Paths)

**❌ No State Persistence Across Runs**
- Current: Each run processes ALL files from scratch
- Desired: Only process new or changed files

**❌ No Input File Hash Tracking**
- Current: No way to detect if source file changed
- Desired: SHA-256 hash of each input file

**❌ No Input → Output Lineage**
- Current: Can't trace which output came from which input
- Desired: Bidirectional mapping in manifest

**❌ No Incremental Processing Logic**
- Current: Pipeline always processes full batch
- Desired: Skip files with unchanged hashes

---

## Part 2: State Management Architecture ("DVC-lite")

### Manifest Structure

```json
{
  "schema_version": "1.0.0",
  "runs": {
    "20251228_132700_batch_parse_648bf25": {
      "started_at": "2025-12-28T13:27:00-06:00",
      "completed_at": "2025-12-28T13:32:45-06:00",
      "status": "completed",
      "git_commit": "648bf25",
      "files": {
        "AAPL_10K_2024.html": {
          "input_hash": "sha256:abc123...",
          "input_size": 1245789,
          "input_modified": "2025-12-20T10:30:00-06:00",
          "output_path": "data/interim/parsed/20251228_132700_batch_parse_648bf25/AAPL_10K_2024_parsed.json",
          "output_hash": "sha256:def456...",
          "output_size": 245678,
          "validation_status": "PASS",
          "processing_time": 12.5
        },
        "MSFT_10K_2024.html": {
          "input_hash": "sha256:ghi789...",
          "input_size": 987654,
          "input_modified": "2025-12-21T14:15:00-06:00",
          "output_path": "data/interim/parsed/20251228_132700_batch_parse_648bf25/MSFT_10K_2024_parsed.json",
          "output_hash": "sha256:jkl012...",
          "output_size": 189234,
          "validation_status": "PASS",
          "processing_time": 10.3
        }
      },
      "summary": {
        "total_files": 2,
        "processed": 2,
        "skipped": 0,
        "failed": 0
      }
    }
  },
  "current_state": {
    "AAPL_10K_2024.html": {
      "latest_run": "20251228_132700_batch_parse_648bf25",
      "input_hash": "sha256:abc123...",
      "output_path": "data/interim/parsed/20251228_132700_batch_parse_648bf25/AAPL_10K_2024_parsed.json",
      "last_processed": "2025-12-28T13:32:45-06:00"
    },
    "MSFT_10K_2024.html": {
      "latest_run": "20251228_132700_batch_parse_648bf25",
      "input_hash": "sha256:ghi789...",
      "output_path": "data/interim/parsed/20251228_132700_batch_parse_648bf25/MSFT_10K_2024_parsed.json",
      "last_processed": "2025-12-28T13:32:45-06:00"
    }
  }
}
```

### Why This Structure?

**1. Run History** (`runs` section)
- Preserves complete audit trail
- Links data to git commits
- Enables rollback to previous run

**2. Current State** (`current_state` section)
- Fast lookup: "Is this file already processed?"
- Fast comparison: "Did the input file change?"
- Enables incremental processing

**3. File-Level Lineage**
- Input hash → Output path mapping
- Bidirectional traceability
- Validation status tracking

---

## Part 3: Incremental Processing Logic

### Algorithm

```python
# Pseudocode for incremental processing

def process_batch_incremental(input_files: List[Path], manifest: StateManifest):
    """Process only new or changed files."""

    to_process = []
    to_skip = []

    for file in input_files:
        # 1. Compute current hash
        current_hash = compute_file_hash(file)

        # 2. Check manifest
        if file.name in manifest.current_state:
            previous_hash = manifest.current_state[file.name].input_hash

            # 3. Compare hashes
            if current_hash == previous_hash:
                to_skip.append(file)
                logger.info(f"Skipping {file.name} (unchanged)")
            else:
                to_process.append(file)
                logger.info(f"Reprocessing {file.name} (changed)")
        else:
            to_process.append(file)
            logger.info(f"Processing {file.name} (new)")

    # 4. Process only changed/new files
    results = pipeline.process_batch(to_process)

    # 5. Update manifest
    manifest.update_run(run_id, results)
    manifest.save()

    return {
        "processed": len(to_process),
        "skipped": len(to_skip),
        "total": len(input_files)
    }
```

### Performance Impact

**Baseline (No Incremental Processing):**
- 100 files × 12 seconds/file = 20 minutes

**With Incremental Processing (90% unchanged):**
- 10 new files × 12 seconds/file = 2 minutes
- 90 files × 0.1 seconds hash check = 9 seconds
- **Total: ~2.5 minutes (87.5% time savings)**

---

## Part 4: Integration with Existing Infrastructure

### Leverage RunContext

**Current Usage:**
```python
# src/config/run_context.py:37-41
run = RunContext(name="auto_label_bart")
run.create()
output_path = run.output_dir  # Already timestamped!
```

**Enhanced Usage:**
```python
run = RunContext(name="batch_parse", auto_git_sha=True)
manifest = StateManifest.load()  # NEW

# Check which files need processing
files_to_process = manifest.get_files_to_process(input_dir)

# Process only changed/new files
for file in files_to_process:
    output = pipeline.process(file)
    run.save_artifact(output)
    manifest.record_file(file, output, run.run_id)  # NEW

manifest.save()
```

### Leverage CheckpointManager

**Current Usage:**
```python
# src/utils/checkpoint.py:22-32
checkpoint = CheckpointManager(run_dir / "_checkpoint.json")
checkpoint.save(processed_files, results, metrics)
```

**Enhanced Usage:**
```python
# Checkpoint now includes hash tracking
checkpoint.save(
    processed_files=[f.name for f in processed],
    results=validation_results,
    metrics={
        "processed": 10,
        "skipped": 90,
        "time_saved_seconds": 1050
    }
)
```

---

## Part 5: Implementation Plan

### New Component: StateManifest Class

**Location:** `src/utils/state_manager.py` (NEW)

**Key Methods:**
```python
class StateManifest:
    """DVC-lite state management for incremental processing."""

    @staticmethod
    def load(manifest_path: Path = Path("data/.manifest.json")) -> "StateManifest":
        """Load existing manifest or create new one."""

    def get_files_to_process(self, input_dir: Path) -> List[Path]:
        """Return only new or changed files."""

    def record_file(self, input_path: Path, output_path: Path, run_id: str) -> None:
        """Record file processing in manifest."""

    def save(self) -> None:
        """Save manifest to disk."""

    def get_lineage(self, file_name: str) -> Optional[FileLineage]:
        """Get full lineage for a file (input → output → validation)."""
```

### Integration Points

**1. Batch Parser** (`scripts/data_preprocessing/batch_parse.py`)
- Add `--incremental` flag
- Load manifest before processing
- Skip unchanged files
- Update manifest after processing

**2. Preprocessing Pipeline** (`src/preprocessing/pipeline.py`)
- No changes needed (processes files independently)
- Manifest logic stays in orchestration layer

**3. Validation Scripts** (`scripts/validation/data_quality/check_preprocessing_batch.py`)
- Read manifest to show lineage
- Report which files were skipped
- Validate only newly processed files (optional)

---

## Part 6: File Hash Implementation

### Hash Function (Cryptographically Secure)

```python
import hashlib
from pathlib import Path

def compute_file_hash(file_path: Path, algorithm: str = "sha256") -> str:
    """
    Compute cryptographic hash of file contents.

    Uses 64KB chunks for memory efficiency (large SEC filings).

    Args:
        file_path: Path to file
        algorithm: Hash algorithm (sha256, md5)

    Returns:
        Hex digest string (e.g., "sha256:abc123...")
    """
    hasher = hashlib.new(algorithm)

    with open(file_path, 'rb') as f:
        while chunk := f.read(65536):  # 64KB chunks
            hasher.update(chunk)

    return f"{algorithm}:{hasher.hexdigest()}"
```

### Why SHA-256?

- ✅ Cryptographically secure (collision-resistant)
- ✅ Fast (C implementation in Python stdlib)
- ✅ Standard (used by Git, Docker, DVC)
- ✅ 64-character hex digest (reasonable size)

**Alternative: MD5**
- ⚠️ Faster but not collision-resistant
- ⚠️ Acceptable for non-adversarial use (file change detection)
- ✅ Used by AWS S3 ETags

**Recommendation:** Use SHA-256 (security > speed for this use case)

---

## Part 7: Manifest Storage Location

### Option 1: `.manifest.json` in data/
**Path:** `data/.manifest.json`

**Pros:**
- Central location
- Easy to find
- .gitignore friendly (hidden file)

**Cons:**
- Grows unbounded (full run history)

### Option 2: Per-run manifests
**Path:** `data/interim/parsed/{run_id}/.manifest.json`

**Pros:**
- Scoped to run
- Easy cleanup (delete run dir → delete manifest)

**Cons:**
- Need to find "latest" manifest
- Harder to aggregate across runs

### Option 3: Database (SQLite)
**Path:** `data/.manifest.db`

**Pros:**
- Queryable (SQL)
- Indexed lookups
- Better for large datasets (1000+ files)

**Cons:**
- Complexity
- Requires sqlalchemy dependency

**Recommendation:** Start with Option 1 (`.manifest.json`), migrate to SQLite if manifest > 10MB

---

## Part 8: Validation Integration

### Inline Validation (Priority 2)

**Current:**
```
Process 100 files → Write to disk → Validate batch → Manual review
```

**With State Management:**
```
For each file:
  1. Check manifest (skip if unchanged)
  2. Process file
  3. Validate immediately (inline)
  4. Update manifest with validation status
  5. If FAIL → log to manifest, continue processing
```

**Benefit:**
- Manifest tracks validation status per file
- Can query: "Which files failed validation in last run?"
- Incremental reprocessing of only failed files

---

## Part 9: Success Metrics

### Performance Metrics

**Baseline (Current State):**
- 100 files, all processed: 20 minutes
- Cache hit rate: 0%

**Target (With State Management):**
- 100 files, 90 unchanged: 2.5 minutes (87.5% reduction)
- Cache hit rate: >80% on subsequent runs

### Operational Metrics

**Audit Trail:**
- ✅ Every file traceable to input hash + git commit
- ✅ Full lineage: raw → parsed → validated
- ✅ Rollback capability (reprocess from any git SHA)

**Incremental Processing:**
- ✅ Only process new SEC filings (daily updates)
- ✅ Reprocess only when code changes (new git SHA)
- ✅ Skip validation for unchanged files

---

## Part 10: Risk Mitigation

### Risk 1: Hash Collision (SHA-256)

**Probability:** 2^-256 (astronomically low)
**Mitigation:** N/A (collision probability < cosmic ray bit flip)
**Fallback:** If paranoid, also check file size + modification time

### Risk 2: Manifest Corruption

**Probability:** Low (JSON format, atomic writes)
**Mitigation:**
- Validate schema on load
- Keep backup of previous manifest (`.manifest.json.bak`)
- Checkpoint manifest every N files

**Fallback:** Reprocess all files (same as current state)

### Risk 3: Manifest Growth (Large Datasets)

**Scenario:** 10,000 files × 100 runs = 1M entries
**Impact:** Manifest file > 500MB (slow to load)
**Mitigation:**
- Prune old runs (keep last N runs)
- Migrate to SQLite database
- Compress manifest (gzip)

**Trigger:** If manifest > 10MB, migrate to SQLite

---

## Part 11: Implementation Timeline

| Phase | Task | Duration |
|-------|------|----------|
| 1 | Create StateManifest class | 2 hours |
| 2 | Integrate with batch_parse.py | 1 hour |
| 3 | Add --incremental flag and testing | 1 hour |
| 4 | Update validation scripts | 30 min |
| 5 | Documentation and examples | 30 min |
| **Total** | | **5 hours** |

---

## Part 12: Files to Create/Modify

### New Files

**`src/utils/state_manager.py`** (NEW - ~200 lines)
- StateManifest class
- File hash utilities
- Incremental processing logic

**`data/.manifest.json`** (AUTO-GENERATED)
- Created on first run
- Updated after each batch

### Modified Files

**`scripts/data_preprocessing/batch_parse.py`** (MODIFY)
- Add `--incremental` flag
- Load manifest before processing
- Skip unchanged files
- Update manifest after processing

**`scripts/validation/data_quality/check_preprocessing_batch.py`** (OPTIONAL)
- Show lineage information from manifest
- Report skipped vs. processed files

---

## Conclusion

**Overall Assessment:** ✅ **HIGH PRIORITY - FOUNDATION FOR RESILIENCE**

**Key Strengths:**
1. Builds on existing well-designed infrastructure (RunContext, CheckpointManager)
2. No external dependencies (pure Python stdlib)
3. Clear performance benefits (60-90% time savings)
4. Enables true incremental processing (only new SEC filings)

**Critical Finding:**
Your project already has 80% of the infrastructure needed. State management is the missing 20% that unlocks incremental processing.

**Next Steps:**
1. Create `src/utils/state_manager.py` with StateManifest class
2. Integrate with batch_parse.py (add --incremental flag)
3. Test with sample dataset (10 files, change 2, verify only 2 processed)
4. Deploy to production batch processing

**This is the foundation for a resilient, production-ready preprocessing pipeline.**

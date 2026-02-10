---
title: "Preprocessing Script Deduplication Analysis"
date: 2025-12-28T19:30:00
branch: main
commit: 648bf2589f7382a0fc89da6a1c8b35d2e05c7e87
researcher: claude
tags: [refactoring, code-quality, preprocessing, cli]
status: completed
---

# Preprocessing Script Deduplication Analysis

## Executive Summary

The preprocessing pipeline has **significant code duplication** between:
- **Script**: `scripts/data_preprocessing/run_preprocessing_pipeline.py` (873 lines)
- **Module**: `src/preprocessing/pipeline.py` (594 lines)

Both implement the same preprocessing flow but with different interfaces. The script has additional features (sentiment analysis, resume functionality, chunking) that are missing from the module.

**Recommendation**: Refactor script to be a thin CLI wrapper around the enhanced pipeline module.

---

## Current State Analysis

### Script (`scripts/data_preprocessing/run_preprocessing_pipeline.py`)

**Pipeline Implementation** (lines 137-312):
- `run_pipeline()`: Implements full 5-step pipeline inline
  1. Parse → ParsedFiling
  2. Extract → ExtractedSection
  3. Clean → cleaned text
  4. Segment → SegmentedRisks
  5. **Sentiment → sentiment features** (MISSING from module)

**Batch Processing** (lines 442-758):
- `process_single_file_fast()`: Worker function with global object reuse
- `_init_worker()`: Initializes global parser, extractor, cleaner, segmenter, analyzer
- `run_batch_pipeline()`: Manages ProcessPoolExecutor with chunking
- `_process_chunk()`: Processes file chunks for memory management

**CLI Features** (lines 761-873):
- `--batch`: Concurrent processing mode
- `--workers N`: Control parallelism
- `--no-sentiment`: Skip sentiment analysis
- `--resume`: Skip already processed files (lines 84-134)
- `--quiet`: Minimal output
- `--chunk-size N`: Process in chunks

**Output Format** (lines 315-394):
- `_build_output_data()`: Creates comprehensive JSON with:
  - Filing metadata (sic_code, sic_name, cik, ticker, company_name)
  - Segmentation settings
  - **Aggregate sentiment** (avg_negative_ratio, etc.)
  - Per-segment sentiment features

**Resume Functionality** (lines 84-134):
- `is_file_processed()`: Check if output exists
- `get_processed_files_set()`: Batch lookup optimization
- `filter_unprocessed_files()`: Efficient filtering

### Module (`src/preprocessing/pipeline.py`)

**Pipeline Implementation** (lines 230-342):
- `SECPreprocessingPipeline.process_filing()`: Clean OOP design
  1. **Sanitize → cleaned HTML** (NEW feature)
  2. Parse → ParsedFiling
  3. Extract → ExtractedSection
  4. Clean → cleaned text
  5. Segment → SegmentedRisks
  6. **NO SENTIMENT ANALYSIS**

**Batch Processing** (lines 442-515):
- `process_batch()`: Uses `ParallelProcessor` utility (cleaner abstraction)
- `_process_single_filing_worker()`: Module-level worker function
- Returns list of `SegmentedRisks` objects

**Additional Features**:
- `process_and_validate()` (lines 344-408): Inline validation for quarantine pattern
- `PipelineConfig` (lines 99-158): Pydantic V2 configuration
- Pre-parser HTML sanitization support (NEW)

---

## Code Duplication Analysis

### Duplicated Logic

| Feature | Script Lines | Module Lines | Duplication |
|---------|-------------|--------------|-------------|
| Parse step | 165-177 | 286-300 | ✅ Yes |
| Extract step | 180-199 | 303-314 | ✅ Yes |
| Clean step | 202-237 | 317-327 | ✅ Yes |
| Segment step | 240-260 | 330-335 | ✅ Yes |
| Batch processing | 589-758 | 442-515 | ✅ Yes |
| Worker initialization | 64-82 | 37-96 | ✅ Yes |
| Parallel execution | 722-758 | 482-493 | ✅ Yes |

### Unique Features

**Script-only**:
- ❌ Sentiment analysis (lines 264-288, 540-544)
- ❌ Resume functionality (lines 84-134)
- ❌ Chunk processing (lines 641-677)
- ❌ Detailed progress reporting (lines 746-754)
- ❌ `_build_output_data()` with sentiment (lines 315-394)
- ❌ Batch summary generation (lines 836-849)

**Module-only**:
- ✅ HTML sanitization (lines 268-283)
- ✅ `process_and_validate()` for inline validation (lines 344-408)
- ✅ `PipelineConfig` for configuration (lines 99-158)
- ✅ `ParallelProcessor` abstraction

---

## Root Cause Analysis

### Why Duplication Exists

**Historical Context**:
1. **Script created first**: Monolithic implementation with all features inline
2. **Module created later**: Cleaner OOP refactoring but missing features
3. **No migration**: Script never refactored to use the module
4. **Feature divergence**: Sentiment analysis added to script, sanitization added to module

### Why It's Problematic

1. **Maintenance burden**: Bug fixes must be applied twice
2. **Feature inconsistency**: Script has sentiment, module has sanitization
3. **Testing complexity**: Must test two implementations of same logic
4. **Cognitive load**: Developers must understand both implementations

### Deeper Architectural Issue: Mixed Concerns

**The script violates separation of concerns by combining**:
- **Preprocessing** (structural): Parse → Extract → Clean → Segment
- **Feature Engineering** (semantic): Sentiment Analysis

**Current Architecture** (run_preprocessing_pipeline.py:264-288):
```python
# Step 4: Segment (PREPROCESSING)
segmented_risks = segmenter.segment_extracted_section(...)

# Step 5: Sentiment Analysis (FEATURE ENGINEERING - wrong layer!)
if extract_sentiment:
    analyzer = SentimentAnalyzer()
    sentiment_features = analyzer.extract_features_batch(...)
```

**Evidence from codebase structure**:
- `src/preprocessing/` → Structural operations (parser, extractor, cleaner, segmenter)
- `src/features/` → Semantic operations (sentiment, readability, topic_modeling)

**Good news**: No logic duplication - script correctly uses `SentimentAnalyzer` from `src/features/sentiment.py:266`

**Bad news**: Architectural boundary violation - preprocessing script shouldn't orchestrate feature extraction

---

## Refactoring Strategy

### Decision Point: Architecture Pattern

**Two options based on separation of concerns:**

#### Option A: Pure Separation (Recommended - Aligns with Production Standards)

**Rationale**: Per `naming_and_reporting_rules.md`, architectural clarity requires clean boundaries between:
- `src/preprocessing/` → Structural operations
- `src/features/` → Semantic operations

**Structure**:
```
scripts/
├─ data_preprocessing/
│  └─ run_preprocessing.py          # ONLY: Parse → Extract → Clean → Segment
└─ feature_engineering/
   ├─ extract_sentiment_features.py # ONLY: Sentiment analysis
   ├─ extract_readability_metrics.py # ONLY: Readability
   └─ run_feature_pipeline.py        # Orchestrator (optional)
```

**Workflow**:
```bash
# Step 1: Preprocessing (structural)
python scripts/data_preprocessing/run_preprocessing.py --batch
# Output: data/processed/*_segmented.json (SegmentedRisks only)

# Step 2: Feature engineering (semantic)
python scripts/feature_engineering/extract_sentiment_features.py --batch
# Input: data/processed/*_segmented.json
# Output: data/features/sentiment/*_sentiment.json

# Step 3: Combine features (optional)
python scripts/feature_engineering/combine_features.py --batch
# Output: data/features/combined/*_features.json
```

**Benefits**:
- ✅ Clear separation of concerns
- ✅ Each step independently testable
- ✅ Can run features in parallel
- ✅ Easier to add new features (readability, topic modeling)
- ✅ Follows MLOps best practices

**Drawbacks**:
- ⚠️ More complex for simple use cases
- ⚠️ Breaking change for existing users

---

#### Option B: Optional Feature Flag (Pragmatic - Maintains Convenience)

**Rationale**: Keep current behavior for convenience, but make architecture violation explicit

**Changes**:
```python
# src/preprocessing/pipeline.py (NO CHANGES - stays pure)
# Preprocessing module remains focused on structural operations only

# scripts/data_preprocessing/run_preprocessing_pipeline.py
# Keep sentiment as optional orchestration (documented as convenience)
```

**Benefits**:
- ✅ Backward compatible
- ✅ Convenient for experiments
- ✅ Single command for full pipeline

**Drawbacks**:
- ❌ Violates separation of concerns
- ❌ Feature engineering coupled to preprocessing
- ❌ Harder to extend with more features

---

### Recommended: Option A (Pure Separation)

**Phase 1: Keep Preprocessing Pure**

`src/preprocessing/pipeline.py` should **NOT** have sentiment analysis:
```python
# ✅ CORRECT - Pure preprocessing
class SECPreprocessingPipeline:
    def process_filing(...) -> SegmentedRisks:
        # 1. Parse
        # 2. Extract
        # 3. Clean
        # 4. Segment
        return segmented_risks  # NO sentiment features

# ❌ INCORRECT - Mixed concerns
class SECPreprocessingPipeline:
    def process_filing(...) -> Tuple[SegmentedRisks, SentimentFeatures]:
        # Mixing preprocessing with feature engineering
```

**Phase 2: Create Separate Feature Engineering Scripts**

`scripts/feature_engineering/extract_sentiment_features.py`:
```python
"""
Extract sentiment features from preprocessed segments

Input: data/processed/*_segmented.json (SegmentedRisks)
Output: data/features/sentiment/*_sentiment.json (List[SentimentFeatures])
"""

from pathlib import Path
from src.preprocessing.models import SegmentedRisks
from src.features.sentiment import SentimentAnalyzer

def extract_sentiment(segmented_file: Path) -> List[SentimentFeatures]:
    # Load preprocessed segments
    risks = SegmentedRisks.load_from_json(segmented_file)

    # Extract sentiment
    analyzer = SentimentAnalyzer()
    segment_texts = risks.get_texts()
    features = analyzer.extract_features_batch(segment_texts)

    return features
```

**Phase 3: Refactor CLI to Pure Preprocessing**

`scripts/data_preprocessing/run_preprocessing.py` (renamed, ~150 lines):
```python
"""
CLI for preprocessing pipeline (STRUCTURAL ONLY)

Output: data/processed/*_segmented.json (SegmentedRisks)

For feature extraction, use:
  - scripts/feature_engineering/extract_sentiment_features.py
  - scripts/feature_engineering/extract_readability_metrics.py
"""

from src.preprocessing.pipeline import SECPreprocessingPipeline, PipelineConfig

def main():
    # Build config (NO sentiment options)
    config = PipelineConfig(
        pre_sanitize=args.sanitize,
        deep_clean=args.deep_clean,
    )

    # Process (returns SegmentedRisks only)
    pipeline = SECPreprocessingPipeline(config)
    results = pipeline.process_batch(...)
```

**Phase 4: Add Orchestration Script (Optional)**

`scripts/run_full_pipeline.py`:
```python
"""
Orchestrate full pipeline: Preprocessing + All Features

This is a CONVENIENCE wrapper that calls:
1. run_preprocessing.py
2. extract_sentiment_features.py
3. extract_readability_metrics.py
4. combine_features.py
"""

def run_full_pipeline():
    subprocess.run(["python", "scripts/data_preprocessing/run_preprocessing.py", "--batch"])
    subprocess.run(["python", "scripts/feature_engineering/extract_sentiment_features.py", "--batch"])
    # ...
```

---

## Migration Checklist

### Architectural Decision

- [x] Identify separation of concerns violation
- [x] Document two options: Pure Separation vs Pragmatic
- [ ] **User decision required**: Choose Option A (Recommended) or Option B

### Option A Implementation (Pure Separation)

#### Phase 1: Preprocessing Module (NO CHANGES NEEDED)
- [x] `src/preprocessing/pipeline.py` already pure (no sentiment)
- [x] Verify `process_filing()` returns only `SegmentedRisks`

#### Phase 2: Feature Engineering Scripts (NEW)
- [ ] Create `scripts/feature_engineering/` directory
- [ ] Create `extract_sentiment_features.py`:
  - [ ] Read `SegmentedRisks` from processed directory
  - [ ] Use `SentimentAnalyzer.extract_features_batch()`
  - [ ] Save to `data/features/sentiment/`
  - [ ] Add CLI with `--batch`, `--resume` flags
- [ ] Create `extract_readability_metrics.py` (future)
- [ ] Create `run_feature_pipeline.py` orchestrator (optional)

#### Phase 3: Refactor Preprocessing Script
- [ ] Rename to `run_preprocessing.py` (remove "pipeline")
- [ ] Remove all sentiment analysis code (lines 264-288, 540-544)
- [ ] Remove `--no-sentiment` flag
- [ ] Use `SECPreprocessingPipeline` from module
- [ ] Output only `SegmentedRisks` (no sentiment in JSON)
- [ ] Reduce from 873 → ~150 lines

#### Phase 4: Migration Support
- [ ] Keep old script as `run_preprocessing_pipeline_legacy.py`
- [ ] Add deprecation warning to legacy script
- [ ] Update documentation with new workflow
- [ ] Create `scripts/run_full_pipeline.py` orchestrator

#### Phase 5: Validation
- [ ] Test preprocessing only: `python scripts/data_preprocessing/run_preprocessing.py --batch`
- [ ] Test sentiment extraction: `python scripts/feature_engineering/extract_sentiment_features.py --batch`
- [ ] Verify output compatibility with downstream consumers
- [ ] Run integration tests

### Option B Implementation (Pragmatic - Backward Compatible)

- [ ] Keep script as-is (or minimal refactoring)
- [ ] Document architectural violation in script docstring
- [ ] Add TODO comment: "Migrate to Option A for MLOps compliance"
- [ ] No breaking changes

---

## Benefits

### Code Quality
- **Single source of truth**: Pipeline logic in one place
- **DRY principle**: No duplicated implementation
- **Maintainability**: Bug fixes in one location

### Features
- **Consistent**: Both interfaces have same features
- **Composable**: Module can be used programmatically
- **Testable**: Easier to test single implementation

### CLI Preservation
- **Backward compatible**: All CLI flags preserved
- **Same behavior**: Output format unchanged
- **Same performance**: Uses same underlying logic

---

## Risk Assessment

### Low Risk
- ✅ No changes to data models
- ✅ No changes to output format
- ✅ No changes to CLI interface
- ✅ Pipeline module already has 90% of logic

### Medium Risk
- ⚠️ Sentiment analysis integration needs testing
- ⚠️ Resume functionality needs validation
- ⚠️ Batch processing needs performance testing

### Mitigation
- Keep old script as `run_preprocessing_pipeline_legacy.py` during migration
- Run parallel tests to verify output equivalence
- Add comprehensive integration tests before deployment

---

## Success Criteria

### Must Have
1. ✅ Script reduced from 873 to ~150 lines
2. ✅ All CLI flags preserved and working
3. ✅ Output format byte-for-byte identical
4. ✅ Performance within 10% of original

### Should Have
1. ✅ Module has sentiment analysis support
2. ✅ Module has resume utilities
3. ✅ Tests updated and passing
4. ✅ Documentation updated

### Nice to Have
1. ⭐ Performance improvements from optimizations
2. ⭐ Additional CLI flags (e.g., `--sanitize`)
3. ⭐ Better error handling and logging

---

## Conclusion

### Two Distinct Problems Identified

1. **Code Duplication**: Script has 700+ lines duplicating `src/preprocessing/pipeline.py`
2. **Architecture Violation**: Preprocessing script orchestrates feature engineering (mixed concerns)

### Recommended Solution: Option A (Pure Separation)

**Aligns with production standards** from `naming_and_reporting_rules.md`:
- Clear architectural boundaries (`src/preprocessing/` vs `src/features/`)
- Separation of concerns (structural vs semantic operations)
- MLOps best practices (independent, testable pipeline stages)

**Trade-offs**:
| Aspect | Option A (Recommended) | Option B (Pragmatic) |
|--------|----------------------|---------------------|
| **Architecture** | ✅ Clean separation | ❌ Mixed concerns |
| **Code duplication** | ✅ Removed (~700 lines) | ✅ Removed (~700 lines) |
| **Testability** | ✅ Each stage independent | ⚠️ Coupled stages |
| **Extensibility** | ✅ Easy to add features | ❌ Hard to add features |
| **Breaking change** | ❌ Yes (workflow change) | ✅ No |
| **User convenience** | ⚠️ Multi-step workflow | ✅ Single command |
| **Effort** | 8-12 hours | 4 hours |

### Implementation Effort

**Option A: Pure Separation**
- **Phase 1-2**: 4 hours (create feature engineering scripts)
- **Phase 3**: 2 hours (refactor preprocessing script)
- **Phase 4**: 2 hours (orchestrator + migration support)
- **Phase 5**: 2-4 hours (testing + documentation)
- **Total**: 10-12 hours

**Option B: Pragmatic**
- **Refactoring**: 3 hours (script → thin wrapper)
- **Testing**: 1 hour
- **Total**: 4 hours

### Decision Required

**Question for user**: Should we:
- **A) Go full MLOps** with proper separation (recommended, breaking change)
- **B) Quick fix** to remove duplication but keep mixed concerns (backward compatible)

The answer depends on:
- Is this project moving toward production MLOps? → Choose A
- Is this still in experimental/research phase? → Choose B (for now)

**My recommendation**: Option A for long-term maintainability, even if it requires updating downstream workflows.

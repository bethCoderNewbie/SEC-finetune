---
date: 2025-12-20T14:30:00-06:00
researcher: bethCoderNewbie
git_commit: 1843e0d
branch: main
repository: SEC finetune
topic: "Data Health Check Architecture for Preprocessing Output"
tags: [research, qa-validation, data-quality, mlops, preprocessing]
status: complete
last_updated: 2025-12-20
last_updated_by: bethCoderNewbie
---

# Research: Data Health Check Architecture for Preprocessing Output

**Date**: 2025-12-20T14:30:00-06:00
**Researcher**: bethCoderNewbie
**Git Commit**: 1843e0d
**Branch**: main
**Topic**: Data Health Check Architecture for Preprocessing Output

## Research Question

Design a comprehensive Data Health Check system that validates preprocessing output meets MLOps quality standards across two conceptual views:

1. **Preprocessing Quality Checks**: Completeness, Cleanliness, Substance, Consistency
2. **Standard Data Health Dimensions**: Schema & Integrity, Distribution & Statistics, Domain-Specific Quality

## Summary

The existing codebase has **strong foundations** for QA validation (ThresholdRegistry, ValidationResult, 52+ thresholds) but lacks **unified enforcement** and **critical gap coverage**. This research maps user requirements to existing infrastructure and identifies what must be built.

---

## Current State Analysis

### Existing Infrastructure

| Component | Location | Status |
|-----------|----------|--------|
| ThresholdRegistry | `src/config/qa_validation.py:370-472` | Complete |
| ValidationResult | `src/config/qa_validation.py:230-364` | Complete |
| YAML Configs | `configs/qa_validation/*.yaml` | 52+ thresholds |
| Report Generators | `scripts/utils/generate_*.py` | 2 scripts |
| Pydantic Models | `src/preprocessing/*.py` | 4 core models |

### Output Data Structure (3 Stages)

```
ParsedFiling → ExtractedSection → SegmentedRisks
```

**Key Fields Preserved Through Pipeline:**
- `sic_code`: Standard Industrial Classification (e.g., "3571")
- `cik`: Central Index Key (e.g., "0000320193")
- `ticker`: Stock symbol (e.g., "AAPL")
- `company_name`: Company name (e.g., "Apple Inc.")
- `form_type`: SEC form type (e.g., "10-K")

---

## Requirements Mapping

### View 1: Preprocessing Quality (4 Checks)

| Check | Metric | Target | Status | Gap |
|-------|--------|--------|--------|-----|
| **Completeness** | `key_item_recall` | >= 99% | EXISTS | None |
| **Completeness** | `identity_fields_present` | 100% | MISSING | CIK, SIC, company must be non-null |
| **Cleanliness** | `html_tag_removal_rate` | 100% | EXISTS | None |
| **Cleanliness** | `page_number_removal_rate` | 100% | EXISTS | None |
| **Cleanliness** | `toc_entry_removal_rate` | 100% | EXISTS | None |
| **Substance** | `min_segment_length` | > 50 chars | EXISTS | None |
| **Substance** | `word_count_filter_pass` | >= 10 words | EXISTS | None |
| **Substance** | `noise_to_signal_ratio` | <= 5% | EXISTS | Needs measurement |
| **Consistency** | `segment_count_min` | >= 5 | EXISTS | None |
| **Consistency** | `segment_count_max` | <= 50 | EXISTS | None |

### View 2: Standard Data Health (3 Dimensions)

| Dimension | Check | Status | Gap |
|-----------|-------|--------|-----|
| **Schema & Integrity** | Required fields present | PARTIAL | Pydantic validates on load, no batch check |
| **Schema & Integrity** | Type correctness | COMPLETE | Pydantic enforces |
| **Schema & Integrity** | Null/NaN rates | MISSING | Need to add |
| **Distribution & Statistics** | Range checks | PARTIAL | Gini exists, others missing |
| **Distribution & Statistics** | Cardinality | MISSING | Sector/SIC validation |
| **Distribution & Statistics** | Distribution drift | MISSING | Cross-run comparison |
| **Domain-Specific** | Risk language present | MISSING | Need keyword density check |
| **Domain-Specific** | Duplicate detection | MISSING | Need hash-based dedup |
| **Domain-Specific** | Artifact removal | EXISTS | HTML/ToC/page numbers |

---

## Detailed Gap Analysis

### Gap 1: Identity Field Validation (CRITICAL)

**Problem**: No validation that required identity fields are populated.

**Current Behavior**: Pydantic models allow `Optional[str]` for sic_code, cik, ticker, company_name.

**Required Behavior**:
- `cik` MUST be non-null (required for SEC compliance)
- `sic_code` SHOULD be non-null (critical for sector analysis)
- `company_name` MUST be non-null (required for identification)

**Evidence** (`extractor.py:25-171`):
```python
sic_code: Optional[str] = None  # Should be required
cik: Optional[str] = None       # Should be required
```

### Gap 2: Null Rate Tracking (HIGH)

**Problem**: No metrics tracking null/missing value rates across a batch.

**Required**:
- Count nulls per field across all files in a run
- Alert if null rate exceeds threshold (e.g., > 5% for optional fields)
- Block if null rate > 0% for required fields (cik, company_name)

### Gap 3: Distribution Drift Detection (MEDIUM)

**Problem**: No comparison between runs to detect sudden shifts.

**Required**:
- Store baseline statistics (avg segment length, avg word count)
- Compare new run against baseline
- Alert if deviation exceeds threshold (e.g., > 2 standard deviations)

### Gap 4: Duplicate Detection (MEDIUM)

**Problem**: No mechanism to detect duplicate filings in training data.

**Required**:
- Hash-based content fingerprinting
- Flag files with identical content
- Report duplicate rate per run

### Gap 5: Risk Language Validation (LOW)

**Problem**: No validation that "Risk Factors" actually contains risk-related words.

**Required**:
- Count risk keywords ("risk", "adverse", "material", "uncertain")
- Flag if keyword density < threshold
- Ensures we're extracting correct section

---

## Architecture Recommendation

### Proposed: DataHealthChecker Class

```
src/
  validation/
    __init__.py
    health_checker.py      # Main orchestrator
    schema_validator.py    # Pydantic-based checks
    distribution_tracker.py # Statistics & drift
    domain_validator.py    # SEC-specific rules
```

### Health Check Pipeline

```
Input (JSON files)
    → Schema Validation (required fields, types)
    → Distribution Check (ranges, cardinality)
    → Domain Check (duplicates, risk keywords)
    → Report Generation (pass/fail, metrics)
```

### Integration Points

1. **CLI Hook**: `python -m src.validation.health_checker --run-dir data/processed/...`
2. **Test Integration**: `tests/validation/test_health_check.py`
3. **CI/CD Gate**: Fail build if blocking thresholds fail

---

## Proposed Threshold Additions

### New YAML: `configs/qa_validation/health_check.yaml`

```yaml
categories:
  identity_completeness:
    display_name: Identity Completeness
    description: Required identity fields validation

  null_rates:
    display_name: Null Rates
    description: Missing value detection

  distribution_health:
    display_name: Distribution Health
    description: Statistical distribution checks

  domain_rules:
    display_name: Domain Rules
    description: SEC-specific business logic

thresholds:
  identity_completeness:
    cik_present_rate:
      display_name: CIK Present Rate
      metric_type: rate
      target: 1.0
      operator: ">="
      blocking: true
      description: All files must have CIK

    sic_code_present_rate:
      display_name: SIC Code Present Rate
      metric_type: rate
      target: 0.95
      operator: ">="
      blocking: false
      description: 95% of files should have SIC code

    company_name_present_rate:
      display_name: Company Name Present Rate
      metric_type: rate
      target: 1.0
      operator: ">="
      blocking: true
      description: All files must have company name

  null_rates:
    ticker_null_rate:
      display_name: Ticker Null Rate
      metric_type: rate
      target: 0.10
      operator: "<="
      blocking: false
      description: Max 10% missing tickers

  distribution_health:
    segment_length_drift:
      display_name: Segment Length Drift
      metric_type: score
      target: 2.0
      operator: "<="
      blocking: false
      description: Max 2 std dev from baseline

    word_count_drift:
      display_name: Word Count Drift
      metric_type: score
      target: 2.0
      operator: "<="
      blocking: false
      description: Max 2 std dev from baseline

  domain_rules:
    duplicate_rate:
      display_name: Duplicate Rate
      metric_type: rate
      target: 0.0
      operator: "=="
      blocking: true
      description: No duplicate filings allowed

    risk_keyword_density:
      display_name: Risk Keyword Density
      metric_type: rate
      target: 0.001
      operator: ">="
      blocking: false
      description: Minimum risk word presence
```

---

## Go/No-Go Validation Table

| Metric | Category | Target | Current Status | Priority |
|--------|----------|--------|----------------|----------|
| `cik_present_rate` | Identity | 100% | NOT CHECKED | P0 |
| `company_name_present_rate` | Identity | 100% | NOT CHECKED | P0 |
| `key_item_recall` | Completeness | >= 99% | IMPLEMENTED | - |
| `html_tag_removal_rate` | Cleanliness | 100% | IMPLEMENTED | - |
| `segment_count_min` | Consistency | >= 5 | IMPLEMENTED | - |
| `duplicate_rate` | Domain | 0% | NOT CHECKED | P1 |
| `segment_length_drift` | Distribution | <= 2 std | NOT CHECKED | P2 |
| `risk_keyword_density` | Domain | >= 0.1% | NOT CHECKED | P3 |

---

## Open Questions

1. **Baseline Storage**: Where to store distribution baselines for drift detection?
   - Option A: `configs/baselines/` YAML files
   - Option B: First run of each batch becomes baseline

2. **Duplicate Scope**: What defines a duplicate?
   - Option A: Exact text match (hash-based)
   - Option B: Same CIK + filing period
   - Option C: Fuzzy similarity threshold

3. **CI/CD Integration**: How to integrate with pytest?
   - Option A: Dedicated `tests/validation/` suite
   - Option B: Fixtures in existing test files
   - Option C: Standalone CLI with exit codes

---

## Code References

* `src/config/qa_validation.py:370-472` - ThresholdRegistry loading
* `src/config/qa_validation.py:230-364` - ValidationResult class
* `src/preprocessing/extractor.py:25-171` - ExtractedSection model (identity fields)
* `src/preprocessing/segmenter.py:42-133` - SegmentedRisks model
* `configs/qa_validation/*.yaml` - Existing threshold definitions
* `scripts/utils/generate_validation_report.py` - Report generation pattern

## Recommended Next Steps

1. **Phase 1**: Add identity field validation (P0)
   - Update Pydantic models with stricter validation
   - Add `identity_completeness` thresholds

2. **Phase 2**: Add duplicate detection (P1)
   - Implement hash-based fingerprinting
   - Add `duplicate_rate` threshold

3. **Phase 3**: Add distribution tracking (P2)
   - Store baseline statistics
   - Implement drift detection

4. **Phase 4**: Add domain validation (P3)
   - Risk keyword density check
   - Sector cardinality validation

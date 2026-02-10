---
date: 2025-12-29T14:00:00-06:00
researcher: bethCoderNewbie
git_commit: 648bf25
branch: main
repository: SEC finetune
topic: "Extractor QA Metrics Config Integration"
tags: [plan, extractor, qa-metrics, config-integration, validation]
status: pending
priority: high
---

# Plan: Integrate Config Loader and Implement Missing Extractor QA Metrics

**Date**: 2025-12-29T14:00:00-06:00
**Researcher**: bethCoderNewbie
**Git Commit**: 648bf25
**Branch**: main
**Repository**: SEC finetune

## Problem Statement

The batch extractor QA script (`scripts/validation/extraction_quality/check_extractor_batch.py`) has **hardcoded metrics** that do not align with the research document (`thoughts/shared/research/2025-12-03_19-16_extractor_qa_metrics.md`) or the config definitions (`configs/qa_validation/extraction.yaml`).

**Critical Gaps:**
- ❌ No config integration (hardcoded thresholds)
- ❌ Missing 6 out of 12 metrics from research/config
- ❌ Missing blocking metrics: `section_boundary_precision_end`, `key_item_recall`, `toc_filtering_rate`, `subsection_classification_accuracy`
- ⚠️ Partial implementation of `section_boundary_precision_start` (only checks identifier)

**Source Documents:**
- Research: `thoughts/shared/research/2025-12-03_19-16_extractor_qa_metrics.md` (lines 199-213)
- Config: `configs/qa_validation/extraction.yaml` (lines 20-98)
- Script: `scripts/validation/extraction_quality/check_extractor_batch.py` (lines 63-104)

---

## Desired End State

**User Capabilities Upon Completion:**

1. **Config-Driven Validation**: Script loads all thresholds from `configs/qa_validation/extraction.yaml` using `ThresholdRegistry`
2. **Complete Metric Coverage**: All 12 metrics from research document validated
3. **Blocking Metrics Enforced**: Critical metrics (section boundary precision, recall, filtering rates) properly evaluated
4. **Flexible Thresholds**: Thresholds can be modified in YAML without code changes
5. **Validation Results**: Reports include `ValidationResult` objects with Go/No-Go status per threshold
6. **Backwards Compatible**: Existing JSON/markdown report format preserved

---

## Anti-Scope (What We're NOT Doing)

1. ❌ **NOT** implementing ground truth labeling infrastructure (future work)
2. ❌ **NOT** modifying the extractor itself (focusing on validation only)
3. ❌ **NOT** creating new test fixtures (use existing extracted JSON files)
4. ❌ **NOT** changing report output format (preserve current structure)
5. ❌ **NOT** implementing automated fixes for failing metrics (detection only)
6. ❌ **NOT** adding UI/dashboard (CLI output only)

---

## Implementation Strategy

### Phase 1: Config Integration (Foundation)

**Goal**: Replace hardcoded metrics with config-driven system

**Changes to `check_extractor_batch.py`:**

```python
# Line 1-56: Add imports
from src.config.qa_validation import (
    ThresholdRegistry,
    ValidationResult,
    ValidationStatus,
    determine_overall_status
)

# Line 63-104: REMOVE hardcoded QA_METRICS dict entirely

# New helper function after imports
def _load_metrics_from_config() -> Dict[str, ThresholdDefinition]:
    """Load extractor metrics from config registry."""
    metrics = {}

    # Load extraction_accuracy category
    for threshold in ThresholdRegistry.by_category("extraction_accuracy"):
        metrics[threshold.name] = threshold

    # Load content_quality category
    for threshold in ThresholdRegistry.by_category("content_quality"):
        metrics[threshold.name] = threshold

    return metrics

# Update validate_single_extraction() signature (line 113)
def validate_single_extraction(
    file_path: Path,
    metrics_config: Dict[str, ThresholdDefinition]
) -> Dict[str, Any]:
    """
    Validate extracted risk JSON file against config-driven metrics.

    Args:
        file_path: Path to extracted risk JSON file
        metrics_config: Dict of ThresholdDefinition objects from config

    Returns:
        Validation result dict with ValidationResult objects
    """
```

**Verification:**
```bash
# Test config loads correctly
python -c "
from src.config.qa_validation import ThresholdRegistry
metrics = ThresholdRegistry.by_category('extraction_accuracy')
print(f'Loaded {len(metrics)} extraction_accuracy metrics')
assert len(metrics) == 4  # section_boundary_precision_start/end, key_item_recall, false_positive_rate
"
```

**Success Criteria:**
- ✅ Script loads all thresholds from config at runtime
- ✅ No hardcoded metrics remain in script
- ✅ All config categories accessible via ThresholdRegistry

---

### Phase 2: Implement Missing Metrics (Accuracy)

**Goal**: Add missing extraction accuracy metrics with proper validation

#### Metric 1: `section_boundary_precision_end`

**Config Spec** (from `extraction.yaml:30-38`):
```yaml
section_boundary_precision_end:
  target: 0.95
  operator: ">="
  blocking: true
  description: Accuracy of section end boundary detection
```

**Implementation**:
```python
# In validate_single_extraction(), after loading JSON
def _check_section_boundary_precision_end(data: Dict, text: str) -> ValidationResult:
    """
    Check if section end boundary is correctly detected.

    Research finding (line 66-76): _is_next_section() regex overshoot -
    Item 1B content leaking into Item 1A due to regex `$` anchor.

    Validation: Check if text contains next ITEM pattern that should have stopped extraction.
    """
    threshold = ThresholdRegistry.get("section_boundary_precision_end")

    # Detect boundary overshoot patterns
    # Pattern: "Item [NUMBER][LETTER]." followed by title text
    overshoot_pattern = r'Item\s+\d+[A-Z]?\s*\.\s+[A-Z]'
    has_overshoot = bool(re.search(overshoot_pattern, text))

    # Pass if NO overshoot detected
    precision = 0.0 if has_overshoot else 1.0

    return ValidationResult.from_threshold(threshold, precision)
```

#### Metric 2: `key_item_recall`

**Config Spec** (from `extraction.yaml:40-47`):
```yaml
key_item_recall:
  target: 0.99
  operator: ">="
  blocking: true
  description: Recall of required regulatory sections (Item 1, 1A, 7, 7A)
```

**Implementation**:
```python
def _check_key_item_recall(data: Dict) -> ValidationResult:
    """
    Check if extracted section identifier matches expected key items.

    This is a file-level check - aggregate across batch for recall metric.
    """
    threshold = ThresholdRegistry.get("key_item_recall")

    identifier = data.get("identifier", "").lower()

    # Key items from research (line 78-87)
    key_items = ["part1item1", "part1item1a", "part2item7", "part2item7a"]

    # Check if this file represents a key item
    is_key_item = any(ki in identifier for ki in key_items)

    # Return 1.0 if key item found, 0.0 otherwise
    # Aggregate recall computed in batch_generate_extractor_qa_report()
    return ValidationResult.from_threshold(threshold, 1.0 if is_key_item else 0.0)
```

**Note**: Key item recall requires aggregation across files. Add to `generate_consolidated_json_report()`:
```python
# Aggregate key item recall
key_item_files = sum(
    1 for r in per_file_results
    if r['metrics'].get('key_item_recall', {}).get('actual') == 1.0
)
total_files = len(per_file_results)
key_item_recall_rate = key_item_files / total_files if total_files > 0 else 0.0
```

---

### Phase 3: Implement Missing Metrics (Content Quality)

#### Metric 3: `toc_filtering_rate`

**Config Spec** (from `extraction.yaml:62-69`):
```yaml
toc_filtering_rate:
  target: 1.0
  operator: ">="
  blocking: true
  description: Rate of Table of Contents entries filtered
```

**Implementation**:
```python
def _check_toc_filtering_rate(text: str) -> ValidationResult:
    """
    Check if ToC patterns are present in extracted text.

    Research finding (line 97-105): No ToC filtering implemented.

    ToC patterns:
    - "Table of Contents"
    - Sequential page numbers (Page 1, Page 2, Page 3...)
    - "Part [Roman] Item [Number]" without content
    """
    threshold = ThresholdRegistry.get("toc_filtering_rate")

    toc_patterns = [
        r'Table\s+of\s+Contents',
        r'Part\s+[IVX]+\s+Item\s+\d+\s+\.\s+\.\s+\.',  # Dots indicating TOC leader
        r'Page\s+\d+\s+Page\s+\d+\s+Page\s+\d+',  # Sequential pages
    ]

    has_toc = any(re.search(pat, text, re.IGNORECASE) for pat in toc_patterns)

    # Pass if NO ToC patterns found (filtering worked)
    filtering_rate = 0.0 if has_toc else 1.0

    return ValidationResult.from_threshold(threshold, filtering_rate)
```

#### Metric 4: `page_header_filtering_rate`

**Config Spec** (from `extraction.yaml:71-78`):
```yaml
page_header_filtering_rate:
  target: 1.0
  operator: ">="
  blocking: true
  description: Rate of page headers correctly removed
```

**Implementation** (upgrade existing `no_page_headers` metric):
```python
def _check_page_header_filtering_rate(data: Dict, text: str) -> ValidationResult:
    """
    Check rate of page headers filtered from content.

    Research finding (line 114-128): Page headers like "Apple Inc. | 2021 Form 10-K | 6"
    incorrectly captured as subsections.

    Check both text content AND subsections list.
    """
    threshold = ThresholdRegistry.get("page_header_filtering_rate")

    # Pattern from research (line 246-248)
    page_header_pattern = re.compile(r'.+\|\s*\d{4}\s+Form\s+\d+-[KQ]\s*\|\s*\d+')

    # Check text content
    text_has_headers = bool(page_header_pattern.search(text))

    # Check subsections
    subsections = data.get("subsections", [])
    subsection_headers = sum(1 for sub in subsections if page_header_pattern.match(sub))

    total_checks = 1 + len(subsections)  # Text + each subsection
    failed_checks = (1 if text_has_headers else 0) + subsection_headers

    filtering_rate = 1.0 - (failed_checks / total_checks) if total_checks > 0 else 1.0

    return ValidationResult.from_threshold(threshold, filtering_rate)
```

#### Metric 5: `subsection_classification_accuracy`

**Config Spec** (from `extraction.yaml:80-88`):
```yaml
subsection_classification_accuracy:
  target: 0.95
  operator: ">="
  warn_threshold: 0.80
  blocking: true
  description: Accuracy of subsection vs page header classification
```

**Implementation**:
```python
def _check_subsection_classification_accuracy(data: Dict) -> ValidationResult:
    """
    Check accuracy of subsection vs page header classification.

    Research finding (line 114-128): ~60% accuracy due to page headers
    incorrectly classified as subsections.

    Evidence: 17 subsections, 10 invalid (page headers) = 41% valid
    """
    threshold = ThresholdRegistry.get("subsection_classification_accuracy")

    subsections = data.get("subsections", [])
    if not subsections:
        return ValidationResult.from_threshold(threshold, 1.0)

    # Page header pattern
    page_header_pattern = re.compile(r'.+\|\s*\d{4}\s+Form\s+\d+-[KQ]\s*\|\s*\d+')

    # Count valid subsections (NOT page headers)
    valid_subsections = sum(
        1 for sub in subsections
        if not page_header_pattern.match(sub)
    )

    accuracy = valid_subsections / len(subsections) if subsections else 1.0

    return ValidationResult.from_threshold(threshold, accuracy)
```

#### Metric 6: `noise_to_signal_ratio`

**Config Spec** (from `extraction.yaml:90-97`):
```yaml
noise_to_signal_ratio:
  target: 0.05
  operator: "<="
  blocking: false
  description: Ratio of non-content to content in extracted text
```

**Implementation**:
```python
def _check_noise_to_signal_ratio(text: str) -> ValidationResult:
    """
    Compute ratio of noise artifacts to meaningful content.

    Noise indicators:
    - Page headers
    - HTML artifacts (should be 0 after cleaning)
    - Excessive whitespace
    - Page numbers
    """
    threshold = ThresholdRegistry.get("noise_to_signal_ratio")

    # Count noise characters
    noise_chars = 0

    # Page headers
    page_headers = re.findall(r'.+\|\s*\d{4}\s+Form\s+\d+-[KQ]\s*\|\s*\d+', text)
    noise_chars += sum(len(h) for h in page_headers)

    # HTML artifacts
    html_tags = re.findall(r'<[^>]+>', text)
    noise_chars += sum(len(tag) for tag in html_tags)

    # Excessive whitespace (more than 3 consecutive spaces/newlines)
    excess_ws = re.findall(r'\s{4,}', text)
    noise_chars += sum(len(ws) - 1 for ws in excess_ws)  # 1 space is legitimate

    total_chars = len(text)
    ratio = noise_chars / total_chars if total_chars > 0 else 0.0

    return ValidationResult.from_threshold(threshold, ratio)
```

---

### Phase 4: Update Report Generation

**Goal**: Integrate ValidationResult objects into report structure

**Changes to `generate_consolidated_json_report()`:**

```python
def generate_consolidated_json_report(
    run_dir: Path,
    per_file_results: List[Dict],
    metadata: Dict
) -> Dict[str, Any]:
    """Generate consolidated JSON report with ValidationResult integration."""

    # Load metrics from config
    metrics_config = _load_metrics_from_config()

    # Count statuses (existing logic)
    passed = sum(1 for r in per_file_results if r['overall_status'] == 'PASS')
    # ... (rest unchanged)

    # NEW: Aggregate ValidationResults across files
    aggregated_results = []

    for metric_name, threshold in metrics_config.items():
        # Aggregate metric across all files
        if metric_name in ["key_item_recall"]:
            # Special handling for recall metrics
            actual = _compute_key_item_recall(per_file_results)
        else:
            # Average metric values
            values = [
                r['metrics'].get(metric_name, {}).get('actual')
                for r in per_file_results
                if r['status'] == 'success' and metric_name in r['metrics']
            ]
            actual = sum(values) / len(values) if values else None

        if actual is not None:
            result = ValidationResult.from_threshold(threshold, actual)
            aggregated_results.append(result)

    # Determine overall status using ValidationResult
    overall_status = determine_overall_status(aggregated_results)

    return {
        "status": overall_status.value,
        # ... existing fields ...
        "validation_results": [r.model_dump() for r in aggregated_results],
        "go_no_go_summary": {
            "blocking_metrics": [
                {
                    "name": r.threshold_name,
                    "status": r.status.value,
                    "go_no_go": r.go_no_go.value
                }
                for r in aggregated_results
                if metrics_config[r.threshold_name].blocking
            ]
        }
    }
```

---

## Verification Plan

### Automated Verification

```bash
# 1. Config loads correctly
python -c "
from src.config.qa_validation import ThresholdRegistry
assert len(ThresholdRegistry.by_category('extraction_accuracy')) == 4
assert len(ThresholdRegistry.by_category('content_quality')) == 4
print('✅ Config loads all 8 thresholds')
"

# 2. Run batch validation on sample data
python scripts/validation/extraction_quality/check_extractor_batch.py \
    --run-dir data/interim/extracted/sample_run \
    --output reports/test_qa_report.json \
    --format json

# Expected: Report includes validation_results with all 8 metrics

# 3. Check ValidationResult structure
python -c "
import json
with open('reports/test_qa_report.json') as f:
    report = json.load(f)
    assert 'validation_results' in report
    assert len(report['validation_results']) == 8
    for vr in report['validation_results']:
        assert 'threshold_name' in vr
        assert 'status' in vr
        assert 'go_no_go' in vr
    print('✅ ValidationResult structure correct')
"
```

### Manual Verification

1. **Metric Coverage Check**:
   - Compare `validation_results` keys against research table (lines 199-213)
   - Verify all 12 metrics present (8 from config + 4 script-specific)

2. **Threshold Enforcement Check**:
   - Modify `extraction.yaml` to set `page_header_filtering_rate: target: 0.5`
   - Run script on known bad data (with page headers)
   - Verify report shows FAIL for `page_header_filtering_rate`

3. **Backwards Compatibility Check**:
   - Generate markdown report: `--format markdown`
   - Verify sections still present: Executive Summary, Metric Performance, Detailed Findings

---

## Migration Guide

**For users with existing scripts:**

1. **No breaking changes** - report format preserved
2. **New fields added**:
   - `validation_results`: List of ValidationResult objects
   - `go_no_go_summary`: Blocking metrics Go/No-Go status
3. **Metric names changed**:
   - `no_page_headers` → `page_header_filtering_rate`
   - Other metrics: same names as config

**Updating custom parsers:**
```python
# Old way
if report['metric_statistics']['no_page_headers']['pass_rate'] < 0.9:
    alert()

# New way
validation_results = {vr['threshold_name']: vr for vr in report['validation_results']}
if validation_results['page_header_filtering_rate']['status'] != 'PASS':
    alert()
```

---

## Success Criteria

### Go Criteria

- ✅ All 8 config metrics loaded and validated
- ✅ All blocking metrics properly enforced
- ✅ ValidationResult objects correctly structured
- ✅ Reports include Go/No-Go status per threshold
- ✅ Backwards compatible report format

### No-Go Criteria

- ❌ Any blocking threshold fails to load from config
- ❌ ValidationResult validation logic incorrect (status/go_no_go mismatch)
- ❌ Existing report format breaks (missing required fields)

---

## Open Questions

1. **Ground Truth Labels**: How to validate `section_boundary_precision_end` and `key_item_recall` without labeled data?
   - **Resolution**: Use heuristic validation (boundary overshoot detection, identifier matching) until labeling infrastructure exists

2. **ToC Detection Accuracy**: How to distinguish ToC entries from legitimate cross-references?
   - **Resolution**: Use pattern-based detection (sequential dots, page number lists) - accept false positives for now

3. **Metric Aggregation**: Should metrics be file-level or batch-level?
   - **Resolution**: Compute both - file-level for debugging, batch-level for overall Go/No-Go

4. **Config Override**: Should environment variables override config thresholds?
   - **Resolution**: Yes - use Pydantic Settings pattern (already supported by ThresholdRegistry)

---

## Timeline & Dependencies

### Dependencies

- ✅ `src/config/qa_validation.py` - Already implemented
- ✅ `src/utils/metadata.py` - Already implemented
- ✅ `src/utils/checkpoint.py` - Already implemented
- ✅ `src/utils/parallel.py` - Already implemented
- ✅ `configs/qa_validation/extraction.yaml` - Already defined

### Implementation Order

1. **Phase 1**: Config integration (2-3 hours)
   - Remove hardcoded metrics
   - Load from ThresholdRegistry
   - Update function signatures

2. **Phase 2**: Missing accuracy metrics (3-4 hours)
   - `section_boundary_precision_end`
   - `key_item_recall`

3. **Phase 3**: Missing quality metrics (4-5 hours)
   - `toc_filtering_rate`
   - `page_header_filtering_rate` (upgrade existing)
   - `subsection_classification_accuracy`
   - `noise_to_signal_ratio`

4. **Phase 4**: Report generation (2-3 hours)
   - Integrate ValidationResult
   - Update JSON/markdown reports
   - Add Go/No-Go summary

5. **Testing & Verification** (2-3 hours)
   - Automated tests
   - Manual verification
   - Documentation updates

**Total Estimated Effort**: 13-18 hours

---

## Notes

- Research document identifies 2 blocking issues (regex overshoot, page headers) - both addressed by new metrics
- Config defines 4 blocking thresholds - all must pass for overall PASS status
- Script will support both file-level validation (per-file metrics) and batch-level aggregation (overall Go/No-Go)
- Threshold modifications in YAML will take effect immediately without code changes

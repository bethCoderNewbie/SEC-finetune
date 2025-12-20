---
date: 2025-12-20T14:45:00-06:00
researcher: bethCoderNewbie
git_commit: 1843e0d
branch: main
topic: "Data Health Check Implementation Plan"
status: pending_approval
---

# Plan: Data Health Check for Preprocessing Output

## Desired End State

After implementation, users will be able to:

1. **Run a single command** to validate all preprocessing output
2. **Get a pass/fail status** with blocking checks that gate model training
3. **See a human-readable report** showing all metrics and their status
4. **Detect data drift** between runs to catch pipeline regressions

```bash
# CLI usage (follows scripts/ convention from repository.txt)
python scripts/utils/validation/validate_preprocessing_output.py --run-dir data/processed/20251212_...

# Output
Data Health Check: PASS (12/12 checks passed)
  [PASS] Identity: 100% CIK present, 100% company name present
  [PASS] Cleanliness: 100% HTML removed, 100% page numbers removed
  [PASS] Substance: 54 segments, avg 897 chars
  [PASS] Consistency: No duplicates detected
```

---

## Architecture (Aligned with repository.txt)

### Design Principles (from repository.txt:273-288)

```
Separation of Concerns:
  src/          - Production code (clean, tested, importable)
  scripts/      - Pipeline execution (numbered by ML stage)
  tests/        - Quality assurance
```

**Key Insight**: Data Health Check is a **QA validation task**, so it EXTENDS the existing `src/config/qa_validation.py` infrastructure rather than creating a parallel `src/validation/` module.

### Corrected File Structure

```
configs/
  qa_validation/
    health_check.yaml           # NEW: Health check thresholds (consistent location)

src/
  config/
    qa_validation.py            # EXTEND: Add HealthCheckValidator class
                                # Reuses existing ThresholdRegistry, ValidationResult

scripts/
  utils/
    validation/
      validate_preprocessing_output.py       # NEW: CLI entry point (consistent with scripts/ pattern)
      validate_pydantic_v2.py   # EXISTING

tests/
  validation/                   # NEW: Test directory for health checks
    __init__.py
    test_health_check.py
```

### Why This Is Better Than Original Proposal

| Original Proposal | Corrected | Benefit |
|------------------|-----------|---------|
| `src/validation/` (new package) | Extend `src/config/qa_validation.py` | Single source of truth for QA |
| `src/validation/__main__.py` | `scripts/utils/validation/validate_preprocessing_output.py` | Follows scripts/ convention |
| 4 separate validator classes | 1 HealthCheckValidator + helper functions | Simpler, less code to maintain |
| New import patterns | Reuses ThresholdRegistry, ValidationResult | Consistent with existing code |

---

## Anti-Scope (What We're NOT Doing)

- NOT building a dashboard or web UI
- NOT integrating with external monitoring systems (Prometheus, Grafana)
- NOT supporting real-time streaming validation
- NOT building ML-based anomaly detection
- NOT adding cross-company comparison features

---

## Phase 1: Threshold Definitions + Registry Update (P0)

**Goal**: Define all health check thresholds and wire them into existing infrastructure.

### 1.1 Add Threshold Definitions

**File**: `configs/qa_validation/health_check.yaml` (NEW)

```yaml
# ============================================
# QA Validation - Data Health Check Thresholds
# ============================================
# Source: thoughts/shared/research/2025-12-20_14-30_data_health_check_architecture.md

categories:
  identity_completeness:
    display_name: Identity Completeness
    description: Required identity fields validation

  data_cleanliness:
    display_name: Data Cleanliness
    description: Artifact-free content validation

  content_substance:
    display_name: Content Substance
    description: Meaningful content validation

  domain_rules:
    display_name: Domain Rules
    description: SEC-specific business logic

thresholds:
  # -------------------------
  # Identity Completeness
  # -------------------------
  identity_completeness:
    cik_present_rate:
      display_name: CIK Present Rate
      metric_type: rate
      target: 1.0
      operator: ">="
      blocking: true
      description: All files must have CIK
      tags: [identity, schema, blocking]

    company_name_present_rate:
      display_name: Company Name Present Rate
      metric_type: rate
      target: 1.0
      operator: ">="
      blocking: true
      description: All files must have company name
      tags: [identity, schema, blocking]

    sic_code_present_rate:
      display_name: SIC Code Present Rate
      metric_type: rate
      target: 0.95
      operator: ">="
      blocking: false
      description: 95% of files should have SIC code
      tags: [identity, schema]

  # -------------------------
  # Data Cleanliness
  # -------------------------
  data_cleanliness:
    html_artifact_rate:
      display_name: HTML Artifact Rate
      metric_type: rate
      target: 0.0
      operator: "=="
      blocking: true
      description: No HTML tags should remain in text
      tags: [cleanliness, blocking]

    page_number_artifact_rate:
      display_name: Page Number Artifact Rate
      metric_type: rate
      target: 0.0
      operator: "=="
      blocking: false
      description: No page number artifacts should remain
      tags: [cleanliness]

  # -------------------------
  # Content Substance
  # -------------------------
  content_substance:
    empty_segment_rate:
      display_name: Empty Segment Rate
      metric_type: rate
      target: 0.0
      operator: "=="
      blocking: true
      description: No empty segments allowed
      tags: [substance, blocking]

    short_segment_rate:
      display_name: Short Segment Rate
      metric_type: rate
      target: 0.05
      operator: "<="
      blocking: false
      description: Max 5% segments below minimum length
      tags: [substance]

  # -------------------------
  # Domain Rules
  # -------------------------
  domain_rules:
    duplicate_rate:
      display_name: Duplicate Rate
      metric_type: rate
      target: 0.0
      operator: "=="
      blocking: true
      description: No duplicate filings allowed
      tags: [domain, blocking]

    risk_keyword_present:
      display_name: Risk Keyword Present
      metric_type: boolean
      target: true
      blocking: false
      description: Risk Factors section should contain risk keywords
      tags: [domain]
```

### 1.2 Update Threshold Registry

**File**: `src/config/qa_validation.py` (MODIFY line ~48)

```python
# QA validation config files to load
_QA_VALIDATION_FILES = [
    "qa_validation/extraction.yaml",
    "qa_validation/parsing.yaml",
    "qa_validation/cleaning.yaml",
    "qa_validation/features.yaml",
    "qa_validation/health_check.yaml",  # ADD THIS
]
```

---

## Phase 2: Extend qa_validation.py with HealthCheckValidator (P0)

**Goal**: Add validation logic to existing QA module (not a separate package).

### 2.1 Add HealthCheckValidator Class

**File**: `src/config/qa_validation.py` (EXTEND - add after line ~570)

```python
# =============================================================================
# Health Check Validator (Data Quality Checks)
# =============================================================================

import hashlib
import re
import statistics
from pathlib import Path


class HealthCheckValidator:
    """
    Unified validator for preprocessing output data health.

    Follows the 4-check framework:
    1. Completeness: Identity fields present (CIK, company name)
    2. Cleanliness: No HTML/page number artifacts
    3. Substance: Meaningful content (segment length, word count)
    4. Consistency: No duplicates, proper segmentation

    Usage:
        from src.config.qa_validation import HealthCheckValidator

        validator = HealthCheckValidator()
        report = validator.check_run(Path("data/processed/20251212_..."))
        print(report["status"])  # "PASS" or "FAIL"
    """

    # Artifact detection patterns
    HTML_PATTERN = re.compile(r'<[^>]+>')
    PAGE_NUMBER_PATTERN = re.compile(r'\b(Page\s+\d+|\d+\s+of\s+\d+)\b', re.IGNORECASE)

    # Domain validation
    RISK_KEYWORDS = {"risk", "adverse", "material", "uncertain", "may", "could", "might"}
    REQUIRED_IDENTITY_FIELDS = ["cik", "company_name"]
    RECOMMENDED_IDENTITY_FIELDS = ["sic_code", "ticker", "form_type"]

    def __init__(self):
        self.registry = ThresholdRegistry()

    def check_run(self, run_dir: Path) -> Dict[str, Any]:
        """Run all health checks on a preprocessing run directory."""
        import json
        from datetime import datetime

        files = list(run_dir.glob("*.json"))
        if not files:
            return {"status": "ERROR", "message": "No JSON files found"}

        # Load all file data
        file_data = []
        for f in files:
            with open(f, 'r', encoding='utf-8') as fp:
                data = json.load(fp)
                data["_source_file"] = str(f)
                file_data.append(data)

        # Collect all validation results
        results: List[ValidationResult] = []

        # 1. Identity completeness
        results.extend(self._check_identity(file_data))

        # 2. Cleanliness
        results.extend(self._check_cleanliness(file_data))

        # 3. Substance
        results.extend(self._check_substance(file_data))

        # 4. Domain rules (duplicates, keywords)
        results.extend(self._check_domain(file_data))

        # Generate report using existing infrastructure
        overall_status = determine_overall_status(results)
        blocking_summary = generate_blocking_summary(results)

        return {
            "status": overall_status.value,
            "timestamp": datetime.now().isoformat(),
            "run_directory": str(run_dir),
            "files_checked": len(files),
            "blocking_summary": blocking_summary,
            "validation_table": generate_validation_table(results),
        }

    def _check_identity(self, file_data: List[Dict]) -> List[ValidationResult]:
        """Check identity field completeness."""
        results = []
        total = len(file_data)

        cik_present = sum(1 for f in file_data if f.get("cik"))
        company_present = sum(1 for f in file_data if f.get("company_name"))
        sic_present = sum(1 for f in file_data if f.get("sic_code"))

        # CIK rate
        threshold = self.registry.get("cik_present_rate")
        if threshold:
            results.append(ValidationResult.from_threshold(
                threshold, cik_present / total if total else 0
            ))

        # Company name rate
        threshold = self.registry.get("company_name_present_rate")
        if threshold:
            results.append(ValidationResult.from_threshold(
                threshold, company_present / total if total else 0
            ))

        # SIC code rate
        threshold = self.registry.get("sic_code_present_rate")
        if threshold:
            results.append(ValidationResult.from_threshold(
                threshold, sic_present / total if total else 0
            ))

        return results

    def _check_cleanliness(self, file_data: List[Dict]) -> List[ValidationResult]:
        """Check for HTML and page number artifacts."""
        results = []
        total_segments = 0
        html_artifacts = 0
        page_artifacts = 0

        for data in file_data:
            for seg in data.get("segments", []):
                total_segments += 1
                text = seg.get("text", "")
                if self.HTML_PATTERN.search(text):
                    html_artifacts += 1
                if self.PAGE_NUMBER_PATTERN.search(text):
                    page_artifacts += 1

        # HTML artifact rate
        threshold = self.registry.get("html_artifact_rate")
        if threshold and total_segments:
            results.append(ValidationResult.from_threshold(
                threshold, html_artifacts / total_segments
            ))

        # Page number artifact rate
        threshold = self.registry.get("page_number_artifact_rate")
        if threshold and total_segments:
            results.append(ValidationResult.from_threshold(
                threshold, page_artifacts / total_segments
            ))

        return results

    def _check_substance(self, file_data: List[Dict]) -> List[ValidationResult]:
        """Check content substance (segment length, word count)."""
        results = []
        total_segments = 0
        empty_segments = 0
        short_segments = 0
        MIN_LENGTH = 50

        for data in file_data:
            for seg in data.get("segments", []):
                total_segments += 1
                length = seg.get("length", len(seg.get("text", "")))
                if length == 0:
                    empty_segments += 1
                elif length < MIN_LENGTH:
                    short_segments += 1

        # Empty segment rate
        threshold = self.registry.get("empty_segment_rate")
        if threshold and total_segments:
            results.append(ValidationResult.from_threshold(
                threshold, empty_segments / total_segments
            ))

        # Short segment rate
        threshold = self.registry.get("short_segment_rate")
        if threshold and total_segments:
            results.append(ValidationResult.from_threshold(
                threshold, short_segments / total_segments
            ))

        return results

    def _check_domain(self, file_data: List[Dict]) -> List[ValidationResult]:
        """Check SEC-specific domain rules."""
        results = []

        # Duplicate detection via content hash
        hashes: Dict[str, List[str]] = {}
        for data in file_data:
            text = "".join(s.get("text", "") for s in data.get("segments", []))
            normalized = re.sub(r'\s+', ' ', text.lower().strip())
            content_hash = hashlib.sha256(normalized.encode()).hexdigest()[:16]

            file_name = data.get("filing_name", data.get("_source_file", "unknown"))
            if content_hash not in hashes:
                hashes[content_hash] = []
            hashes[content_hash].append(file_name)

        duplicates = sum(1 for files in hashes.values() if len(files) > 1)
        duplicate_rate = duplicates / len(file_data) if file_data else 0

        threshold = self.registry.get("duplicate_rate")
        if threshold:
            results.append(ValidationResult.from_threshold(threshold, duplicate_rate))

        # Risk keyword presence
        total_risk_words = 0
        for data in file_data:
            text = " ".join(s.get("text", "") for s in data.get("segments", []))
            words = re.findall(r'\b\w+\b', text.lower())
            total_risk_words += sum(1 for w in words if w in self.RISK_KEYWORDS)

        threshold = self.registry.get("risk_keyword_present")
        if threshold:
            results.append(ValidationResult.from_threshold(
                threshold, total_risk_words >= 10
            ))

        return results
```

---

## Phase 3: CLI Script (P1)

**Goal**: Add CLI entry point following scripts/ convention.

### 3.1 Create CLI Script

**File**: `scripts/utils/validation/validate_preprocessing_output.py` (NEW)

```python
#!/usr/bin/env python
"""
Run data health checks on preprocessing output.

Usage:
    python scripts/utils/validation/validate_preprocessing_output.py --run-dir data/processed/20251212_...
    python scripts/utils/validation/validate_preprocessing_output.py --run-dir data/processed/... --output reports/health.json
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config.qa_validation import HealthCheckValidator


def main():
    parser = argparse.ArgumentParser(
        description="Run data health checks on preprocessing output"
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        required=True,
        help="Directory containing JSON output files"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output JSON report file"
    )
    parser.add_argument(
        "--fail-on-warn",
        action="store_true",
        help="Exit with code 1 on warnings"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed validation table"
    )

    args = parser.parse_args()

    # Run health check
    validator = HealthCheckValidator()
    report = validator.check_run(args.run_dir)

    # Save output if requested
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"Report saved to: {args.output}")

    # Print summary
    print(f"\nData Health Check: {report['status']}")
    print(f"  Files checked: {report['files_checked']}")

    summary = report['blocking_summary']
    print(f"  Blocking checks: {summary['passed']}/{summary['total_blocking']} passed")

    if args.verbose:
        print("\nValidation Details:")
        for item in report['validation_table']:
            status_icon = "PASS" if item['status'] == 'PASS' else "FAIL"
            print(f"  [{status_icon}] {item['display_name']}: {item['actual']} (target: {item['target']})")

    # Exit code
    if report['status'] == "FAIL":
        sys.exit(1)
    if report['status'] == "WARN" and args.fail_on_warn:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
```

---

## Phase 4: Test Suite (P1)

**Goal**: Add pytest tests for health check functionality.

### 4.1 Create Test File

**File**: `tests/validation/test_health_check.py` (NEW)

```python
"""Tests for data health check validation."""

import json
import pytest
from pathlib import Path

from src.config.qa_validation import HealthCheckValidator, ThresholdRegistry


class TestHealthCheckValidator:
    """Test HealthCheckValidator functionality."""

    @pytest.fixture
    def validator(self):
        return HealthCheckValidator()

    @pytest.fixture
    def sample_valid_data(self, tmp_path):
        """Create valid sample data."""
        data = {
            "cik": "0000320193",
            "company_name": "Apple Inc.",
            "sic_code": "3571",
            "segments": [
                {"id": 1, "text": "This is a risk factor about market conditions.", "length": 50},
                {"id": 2, "text": "The company may face adverse economic conditions.", "length": 55},
            ]
        }
        file_path = tmp_path / "valid_file.json"
        with open(file_path, 'w') as f:
            json.dump(data, f)
        return tmp_path

    def test_valid_data_passes(self, validator, sample_valid_data):
        """Valid data should pass all checks."""
        report = validator.check_run(sample_valid_data)
        assert report["status"] == "PASS"

    def test_missing_cik_fails(self, validator, tmp_path):
        """Missing CIK should fail blocking check."""
        data = {
            "company_name": "Test Corp",
            "segments": [{"id": 1, "text": "x" * 100, "length": 100}]
        }
        with open(tmp_path / "missing_cik.json", 'w') as f:
            json.dump(data, f)

        report = validator.check_run(tmp_path)
        assert report["status"] == "FAIL"

    def test_html_artifacts_detected(self, validator, tmp_path):
        """HTML artifacts should be flagged."""
        data = {
            "cik": "123",
            "company_name": "Test",
            "segments": [
                {"id": 1, "text": "<div>This has HTML</div>", "length": 25}
            ]
        }
        with open(tmp_path / "html_artifact.json", 'w') as f:
            json.dump(data, f)

        report = validator.check_run(tmp_path)
        # Should fail due to HTML artifacts
        blocking_failed = report["blocking_summary"]["failed"]
        assert blocking_failed > 0


class TestThresholdRegistryHealthCheck:
    """Test health check thresholds are loaded."""

    def test_health_check_thresholds_exist(self):
        """Health check thresholds should be available."""
        registry = ThresholdRegistry()

        # Identity thresholds
        assert registry.get("cik_present_rate") is not None
        assert registry.get("company_name_present_rate") is not None

    def test_health_check_blocking_flags(self):
        """Critical thresholds should be blocking."""
        registry = ThresholdRegistry()

        cik_threshold = registry.get("cik_present_rate")
        assert cik_threshold.blocking is True
```

---

## Success Criteria

### Automated Verification

```bash
# Run all health checks
python scripts/utils/validation/validate_preprocessing_output.py --run-dir data/processed/20251212_... -v

# Run pytest validation suite
pytest tests/validation/ -v
```

### Manual Verification

1. Generate report for sample run:
   ```bash
   python scripts/utils/validation/validate_preprocessing_output.py \
       --run-dir data/processed/20251212_... \
       --output reports/health_check.json \
       --verbose
   ```

2. Verify report contains:
   - [ ] Identity completeness metrics (CIK, company name rates)
   - [ ] Cleanliness metrics (HTML artifact rate)
   - [ ] Substance metrics (empty/short segment rates)
   - [ ] Domain validation (duplicate rate, risk keywords)
   - [ ] Overall pass/fail status

3. Test blocking behavior:
   - Remove CIK from test file → should FAIL
   - Add HTML tag to segment → should FAIL

---

## File Changes Summary (Corrected)

| File | Action | Description |
|------|--------|-------------|
| `configs/qa_validation/health_check.yaml` | CREATE | Threshold definitions (8 thresholds) |
| `src/config/qa_validation.py` | EXTEND | Add HealthCheckValidator class (~150 lines) |
| `scripts/utils/validation/validate_preprocessing_output.py` | CREATE | CLI entry point |
| `tests/validation/__init__.py` | CREATE | Test package init |
| `tests/validation/test_health_check.py` | CREATE | Test suite |

**Total: 4 new files, 1 extension** (vs. original 10 new files)

---

## Implementation Order

1. **Phase 1**: `configs/qa_validation/health_check.yaml` + registry update
2. **Phase 2**: Extend `src/config/qa_validation.py` with HealthCheckValidator
3. **Phase 3**: `scripts/utils/validation/validate_preprocessing_output.py` CLI
4. **Phase 4**: `tests/validation/test_health_check.py`

---

## Open Questions Resolved

| Question | Decision | Rationale |
|----------|----------|-----------|
| Baseline storage for drift | Option A (Modified): `data/baselines/` | Separates data stats from code config; fits existing data/raw, data/processed pattern |
| Duplicate definition | Hybrid A+B: Content hash + metadata | SHA-256 hashing primary; CIK/Company metadata for reporting (not detection) |
| CI/CD integration | Option C: CLI with exit codes | Works with any CI system; separates data validation from unit testing |

### Validation Notes (2025-12-20)

1. **Baseline Storage**: Using `data/baselines/` instead of `configs/baselines/` because:
   - Maintains separation between "code configuration" and "data-derived statistics"
   - Consistent with existing `data/raw`, `data/processed`, `data/interim` structure
   - Create `generate_baseline.py` script to calculate stats from approved data

2. **Duplicate Scope**: Hybrid approach validated because:
   - Identity fields (cik, sic_code) are currently `Optional[str] = None` in `extractor.py:25-171`
   - Period extraction is unreliable - using for detection would create false negatives
   - Content hashing is deterministic; metadata used only for duplicate reporting

3. **CI/CD Integration**: Standalone CLI validated because:
   - `tests/validation/` tests the validator logic ("does hash detect duplicates?")
   - `python -m src.validation.health_check` runs validators on actual data
   - Exit codes (0=Pass, 1=Fail) are POSIX standard for CI/CD

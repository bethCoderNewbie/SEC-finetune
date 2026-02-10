# NLP Validation Report (Batch)

**Status**: `FAIL`
**Source**: Batch validation of segmented risk files

## 0. Run Environment (Metadata)

| Key | Value |
|-----|-------|
| **Timestamp** | `2025-12-27T13:28:00.825271-06:00` |
| **Researcher** | `bethCoderNewbie` |
| **Git Commit** | `648bf25` (Branch: `main`) |
| **Python** | `3.13.5` |
| **Platform** | `Windows-11-10.0.22631-SP0` |
| **Run Directory** | `data\processed\20251212_161906_preprocessing_ea45dd2` |

---

## 1. Executive Summary

This report validates 1 segmented risk files against NLP feature QA metrics.

**File Status Summary**:
*   ✅ **Passed**: 0
*   ⚠️ **Warned**: 0
*   ❌ **Failed**: 1
*   🔴 **Errors**: 0

### Aggregate Metrics (Across All Files)

| Category | Metric | Avg Value | Target | Status |
|----------|--------|-----------|--------|--------|
| **Sentiment** | LM Dictionary Hit Rate | 10.19% | >2% | ✅ PASS |
| **Sentiment** | Zero-Vector Rate | 1.85% | <50% | ✅ PASS |
| **Sentiment** | Uncertainty-Neg Correlation | 0.63 | >0.3 | ✅ PASS |
| **Readability** | Avg Gunning Fog | 24.6 | 14-22 | ❌ FAIL |
| **Readability** | FK-Fog Correlation | 0.98 | >0.7 | ✅ PASS |

---

## 2. Failed Files

Total failed files: 1

### AAPL_10K_2021_segmented_risks.json

**Status**: FAIL

**Failed Validations**:
*   ValidationStatus.FAIL: Gunning Fog Average (Actual: 24.610425531914895, Target: 14.0)
*   ValidationStatus.FAIL: Gunning Fog Maximum (Actual: 41.39, Target: 35.0)


---

## 3. Summary

1 files failed NLP validation. Review failed metrics and fix feature extraction issues.

# SEC Section Extractor QA Report (Batch)

**Status**: `FAIL`
**Source**: Batch validation of extracted risk files

## 0. Run Environment (Metadata)

| Key | Value |
|-----|-------|
| **Timestamp** | `2025-12-30T15:38:22.873015-06:00` |
| **Researcher** | `bethCoderNewbie` |
| **Git Commit** | `7942943` (Branch: `main`) |
| **Python** | `3.13.5` |
| **Platform** | `Windows-11-10.0.22631-SP0` |
| **Run Directory** | `data\interim\extracted\20251229_140905_batch_extract_648bf25` |

---

## 1. Executive Summary

This report validates 309 extracted risk factor files against QA metrics.

**File Status Summary**:
*   ✅ **Passed**: 7
*   ⚠️ **Warned**: 26
*   ❌ **Failed**: 276
*   🔴 **Errors**: 0

### Metric Performance

| Metric Category | Metric Name | Pass Rate | Passed | Failed | Warned | Blocking |
|-----------------|-------------|-----------|--------|--------|--------|----------|

---

## 2. Detailed Findings

### 2.1 Critical Metrics (Blocking)

*   ❌ **Section Start Precision**: 269/309 files passed (87.1%)
*   ❌ **Section End Precision**: 146/309 files passed (47.2%)
*   ✅ **Key Item Recall**: 309/309 files passed (100.0%)
*   ❌ **ToC Filtering Rate**: 134/309 files passed (43.4%)
*   ❌ **Page Header Removal**: 304/309 files passed (98.4%)
*   ✅ **Subsection Classification**: 309/309 files passed (100.0%)
*   ✅ **Valid Section Identifier**: 309/309 files passed (100.0%)
*   ✅ **Section Has Title**: 309/309 files passed (100.0%)
*   ❌ **Substantial Content (>1000 chars)**: 300/309 files passed (97.1%)

### 2.2 Quality Metrics (Non-Blocking)

*   ⚠️ **Ghost Section Rate**: 0/309 files passed (0.0%)
*   ✅ **Noise-to-Signal Ratio**: 289/309 files passed (93.5%)
*   ✅ **Title Mentions Risk**: 309/309 files passed (100.0%)
*   ⚠️ **Character Count in Range (5k-50k)**: 69/309 files passed (22.3%)
*   ✅ **Has Subsections**: 296/309 files passed (95.8%)
*   ✅ **Risk Keyword Density (>0.5%)**: 288/309 files passed (93.2%)

---

## 3. Failed Files

Total failed files: 276

### AAPL_10K_2022_20251229_140905_extracted_risks.json

**Status**: FAIL

**Failed Metrics**:
*   ❌ Section End Precision: 0.0 (Expected: 0.95)
*   ❌ Page Header Removal: 0.8333333333333334 (Expected: 1.0)

### AAPL_10K_2021_20251229_140905_extracted_risks.json

**Status**: FAIL

**Failed Metrics**:
*   ❌ Section End Precision: 0.0 (Expected: 0.95)
*   ❌ Page Header Removal: 0.8571428571428572 (Expected: 1.0)

### AAPL_10K_2023_20251229_140905_extracted_risks.json

**Status**: FAIL

**Failed Metrics**:
*   ❌ Section End Precision: 0.0 (Expected: 0.95)
*   ❌ Page Header Removal: 0.8333333333333334 (Expected: 1.0)

### AAPL_10K_2024_20251229_140905_extracted_risks.json

**Status**: FAIL

**Failed Metrics**:
*   ❌ Section End Precision: 0.0 (Expected: 0.95)
*   ❌ Page Header Removal: 0.8333333333333334 (Expected: 1.0)

### AAPL_10K_2025_20251229_140905_extracted_risks.json

**Status**: FAIL

**Failed Metrics**:
*   ❌ Section End Precision: 0.0 (Expected: 0.95)
*   ❌ Page Header Removal: 0.8333333333333334 (Expected: 1.0)

### ABT_10K_2024_20251229_140905_extracted_risks.json

**Status**: FAIL

**Failed Metrics**:
*   ❌ Section End Precision: 0.0 (Expected: 0.95)
*   ❌ ToC Filtering Rate: 0.0 (Expected: 1.0)

### ABT_10K_2025_20251229_140905_extracted_risks.json

**Status**: FAIL

**Failed Metrics**:
*   ❌ Section End Precision: 0.0 (Expected: 0.95)
*   ❌ ToC Filtering Rate: 0.0 (Expected: 1.0)

### ABT_10K_2021_20251229_140905_extracted_risks.json

**Status**: FAIL

**Failed Metrics**:
*   ❌ Section End Precision: 0.0 (Expected: 0.95)

### ADBE_10K_2023_20251229_140905_extracted_risks.json

**Status**: FAIL

**Failed Metrics**:
*   ❌ ToC Filtering Rate: 0.0 (Expected: 1.0)

### ADBE_10K_2021_20251229_140905_extracted_risks.json

**Status**: FAIL

**Failed Metrics**:
*   ❌ ToC Filtering Rate: 0.0 (Expected: 1.0)

### ADBE_10K_2022_20251229_140905_extracted_risks.json

**Status**: FAIL

**Failed Metrics**:
*   ❌ ToC Filtering Rate: 0.0 (Expected: 1.0)

### ADBE_10K_2025_20251229_140905_extracted_risks.json

**Status**: FAIL

**Failed Metrics**:
*   ❌ ToC Filtering Rate: 0.0 (Expected: 1.0)

### ABT_10K_2022_20251229_140905_extracted_risks.json

**Status**: FAIL

**Failed Metrics**:
*   ❌ Section End Precision: 0.0 (Expected: 0.95)

### AIG_10K_2024_20251229_140905_extracted_risks.json

**Status**: FAIL

**Failed Metrics**:
*   ❌ Substantial Content (>1000 chars): 894 chars (Expected: >1000 chars)
*   ❌ Section Start Precision: 0.0 (Expected: 1.0)
*   ❌ Section End Precision: 0.0 (Expected: 0.95)
*   ❌ ToC Filtering Rate: 0.0 (Expected: 1.0)

### AIG_10K_2025_20251229_140905_extracted_risks.json

**Status**: FAIL

**Failed Metrics**:
*   ❌ Substantial Content (>1000 chars): 861 chars (Expected: >1000 chars)
*   ❌ Section Start Precision: 0.0 (Expected: 1.0)
*   ❌ Section End Precision: 0.0 (Expected: 0.95)

### AFL_10K_2022_20251229_140905_extracted_risks.json

**Status**: FAIL

**Failed Metrics**:
*   ❌ Section End Precision: 0.0 (Expected: 0.95)

### ALL_10K_2021_20251229_140905_extracted_risks.json

**Status**: FAIL

**Failed Metrics**:
*   ❌ Section End Precision: 0.0 (Expected: 0.95)

### AFL_10K_2025_20251229_140905_extracted_risks.json

**Status**: FAIL

**Failed Metrics**:
*   ❌ Section End Precision: 0.0 (Expected: 0.95)

### ALL_10K_2022_20251229_140905_extracted_risks.json

**Status**: FAIL

**Failed Metrics**:
*   ❌ Section End Precision: 0.0 (Expected: 0.95)

### ALL_10K_2024_20251229_140905_extracted_risks.json

**Status**: FAIL

**Failed Metrics**:
*   ❌ Section End Precision: 0.0 (Expected: 0.95)


---

## 4. Summary

**Overall Status**: `FAIL`

276 files failed QA validation. Review failed metrics and fix extraction issues before proceeding.

# SEC Section Extractor QA Report (Batch)

**Status**: `WARN`
**Source**: Batch validation of extracted risk files

## 0. Run Environment (Metadata)

| Key | Value |
|-----|-------|
| **Timestamp** | `2025-12-27T13:14:09.943291-06:00` |
| **Researcher** | `bethCoderNewbie` |
| **Git Commit** | `648bf25` (Branch: `main`) |
| **Python** | `3.13.5` |
| **Platform** | `Windows-11-10.0.22631-SP0` |
| **Run Directory** | `C:\Users\bichn\MSBA\SEC finetune\data\interim\extracted\20251212_203231_test_fix_ea45dd2` |

---

## 1. Executive Summary

This report validates 23 extracted risk factor files against QA metrics.

**File Status Summary**:
*   ✅ **Passed**: 4
*   ⚠️ **Warned**: 19
*   ❌ **Failed**: 0
*   🔴 **Errors**: 0

### Metric Performance

| Metric Category | Metric Name | Pass Rate | Passed | Failed | Warned | Blocking |
|-----------------|-------------|-----------|--------|--------|--------|----------|
| **Boundary Detection** | Valid Section Identifier 🔒 | 100.0% | 23 | 0 | 0 | Yes |
| **Boundary Detection** | Section Has Title 🔒 | 100.0% | 23 | 0 | 0 | Yes |
| **Content Quality** | Title Mentions Risk  | 100.0% | 23 | 0 | 0 | No |
| **Content Quality** | Substantial Content (>1000 chars) 🔒 | 100.0% | 23 | 0 | 0 | Yes |
| **Content Quality** | No Page Headers in Text  | 78.3% | 18 | 5 | 0 | No |
| **Content Quality** | Has Subsections  | 100.0% | 23 | 0 | 0 | No |
| **Benchmarking** | Character Count in Range (5k-50k)  | 17.4% | 4 | 0 | 19 | No |
| **Benchmarking** | Risk Keyword Density (>0.5%)  | 100.0% | 23 | 0 | 0 | No |

---

## 2. Detailed Findings

### 2.1 Critical Metrics (Blocking)

*   ✅ **Valid Section Identifier**: 23/23 files passed (100.0%)
*   ✅ **Section Has Title**: 23/23 files passed (100.0%)
*   ✅ **Substantial Content (>1000 chars)**: 23/23 files passed (100.0%)

### 2.2 Quality Metrics (Non-Blocking)

*   ✅ **Title Mentions Risk**: 23/23 files passed (100.0%)
*   ⚠️ **Character Count in Range (5k-50k)**: 4/23 files passed (17.4%)
*   ⚠️ **No Page Headers in Text**: 18/23 files passed (78.3%)
*   ✅ **Has Subsections**: 23/23 files passed (100.0%)
*   ✅ **Risk Keyword Density (>0.5%)**: 23/23 files passed (100.0%)

---

## 3. Failed Files

No failed files! All extractions passed QA checks.


---

## 4. Summary

**Overall Status**: `WARN`

19 files have warnings but no blocking failures. Review non-critical metrics for potential improvements.

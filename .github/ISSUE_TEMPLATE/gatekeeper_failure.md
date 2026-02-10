---
name: Data Quality Gate Failure
about: Report a gatekeeper validation failure
title: 'Data Quality Gate Failed'
labels: ['data-quality', 'validation-failure', 'gatekeeper']
assignees: []
---

## Validation Failure Report

**Status:** Provide gatekeeper status (FAIL/WARN)
**Timestamp:**
**Run Directory:** `data/processed/...`

## Failed Checks

### Blocking Checks
- [ ] CIK Present Rate
- [ ] Company Name Present Rate
- [ ] HTML Artifact Rate
- [ ] Empty Segment Rate
- [ ] Duplicate Rate
- [ ] Other: _____

### Check Details
- **Check Name:**
- **Actual Value:**
- **Target Value:**
- **Impact:** What does this failure mean?

## Root Cause Analysis

### Suspected Root Cause
- [ ] Parser missing metadata
- [ ] Cleaner not removing artifacts
- [ ] Segmenter creating empty segments
- [ ] Duplicate filings in input
- [ ] Other: _____

### Evidence
Provide details supporting your hypothesis:

```
Example: File X has [issue], suggesting [root cause]
```

## Remediation

### Option 1: Fix Data
1. Identify source files causing failure
2. Correct preprocessing configuration
3. Re-run preprocessing
4. Re-validate

### Option 2: Adjust Threshold
1. Modify `configs/qa_validation/health_check.yaml`
2. Document justification in this issue
3. Re-validate with new threshold
4. Request approval for threshold change

### Option 3: Accept Conditional
1. Keep status as WARN
2. Document risk acceptance
3. Proceed with caution to training
4. Plan improvement for next cycle

## Steps to Reproduce

```bash
# Command to reproduce validation failure
python scripts/validation/data_quality/check_preprocessing_batch.py \
  --run-dir data/processed/... \
  --max-workers 8 \
  --fail-on-warn
```

## Validation Report

- Link to artifact: [GitHub Actions Artifact URL]
- Download JSON report for detailed check results

## Resolution Checklist

- [ ] Root cause identified
- [ ] Remediation approach selected
- [ ] Changes implemented
- [ ] Validation re-run
- [ ] Validation passes
- [ ] Related data team notified
- [ ] Issue closed

## Timeline

| Event | Date | Owner |
|-------|------|-------|
| Failure detected | | |
| Root cause identified | | |
| Fix deployed | | |
| Validation passes | | |

# Gatekeeper Pattern - Quick Start Guide

**For:** Data/ML Ops Team
**Purpose:** Automated validation gates preventing unvalidated data from reaching production
**Status:** Ready for implementation (Q1 2026)

## What is the Gatekeeper?

The Gatekeeper is an automated quality checkpoint that runs after data preprocessing. It validates that output meets quality thresholds before allowing it to proceed to model training.

```
Preprocessing → Validation (Gatekeeper) → Training
                    ↓
              FAIL → Block PR + Create Issue
              PASS → Proceed to Training
```

## Quick Start (5 Minutes)

### 1. Deploy the Gatekeeper Workflow

```bash
# The workflow is already in place at:
# .github/workflows/gatekeeper.yml

# Verify it exists:
ls -l .github/workflows/gatekeeper.yml
```

### 2. Trigger a Validation Run

**Via GitHub UI:**
1. Go to: Actions → "Data Quality Gatekeeper"
2. Click "Run workflow"
3. Enter run directory: `data/processed/20251228_143022_preprocessing_ea45dd2`
4. Click "Run workflow"

**Via Command Line:**
```bash
# Find latest preprocessing run
RUN_DIR=$(ls -td data/processed/2025* | head -1)

# Trigger workflow (requires gh CLI)
gh workflow run gatekeeper.yml \
  -f run_dir="$RUN_DIR"
```

### 3. Monitor Validation

1. Go to Actions tab → Latest "Data Quality Gatekeeper" run
2. Check job output for status:
   - ✅ **GATE OPEN** = Data quality passed, pipeline can proceed
   - ⚠️ **GATE CONDITIONAL** = Passed with warnings (review issues)
   - ❌ **GATE CLOSED** = Failed, pipeline blocked

### 4. Review Detailed Report

1. After validation completes, go to "Artifacts" section
2. Download `gatekeeper-report-{id}.json`
3. Open in text editor or browser
4. Review `validation_table` for individual check results

### 5. Fix and Rerun (if needed)

If validation fails:
1. GitHub issue auto-created with failure details
2. Identify root cause (see Troubleshooting section)
3. Re-run preprocessing with corrected settings
4. Trigger validation again
5. Merge PR when validation passes

---

## How It Works

### Validation Checks (4 Categories)

| Category | Checks | Blocks Pipeline? |
|----------|--------|------------------|
| **Identity** | CIK present, Company name present, SIC code present | Yes (CIK/Company) |
| **Cleanliness** | HTML artifacts, Page number artifacts | Yes |
| **Substance** | Empty segments, Short segments | Yes (empty) |
| **Consistency** | Duplicates, Risk keywords | Yes (duplicates) |

### Exit Codes

| Exit Code | Meaning | Action |
|-----------|---------|--------|
| 0 | ✅ PASS or WARN | Pipeline can proceed |
| 1 | ❌ FAIL | Pipeline blocked, PR cannot merge |

### Report Structure

```json
{
  "status": "PASS",                    // Overall status
  "total_files": 317,                  // Files validated
  "blocking_summary": {
    "total_blocking": 8,               // Total blocking checks
    "passed": 8,                       // Number that passed
    "failed": 0,                       // Number that failed
    "warned": 0,                       // Number that warned
    "all_pass": true                   // Easy boolean check
  },
  "validation_table": [                // Individual check results
    {
      "category": "identity_completeness",
      "metric": "cik_present_rate",
      "display_name": "CIK Present Rate",
      "target": 1.0,
      "actual": 0.95,
      "status": "PASS",
      "go_no_go": "GO"
    }
    // ... more checks
  ]
}
```

---

## Common Scenarios

### Scenario 1: Validation Passes ✅

**What to do:**
- Proceed to model training
- Save metrics for future reference
- No action needed

### Scenario 2: Validation Fails ❌

**What to do:**
1. Check GitHub issue (auto-created)
2. Review failed check details:
   ```bash
   # Extract failed checks from report
   python3 << 'EOF'
   import json
   with open('gatekeeper_report.json') as f:
       report = json.load(f)
   for check in report['validation_table']:
       if check['status'] != 'PASS':
           print(f"{check['display_name']}: {check['actual']} vs {check['target']}")
   EOF
   ```
3. Identify root cause
4. Re-run preprocessing or adjust thresholds
5. Re-trigger validation

### Scenario 3: Too Many Warnings ⚠️

**What to do:**
- Validation still passes but indicates potential issues
- Review warning thresholds (editable in `configs/qa_validation/health_check.yaml`)
- Decide: adjust thresholds or fix root cause
- Document decision in issue

---

## Troubleshooting Guide

### Problem: "No JSON files found"

**Cause:** Run directory path is incorrect or doesn't exist

**Solution:**
```bash
# Verify directory exists and contains JSON files
ls -la data/processed/20251228_143022_preprocessing_ea45dd2/ | grep ".json"

# Should see files like: filing_name_segmented_risks.json

# Find latest valid run directory
ls -td data/processed/2025* | head -1
```

### Problem: All checks show "SKIP"

**Cause:** JSON files have unexpected structure

**Solution:**
```bash
# Inspect a sample JSON file
python3 << 'EOF'
import json
path = "data/processed/20251228_143022_preprocessing_ea45dd2/sample.json"
with open(path) as f:
    data = json.load(f)
print(f"Keys: {data.keys()}")
print(f"Has 'cik': {'cik' in data}")
print(f"Has 'segments': {'segments' in data}")
if 'segments' in data:
    print(f"Num segments: {len(data['segments'])}")
EOF
```

### Problem: "CIK Present Rate" fails

**Cause:** One or more files missing CIK field

**Solution:**
```bash
# Find files without CIK
python3 << 'EOF'
import json
from pathlib import Path

run_dir = Path("data/processed/20251228_143022_preprocessing_ea45dd2")
for f in run_dir.glob("*.json"):
    with open(f) as fp:
        data = json.load(fp)
    if not data.get('cik'):
        print(f"Missing CIK: {f.name}")
EOF

# Then fix in preprocessing parser or data source
```

### Problem: "HTML Artifact Rate" fails

**Cause:** Cleaner not removing HTML tags

**Solution:**
```bash
# Find files with HTML tags
python3 << 'EOF'
import json
import re
from pathlib import Path

html_pattern = re.compile(r'<[^>]+>')
run_dir = Path("data/processed/20251228_143022_preprocessing_ea45dd2")

for f in run_dir.glob("*.json"):
    with open(f) as fp:
        data = json.load(fp)
    for seg in data.get('segments', []):
        if html_pattern.search(seg.get('text', '')):
            print(f"HTML in {f.name}: {seg['text'][:100]}")
            break
EOF

# Then check cleaner configuration in configs/config.yaml
# Ensure: remove_html_tags: true
```

### Problem: Validation times out

**Cause:** Too many files or workers overloaded

**Solution:**
```bash
# Reduce worker count in gatekeeper.yml
# Change: --max-workers 8 → --max-workers 4

# Or process in smaller batches
# Split run directory and validate separately
```

---

## Configuration & Threshold Customization

### View Current Thresholds

```bash
cat configs/qa_validation/health_check.yaml
```

### Modify Threshold Values

```yaml
# Example: Make CIK requirement less strict
thresholds:
  identity_completeness:
    cik_present_rate:
      target: 0.95  # Changed from 1.0
      warn_threshold: 0.90  # Add warning level
```

### Add Custom Checks

1. Edit `configs/qa_validation/health_check.yaml` - add threshold definition
2. Implement check logic in `src/config/qa_validation.py` - HealthCheckValidator class
3. Rerun validation

---

## Integration with Pipeline

### Blocking PR Merges

**To require Gatekeeper before merge:**

1. Go to: Repository Settings → Branches
2. Edit "main" branch protection rule
3. Add required check: "Data Quality Gatekeeper"
4. Save

Now PRs cannot merge until gatekeeper passes.

### Automatic Triggering (Optional)

To run gatekeeper automatically after preprocessing:

1. Edit `.github/workflows/gatekeeper.yml`
2. Uncomment the `workflow_run` trigger section
3. Commit and push

Now gatekeeper runs automatically after preprocessing completes.

---

## Monitoring & Maintenance

### Check Validation Status

```bash
# Get summary of last 10 validation runs
gh run list --workflow gatekeeper.yml --limit 10
```

### Download Report for Analysis

```bash
# List artifacts from latest run
gh run view --json artifacts | jq '.artifacts[] | {name, path}'

# Download specific artifact
gh run download <RUN_ID> -n gatekeeper-report
```

### Track Trends

```bash
# Extract metrics from multiple reports
python3 << 'EOF'
import json
from pathlib import Path

reports = Path(".").glob("**/gatekeeper_report.json")
for report_path in reports:
    with open(report_path) as f:
        data = json.load(f)
    print(f"{data['timestamp']}: {data['status']} ({data['total_files']} files)")
EOF
```

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `.github/workflows/gatekeeper.yml` | Workflow definition |
| `scripts/validation/data_quality/check_preprocessing_batch.py` | Validation script (executable) |
| `src/config/qa_validation.py` | Validation logic |
| `configs/qa_validation/health_check.yaml` | Threshold definitions |
| `docs/DATA_HEALTH_CHECK_GUIDE.md` | Detailed validation documentation |

---

## Getting Help

### Common Questions

**Q: Can I skip validation?**
A: Not recommended, but you can comment out `--fail-on-warn` flag temporarily

**Q: How do I adjust thresholds?**
A: Edit `configs/qa_validation/health_check.yaml` - see Configuration section above

**Q: Can I validate a specific file?**
A: Yes, use single-file validator: `scripts/validation/data_quality/check_preprocessing_single.py`

**Q: How do I debug validation failures?**
A: See Troubleshooting section above

### Support Contacts

- **Validation Issues:** Check `docs/DATA_HEALTH_CHECK_GUIDE.md`
- **GitHub Actions Issues:** Review `.github/workflows/gatekeeper.yml`
- **Data Quality Issues:** File issue with label `validation-failure`

---

## Implementation Checklist

After deploying gatekeeper, verify:

- [ ] Workflow file exists and has no syntax errors
- [ ] Workflow triggers successfully via GitHub UI
- [ ] Validation reports generated and downloadable
- [ ] Exit codes correct (0 for PASS, 1 for FAIL)
- [ ] GitHub issue creation works on failure
- [ ] PR checks show gatekeeper status
- [ ] Team trained on using gatekeeper
- [ ] Threshold documentation updated

---

## Quick Commands Reference

```bash
# Find latest run directory
RUN_DIR=$(ls -td data/processed/2025* | head -1)
echo "Latest run: $RUN_DIR"

# Validate locally
python scripts/validation/data_quality/check_preprocessing_batch.py \
  --run-dir "$RUN_DIR" \
  --max-workers 8 \
  --output report.json

# Check result
python3 -c "import json; r=json.load(open('report.json')); print(r['status'])"

# View report summary
python3 -c "import json; r=json.load(open('report.json')); \
  print(f\"Files: {r['total_files']}\"); \
  print(f\"Status: {r['status']}\"); \
  print(f\"Blocking: {r['blocking_summary']['passed']}/{r['blocking_summary']['total_blocking']} passed\")"

# Trigger via CLI
gh workflow run gatekeeper.yml -f run_dir="$RUN_DIR"

# List validation artifacts
gh run list --workflow gatekeeper.yml --limit 5 --json number,status,name | jq
```

---

**Version:** 1.0
**Last Updated:** 2025-12-28
**Status:** Ready for Team Deployment

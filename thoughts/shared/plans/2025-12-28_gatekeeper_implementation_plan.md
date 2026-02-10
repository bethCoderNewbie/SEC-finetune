# Gatekeeper Pattern Implementation Plan

**Prepared:** 2025-12-28
**Target:** 5-day implementation sprint
**Owner:** Data/ML Ops Team

## Executive Summary

This plan provides step-by-step implementation guidance for the Gatekeeper pattern, converting research recommendations into actionable tasks. The pattern ensures no unvalidated data reaches model training via automatic GitHub Actions gates.

**Outcome:** Automated data quality gates that block PRs/pipeline if preprocessing validation fails, with artifact reports and failure notifications.

---

## Phase 1: Foundation Setup (Days 1-2)

### Task 1.1: Create Gatekeeper Workflow File

**File:** `.github/workflows/gatekeeper.yml`
**Type:** New GitHub Actions Workflow
**Complexity:** Low (template-based)

**Steps:**
1. Create file: `touch .github/workflows/gatekeeper.yml`
2. Copy template from research Part 9 (Template 1: Minimal Gatekeeper)
3. Customize inputs:
   - Run directory parameter name
   - Python version (3.11)
   - Max workers (8)
4. Test locally via GitHub Actions UI with sample run directory

**Acceptance Criteria:**
- File exists in `.github/workflows/`
- Validates with GitHub Actions schema checker
- Can be triggered manually with `run_dir` parameter
- No syntax errors in YAML

**Estimated Time:** 30 minutes

---

### Task 1.2: Test Validation Script Locally

**Goal:** Verify `check_preprocessing_batch.py` works end-to-end
**Prerequisite:** Have sample preprocessing output directory

**Steps:**
1. Identify latest preprocessing run directory:
   ```bash
   ls -td data/processed/2025* | head -1
   ```
2. Run validation script:
   ```bash
   python scripts/validation/data_quality/check_preprocessing_batch.py \
     --run-dir <RUN_DIR> \
     --max-workers 4 \
     --output test_report.json
   ```
3. Verify exit code:
   ```bash
   echo $?  # Should be 0 for PASS, 1 for FAIL
   ```
4. Inspect output:
   ```bash
   python -m json.tool test_report.json | head -50
   ```
5. Check report structure:
   - `status` field (PASS/WARN/FAIL)
   - `blocking_summary` section
   - `validation_table` with check details

**Acceptance Criteria:**
- Script runs without errors
- Exit code matches validation status
- JSON report is valid and contains expected fields
- Can parse and display summary

**Estimated Time:** 20 minutes

---

### Task 1.3: Set Up GitHub Actions Secrets (if needed)

**Goal:** Configure credentials for external notifications (optional at this stage)
**Skip if:** Not implementing Slack/email notifications yet

**Steps:**
1. If using Slack: Add webhook URL to GitHub Secrets
   - Settings → Secrets and variables → Actions
   - New Secret: `SLACK_WEBHOOK`
   - Value: (from Slack workspace admin)
2. If using email: Configure external service API key
3. Document secret names in team wiki

**Acceptance Criteria:**
- Secrets configured in GitHub Actions
- Accessible to workflows
- No secrets committed to git

**Estimated Time:** 15 minutes (skip if not needed)

---

## Phase 2: Core Gatekeeper Implementation (Days 2-3)

### Task 2.1: Implement Validation Execution Step

**What:** Add validation call to gatekeeper workflow
**File:** `.github/workflows/gatekeeper.yml` (modify from Task 1.1)

**Implementation:**
```yaml
steps:
  - uses: actions/checkout@v4
  - uses: actions/setup-python@v5
    with:
      python-version: "3.11"

  - name: Install validation dependencies
    run: |
      pip install pydantic pydantic-settings pyyaml

  - name: Run gatekeeper validation
    run: |
      python scripts/validation/data_quality/check_preprocessing_batch.py \
        --run-dir "${{ github.event.inputs.run_dir }}" \
        --max-workers 8 \
        --output gatekeeper_report.json \
        --fail-on-warn
```

**Testing:**
1. Trigger workflow manually via GitHub UI
2. Provide sample run directory path in input
3. Monitor execution (should take 1-2 min)
4. Check job output for validation results

**Acceptance Criteria:**
- Workflow executes without errors
- Validation script runs successfully
- Exit code (0 or 1) reflects validation status
- Report file created: `gatekeeper_report.json`

**Estimated Time:** 30 minutes

---

### Task 2.2: Add Report Artifact Upload

**What:** Save validation report as GitHub Actions artifact
**Why:** Enables review and audit trail

**Implementation:**
```yaml
  - name: Upload validation report
    if: always()  # Upload even if validation failed
    uses: actions/upload-artifact@v4
    with:
      name: gatekeeper-report-${{ github.run_id }}
      path: gatekeeper_report.json
      retention-days: 30
```

**Testing:**
1. Run workflow (from Task 2.1)
2. After completion, check "Artifacts" section in GitHub Actions UI
3. Download report and verify JSON structure
4. Confirm retention period (30 days)

**Acceptance Criteria:**
- Report uploaded as artifact
- Accessible in GitHub Actions UI
- JSON is valid and parseable
- Retention properly configured

**Estimated Time:** 15 minutes

---

### Task 2.3: Parse Report for Status

**What:** Extract validation result for downstream decisions
**Why:** Enables conditional workflow progression

**Implementation:**
```yaml
  - name: Parse validation report
    if: always()
    run: |
      python -c "
      import json
      with open('gatekeeper_report.json') as f:
          report = json.load(f)
      status = report.get('status', 'ERROR')
      print(f'Validation Status: {status}')
      with open('validation_status.txt', 'w') as out:
          out.write(status)
      "

  - name: Load status to env
    if: always()
    run: echo "VALIDATION_STATUS=$(cat validation_status.txt)" >> $GITHUB_ENV
```

**Testing:**
1. Run workflow
2. Check job logs for "Validation Status:" output
3. Verify environment variable is set

**Acceptance Criteria:**
- Status extracted from JSON report
- Accessible in subsequent steps
- Correct value (PASS/WARN/FAIL)

**Estimated Time:** 20 minutes

---

### Task 2.4: Implement Gatekeeper Decision Logic

**What:** Report final gate status (OPEN/CONDITIONAL/CLOSED)
**Why:** Clear communication to team about pipeline progression

**Implementation:**
```yaml
  - name: Gatekeeper decision
    if: always()
    run: |
      echo "=== GATEKEEPER DECISION ===" >> $GITHUB_STEP_SUMMARY
      echo "" >> $GITHUB_STEP_SUMMARY

      case "${{ env.VALIDATION_STATUS }}" in
        PASS)
          echo "✅ GATE OPEN - Pipeline can proceed to training" >> $GITHUB_STEP_SUMMARY
          exit 0
          ;;
        WARN)
          echo "⚠️  GATE CONDITIONAL - Data passed with warnings" >> $GITHUB_STEP_SUMMARY
          exit 0  # Allow progression with caution
          ;;
        FAIL)
          echo "❌ GATE CLOSED - Data quality failed, pipeline blocked" >> $GITHUB_STEP_SUMMARY
          exit 1  # Block pipeline
          ;;
        *)
          echo "❌ GATE ERROR - Unknown validation status" >> $GITHUB_STEP_SUMMARY
          exit 1
          ;;
      esac
```

**Testing:**
1. Run workflow with sample data in all states (PASS, WARN, FAIL)
2. Verify exit codes and summary messages
3. Check that exit code 1 shows as red X in GitHub UI

**Acceptance Criteria:**
- Decision message appears in job summary
- Exit codes correct (0 for PASS/WARN, 1 for FAIL)
- Clear communication to team

**Estimated Time:** 15 minutes

---

## Phase 3: Blocking Integration (Days 3-4)

### Task 3.1: Connect Gatekeeper to PR Checks

**What:** Make gatekeeper failure visible in PR UI
**Goal:** Block PR merges if validation fails

**Steps:**
1. Enable required check in GitHub branch protection:
   - Repo Settings → Branches
   - Find main branch rule (or create new)
   - Add required status check: "Gatekeeper"
2. Test:
   - Create test PR
   - Trigger gatekeeper workflow
   - PR should show check status (passing/failing)
   - Cannot merge if failing

**Alternative:** Use workflow_run trigger

**Implementation (automatic trigger):**
```yaml
on:
  workflow_run:
    workflows: ["CI"]  # Name of preprocessing CI workflow
    types: [completed]
    branches: [main]
```

This runs gatekeeper automatically after preprocessing completes.

**Acceptance Criteria:**
- Gatekeeper check visible on PR commits
- PR merge blocked if check fails
- Can view check details in PR UI
- Team receives clear feedback

**Estimated Time:** 20 minutes

---

### Task 3.2: Add Failure Notifications

**What:** Create GitHub issue when validation fails
**Why:** Automatic alerting without relying on team to check CI

**Implementation:**
```yaml
  - name: Create issue on validation failure
    if: failure() || env.VALIDATION_STATUS == 'FAIL'
    uses: actions/github-script@v7
    with:
      script: |
        const fs = require('fs');
        const report = JSON.parse(fs.readFileSync('gatekeeper_report.json'));

        github.rest.issues.create({
          owner: context.repo.owner,
          repo: context.repo.repo,
          title: `🚨 Data Quality Gate Failed: ${report.status}`,
          body: `
## Gatekeeper Validation Failed

**Status:** ${report.status}
**Run Directory:** ${report.run_directory}
**Files Checked:** ${report.total_files}
**Timestamp:** ${report.timestamp}

### Blocking Summary
- Total: ${report.blocking_summary.total_blocking}
- Passed: ${report.blocking_summary.passed}
- Failed: ${report.blocking_summary.failed}
- Warned: ${report.blocking_summary.warned}

### Failed Checks
${report.validation_table
  .filter(t => t.status !== 'PASS')
  .map(t => `- **${t.display_name}** (${t.category}): ${t.actual} vs ${t.target}`)
  .join('\n')}

**Action:** Investigate failures above. Rerun preprocessing or adjust thresholds.
          `,
          labels: ['data-quality', 'validation-failure'],
          assignees: ['@data-team']  // Adjust to your team
        });
```

**Testing:**
1. Trigger workflow with intentionally bad data
2. Verify issue is created
3. Check issue content and labels
4. Confirm team is notified

**Acceptance Criteria:**
- Issue created on validation failure
- Contains useful debugging info
- Proper labels and assignees
- Closes automatically when fixed (optional)

**Estimated Time:** 30 minutes

---

### Task 3.3: Document Gatekeeper in README

**What:** Team documentation for using/understanding gatekeeper
**Where:** `docs/GATEKEEPER_USAGE.md` (new file)

**Contents:**
1. What is the Gatekeeper?
2. How to trigger it (manual vs automatic)
3. Interpreting results (PASS/WARN/FAIL)
4. Common failure causes and fixes
5. Troubleshooting guide

**Estimated Time:** 30 minutes

---

## Phase 4: Enhancement & Monitoring (Days 4-5)

### Task 4.1: Add Metrics Reporting

**What:** Track validation trends over time
**Why:** Detect data quality degradation

**Implementation:**
```yaml
  - name: Log metrics
    if: always()
    run: |
      python -c "
      import json, os
      from datetime import datetime

      with open('gatekeeper_report.json') as f:
          report = json.load(f)

      metrics = {
          'timestamp': datetime.now().isoformat(),
          'run_dir': report['run_directory'],
          'status': report['status'],
          'total_files': report['total_files'],
          'blocking_passed': report['blocking_summary']['passed'],
          'blocking_failed': report['blocking_summary']['failed'],
          'error_count': report['overall_summary']['errors']
      }

      # Append to metrics CSV
      import csv
      with open('gatekeeper_metrics.csv', 'a', newline='') as f:
          writer = csv.DictWriter(f, fieldnames=metrics.keys())
          writer.writerow(metrics)
      "

  - name: Commit metrics
    if: always()
    run: |
      git add gatekeeper_metrics.csv
      git diff --cached --quiet || git commit -m "ci: log gatekeeper metrics"
      git push origin HEAD || true
```

**Alternative (simpler):** Store in separate branch or external database

**Acceptance Criteria:**
- Metrics captured in structured format
- Accessible for analysis
- No performance impact

**Estimated Time:** 30 minutes

---

### Task 4.2: Parallel Processing Tuning

**What:** Optimize validation speed
**Goal:** Validation completes in < 2 minutes for 300 files

**Testing:**
1. Run validation on largest available dataset
2. Measure execution time:
   ```bash
   time python scripts/validation/data_quality/check_preprocessing_batch.py \
     --run-dir <RUN_DIR> \
     --max-workers 8
   ```
3. Try different worker counts (4, 8, 12)
4. Record timings and throughput
5. Update workflow with optimal value

**Acceptance Criteria:**
- Validation completes in acceptable time
- CPU/memory usage reasonable
- No file corruption or data loss

**Estimated Time:** 20 minutes

---

### Task 4.3: Test Failure Scenarios

**What:** Verify gatekeeper behaves correctly in failure modes
**Checklist:**
- [ ] Validation correctly identifies HTML artifacts
- [ ] Missing identity fields are caught
- [ ] Duplicate detection works
- [ ] Exit code 1 blocks PR merge
- [ ] Report is generated even on failure
- [ ] Issue creation works
- [ ] Partial file failures don't crash validation

**Testing Procedure:**
1. Create intentionally bad test files:
   - File with HTML tags
   - File missing CIK field
   - File with empty segments
2. Run validation
3. Verify each failure is caught
4. Check exit code and report
5. Document findings

**Acceptance Criteria:**
- All failure modes handled gracefully
- No silent failures
- Clear error messages

**Estimated Time:** 45 minutes

---

### Task 4.4: Create Troubleshooting Runbook

**What:** Documentation for common failures
**File:** `docs/GATEKEEPER_TROUBLESHOOTING.md`

**Contents:**
1. "Validation always fails" → Check thresholds
2. "Files not being validated" → Check naming pattern
3. "Timeout errors" → Increase worker count or reduce files
4. "Can't find run directory" → Path format guidance
5. "Issue creation failing" → GitHub token/permissions

**Acceptance Criteria:**
- Common issues documented
- Solutions are actionable
- Team can self-serve

**Estimated Time:** 30 minutes

---

## Success Metrics

### Immediate (after implementation)
- [ ] Gatekeeper workflow runs without errors
- [ ] Validation reports generated for all runs
- [ ] PR merge blocked on validation failure
- [ ] Failure issues created automatically
- [ ] Team receives feedback within 5 minutes of validation failure

### Short-term (2-4 weeks)
- [ ] 100% of preprocessing runs validated
- [ ] Average validation time < 2 minutes
- [ ] Zero unvalidated data reaching model training
- [ ] Team confidence in data quality gates

### Long-term (monthly reviews)
- [ ] Validation pass rate stable (> 85%)
- [ ] Threshold adjustments based on trends
- [ ] Automated recovery workflows (if applicable)
- [ ] Data quality metrics dashboard available

---

## Risk Mitigation

### Risk: Gatekeeper Becomes Too Strict

**Mitigation:**
- Monitor threshold breach frequency
- Discuss with team before tightening thresholds
- Document threshold rationale

### Risk: False Positives Block Valid Data

**Mitigation:**
- Extensive testing before enabling blocking
- Use WARN threshold initially
- Gradual tightening (WARN → FAIL after validation)

### Risk: Validation Script Failures

**Mitigation:**
- Use `continue-on-error: true` to capture errors
- Distinguish between validation failure (bad data) vs infrastructure failure
- Alert on script failures separately

### Risk: Performance Degradation

**Mitigation:**
- Monitor validation execution time
- Set timeout limits
- Test with largest dataset upfront

---

## Rollback Plan

If gatekeeper causes issues:

1. **Immediate:** Disable blocking check in branch protection
   - Settings → Branches → Remove required check
2. **Short-term:** Revert workflow to non-blocking mode
   - Change `--fail-on-warn` to optional
   - Exit with 0 even on FAIL
3. **Analysis:** Debug issues and replan
4. **Gradual re-enable:**
   - Enable for new branches first
   - Monitor success rate
   - Re-enable for main after validation

---

## Sign-Off & Handoff

**Implementation Owner:** [Data/ML Ops Lead]
**QA/Testing Owner:** [QA Engineer]
**Documentation Owner:** [Technical Writer]
**Monitoring Owner:** [DevOps/Platform Engineer]

**Expected Completion Date:** [Today + 5 days]
**Maintenance Mode:** [Date + 2 weeks]

---

## Appendix: Implementation Checklist

### Day 1
- [ ] Create `.github/workflows/gatekeeper.yml`
- [ ] Test validation script locally
- [ ] Configure GitHub Actions secrets (if needed)

### Day 2
- [ ] Implement validation execution step
- [ ] Add report artifact upload
- [ ] Parse report for status

### Day 3
- [ ] Implement decision logic
- [ ] Connect to PR checks
- [ ] Add failure issue creation
- [ ] Document in README

### Day 4
- [ ] Add metrics reporting
- [ ] Tune parallel processing
- [ ] Test failure scenarios

### Day 5
- [ ] Create troubleshooting runbook
- [ ] Final testing and validation
- [ ] Team training/documentation
- [ ] Production deployment

---

**Document Version:** 1.0
**Last Updated:** 2025-12-28
**Next Review:** 2026-01-15

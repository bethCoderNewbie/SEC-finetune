# Gatekeeper Pattern for SEC Filings Preprocessing Pipeline

**Date:** 2025-12-28
**Author:** Research Analysis
**Status:** Complete
**Scope:** Architectural recommendations for automated data validation gates in GitHub Actions

## Executive Summary

This research document provides a comprehensive architectural blueprint for implementing the "Gatekeeper" pattern to your SEC filings preprocessing pipeline. The Gatekeeper pattern enforces automatic validation gates that halt pipeline progression if data quality thresholds are not met, ensuring only production-ready data flows downstream to model training.

**Key Findings:**
1. Your validation infrastructure is production-ready (HealthCheckValidator, ThresholdRegistry, batch validation scripts)
2. GitHub Actions integration requires a new "gatekeeper" workflow that runs **after** preprocessing completes
3. Exit codes (0/1) from validation scripts already support CI/CD automation
4. Validation reports can be stored as job artifacts for PR review
5. Alert mechanisms support both synchronous (CI/CD failure) and asynchronous (issue creation, notifications) patterns

---

## Part 1: Current Architecture Assessment

### 1.1 Validation Infrastructure (READY)

**HealthCheckValidator class** (`src/config/qa_validation.py:593-829`)
- 4-check framework already implemented:
  1. **Completeness** - CIK, company_name, SIC code rates
  2. **Cleanliness** - HTML artifact rate, page number artifact rate
  3. **Substance** - Empty segment rate, short segment rate
  4. **Consistency** - Duplicate rate, risk keyword presence
- Returns structured report with `status` (PASS/WARN/FAIL) and blocking summary
- Output: JSON with `validation_table` containing per-check ValidationResult objects

**ThresholdRegistry** (`src/config/qa_validation.py:372-473`)
- Centralized threshold management loaded from `configs/qa_validation/*.yaml`
- Supports query methods: `get()`, `by_category()`, `by_tag()`, `blocking_thresholds()`
- Metadata-rich: supports `blocking` flag, `warn_threshold`, operator types (GTE, LTE, EQ, etc.)
- Pydantic V2 models for type safety

**ValidationResult class** (`src/config/qa_validation.py:232-365`)
- Encapsulates single threshold validation outcome
- Properties: `status` (PASS/WARN/FAIL/SKIP), `go_no_go` (GO/NO-GO/CONDITIONAL)
- Helper functions for report aggregation:
  - `determine_overall_status()` - resolves overall PASS/WARN/FAIL from results
  - `generate_blocking_summary()` - counts passed/failed/warned
  - `generate_validation_table()` - serializable validation output

### 1.2 Batch Validation Script (READY)

**check_preprocessing_batch.py** (`scripts/validation/data_quality/check_preprocessing_batch.py`)

Exit Code Logic (lines 581-585):
```python
if report['status'] == 'FAIL':
    sys.exit(1)  # Blocks pipeline
if report['status'] == 'WARN' and args.fail_on_warn:
    sys.exit(1)  # Optional strict mode
sys.exit(0)      # Allows pipeline
```

Output Structure (lines 279-300):
```python
{
    "status": "PASS" | "WARN" | "FAIL",
    "timestamp": ISO_8601,
    "run_directory": str,
    "total_files": int,
    "overall_summary": {"passed": int, "warned": int, "failed": int, "errors": int},
    "blocking_summary": {"total_blocking": int, "passed": int, "failed": int, "warned": int, "all_pass": bool},
    "per_file_results": [...]
}
```

Key Capabilities:
- Parallel processing with `--max-workers` flag (ProcessPoolExecutor)
- Checkpointing for resume (`--resume` flag)
- Structured JSON report output (`--output` flag)
- `--fail-on-warn` for strict CI/CD gates

### 1.3 Run Context & Metadata (READY)

**RunContext class** (`src/config/run_context.py:28-188`)
- Automatically manages run directories with structured naming:
  - Pattern: `{run_id}_{name}_{git_sha}`
  - Example: `20251228_143022_preprocessing_ea45dd2`
- Methods: `create()`, `save_config()`, `save_metrics()`, `load_metrics()`, `get_artifact_path()`
- Git SHA tracking enables data-code linkage crucial for Gatekeeper decisions

### 1.4 Preprocessing Pipeline Integration Points

**run_preprocessing_pipeline.py** (lines 870-932)
```python
# Creates RunContext with git_sha
run = RunContext(
    name=args.run_name,
    auto_git_sha=True,
    base_dir=PROCESSED_DATA_DIR
)
run.create()

# Outputs to: data/processed/{run_id}_{name}_{git_sha}/
# Saves metrics: run.save_metrics(summary_data)
```

**Output Directory Convention:**
- Processed files: `data/processed/{timestamp}_{name}_{sha}/*.json`
- Interim files: `data/interim/extracted/{timestamp}_{name}_{sha}/*.json`
- Metrics file: `data/processed/{timestamp}_{name}_{sha}/metrics.json`

---

## Part 2: Gatekeeper Workflow Design

### 2.1 Gatekeeper Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    GitHub Actions CI                        │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Job 1: Run Preprocessing (existing)                  │  │
│  │ - Processes HTML files                               │  │
│  │ - Outputs: data/processed/{run_id}_{name}_{sha}/     │  │
│  │ - Exports: RUN_DIR, RUN_ID as artifacts              │  │
│  └──────────────────────────────────────────────────────┘  │
│                           ↓                                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Job 2: Gatekeeper Validation (NEW)                   │  │
│  │ - Receives RUN_DIR from artifact                     │  │
│  │ - Runs: check_preprocessing_batch.py                 │  │
│  │ - Output: JSON validation report (artifact)          │  │
│  │ - Exit: 0=PASS, 1=FAIL → blocks downstream          │  │
│  │ - Alert: Creates issues on failure                   │  │
│  └──────────────────────────────────────────────────────┘  │
│                           ↓                                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Job 3: Train Model (conditional on Gatekeeper)       │  │
│  │ - Depends: needs: gatekeeper                         │  │
│  │ - Only runs if validation passes                     │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Gatekeeper Decision Points

**Primary Gate: Overall Status**
- Status from `report['status']` (PASS/WARN/FAIL)
- Exit code: `report['status'] == 'FAIL' → exit(1)` (blocks pipeline)
- Recommendation: Use `--fail-on-warn` in CI/CD for strict gates

**Secondary Gates: Blocking Checks**
- Individual threshold checks with `blocking: true` flag
- Aggregated in `blocking_summary['all_pass']`
- If `all_pass: false` → exit(1)

**Tertiary Gates: Per-File Failures**
- Track error count: `overall_summary['errors']`
- Some files may fail while batch succeeds (file-level exceptions)
- Consider: `if errors > 0 and errors > tolerance → warn`

### 2.3 Proposed Workflow: `gatekeeper.yml`

**Location:** `.github/workflows/gatekeeper.yml` (new file)

**Trigger Strategy:**
```yaml
# Option A: Explicit on-demand (recommended for control)
on:
  workflow_dispatch:
    inputs:
      run_dir:
        description: 'Run directory (e.g., data/processed/20251228_143022_preprocessing_ea45dd2)'
        required: true

# Option B: After preprocessing completes (automated, requires artifact passing)
on:
  workflow_run:
    workflows: ["preprocessing"]
    types: [completed]
    branches: [main]
```

**Job Dependencies:**
```yaml
jobs:
  gatekeeper:
    runs-on: ubuntu-latest
    steps:
      # 1. Download run directory from artifact (if workflow_run trigger)
      - name: Download preprocessing artifact
        uses: actions/download-artifact@v4
        with:
          name: preprocessing-run-dir
          path: ./run-dir-info

      # 2. Parse RUN_DIR from artifact or input
      - name: Load run directory
        run: |
          if [ -f ./run-dir-info/run_dir.txt ]; then
            RUN_DIR=$(cat ./run-dir-info/run_dir.txt)
          else
            RUN_DIR="${{ github.event.inputs.run_dir }}"
          fi
          echo "RUN_DIR=$RUN_DIR" >> $GITHUB_ENV

      # 3. Checkout and setup environment
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      # 4. Install dependencies
      - name: Install validation dependencies
        run: |
          pip install pydantic pydantic-settings pyyaml

      # 5. Run Gatekeeper validation
      - name: Run data quality validation
        run: |
          python scripts/validation/data_quality/check_preprocessing_batch.py \
            --run-dir "${{ env.RUN_DIR }}" \
            --max-workers 8 \
            --output gatekeeper_report.json \
            --fail-on-warn
        continue-on-error: true  # Capture report even if validation fails

      # 6. Capture validation result
      - name: Parse validation report
        if: always()
        run: |
          python -c "
          import json
          with open('gatekeeper_report.json') as f:
              report = json.load(f)
          status = report.get('status', 'ERROR')
          blocking_all_pass = report.get('blocking_summary', {}).get('all_pass', False)
          echo \"VALIDATION_STATUS=$status\" >> $GITHUB_ENV
          echo \"BLOCKING_ALL_PASS=$blocking_all_pass\" >> $GITHUB_ENV
          "

      # 7. Archive report as artifact
      - name: Upload validation report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: gatekeeper-report-${{ github.run_id }}
          path: gatekeeper_report.json
          retention-days: 30

      # 8. Create GitHub issue on failure
      - name: Create issue on validation failure
        if: failure() || env.VALIDATION_STATUS == 'FAIL'
        uses: actions/github-script@v7
        with:
          script: |
            const report = require('fs').readFileSync('gatekeeper_report.json', 'utf8');
            const data = JSON.parse(report);
            github.rest.issues.create({
              owner: context.repo.owner,
              repo: context.repo.repo,
              title: `Data Quality Gate Failed: ${data.status}`,
              body: `## Gatekeeper Validation Report\n\n` +
                    `**Status:** ${data.status}\n` +
                    `**Run Directory:** ${data.run_directory}\n` +
                    `**Files Checked:** ${data.total_files}\n\n` +
                    `### Blocking Summary\n` +
                    `- Passed: ${data.blocking_summary.passed}/${data.blocking_summary.total_blocking}\n` +
                    `- Failed: ${data.blocking_summary.failed}\n` +
                    `- Warned: ${data.blocking_summary.warned}\n\n` +
                    `**Artifact:** [Download Report](https://github.com/${context.repo.owner}/${context.repo.repo}/actions/runs/${context.runId})\n`,
              labels: ['data-quality', 'validation-failure']
            });

      # 9. Report final status
      - name: Gatekeeper decision
        if: always()
        run: |
          if [ "${{ env.VALIDATION_STATUS }}" = "FAIL" ]; then
            echo "❌ GATE CLOSED: Data validation failed"
            exit 1
          elif [ "${{ env.VALIDATION_STATUS }}" = "WARN" ]; then
            echo "⚠️  GATE CONDITIONAL: Data validation passed with warnings"
            exit 0
          else
            echo "✅ GATE OPEN: Data validation passed"
            exit 0
          fi
```

---

## Part 3: Integration Strategies

### 3.1 Option A: Separate Gatekeeper Workflow (RECOMMENDED)

**File:** `.github/workflows/gatekeeper.yml`
**Trigger:** Workflow dispatch (manual) or workflow_run (automatic after preprocessing)

**Advantages:**
- Decoupled from preprocessing (preprocessing can fail without gatekeeper running)
- Explicit control over when gatekeeper runs
- Can be run on-demand for validation-only purposes
- Simpler to debug and modify independently
- Supports resuming validation if preprocessing is interrupted

**Disadvantages:**
- Requires artifact passing between workflows (more complex)
- Adds separate job to view/manage

**Recommended Configuration:**
```yaml
# Trigger on manual dispatch
on:
  workflow_dispatch:
    inputs:
      run_dir:
        description: 'Run directory path'
        required: true

# Also support automatic trigger after preprocessing completes
on:
  workflow_run:
    workflows: ["preprocessing"]
    types: [completed]
```

### 3.2 Option B: Integrated into CI Workflow

**File:** Modify existing `.github/workflows/ci.yml`

**Advantages:**
- Single workflow file to manage
- Tighter coupling ensures gatekeeper always runs after preprocessing
- No artifact passing complexity

**Disadvantages:**
- CI workflow becomes longer/more complex
- Cannot run gatekeeper independently
- If preprocessing fails, gatekeeper doesn't run (may want to validate partial results)

**Integration Snippet:**
```yaml
  preprocessing:
    runs-on: ubuntu-latest
    outputs:
      run-dir: ${{ steps.preprocess.outputs.run_dir }}
    steps:
      # ... existing preprocessing steps ...
      - name: Save run directory
        id: preprocess
        run: |
          RUN_DIR=$(ls -td data/processed/2025* | head -1)
          echo "run_dir=$RUN_DIR" >> $GITHUB_OUTPUT

  gatekeeper:
    needs: preprocessing
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Run gatekeeper validation
        run: |
          python scripts/validation/data_quality/check_preprocessing_batch.py \
            --run-dir "${{ needs.preprocessing.outputs.run-dir }}" \
            --max-workers 8 \
            --fail-on-warn
```

### 3.3 Recommended: Hybrid Approach

**Primary Workflow (preprocessing):** Existing `ci.yml` - runs preprocessing, exports RUN_DIR as output

**Secondary Workflow (gatekeeper):** New `gatekeeper.yml` - runs validation, has dependency on preprocessing success

**Rationale:**
- Clean separation of concerns
- Allows on-demand gatekeeper runs
- Easy to add other post-processing jobs (feature engineering, model training)
- Follows GitHub Actions best practices for multi-stage pipelines

---

## Part 4: Alert Mechanisms & Notifications

### 4.1 Synchronous Alerts (CI/CD Blocking)

**Primary:** Exit code from validation script
- `exit(0)` → validation passes, subsequent jobs run (if needed)
- `exit(1)` → validation fails, CI/CD shows red X on commit, PR shows blocking check

**Implementation in GitHub Actions:**
```yaml
- name: Run validation
  run: python scripts/validation/data_quality/check_preprocessing_batch.py ...
  # Script naturally exits with 1 on failure, stops workflow
```

**Effect on PR:**
- Appears as "Gatekeeper" check on PR commits
- Can be configured as required check (Settings → Branches → Branch Protection Rules)
- Prevents merge until validation passes

### 4.2 Asynchronous Alerts (Issue Creation)

**Recommended:** Create GitHub issue on failure

```yaml
- name: Create issue on validation failure
  if: failure()
  uses: actions/github-script@v7
  with:
    script: |
      github.rest.issues.create({
        owner: context.repo.owner,
        repo: context.repo.repo,
        title: `🚨 Data Quality Gate Failed`,
        body: `... validation details ...`,
        labels: ['data-quality', 'validation-failure']
      })
```

**Benefits:**
- Asynchronous notification (doesn't block workflow)
- Trackable as issue (can be assigned, discussed)
- Includes context (timestamps, file paths, threshold breaches)

### 4.3 External Notifications (Optional)

#### Option 1: Slack Integration

```yaml
- name: Notify Slack on failure
  if: failure()
  uses: slackapi/slack-github-action@v1
  with:
    webhook-url: ${{ secrets.SLACK_WEBHOOK }}
    payload: |
      {
        "text": "Data Quality Validation Failed",
        "blocks": [
          {
            "type": "section",
            "text": {
              "type": "mrkdwn",
              "text": "Run: ${{ github.run_id }}\nStatus: ${{ job.status }}"
            }
          }
        ]
      }
```

#### Option 2: Email via GitHub Actions

GitHub doesn't support native email, but can integrate via:
- Workflow dispatch to trigger notification workflow
- External service (SendGrid, Mailgun) via API
- Team notifications via GitHub team mentions in issues

### 4.4 Recommended Alert Strategy

**Tier 1 - Blocking (Synchronous):**
- Exit code (0/1) from validation script
- Prevents merge in GitHub UI
- No delays, immediate feedback

**Tier 2 - Issue Creation (Asynchronous):**
- Create GitHub issue with detailed report
- Assigned to data team
- Labels for routing and tracking
- Can be searched/reported on later

**Tier 3 - Optional External (Async):**
- Slack message to #data-quality channel (optional)
- For time-sensitive issues in production environments

---

## Part 5: Validation Report Artifacts

### 5.1 Report Structure & Accessibility

**Stored Artifacts:**
```
GitHub Actions Run
├── Artifacts
│   ├── gatekeeper-report-{run_id}.json
│   ├── preprocessing-output-{run_id}/
│   │   ├── metrics.json
│   │   └── sample_files.json
│   └── logs
```

**Retention Policy:**
- Artifact retention: 30 days (configurable)
- JSON reports: archive to external storage if needed (e.g., S3 for long-term analysis)

### 5.2 PR Review Integration

**Approach 1: Report Comment**

```yaml
- name: Comment with validation results
  if: always()
  uses: actions/github-script@v7
  with:
    script: |
      const report = require('fs').readFileSync('gatekeeper_report.json', 'utf8');
      const data = JSON.parse(report);
      const comment = `## ✓ Gatekeeper Validation Report\n\n` +
        `**Status:** ${data.status}\n` +
        `**Files Checked:** ${data.total_files}\n` +
        `**Blocking Checks:** ${data.blocking_summary.passed}/${data.blocking_summary.total_blocking} passed\n`;
      github.rest.issues.createComment({
        issue_number: context.issue.number,
        owner: context.repo.owner,
        repo: context.repo.repo,
        body: comment
      });
```

**Approach 2: Check Run with Summary**

```yaml
- name: Report validation via check run
  if: always()
  uses: actions/github-script@v7
  with:
    script: |
      const report = require('fs').readFileSync('gatekeeper_report.json', 'utf8');
      const data = JSON.parse(report);
      github.rest.checks.create({
        owner: context.repo.owner,
        repo: context.repo.repo,
        name: 'Gatekeeper Validation',
        head_sha: context.sha,
        status: 'completed',
        conclusion: data.status === 'PASS' ? 'success' : 'failure',
        output: {
          title: 'Data Quality Validation',
          summary: `Files: ${data.total_files} | Passed: ${data.blocking_summary.passed} | Failed: ${data.blocking_summary.failed}`,
          text: JSON.stringify(data.validation_table, null, 2)
        }
      });
```

### 5.3 Report Metrics & Tracking

**Store for Dashboard:**
```python
# In workflow, parse report and write to database/CSV
with open('gatekeeper_report.json') as f:
    report = json.load(f)
    metrics = {
        'timestamp': report['timestamp'],
        'run_id': report['run_directory'].split('/')[-1],
        'total_files': report['total_files'],
        'status': report['status'],
        'blocking_passed': report['blocking_summary']['passed'],
        'blocking_failed': report['blocking_summary']['failed'],
        'error_count': report['overall_summary']['errors']
    }
```

**Recommended Storage:**
- Option 1: CSV file in repo (simple, version-controlled)
- Option 2: GitHub Actions workflow artifacts (queryable via API)
- Option 3: External database (PostgreSQL, ClickHouse for analytics)

---

## Part 6: Best Practices for Data Pipeline Validation in GitHub Actions

### 6.1 Idempotency & Reproducibility

**Principle:** Validation should give same results for same inputs

**Implementation:**
```yaml
# Use git SHA for reproducible runs
- name: Capture git SHA
  run: |
    echo "GIT_SHA=$(git rev-parse --short HEAD)" >> $GITHUB_ENV

# Include in artifact names
- name: Upload report
  uses: actions/upload-artifact@v4
  with:
    name: gatekeeper-report-${{ env.GIT_SHA }}-${{ github.run_id }}
```

### 6.2 Error Handling & Graceful Degradation

**Principle:** Validation should not fail silently or hide errors

**Pattern:**
```yaml
- name: Validate
  id: validate
  run: python scripts/validation/... || echo "VALIDATION_FAILED=true" >> $GITHUB_OUTPUT

- name: Check results
  if: always()
  run: |
    if [ "${{ steps.validate.outputs.VALIDATION_FAILED }}" = "true" ]; then
      echo "Validation failed but continuing to preserve logs"
    fi

- name: Create summary
  if: always()
  run: |
    # Always capture and report, even on partial failure
```

### 6.3 Performance Optimization

**Parallel Validation:**
```yaml
- name: Run parallel validation
  run: |
    python scripts/validation/data_quality/check_preprocessing_batch.py \
      --max-workers 8 \  # Use available CPU cores
      --checkpoint-interval 50  # Resume-friendly
      --quiet  # Suppress verbose output
```

**Caching:**
```yaml
- name: Cache Python packages
  uses: actions/cache@v4
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}
```

### 6.4 Data Persistence & Artifact Management

**Strategy for Intermediate Files:**
```yaml
# Only save essential artifacts
- name: Save validation reports
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: validation-report
    path: gatekeeper_report.json
    retention-days: 30  # Don't hoard old reports

# Delete intermediate validation cache
- name: Cleanup
  if: always()
  run: |
    rm -f data/processed/*/_validation_checkpoint.json
```

### 6.5 Threshold Management & Configuration

**Pattern: Store thresholds in repository**
```yaml
# Thresholds in configs/qa_validation/health_check.yaml
# Git history tracks threshold changes
# Can audit "when did we relax the CIK requirement?"

# To override thresholds in CI:
- name: Strict validation (PR context)
  run: |
    # Override thresholds before running validation
    export OVERRIDE_CIK_THRESHOLD=1.0  # Stricter in PRs
    python scripts/validation/...
```

### 6.6 Documentation & Observability

**Log Key Decisions:**
```yaml
- name: Gatekeeper decision
  run: |
    echo "=== Gatekeeper Status ===" >> $GITHUB_STEP_SUMMARY
    echo "Run Directory: $RUN_DIR" >> $GITHUB_STEP_SUMMARY
    echo "Validation Status: $VALIDATION_STATUS" >> $GITHUB_STEP_SUMMARY
    echo "Blocking Checks: $BLOCKING_SUMMARY" >> $GITHUB_STEP_SUMMARY
```

### 6.7 Conditional Workflows

**Pattern: Only proceed if validation passes**

```yaml
jobs:
  validation:
    runs-on: ubuntu-latest
    outputs:
      status: ${{ steps.validate.outputs.status }}

  training:
    needs: validation
    if: needs.validation.outputs.status == 'PASS'
    runs-on: ubuntu-latest
    steps:
      - name: Train model
        run: python scripts/training/train_model.py
```

---

## Part 7: Implementation Roadmap

### Phase 1: Setup (Day 1)

1. **Create `.github/workflows/gatekeeper.yml`** with basic validation
2. **Test locally:** Run `check_preprocessing_batch.py` with sample data
3. **Configure artifact upload:** Ensure reports are captured
4. **Set up GitHub Actions secrets:** (if using external notifications)

### Phase 2: Blocking Integration (Day 2-3)

1. **Enable PR checks:** Configure GitHub branch protection
   - Require "Gatekeeper" check to pass before merge
2. **Test failure scenarios:** Run with intentionally bad data
3. **Verify exit codes:** Confirm 0/1 behavior propagates correctly
4. **Document:** Add workflow details to team wiki/README

### Phase 3: Alerting (Day 3-4)

1. **Implement issue creation** on validation failure
2. **Add Slack notifications** (optional)
3. **Set up dashboard** to track validation trends
4. **Create runbooks:** Document failure diagnosis

### Phase 4: Optimization (Day 5+)

1. **Parallel processing tuning:** Find optimal worker count
2. **Cache management:** Reduce artifact storage
3. **Alert fatigue reduction:** Tune alert thresholds
4. **Monitor & iterate:** Improve based on real-world runs

---

## Part 8: Failure Scenarios & Remediation

### Scenario 1: Validation Fails → Pipeline Halted

**Status:** Gatekeeper rejects data
**Decision:** Cannot proceed to training

**Automated Response:**
1. CI/CD exits with code 1 (red X on commit)
2. PR merge blocked (if configured)
3. GitHub issue created (automatic)

**Manual Response:**
1. Data team investigates issue
2. Identifies root cause (e.g., HTML artifact rate > threshold)
3. Re-runs preprocessing with corrected settings
4. Re-triggers validation workflow
5. Merges when validation passes

### Scenario 2: Validation Passes with Warnings

**Status:** Gatekeeper issues warning
**Decision:** Proceed but with caution

**Configuration:**
```yaml
# Don't use --fail-on-warn to allow conditional flow
- name: Validate (warning-tolerant)
  run: |
    python scripts/validation/data_quality/check_preprocessing_batch.py ... || true
```

**Effect:**
- Training proceeds (warnings don't block)
- Issue created to track warnings
- Data team monitors quality degradation

### Scenario 3: Validation Script Crashes

**Status:** Validation itself errors (different from data failure)

**Recovery:**
```yaml
- name: Validate
  id: validate
  continue-on-error: true  # Capture error without blocking
  run: python scripts/validation/...

- name: Check validation success
  run: |
    if [ ${{ steps.validate.outcome }} != "success" ]; then
      echo "Validation infrastructure error!"
      exit 1
    fi
```

---

## Part 9: Specific Workflow YAML Templates

### Template 1: Minimal Gatekeeper (Recommended for Start)

```yaml
name: Data Quality Gatekeeper

on:
  workflow_dispatch:
    inputs:
      run_dir:
        description: 'Run directory (data/processed/...)'
        required: true

jobs:
  gatekeeper:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          pip install pydantic pydantic-settings pyyaml

      - name: Run validation
        run: |
          python scripts/validation/data_quality/check_preprocessing_batch.py \
            --run-dir "${{ inputs.run_dir }}" \
            --max-workers 8 \
            --output gatekeeper_report.json \
            --fail-on-warn

      - name: Upload report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: gatekeeper-report
          path: gatekeeper_report.json
```

### Template 2: Full Gatekeeper with Alerting

See Part 2.3 above - includes issue creation, check runs, artifact uploads

### Template 3: Integrated into Preprocessing CI

```yaml
# .github/workflows/ci.yml (modified)

jobs:
  preprocessing:
    runs-on: ubuntu-latest
    outputs:
      run-dir: ${{ steps.run.outputs.dir }}
    steps:
      - uses: actions/checkout@v4
      - name: Run preprocessing
        id: run
        run: |
          python scripts/data_preprocessing/run_preprocessing_pipeline.py --batch
          RUN_DIR=$(ls -td data/processed/2025* | head -1)
          echo "dir=$RUN_DIR" >> $GITHUB_OUTPUT

  gatekeeper:
    needs: preprocessing
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install pydantic pydantic-settings pyyaml
      - run: |
          python scripts/validation/data_quality/check_preprocessing_batch.py \
            --run-dir "${{ needs.preprocessing.outputs.run-dir }}" \
            --max-workers 8 \
            --output report.json \
            --fail-on-warn
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: validation-report
          path: report.json
```

---

## Part 10: Monitoring & Metrics

### 10.1 Key Metrics to Track

| Metric | Purpose | Threshold Alert |
|--------|---------|-----------------|
| Validation Pass Rate | Data quality trend | < 90% → investigate |
| Avg Validation Time | Performance SLO | > 5 min → optimize |
| File Error Rate | Infrastructure health | > 1% → alert |
| Threshold Breach Freq | Need for adjustment | > 2x/week → review |
| Mean-time-to-recovery | Pipeline resilience | > 1 hour → incident |

### 10.2 Dashboard Recommendations

**GitHub-native:**
- Issue board tracking validation failures
- Pull request history showing gatekeeper status
- Actions workflow analytics

**External (optional):**
- Grafana dashboard pulling data from CSV artifacts
- Custom database tracking validation metrics over time
- Slack dashboard with validation trends

---

## Conclusions & Recommendations

### Summary of Key Findings

1. **Your infrastructure is production-ready:** HealthCheckValidator, ThresholdRegistry, and batch validation scripts are well-designed and can immediately support Gatekeeper implementation.

2. **Recommended workflow:** Separate `gatekeeper.yml` workflow (triggered manually or after preprocessing) provides best balance of flexibility and clarity.

3. **Exit code integration:** Your validation scripts already support 0/1 exit codes that map directly to GitHub Actions success/failure.

4. **Artifact management:** Validation reports as GitHub Actions artifacts provide accessible audit trail and PR integration points.

5. **Alerting:** Combine synchronous (exit code) + asynchronous (issue creation) for robust notification without CI spam.

### Implementation Priority

**MVP (1 week):**
- Create `.github/workflows/gatekeeper.yml`
- Implement basic validation with exit code blocking
- Upload report as artifact
- Test on sample preprocessing run

**Phase 2 (week 2):**
- Add GitHub issue creation on failure
- Integrate with PR checks (branch protection)
- Create documentation for team

**Phase 3 (week 3+):**
- Add optional Slack notifications
- Implement metrics dashboard
- Optimize parallel processing
- Tune threshold warnings

### Success Criteria

- [ ] Gatekeeper validates all preprocessing runs
- [ ] Validation blocks PRs if data quality fails (< 5 min decision time)
- [ ] Reports accessible to team via GitHub UI
- [ ] Failure issues created automatically
- [ ] 0 manual validation checks required before training
- [ ] < 2% validation infrastructure failures/month

---

## Appendix A: File References

**Validation Implementation:**
- `src/config/qa_validation.py` - HealthCheckValidator (lines 593-829), ThresholdRegistry (lines 372-473)
- `scripts/validation/data_quality/check_preprocessing_batch.py` - Batch validation with exit codes
- `configs/qa_validation/health_check.yaml` - Threshold definitions

**Integration Points:**
- `src/config/run_context.py` - RunContext for managing run directories
- `scripts/data_preprocessing/run_preprocessing_pipeline.py` - Preprocessing script (outputs to RUN_DIR)
- `.github/workflows/ci.yml` - Existing CI workflow (modify to add gatekeeper)

**Utilities:**
- `src/utils/checkpoint.py` - Checkpoint manager for resume capability
- `src/utils/parallel.py` - ParallelProcessor for concurrent validation

**Documentation:**
- `docs/DATA_HEALTH_CHECK_GUIDE.md` - Usage guide (comprehensive reference)

---

**End of Research Document**
**Generated:** 2025-12-28
**Status:** Ready for Architecture Review

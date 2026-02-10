# Scheduled Drift Detection Implementation via GitHub Actions

**Author:** Claude Code (Haiku 4.5)
**Date:** 2025-12-28 14:30 UTC
**Status:** Research Complete
**Related Ticket/Request:** Scheduled drift detection using GitHub Actions cron workflows

---

## Executive Summary

This document provides comprehensive research on implementing production-ready scheduled drift detection for your SEC finetune ML pipeline using GitHub Actions cron workflows. The implementation addresses five key areas: GitHub Actions scheduled workflows, drift detection automation, alerting mechanisms, data/model artifact management, and production best practices.

**Key Findings:**
- GitHub Actions cron syntax supports reliable nightly scheduling with cost considerations (~$0.008/run for ubuntu-latest)
- Drift detection requires artifact persistence strategy: GitHub Actions artifacts (90-day retention), GitHub Releases, or external storage (S3)
- Alert mechanisms should include issue creation (for triage) and webhook integration (Slack/email)
- Production drift monitoring requires monitoring/observability for failure handling and retry logic

---

## 1. GitHub Actions Scheduled Workflows

### 1.1 Cron Syntax for Nightly Runs

**Current Implementation Status:** `.github/workflows/ci.yml` exists but has no scheduled workflows (only push/PR triggers).

GitHub Actions uses POSIX cron syntax with 5 fields:
```yaml
on:
  schedule:
    - cron: '0 0 * * *'  # Run at 00:00 UTC every day
```

**Cron Field Breakdown:**
```
┌───────────── minute (0 - 59)
│ ┌───────────── hour (0 - 23)
│ │ ┌───────────── day of the month (1 - 31)
│ │ │ ┌───────────── month (1 - 12)
│ │ │ │ ┌───────────── day of the week (0 - 6) (Sunday to Saturday)
│ │ │ │ │
│ │ │ │ │
* * * * *
```

**Recommended Schedules for Drift Detection:**

| Schedule | Cron | Use Case |
|----------|------|----------|
| Daily at midnight UTC | `0 0 * * *` | Standard nightly batch |
| Daily at 2 AM UTC | `0 2 * * *` | Offset if other jobs at midnight |
| Weekly Monday 2 AM | `0 2 * * 1` | Weekly comprehensive analysis |
| Multiple times daily | `0 0,6,12,18 * * *` | High-frequency drift detection |

**Important Constraints:**
- Scheduled workflows can have 5-minute delays in starting
- Minimum frequency: 5 minutes (not practical for this use case)
- Maximum precision: minutes (not seconds)
- Runs are queued during repository maintenance (GitHub may pause)
- Free tier: 3,000 workflow run minutes/month

### 1.2 Accessing Latest Processed Data in Scheduled Jobs

**Challenge:** Scheduled workflows don't have context about which models/datasets to compare. You need a strategy to identify the "latest" models.

**Option A: Model Registry Approach (RECOMMENDED)**
```yaml
- name: Find Latest Models
  run: |
    # Find two most recent LDA models by timestamp
    LATEST_MODEL=$(find models/registry -type d -name "*lda*" | sort -V | tail -1)
    PREVIOUS_MODEL=$(find models/registry -type d -name "*lda*" | sort -V | tail -2 | head -1)

    echo "LATEST_MODEL=$LATEST_MODEL" >> $GITHUB_ENV
    echo "PREVIOUS_MODEL=$PREVIOUS_MODEL" >> $GITHUB_ENV
```

**Option B: Git History Approach**
```yaml
- name: Find Models from Git History
  run: |
    # Find most recent commits that added models
    git log --name-only --pretty=format: | grep "models/registry" | sort -u | tail -2
```

**Option C: Timestamp File Registry**
```yaml
- name: Query Model Registry
  run: |
    python -c "
    import json
    from pathlib import Path

    registry = json.loads(Path('models/registry/models.json').read_text())
    models = sorted(registry.items(), key=lambda x: x[1]['timestamp'])

    latest = models[-1]
    previous = models[-2] if len(models) > 1 else None

    print(f'LATEST_MODEL={latest[0]}')
    print(f'PREVIOUS_MODEL={previous[0]}')
    " >> $GITHUB_ENV
```

**Recommendation:** Use **Option C (Timestamp File Registry)** - it's deterministic, language-agnostic, and supports versioning without git operations.

### 1.3 Permissions and Secrets Management

**GitHub Actions Permissions for Drift Detection:**

```yaml
permissions:
  contents: read              # Read repository files
  issues: write               # Create issues for drift alerts
  pull-requests: write        # Create PR comments (optional)
  actions: read               # Read workflow status
```

**Secrets Management:**
```yaml
env:
  DRIFT_THRESHOLD: ${{ secrets.DRIFT_THRESHOLD || '0.1' }}
  SLACK_WEBHOOK: ${{ secrets.SLACK_WEBHOOK }}
  EMAIL_RECIPIENT: ${{ secrets.ALERT_EMAIL }}
```

**To configure secrets in GitHub:**
1. Go to `Settings → Secrets and variables → Actions`
2. Create `DRIFT_THRESHOLD`, `SLACK_WEBHOOK`, `ALERT_EMAIL`
3. Store sensitive credentials (API keys, email credentials) as secrets

**Security Best Practices:**
- Secrets are never logged or exposed in GitHub UI
- Each secret has automatic masking in workflow logs
- Use `secrets.GITHUB_TOKEN` (auto-created) for GitHub API calls
- Rotate external service tokens quarterly

### 1.4 Cost Implications of Nightly Runs

**GitHub Actions Pricing (as of 2025):**

| Plan | Included Minutes | Cost per Extra Minute |
|------|------------------|-----------------------|
| Free | 2,000/month | $0.008/min (ubuntu) |
| Pro | 3,000/month | $0.008/min |
| Enterprise | Custom | Custom |

**Estimated Costs for Drift Detection:**

```
Nightly run (30 runs/month):
- Checkout + setup: 30s
- Model loading: 60s
- Drift detection: 120s
- Report generation: 30s
Total: ~240s (4 min) per run

Cost: 30 runs × 4 min × $0.008/min = $0.96/month
```

**Optimization Strategies:**
- Use `ubuntu-latest` (cheaper) vs `macos-latest` (2x cost) or `windows-latest` (2x cost)
- Cache dependencies: `actions/setup-python@v5` with `cache: pip`
- Terminate early on success (don't wait for all steps)
- Group checks: 1 comprehensive daily check vs 4 smaller checks

**With Daily Nightly Runs:** ~$1/month (negligible cost)

---

## 2. Drift Detection Integration

### 2.1 Finding Latest Two Model Runs Automatically

**Current Implementation Analysis:**
- `scripts/feature_engineering/detect_drift.py` expects `--ref-model` and `--target-model` paths
- Models are saved with `RunContext` naming: `{run_id}_{name}_{git_sha}/`
- Example: `20231201_143022_auto_label_bart_ea45dd2/`

**Automated Model Discovery Strategy:**

```python
# scripts/utils/find_latest_models.py
from pathlib import Path
from datetime import datetime
from typing import Tuple, Optional
import logging

def get_lda_models(
    models_dir: Path = Path("models/registry"),
    count: int = 2
) -> Tuple[Optional[Path], Optional[Path]]:
    """
    Find the most recent LDA models by timestamp in filename.

    Returns:
        Tuple of (latest_model, previous_model) paths
    """
    # Find all LDA model directories
    lda_models = sorted(
        [d for d in models_dir.glob("*") if d.is_dir() and "lda" in d.name],
        key=lambda p: datetime.strptime(
            p.name.split("_")[0], "%Y%m%d%H%M%S"
        ),
        reverse=True
    )

    if len(lda_models) < count:
        logging.warning(
            f"Only {len(lda_models)} models found, need {count}"
        )
        return lda_models[0] if lda_models else None, None

    return lda_models[0], lda_models[1]
```

**Workflow Integration:**

```yaml
- name: Detect Drift
  run: |
    python -c "
    from pathlib import Path
    from src.features.topic_modeling import LDATrainer
    import scripts.utils.find_latest_models as finder

    latest, previous = finder.get_lda_models()

    if not latest or not previous:
        print('ERROR: Cannot find two models for comparison')
        exit(1)

    python scripts/feature_engineering/detect_drift.py \
      --ref-model $previous \
      --target-model $latest \
      --threshold 0.1
    "
```

### 2.2 Drift Report Storage Strategy

**Storage Options:**

| Option | Pros | Cons | Best For |
|--------|------|------|----------|
| **GitHub Artifacts** | Built-in, 90-day retention, 10GB limit | Deleted after 90 days, can't query | Short-term tracking |
| **GitHub Releases** | Permanent, versioned, easy download | Manual creation overhead | Release milestones |
| **S3/Cloud Storage** | Unlimited retention, queryable, cheap | External dependency, auth overhead | Long-term archive |
| **Git LFS** | Version controlled, integrated | Requires LFS setup, storage costs | Large model files |
| **Repository Data/ Dir** | Simple, version controlled | Git bloat (binary files) | Small reports only |

**Recommended Approach: Dual Strategy**

```yaml
- name: Save Drift Report
  if: always()
  run: |
    # Create report directory with timestamp
    REPORT_DIR="reports/drift/$(date -u +%Y%m%d_%H%M%S)"
    mkdir -p $REPORT_DIR

    # Copy drift report
    cp drift_report.json $REPORT_DIR/
    cp drift_report.html $REPORT_DIR/index.html

    # Create index metadata
    cat > $REPORT_DIR/metadata.json <<EOF
    {
      "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
      "ref_model": "${{ env.PREVIOUS_MODEL }}",
      "target_model": "${{ env.LATEST_MODEL }}",
      "threshold": "${{ env.DRIFT_THRESHOLD }}",
      "status": "${{ job.status }}"
    }
    EOF

- name: Upload Drift Report
  if: always()
  uses: actions/upload-artifact@v3
  with:
    name: drift-report-${{ github.run_id }}
    path: reports/drift/
    retention-days: 90

- name: Archive to Release (on significant drift)
  if: env.SIGNIFICANT_DRIFT == 'true'
  uses: actions/create-release@v1
  with:
    tag_name: drift-${{ github.run_id }}
    files: reports/drift/
```

**Report Structure:**
```
reports/drift/
├── 20231201_000000/
│   ├── drift_report.json          # Full metrics
│   ├── index.html                 # Visual summary
│   └── metadata.json              # Workflow context
└── README.md                      # Report guide
```

### 2.3 Defining Drift Score Thresholds

**Current Implementation:** `settings.risk_analysis.drift_threshold` (default 0.2 from config)

**Threshold Strategy:**

```yaml
env:
  DRIFT_THRESHOLD: 0.1  # Jaccard similarity < 0.1 = new risk
  SIGNIFICANT_DRIFT: false

- name: Run Drift Detection
  run: |
    python scripts/feature_engineering/detect_drift.py \
      --ref-model ${{ env.PREVIOUS_MODEL }} \
      --target-model ${{ env.LATEST_MODEL }} \
      --threshold ${{ env.DRIFT_THRESHOLD }} \
      --output drift_report.json

- name: Check for Significant Drift
  run: |
    python -c "
    import json

    with open('drift_report.json') as f:
      report = json.load(f)

    new_topics = [r for r in report if r['is_new_risk']]
    critical_count = len([t for t in new_topics if t['similarity_score'] < 0.05])

    # Define significance: more than 3 new topics OR critical drift
    if len(new_topics) > 3 or critical_count > 0:
      print('SIGNIFICANT_DRIFT=true')
    else:
      print('SIGNIFICANT_DRIFT=false')
    " >> $GITHUB_ENV
```

**Threshold Recommendations:**

| Threshold | Interpretation | Action |
|-----------|-----------------|--------|
| 0.05 | Critical: Completely new risk pattern | Create urgent issue |
| 0.1 | Significant: New or shifted risks | Create standard issue |
| 0.2 | Minor: Slight topic variations | Log to report only |
| >0.3 | Stable: No actionable drift | Silent success |

---

## 3. Alert Mechanisms

### 3.1 GitHub Issues for Drift Detection

**Issue Creation on Drift Detected:**

```yaml
- name: Create Issue on Drift
  if: env.SIGNIFICANT_DRIFT == 'true'
  uses: actions/github-script@v7
  with:
    script: |
      const fs = require('fs');
      const drift_report = JSON.parse(
        fs.readFileSync('drift_report.json', 'utf8')
      );

      const new_risks = drift_report.filter(r => r.is_new_risk);
      const body = `
      ## Risk Drift Detected

      **Timestamp:** ${new Date().toISOString()}
      **Threshold:** ${{ env.DRIFT_THRESHOLD }}
      **New Risks Found:** ${new_risks.length}

      ### Summary
      ${new_risks.slice(0, 5).map(risk =>
        `- Topic #${risk.target_topic_id}: ${risk.target_top_words.slice(0, 5).join(', ')} (sim: ${risk.similarity_score.toFixed(2)})`
      ).join('\n')}

      **Reports:** [View Full Report](#)

      See \`.github/workflows/drift-detection.yml\` for configuration.
      `;

      github.rest.issues.create({
        owner: context.repo.owner,
        repo: context.repo.repo,
        title: `Risk Drift Alert: ${new_risks.length} new topics`,
        body: body,
        labels: ['drift-alert', 'ml-monitoring'],
        milestone: null
      });
```

**Issue Labels & Assignment:**
```yaml
labels: ['drift-alert', 'ml-monitoring']
assignees: ['@data-team']  # Assign to team member
```

### 3.2 Slack Integration

**Option A: Using Slack Webhook (Simple)**

```yaml
- name: Send Slack Notification
  if: always()
  uses: slackapi/slack-github-action@v1.24
  with:
    webhook-url: ${{ secrets.SLACK_WEBHOOK }}
    payload: |
      {
        "text": "Drift Detection Complete",
        "blocks": [
          {
            "type": "header",
            "text": {
              "type": "plain_text",
              "text": "Risk Drift Detection Report",
              "emoji": true
            }
          },
          {
            "type": "section",
            "fields": [
              {
                "type": "mrkdwn",
                "text": "*Status:*\n${{ job.status }}"
              },
              {
                "type": "mrkdwn",
                "text": "*New Risks:*\n${{ env.NEW_RISK_COUNT }}"
              }
            ]
          },
          {
            "type": "actions",
            "elements": [
              {
                "type": "button",
                "text": {
                  "type": "plain_text",
                  "text": "View Report"
                },
                "url": "${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
              }
            ]
          }
        ]
      }
```

**Option B: Using Slack Bot Token (Advanced)**

```yaml
- name: Post to Slack Channel
  if: env.SIGNIFICANT_DRIFT == 'true'
  uses: slackapi/slack-github-action@v1.24
  with:
    payload: |
      {
        "channel": "${{ secrets.SLACK_CHANNEL }}",
        "text": "Risk drift detected - ${{ env.NEW_RISK_COUNT }} new topics",
        "blocks": [...] # Same as above
      }
  env:
    SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}
```

### 3.3 Email Notifications

**Using GitHub's Built-in Email:**
```yaml
- name: Send Email Alert
  if: env.SIGNIFICANT_DRIFT == 'true'
  run: |
    # Use Python to send email
    python -c "
    import smtplib
    from email.mime.text import MIMEText

    msg = MIMEText('''
    Risk drift detected in nightly analysis.

    New topics: ${{ env.NEW_RISK_COUNT }}
    Threshold: ${{ env.DRIFT_THRESHOLD }}

    Review: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
    ''')

    msg['Subject'] = 'Risk Drift Alert'
    msg['From'] = 'github-actions@example.com'
    msg['To'] = '${{ secrets.ALERT_EMAIL }}'

    # Use SMTP - requires secrets for credentials
    "
```

**Recommendation:** Use Slack for engineering teams (real-time), email for stakeholders (formal alerts).

### 3.4 Workflow Failure Notifications

GitHub automatically notifies:
- Push committer on workflow failure (if email enabled)
- Workflow creator via GitHub notifications

**To enhance failure notifications:**

```yaml
- name: Notify on Failure
  if: failure()
  uses: actions/github-script@v7
  with:
    script: |
      github.rest.issues.createComment({
        issue_number: context.payload.pull_request?.number || 1,
        owner: context.repo.owner,
        repo: context.repo.repo,
        body: '❌ Drift detection workflow failed. Check logs: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}'
      });
```

---

## 4. Data Availability & Artifact Management

### 4.1 Ensuring Models in GitHub Actions

**Challenge:** Models may be too large for Git (LDA models ~50-500MB).

**Strategy 1: Store in Repository (for small models)**
```yaml
- name: Load Local Models
  run: |
    ls -la models/registry/
    python scripts/feature_engineering/detect_drift.py \
      --ref-model models/registry/lda_2022 \
      --target-model models/registry/lda_2023
```

**Strategy 2: Download from Artifact of Previous Job**
```yaml
jobs:
  train-model:
    runs-on: ubuntu-latest
    outputs:
      model-path: ${{ steps.train.outputs.model-path }}
    steps:
      - uses: actions/checkout@v4
      - name: Train LDA Model
        id: train
        run: |
          python scripts/train_lda_model.py
          echo "model-path=models/registry/$(ls models/registry -t | head -1)" >> $GITHUB_OUTPUT
      - uses: actions/upload-artifact@v3
        with:
          name: lda-model
          path: models/registry/

  detect-drift:
    needs: train-model
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v3
        with:
          name: lda-model
          path: models/registry/
      - name: Run Drift Detection
        run: |
          python scripts/feature_engineering/detect_drift.py ...
```

**Strategy 3: Use GitHub Releases as Model Registry**
```yaml
- name: Download Latest Model Release
  run: |
    # Download from releases
    gh release download lda-latest \
      --pattern "lda_*.tar.gz" \
      --dir models/registry/

    tar xzf models/registry/lda_*.tar.gz -C models/registry/
```

**Strategy 4: External Storage (AWS S3)**
```yaml
- name: Download Models from S3
  env:
    AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
    AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
  run: |
    aws s3 sync s3://my-models-bucket/lda/ models/registry/ \
      --region us-east-1 \
      --exclude "*" \
      --include "lda_*.tar.gz" \
      | head -2  # Get latest 2
```

**Recommendation for SEC Finetune:** Use **Strategy 1 (Local) + Strategy 3 (Releases)** - keep latest models in repo with Git LFS, archive older models to Releases.

### 4.2 Artifact Retention Across Workflow Runs

**GitHub Artifacts Limits:**
- Retention: 90 days (free tier), configurable up to 400 days
- Size: 10GB total per repository
- Per artifact: No single-file limit, but upload/download rate-limited

**Workflow to Persist Drift Reports:**

```yaml
name: Scheduled Drift Detection

on:
  schedule:
    - cron: '0 0 * * *'  # Daily at midnight

jobs:
  drift-detection:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Generate Drift Report
        run: |
          # Report saved as drift_report.json
          python scripts/feature_engineering/detect_drift.py ...

      # Keep last 90 days of reports
      - uses: actions/upload-artifact@v3
        if: always()
        with:
          name: drift-report-${{ github.run_number }}
          path: drift_report.json
          retention-days: 90

      # Archive to releases for longer retention
      - name: Archive Significant Drifts
        if: env.SIGNIFICANT_DRIFT == 'true'
        run: |
          # Create release tag
          TAG="drift-$(date -u +%Y%m%d-%H%M%S)"
          git tag $TAG
          git push origin $TAG

          # Upload report to release
          gh release create $TAG drift_report.json \
            --title "Risk Drift Detection: $TAG" \
            --notes "Significant drift detected"
```

**Querying Artifacts:**
```bash
# List artifacts from latest run
gh run list --workflow drift-detection.yml --limit 1 --json databaseId
gh run view <run-id> --json artifacts

# Download specific artifact
gh run download <run-id> -n drift-report-<number>
```

### 4.3 Alternative Storage: GitHub Releases, LFS, S3

| Storage | Setup Complexity | Cost | Query Support | Best For |
|---------|------------------|------|----------------|----------|
| Artifacts | 0 (built-in) | Free (90 days) | UI only | Short-term |
| Releases | Low (gh CLI) | Free (unlimited) | Git tags | Archival |
| LFS | Medium | $5/mo (1GB) | Git native | Large models |
| S3 | Medium (IAM) | ~$1/month | Boto3/SDK | Production scale |

**S3 Setup Example:**
```yaml
- name: Archive to S3
  if: always()
  env:
    AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
    AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
  run: |
    TIMESTAMP=$(date -u +%Y%m%d_%H%M%S)

    aws s3 cp drift_report.json \
      s3://my-reports-bucket/drift/$TIMESTAMP/ \
      --region us-east-1

    # Maintain index of all reports
    aws s3 cp - s3://my-reports-bucket/drift/index.txt \
      --sse AES256 <<EOF
    $TIMESTAMP: ${{ env.NEW_RISK_COUNT }} new risks
    EOF
```

---

## 5. Best Practices for ML Pipeline Monitoring

### 5.1 Scheduled Workflow Patterns

**Recommended Complete Workflow Pattern:**

```yaml
name: Nightly Drift Detection

on:
  schedule:
    - cron: '0 0 * * *'  # Daily at midnight UTC
  workflow_dispatch:     # Manual trigger for testing

concurrency:
  group: drift-detection
  cancel-in-progress: false  # Don't cancel if another run in progress

jobs:
  drift-detection:
    runs-on: ubuntu-latest
    outputs:
      status: ${{ job.status }}
      new-risks: ${{ steps.drift.outputs.new-risks }}

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Full history for model discovery

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Find Latest Models
        id: models
        run: |
          python -c "
          from pathlib import Path
          models = sorted(Path('models/registry').glob('*lda*'), reverse=True)
          echo(f'LATEST={models[0]}')
          echo(f'PREVIOUS={models[1]}')
          " >> $GITHUB_ENV

      - name: Run Drift Detection
        id: drift
        continue-on-error: true  # Don't fail if drift detected
        run: |
          python scripts/feature_engineering/detect_drift.py \
            --ref-model ${{ env.PREVIOUS }} \
            --target-model ${{ env.LATEST }} \
            --threshold 0.1 \
            > drift_report.json

          # Parse report for downstream alerts
          NEW_RISKS=$(python -c "
          import json
          report = json.load(open('drift_report.json'))
          count = len([r for r in report if r['is_new_risk']])
          print(count)
          ")
          echo "new-risks=$NEW_RISKS" >> $GITHUB_OUTPUT

      - name: Create Alert Issue
        if: steps.drift.outputs.new-risks > 3
        uses: actions/github-script@v7
        with:
          script: |
            github.rest.issues.create({
              owner: context.repo.owner,
              repo: context.repo.repo,
              title: `Risk Drift Alert: ${{ steps.drift.outputs.new-risks }} new topics`,
              body: `...`,
              labels: ['drift-alert']
            })

      - uses: actions/upload-artifact@v3
        if: always()
        with:
          name: drift-report
          path: drift_report.json
          retention-days: 90

      - name: Send Slack Notification
        if: always()
        uses: slackapi/slack-github-action@v1.24
        with:
          webhook-url: ${{ secrets.SLACK_WEBHOOK }}
          payload: |
            {"text": "Drift check: ${{ job.status }} (${{ steps.drift.outputs.new-risks }} risks)"}
```

### 5.2 Failure Handling & Retry Logic

**Retry Strategy:**
```yaml
- name: Run Drift Detection with Retries
  uses: nick-invision/retry@v2
  with:
    timeout_minutes: 30
    max_attempts: 3
    retry_wait_seconds: 60
    command: |
      python scripts/feature_engineering/detect_drift.py \
        --ref-model ${{ env.PREVIOUS }} \
        --target-model ${{ env.LATEST }}
```

**Failure Handling:**
```yaml
- name: Handle Workflow Failure
  if: failure()
  run: |
    # Log detailed error
    cat > failure_report.txt <<EOF
    Workflow: ${{ github.workflow }}
    Run: ${{ github.run_id }}
    Attempt: ${{ github.run_attempt }}
    Error: See logs above
    EOF

    # Notify team
    python -c "
    import os
    webhook = os.getenv('SLACK_WEBHOOK')
    # Send critical alert
    "
  env:
    SLACK_WEBHOOK: ${{ secrets.SLACK_WEBHOOK }}
```

### 5.3 Monitoring & Observability

**Key Metrics to Track:**

```yaml
- name: Log Metrics
  run: |
    # Save to artifacts for dashboarding
    python -c "
    import json
    from datetime import datetime

    metrics = {
      'timestamp': datetime.utcnow().isoformat(),
      'workflow_duration': ${{ job.duration }},
      'model_loading_time': ...,
      'drift_detection_time': ...,
      'new_risks_count': ${{ steps.drift.outputs.new-risks }},
      'git_sha': '${{ github.sha }}',
      'run_id': '${{ github.run_id }}'
    }

    with open('workflow_metrics.json', 'w') as f:
      json.dump(metrics, f, indent=2)
    "

    # Optional: send to monitoring backend
    curl -X POST https://monitoring.example.com/metrics \
      -H "Authorization: Bearer ${{ secrets.MONITORING_TOKEN }}" \
      -d @workflow_metrics.json
```

**Recommended Dashboards (GitHub/External):**
- Workflow success rate (% runs completed)
- Average run duration (should be stable)
- Drift detection frequency (spikes indicate issues)
- Alert volume trend (increasing = risk shift)

---

## 6. Production-Ready Architecture

### 6.1 Complete Implementation Checklist

- [ ] **Cron Scheduling:** Schedule set to `0 0 * * *` (daily midnight UTC)
- [ ] **Model Registry:** Implement timestamp-based model discovery
- [ ] **Configuration:** Store thresholds in `settings.risk_analysis.drift_threshold`
- [ ] **Artifact Storage:** Drift reports in GitHub Artifacts (90 days) + Releases (permanent)
- [ ] **Alerting:**
  - [ ] GitHub Issues for triage (threshold > 0.1)
  - [ ] Slack notifications for significant drift
  - [ ] Email fallback for critical alerts
- [ ] **Permissions:** Configure `contents: read`, `issues: write`
- [ ] **Secrets:** Store `SLACK_WEBHOOK`, `ALERT_EMAIL`, `DRIFT_THRESHOLD`
- [ ] **Monitoring:** Log workflow metrics to artifacts
- [ ] **Testing:** Test with `workflow_dispatch` trigger before scheduling

### 6.2 Expected Workflow Performance

Based on your codebase:

```
Workflow Timeline:
├─ Checkout (30s)
├─ Setup Python (20s)
├─ Install deps (60s)
├─ Load model 1 (30s)
├─ Load model 2 (30s)
├─ Run drift detection (120s)    # Depends on topic count
├─ Generate report (20s)
└─ Upload artifact (10s)
   ──────────────────────
   Total: ~320s (5.3 min)

Cost: 30 runs/month × 5.3 min × $0.008/min = $1.27/month
```

**Optimization Tips:**
- Cache Python dependencies: saves ~60s
- Use S3/LFS for models: avoids checkout bloat
- Parallelize checks: run multiple drift configurations simultaneously
- Pre-train models in separate CI job: don't train during drift detection

---

## 7. Key Decision Points for Your Project

1. **Model Storage:** Use git LFS for models in repo OR S3 for external storage?
   - *Recommendation:* Git LFS for versions <500MB, S3 for production scale

2. **Report Destination:** GitHub Artifacts OR dedicated S3 bucket?
   - *Recommendation:* Both - Artifacts for 90 days, S3 for indefinite archival

3. **Alert Channels:** Slack OR Email OR Issues?
   - *Recommendation:* Slack (dev team) + Issues (triage) + Email (stakeholders)

4. **Frequency:** Daily OR Weekly?
   - *Recommendation:* Daily (detect issues early) with weekly summary digest

5. **Threshold:** What Jaccard similarity = actionable drift?
   - *Recommendation:* 0.1 for alerts, 0.05 for critical issues

---

## 8. Related Configuration Files

**Current Locations:**
- Drift Detection Script: `/scripts/feature_engineering/detect_drift.py:95` (threshold config)
- LDA Trainer: `/src/features/topic_modeling/lda_trainer.py:36-84` (model save/load)
- RunContext: `/src/config/run_context.py:87-107` (output dir structure)
- Config: `/configs/config.yaml` (no drift_threshold yet - needs addition)

**Files to Create/Modify:**
1. `.github/workflows/drift-detection.yml` (new)
2. `scripts/utils/find_latest_models.py` (new)
3. `scripts/utils/generate_drift_alert.py` (new)
4. `configs/config.yaml` (add `risk_analysis.drift_threshold`)

---

## 9. References & Resources

- GitHub Actions Docs: https://docs.github.com/en/actions
- Cron Syntax: https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#schedule
- Slack GitHub Action: https://github.com/slackapi/slack-github-action
- AWS S3 GitHub Action: https://github.com/aws-actions/configure-aws-credentials
- Gensim LDA Documentation: https://radimrehurek.com/gensim/

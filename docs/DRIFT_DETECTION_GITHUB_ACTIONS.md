# GitHub Actions Scheduled Drift Detection - Technical Reference

**Last Updated:** 2025-12-28
**Status:** Complete Research & Planning Documentation
**Audience:** Engineering Team

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Complete Workflow YAML](#complete-workflow-yaml)
3. [Utility Scripts](#utility-scripts)
4. [Configuration Examples](#configuration-examples)
5. [Troubleshooting Guide](#troubleshooting-guide)
6. [FAQ](#faq)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                   GitHub Actions Scheduled Workflow                  │
│                     (Every day at 00:00 UTC)                         │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                        ┌───────────┴────────────┐
                        │                        │
                    ┌───▼──────┐         ┌──────▼──┐
                    │  Checkout │         │ Setup   │
                    │Repository │         │ Python  │
                    └──────┬───┘         └────┬─────┘
                           │                  │
                           └──────────┬───────┘
                                      │
                         ┌────────────▼──────────────┐
                         │ Install Dependencies      │
                         │ (gensim, nltk, pydantic)  │
                         └────────────┬──────────────┘
                                      │
                         ┌────────────▼──────────────┐
                         │  Discover Latest Models   │
                         │  (find_latest_models.py)  │
                         └────────────┬──────────────┘
                                      │
                    ┌─────────────────┴──────────────────┐
                    │                                    │
            ┌───────▼──────┐                 ┌──────────▼────┐
            │ Load Ref      │                 │  Load Target  │
            │ LDA Model     │                 │  LDA Model    │
            └───────┬──────┘                 └──────────┬────┘
                    │                                    │
                    └─────────────────┬──────────────────┘
                                      │
                        ┌─────────────▼─────────────┐
                        │  Run Drift Detection      │
                        │  (detect_drift.py)        │
                        │  - Compare topics         │
                        │  - Calculate Jaccard sim  │
                        │  - Generate report JSON   │
                        └─────────────┬─────────────┘
                                      │
                    ┌─────────────────┴──────────────────┐
                    │                                    │
            ┌───────▼───────┐              ┌────────────▼────┐
            │ Analyze Report│              │ Create Issue    │
            │ Count new risks              │ (if sig drift)  │
            └───────┬───────┘              └─────────────────┘
                    │
            ┌───────▼──────────┐
            │ Send Alerts      │
            │ ├─ Slack         │
            │ └─ GitHub Issues │
            └───────┬──────────┘
                    │
            ┌───────▼──────────┐
            │ Upload Artifacts │
            │ ├─ drift_report  │
            │ └─ metrics       │
            └──────────────────┘
```

### Data Flow

```
models/registry/
  ├── lda_20230101_120000_experiment_abc123/  (Older)
  │   ├── lda_model.pkl
  │   ├── dictionary.pkl
  │   └── model_info.json
  │
  └── lda_20231201_120000_experiment_def456/  (Latest)
      ├── lda_model.pkl
      ├── dictionary.pkl
      └── model_info.json
            │
            └─────────────────────┐
                                  │
                    ┌─────────────▼────────────┐
                    │  find_latest_models()    │
                    │  Returns:                │
                    │  - latest path (newer)   │
                    │  - previous path (older) │
                    └─────────────┬────────────┘
                                  │
                    ┌─────────────▼────────────┐
                    │  detect_drift.py         │
                    │  Input: 2 models         │
                    │  Output: JSON report     │
                    └─────────────┬────────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        │                         │                         │
        ▼                         ▼                         ▼
    GitHub Artifacts       GitHub Issues              Slack
    (90 days)             (w/ labels)               (webhook)
```

---

## Complete Workflow YAML

**File:** `.github/workflows/drift-detection.yml`

```yaml
name: Scheduled Drift Detection

on:
  # Automatic trigger: Every day at 00:00 UTC
  schedule:
    - cron: '0 0 * * *'

  # Manual trigger for testing
  workflow_dispatch:
    inputs:
      threshold:
        description: 'Override drift threshold'
        required: false
        type: string

# Prevent overlapping runs
concurrency:
  group: drift-detection
  cancel-in-progress: false

# GitHub API permissions
permissions:
  contents: read
  issues: write
  actions: read

env:
  PYTHON_VERSION: '3.11'
  SLACK_WEBHOOK: ${{ secrets.SLACK_WEBHOOK }}

jobs:
  drift-detection:
    name: Detect Topic Drift in LDA Models
    runs-on: ubuntu-latest

    outputs:
      status: ${{ job.status }}
      new-risks: ${{ steps.analyze.outputs.new_risks_count }}
      critical: ${{ steps.analyze.outputs.critical_drift }}

    steps:
      # =====================================================
      # Setup Phase
      # =====================================================

      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Setup Python ${{ env.PYTHON_VERSION }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: 'pip'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          # Explicit drift detection deps
          pip install gensim>=4.2.0 nltk numpy pandas

      # =====================================================
      # Model Discovery Phase
      # =====================================================

      - name: Discover latest LDA models
        id: models
        run: |
          python << 'EOF'
          import sys
          from pathlib import Path
          sys.path.insert(0, '.')

          from scripts.utils.find_latest_models import get_lda_models

          latest, previous = get_lda_models()

          if not latest or not previous:
              print("ERROR: Could not find two models for comparison")
              sys.exit(1)

          print(f"Latest:   {latest}")
          print(f"Previous: {previous}")

          # Write to environment for downstream steps
          with open(os.environ['GITHUB_ENV'], 'a') as f:
              f.write(f"LATEST_MODEL={latest}\n")
              f.write(f"PREVIOUS_MODEL={previous}\n")
          EOF

      - name: Validate models exist
        run: |
          echo "Checking for models..."
          ls -la "${{ env.LATEST_MODEL }}"
          ls -la "${{ env.PREVIOUS_MODEL }}"
          echo "✓ Both models found"

      # =====================================================
      # Drift Detection Phase
      # =====================================================

      - name: Determine drift threshold
        run: |
          THRESHOLD="${{ github.event.inputs.threshold }}"

          if [ -z "$THRESHOLD" ]; then
              THRESHOLD=$(python -c "
              from src.config import settings
              print(settings.risk_analysis.drift_threshold)
              ")
          fi

          echo "Using threshold: $THRESHOLD"
          echo "DRIFT_THRESHOLD=$THRESHOLD" >> $GITHUB_ENV

      - name: Run drift detection
        id: drift
        continue-on-error: true
        timeout-minutes: 30
        run: |
          python scripts/feature_engineering/detect_drift.py \
            --ref-model "${{ env.PREVIOUS_MODEL }}" \
            --target-model "${{ env.LATEST_MODEL }}" \
            --threshold "${{ env.DRIFT_THRESHOLD }}" \
            | tee drift_report.json

          echo "Drift detection completed"

      - name: Validate drift report
        id: validate
        run: |
          python << 'EOF'
          import json
          import sys

          try:
              with open('drift_report.json') as f:
                  report = json.load(f)
              print(f"✓ Valid drift report with {len(report)} topics")
          except Exception as e:
              print(f"✗ Invalid drift report: {e}")
              sys.exit(1)
          EOF

      # =====================================================
      # Analysis & Alerting Phase
      # =====================================================

      - name: Analyze drift report
        id: analyze
        if: steps.validate.outcome == 'success'
        run: |
          python << 'EOF'
          import json
          import os

          with open('drift_report.json') as f:
              report = json.load(f)

          # Count new risks
          new_risks = [r for r in report if r.get('is_new_risk', False)]
          critical_risks = [r for r in report if r.get('similarity_score', 1.0) < 0.05]

          new_count = len(new_risks)
          critical_count = len(critical_risks)

          print(f"New risks detected: {new_count}")
          print(f"Critical drifts: {critical_count}")

          # Determine if significant
          is_significant = new_count > 3 or critical_count > 0

          # Write outputs
          with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
              f.write(f"new_risks_count={new_count}\n")
              f.write(f"critical_drift={'true' if critical_count > 0 else 'false'}\n")
              f.write(f"is_significant={'true' if is_significant else 'false'}\n")
          EOF

      - name: Create GitHub issue (significant drift)
        if: steps.analyze.outputs.is_significant == 'true'
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');

            // Parse drift report
            let topRisks = [];
            try {
                const report = JSON.parse(fs.readFileSync('drift_report.json', 'utf8'));
                topRisks = report
                    .filter(r => r.is_new_risk)
                    .slice(0, 10)
                    .map(r => ({
                        topic: r.target_topic_id,
                        words: r.target_top_words.slice(0, 5),
                        score: r.similarity_score
                    }));
            } catch (e) {
                console.error('Failed to parse report:', e);
            }

            // Build issue body
            const risksList = topRisks.map(r =>
                `- **Topic #${r.topic}**: ${r.words.join(', ')} (Sim: ${r.score.toFixed(3)})`
            ).join('\n');

            const body = `## Risk Drift Detected ⚠️

            **Timestamp:** ${new Date().toISOString()}
            **Threshold:** ${{ env.DRIFT_THRESHOLD }}

            ### Summary
            - New Risks Found: **${{ steps.analyze.outputs.new_risks_count }}**
            - Critical Drifts: **${{ steps.analyze.outputs.critical_drift }}**

            ### Top Risk Topics
            ${risksList}

            ### Models Compared
            - Reference: \`${{ env.PREVIOUS_MODEL }}\`
            - Target: \`${{ env.LATEST_MODEL }}\`

            ### Action Items
            - [ ] Review new risk topics
            - [ ] Assess business impact
            - [ ] Update risk model if needed
            - [ ] Close issue when reviewed

            ---
            *Workflow:* [${{ github.run_id }}](${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }})
            `;

            const issue = await github.rest.issues.create({
                owner: context.repo.owner,
                repo: context.repo.repo,
                title: `Risk Drift Alert: ${{ steps.analyze.outputs.new_risks_count }} new topics`,
                body: body,
                labels: ['drift-alert', 'ml-monitoring'],
            });

            console.log(`Created issue #${issue.data.number}`);

      - name: Send Slack notification (all runs)
        if: always() && env.SLACK_WEBHOOK != ''
        uses: slackapi/slack-github-action@v1.24
        with:
          webhook-url: ${{ secrets.SLACK_WEBHOOK }}
          payload: |
            {
              "blocks": [
                {
                  "type": "header",
                  "text": {
                    "type": "plain_text",
                    "text": "Drift Detection Report"
                  }
                },
                {
                  "type": "section",
                  "fields": [
                    {
                      "type": "mrkdwn",
                      "text": "*Status*\n${{ job.status }}"
                    },
                    {
                      "type": "mrkdwn",
                      "text": "*New Risks*\n${{ steps.analyze.outputs.new_risks_count || 'N/A' }}"
                    },
                    {
                      "type": "mrkdwn",
                      "text": "*Threshold*\n${{ env.DRIFT_THRESHOLD }}"
                    },
                    {
                      "type": "mrkdwn",
                      "text": "*Time*\n$(date -u +%H:%M UTC)"
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
                        "text": "View Workflow Run"
                      },
                      "url": "${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
                    },
                    {
                      "type": "button",
                      "text": {
                        "type": "plain_text",
                        "text": "View Issues"
                      },
                      "url": "${{ github.server_url }}/${{ github.repository }}/issues?q=label:drift-alert"
                    }
                  ]
                }
              ]
            }

      # =====================================================
      # Artifact & Metrics Phase
      # =====================================================

      - name: Generate workflow metrics
        if: always()
        run: |
          python << 'EOF'
          import json
          from datetime import datetime
          import os

          metrics = {
              "timestamp": datetime.utcnow().isoformat(),
              "workflow": "drift-detection",
              "run_id": "${{ github.run_id }}",
              "run_number": "${{ github.run_number }}",
              "status": "${{ job.status }}",
              "duration_seconds": int("${{ job.elapsed_seconds }}" or 0),
              "new_risks": int("${{ steps.analyze.outputs.new_risks_count }}" or -1),
              "critical_drift": "${{ steps.analyze.outputs.critical_drift }}" == "true",
              "threshold": "${{ env.DRIFT_THRESHOLD }}",
              "git_sha": "${{ github.sha }}",
              "git_ref": "${{ github.ref }}",
              "models": {
                  "reference": "${{ env.PREVIOUS_MODEL }}",
                  "target": "${{ env.LATEST_MODEL }}"
              }
          }

          with open('workflow_metrics.json', 'w') as f:
              json.dump(metrics, f, indent=2)

          print("Generated metrics:")
          print(json.dumps(metrics, indent=2))
          EOF

      - name: Upload drift report artifact
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: drift-report-${{ github.run_number }}
          path: drift_report.json
          retention-days: 90
          if-no-files-found: warn

      - name: Upload workflow metrics artifact
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: workflow-metrics-${{ github.run_number }}
          path: workflow_metrics.json
          retention-days: 90
          if-no-files-found: warn

      - name: Archive to release (critical drift)
        if: steps.analyze.outputs.critical_drift == 'true'
        uses: softprops/action-gh-release@v1
        with:
          tag_name: drift-alert-${{ github.run_id }}
          files: |
            drift_report.json
            workflow_metrics.json
          draft: false
          prerelease: false

      # =====================================================
      # Failure Handling
      # =====================================================

      - name: Log failure details
        if: failure()
        run: |
          echo "=== Drift Detection Failure Details ===" >> debug.log
          echo "Timestamp: $(date -u)" >> debug.log
          echo "Run ID: ${{ github.run_id }}" >> debug.log
          echo "Repository: ${{ github.repository }}" >> debug.log
          echo "Ref: ${{ github.ref }}" >> debug.log
          echo "" >> debug.log
          echo "Environment:" >> debug.log
          env | grep -E "MODEL|DRIFT|THRESHOLD" >> debug.log || true
          echo "" >> debug.log
          echo "Last 50 lines of output:" >> debug.log
          tail -50 drift_report.json >> debug.log 2>/dev/null || echo "No report" >> debug.log
          cat debug.log

      - name: Upload debug logs on failure
        if: failure()
        uses: actions/upload-artifact@v3
        with:
          name: failure-debug-${{ github.run_number }}
          path: debug.log
          retention-days: 30
```

---

## Utility Scripts

### 1. Model Discovery (`scripts/utils/find_latest_models.py`)

```python
"""Find latest LDA models for drift detection."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def parse_run_id(dirname: str) -> Optional[datetime]:
    """
    Parse timestamp from RunContext dirname format.

    Expected: {YYYYMMDD_HHMMSS}_{name}_{git_sha}
    Example: 20231201_120000_topic_model_abc123

    Args:
        dirname: Directory name to parse

    Returns:
        datetime object or None if parsing fails
    """
    try:
        timestamp_str = dirname.split('_')[0]
        if len(timestamp_str) == 8:
            # Format: YYYYMMDD only (no time)
            return datetime.strptime(timestamp_str, "%Y%m%d")
        else:
            # Format: YYYYMMDD_HHMMSS
            timestamp_str = '_'.join(dirname.split('_')[:2])
            return datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
    except (ValueError, IndexError) as e:
        logger.warning(f"Could not parse timestamp from {dirname}: {e}")
        return None


def get_lda_models(
    models_dir: Optional[Path] = None,
    count: int = 2,
    verbose: bool = True
) -> Tuple[Optional[Path], Optional[Path]]:
    """
    Find the most recent LDA model directories.

    Args:
        models_dir: Directory containing models (default: models/registry)
        count: Number of models to find (default: 2 for comparison)
        verbose: Print debug information (default: True)

    Returns:
        Tuple of (latest_model, previous_model) or (model, None) if only 1 found

    Raises:
        FileNotFoundError: If models_dir doesn't exist

    Example:
        >>> latest, previous = get_lda_models()
        >>> if not latest or not previous:
        ...     raise ValueError("Not enough models for drift detection")
        >>> print(f"Latest: {latest}, Previous: {previous}")
    """
    if models_dir is None:
        models_dir = Path("models/registry")

    if not models_dir.exists():
        raise FileNotFoundError(f"Models directory not found: {models_dir}")

    # Find all directories containing 'lda' in name
    lda_models = []

    for item in models_dir.iterdir():
        if not item.is_dir():
            continue

        if "lda" not in item.name.lower():
            continue

        # Try to parse timestamp from directory name
        timestamp = parse_run_id(item.name)

        if timestamp is None:
            if verbose:
                logger.warning(f"Skipping {item.name} - could not parse timestamp")
            continue

        lda_models.append((timestamp, item))

        if verbose:
            logger.info(f"Found LDA model: {item.name} (timestamp: {timestamp})")

    # Sort by timestamp descending (most recent first)
    lda_models.sort(key=lambda x: x[0], reverse=True)

    if verbose:
        logger.info(f"Total LDA models found: {len(lda_models)}")

    if len(lda_models) < count:
        logger.warning(
            f"Only {len(lda_models)} models found, but {count} required for comparison"
        )
        if not lda_models:
            return None, None
        if count == 2 and len(lda_models) == 1:
            logger.error("Need at least 2 models for drift detection")
            return lda_models[0][1], None

    return lda_models[0][1], lda_models[1][1]


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    try:
        latest, previous = get_lda_models()
        if latest and previous:
            print(f"\n✓ Found models for comparison:")
            print(f"  Latest:   {latest}")
            print(f"  Previous: {previous}")
        else:
            print("✗ Not enough models found for drift detection")
            exit(1)
    except Exception as e:
        print(f"✗ Error: {e}")
        exit(1)
```

---

## Configuration Examples

### GitHub Secrets Setup

```bash
# Set Slack webhook
gh secret set SLACK_WEBHOOK \
  --body "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

# Optional: Set drift threshold override
gh secret set DRIFT_THRESHOLD \
  --body "0.1"
```

### Config YAML Addition

Add this to `configs/config.yaml`:

```yaml
# ===========================
# Risk Analysis Configuration
# ===========================
risk_analysis:
  # Drift detection Jaccard similarity threshold
  # Topics below this similarity are flagged as "new risks"
  drift_threshold: 0.1

  # Number of new topics before creating GitHub issue
  alert_on_new_topics: 3

  # Similarity score threshold for critical alerts
  critical_drift_score: 0.05
```

---

## Troubleshooting Guide

### Issue: "Models not found"

**Error:** `ERROR: Could not find two models for comparison`

**Causes:**
1. No models in `models/registry/`
2. Directory names don't follow RunContext pattern
3. Models exist but directory isn't named with LDA prefix

**Solution:**
```bash
# Check what's in models/registry
ls -la models/registry/

# Verify naming pattern
# Expected: {YYYYMMDD_HHMMSS}_{name}_{sha} where name contains 'lda'

# Train a model if none exist
python scripts/feature_engineering/train_lda_model.py
```

### Issue: "Workflow timeout"

**Error:** Drift detection takes >30 minutes

**Causes:**
1. Large topic model (many topics)
2. Slow I/O (reading large pickle files)
3. High coherence computation

**Solution:**
```yaml
# Increase timeout
timeout-minutes: 60

# Or optimize:
# - Reduce num_topics in config
# - Disable coherence computation if not needed
# - Use larger runner: ubuntu-latest is fine
```

### Issue: "Slack notification not sent"

**Error:** Slack step skipped or fails silently

**Causes:**
1. `SLACK_WEBHOOK` secret not set
2. Webhook URL is invalid
3. Slack workspace doesn't allow webhooks

**Solution:**
```bash
# Verify secret exists
gh secret list | grep SLACK

# Test webhook manually
curl -X POST https://hooks.slack.com/services/YOUR/WEBHOOK \
  -H 'Content-type: application/json' \
  -d '{"text":"Test"}'
```

### Issue: "GitHub issue creation fails"

**Error:** Actions: Insufficient permissions to use this API

**Causes:**
1. Workflow permissions not set
2. Token doesn't have `issues:write` permission

**Solution:**
Verify `.github/workflows/drift-detection.yml` has:
```yaml
permissions:
  contents: read
  issues: write
```

---

## FAQ

### Q: How often should drift detection run?

**A:** Nightly (daily at 00:00 UTC) is recommended for most use cases. This balances:
- Cost: ~$1-2/month
- Detection latency: Models trained daily or weekly
- Alert fatigue: Not overwhelming with constant alerts

To change frequency, modify the cron in `.github/workflows/drift-detection.yml`:
- `0 0 * * *` → Daily at midnight
- `0 2 * * 1` → Weekly Monday at 2 AM
- `0 0,12 * * *` → Twice daily (noon & midnight)

### Q: Can I test the workflow before scheduling?

**A:** Yes! Use `workflow_dispatch` trigger:
```bash
gh workflow run drift-detection.yml --ref main -f threshold=0.1
```

### Q: What's the cost for running this daily?

**A:** ~$0.96-1.20/month:
- 30 runs × 4-5 minutes × $0.008/minute = $0.96-1.20

This is negligible. You get 2,000+ free workflow minutes/month on free tier.

### Q: How do I archive reports long-term?

**A:** Three options (in order of preference):

1. **GitHub Releases** (Recommended)
   - Permanent, versioned, easy search
   - Use `softprops/action-gh-release@v1`

2. **AWS S3**
   - Unlimited capacity, queryable
   - Requires AWS credentials in secrets

3. **Git LFS**
   - Version controlled
   - Requires LFS storage quota

### Q: Can I get alerts beyond Slack?

**A:** Yes! Additional options:

1. **Email** (via GitHub): Configure in Settings
2. **Webhook to custom service**: Use curl in workflow
3. **PagerDuty**: Use slackapi/slack-github-action with PagerDuty integration
4. **Microsoft Teams**: Use `action-ifttt@v0` or Teams webhook

### Q: What if a model is missing or corrupted?

**A:** Add validation:

```yaml
- name: Validate model integrity
  run: |
    python << 'EOF'
    from pathlib import Path

    for model_path in ["${{ env.LATEST_MODEL }}", "${{ env.PREVIOUS_MODEL }}"]:
        # Check required files
        required = ["lda_model.pkl", "dictionary.pkl"]
        for file in required:
            if not Path(model_path, file).exists():
                raise FileNotFoundError(f"Missing {file} in {model_path}")

        # Check file size (should be >1MB)
        size = sum(f.stat().st_size for f in Path(model_path).iterdir())
        if size < 1024*1024:
            raise ValueError(f"Model seems empty: {size} bytes")

    print("✓ Models validated")
    EOF
```

### Q: How do I silence alerts during maintenance?

**A:** Add a check for maintenance mode:

```yaml
- name: Check maintenance mode
  run: |
    MAINTENANCE=$(curl -s https://your-status-page.com/api/status | jq .maintenance)
    if [ "$MAINTENANCE" = "true" ]; then
      echo "SKIP_ALERTS=true" >> $GITHUB_ENV
    fi

- name: Send alerts
  if: env.SKIP_ALERTS != 'true'
  # ... rest of notification step
```

---

## Next Steps

1. **Create workflow file** (`.github/workflows/drift-detection.yml`)
2. **Create utility script** (`scripts/utils/find_latest_models.py`)
3. **Configure secrets** (SLACK_WEBHOOK, etc.)
4. **Test with manual dispatch** before scheduling
5. **Monitor first week** for false positives/negatives
6. **Adjust thresholds** based on results
7. **Create dashboards** to track trend

See implementation plan: `/thoughts/shared/plans/2025-12-28_scheduled_drift_detection_implementation.md`

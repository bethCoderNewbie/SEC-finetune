# Implementation Plan: Scheduled Drift Detection with GitHub Actions

**Status:** Ready for Implementation
**Effort:** 2-3 days (research: done, implementation: pending)
**Priority:** High (production monitoring)
**Related Research:** `2025-12-28_14-30_scheduled_drift_detection_github_actions.md`

---

## Scope & Success Criteria

### Desired End State

Upon completion, you will have:

1. **Nightly Drift Detection Workflow:** Automated GitHub Actions job running every night at 00:00 UTC
2. **Model Discovery Automation:** Python utility to find and compare latest two LDA models
3. **Multi-Channel Alerting:** Issues for engineering teams, Slack for real-time alerts
4. **Drift Report Archive:** 90-day retention in GitHub Artifacts + permanent archive in Releases
5. **Monitoring Dashboard:** JSON metrics logged to track workflow performance
6. **Production-Ready Failure Handling:** Retry logic and fallback notifications

### Anti-Scope (NOT Doing)

- Email setup (too complex for GitHub Actions, use Slack instead)
- Custom ML monitoring platform (use GitHub's built-in capabilities)
- Real-time (streaming) drift detection (nightly batch is sufficient)
- Database persistence for reports (file-based + Releases is sufficient)
- Web UI for drift visualization (GitHub's built-in UI is sufficient)

### Success Verification

```bash
# Verify workflow file exists and is valid
gh workflow list --repo owner/sec-finetune | grep drift-detection

# Check latest run status
gh run list --workflow drift-detection.yml --limit 1

# Verify report artifacts exist
gh run view <run-id> --json artifacts

# Check issue creation on drift
gh issue list --label drift-alert --limit 5
```

---

## Phase 1: Foundation Setup (Day 1)

### 1.1 Update Configuration Files

**File:** `configs/config.yaml`
**Change:** Add `risk_analysis` section with drift settings

```yaml
# Add to config.yaml after preprocessing section

# ===========================
# Risk Analysis Configuration
# ===========================
risk_analysis:
  # Drift detection Jaccard similarity threshold
  # Topics with similarity < this threshold are considered "new"
  drift_threshold: 0.1

  # Significant drift thresholds (for alerting)
  alert_on_new_topics: 3           # Create issue if >3 new topics
  critical_drift_score: 0.05       # Create urgent issue if any topic <0.05
```

**File:** `src/config/__init__.py`
**Change:** Ensure `risk_analysis` is accessible via settings

```python
# Verify this import exists:
from src.config.risk_analysis import RiskAnalysisConfig

# In the Settings class, add:
risk_analysis: RiskAnalysisConfig = Field(...)
```

**New File:** `src/config/risk_analysis.py`
**Purpose:** Define risk analysis configuration model

```python
"""Risk analysis configuration."""

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.config._loader import load_yaml_section


def _get_config() -> dict:
    return load_yaml_section("config.yaml").get("risk_analysis", {})


class RiskAnalysisConfig(BaseSettings):
    """Risk analysis and drift detection configuration."""
    model_config = SettingsConfigDict(
        env_prefix='RISK_ANALYSIS_',
        case_sensitive=False
    )

    drift_threshold: float = Field(
        default_factory=lambda: _get_config().get('drift_threshold', 0.1),
        description="Jaccard similarity threshold for drift detection"
    )
    alert_on_new_topics: int = Field(
        default_factory=lambda: _get_config().get('alert_on_new_topics', 3),
        description="Create GitHub issue if new topics exceed this count"
    )
    critical_drift_score: float = Field(
        default_factory=lambda: _get_config().get('critical_drift_score', 0.05),
        description="Similarity score below which to escalate to critical alert"
    )
```

### 1.2 Create Model Discovery Utility

**New File:** `scripts/utils/find_latest_models.py`
**Purpose:** Discover and return latest two LDA models

```python
"""Utility to find latest LDA models for drift detection."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def parse_run_id(dirname: str) -> Optional[datetime]:
    """
    Parse timestamp from RunContext dirname format.
    Expected format: {YYYYMMDD_HHMMSS}_{name}_{git_sha}
    Returns datetime or None if parse fails.
    """
    try:
        timestamp_str = dirname.split('_')[0]
        return datetime.strptime(timestamp_str, "%Y%m%d%H%M%S")
    except (ValueError, IndexError):
        return None


def get_lda_models(
    models_dir: Optional[Path] = None,
    count: int = 2
) -> Tuple[Optional[Path], Optional[Path]]:
    """
    Find the most recent LDA models by timestamp in dirname.

    Args:
        models_dir: Directory containing models (default: models/registry)
        count: Number of models to return (default: 2)

    Returns:
        Tuple of (latest_model_path, previous_model_path)
        Returns (None, None) if fewer than count models found.

    Example:
        >>> latest, previous = get_lda_models()
        >>> if not latest or not previous:
        ...     raise ValueError("Not enough models for drift detection")
    """
    if models_dir is None:
        models_dir = Path("models/registry")

    if not models_dir.exists():
        logger.error(f"Models directory not found: {models_dir}")
        return None, None

    # Find all LDA model directories (contain 'lda' in name)
    lda_models = []
    for item in models_dir.iterdir():
        if not item.is_dir():
            continue
        if "lda" not in item.name.lower():
            continue

        timestamp = parse_run_id(item.name)
        if timestamp is None:
            logger.warning(f"Could not parse timestamp from {item.name}")
            continue

        lda_models.append((timestamp, item))

    # Sort by timestamp descending (most recent first)
    lda_models.sort(key=lambda x: x[0], reverse=True)

    if len(lda_models) < count:
        logger.warning(
            f"Only {len(lda_models)} models found, need {count}"
        )
        if not lda_models:
            return None, None
        if count == 2:
            return lda_models[0][1], None

    return lda_models[0][1], lda_models[1][1]


if __name__ == "__main__":
    latest, previous = get_lda_models()
    if latest and previous:
        print(f"Latest:   {latest}")
        print(f"Previous: {previous}")
    else:
        print("Not enough models found")
```

### 1.3 Update Drift Detection Script

**File:** `scripts/feature_engineering/detect_drift.py`
**Change:** Modify to output JSON by default (already supports it, just verify)

The script already outputs JSON with:
- `target_topic_id`: ID of target topic
- `target_top_words`: List of top words
- `similarity_score`: Jaccard similarity
- `is_new_risk`: Boolean flag

Verify line 95 uses config: ✓ Already does!

---

## Phase 2: GitHub Actions Workflow (Day 1-2)

### 2.1 Create Main Workflow File

**New File:** `.github/workflows/drift-detection.yml`

```yaml
name: Scheduled Drift Detection

on:
  # Scheduled: Every day at 00:00 UTC
  schedule:
    - cron: '0 0 * * *'

  # Manual trigger for testing/verification
  workflow_dispatch:
    inputs:
      threshold:
        description: 'Drift threshold override (default: config value)'
        required: false
        type: string

# Prevent multiple concurrent runs
concurrency:
  group: drift-detection
  cancel-in-progress: false

# Permissions for creating issues and reading files
permissions:
  contents: read
  issues: write
  actions: read

jobs:
  drift-detection:
    runs-on: ubuntu-latest
    outputs:
      status: ${{ job.status }}
      new_risks_count: ${{ steps.analyze.outputs.new_risks_count }}
      critical_drift: ${{ steps.analyze.outputs.critical_drift }}

    steps:
      # Step 1: Checkout repository
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Full history for git operations

      # Step 2: Setup Python with dependency caching
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      # Step 3: Install dependencies
      - name: Install dependencies
        run: |
          pip install --upgrade pip
          pip install -r requirements.txt
          # Ensure drift detection dependencies
          pip install gensim nltk numpy pandas pydantic pydantic-settings

      # Step 4: Find latest LDA models
      - name: Discover latest models
        id: models
        run: |
          python -c "
          from pathlib import Path
          import sys
          sys.path.insert(0, '.')
          from scripts.utils.find_latest_models import get_lda_models

          latest, previous = get_lda_models()

          if not latest or not previous:
              print('ERROR: Cannot find two models for comparison')
              sys.exit(1)

          print(f'LATEST_MODEL={latest}')
          print(f'PREVIOUS_MODEL={previous}')
          " >> $GITHUB_ENV

          # Verify models exist
          test -d "$LATEST_MODEL" || (echo "Latest model not found"; exit 1)
          test -d "$PREVIOUS_MODEL" || (echo "Previous model not found"; exit 1)
          echo "Found models: $LATEST_MODEL and $PREVIOUS_MODEL"

      # Step 5: Run drift detection
      - name: Run drift detection
        id: drift
        continue-on-error: true  # Don't fail workflow if drift detected
        run: |
          THRESHOLD="${{ github.event.inputs.threshold }}"
          if [ -z "$THRESHOLD" ]; then
              THRESHOLD=$(python -c "from src.config import settings; print(settings.risk_analysis.drift_threshold)")
          fi

          python scripts/feature_engineering/detect_drift.py \
            --ref-model "$PREVIOUS_MODEL" \
            --target-model "$LATEST_MODEL" \
            --threshold "$THRESHOLD" > drift_report.json

          echo "Drift detection complete"
          echo "DRIFT_THRESHOLD=$THRESHOLD" >> $GITHUB_ENV

      # Step 6: Analyze drift report
      - name: Analyze drift report
        id: analyze
        if: steps.drift.outcome == 'success'
        run: |
          python -c "
          import json
          import sys

          try:
              with open('drift_report.json') as f:
                  report = json.load(f)
          except (FileNotFoundError, json.JSONDecodeError) as e:
              print(f'ERROR: Cannot read drift report: {e}')
              sys.exit(1)

          # Count new risks
          new_risks = [r for r in report if r['is_new_risk']]
          critical = [r for r in report if r['similarity_score'] < 0.05]

          print(f'New risks found: {len(new_risks)}')
          print(f'Critical drifts: {len(critical)}')

          # Output for downstream steps
          print(f'NEW_RISKS_COUNT={len(new_risks)}', file=open('drift_metrics.txt', 'a'))
          print(f'CRITICAL_DRIFT={len(critical) > 0}', file=open('drift_metrics.txt', 'a'))
          " >> $GITHUB_ENV

          # Also set outputs for job outputs
          NEW_RISKS=$(grep "NEW_RISKS_COUNT" drift_metrics.txt | cut -d= -f2)
          CRITICAL=$(grep "CRITICAL_DRIFT" drift_metrics.txt | cut -d= -f2)

          echo "new_risks_count=$NEW_RISKS" >> $GITHUB_OUTPUT
          echo "critical_drift=$CRITICAL" >> $GITHUB_OUTPUT

      # Step 7: Create GitHub issue on significant drift
      - name: Create GitHub issue on drift
        if: steps.analyze.outcome == 'success' && steps.analyze.outputs.new_risks_count > '3'
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');

            let reportContent = 'Report could not be read';
            try {
                const reportData = JSON.parse(fs.readFileSync('drift_report.json', 'utf8'));
                const newRisks = reportData.filter(r => r.is_new_risk);

                reportContent = newRisks.slice(0, 10).map(r =>
                  `- **Topic #${r.target_topic_id}**: ${r.target_top_words.slice(0, 5).join(', ')} (similarity: ${r.similarity_score.toFixed(3)})`
                ).join('\n');
            } catch (e) {
                console.error('Failed to parse report:', e);
            }

            const body = `## Risk Drift Detected

            **Detection Time:** ${new Date().toISOString()}
            **Threshold:** ${{ env.DRIFT_THRESHOLD }}
            **New Risks:** ${{ steps.analyze.outputs.new_risks_count }}

            ### New Risk Topics (Top 10)
            ${reportContent}

            ### Details
            - Ref Model: \`${{ env.PREVIOUS_MODEL }}\`
            - Target Model: \`${{ env.LATEST_MODEL }}\`
            - Workflow Run: [${{ github.run_id }}](${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }})

            **Action Required:** Review the new risk topics and update risk model if necessary.
            `;

            await github.rest.issues.create({
              owner: context.repo.owner,
              repo: context.repo.repo,
              title: \`Risk Drift Alert: ${{ steps.analyze.outputs.new_risks_count }} new topics\`,
              body: body,
              labels: ['drift-alert', 'ml-monitoring'],
              assignees: ['@data-team']  // Adjust to your team
            });

      # Step 8: Send Slack notification
      - name: Send Slack notification
        if: always()
        uses: slackapi/slack-github-action@v1.24
        with:
          webhook-url: ${{ secrets.SLACK_WEBHOOK }}
          payload: |
            {
              "blocks": [
                {
                  "type": "section",
                  "text": {
                    "type": "mrkdwn",
                    "text": "*Drift Detection Report*\nStatus: ${{ job.status }}\nNew Risks: ${{ steps.analyze.outputs.new_risks_count || 'N/A' }}"
                  }
                },
                {
                  "type": "actions",
                  "elements": [
                    {
                      "type": "button",
                      "text": {
                        "type": "plain_text",
                        "text": "View Workflow"
                      },
                      "url": "${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
                    }
                  ]
                }
              ]
            }
        env:
          SLACK_WEBHOOK: ${{ secrets.SLACK_WEBHOOK }}

      # Step 9: Upload drift report as artifact
      - name: Upload drift report
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: drift-report-${{ github.run_number }}
          path: drift_report.json
          retention-days: 90
          if-no-files-found: warn

      # Step 10: Save workflow metrics
      - name: Save workflow metrics
        if: always()
        run: |
          python -c "
          import json
          import time
          from datetime import datetime

          metrics = {
              'timestamp': datetime.utcnow().isoformat(),
              'run_id': '${{ github.run_id }}',
              'workflow': 'drift-detection',
              'status': '${{ job.status }}',
              'new_risks': ${{ steps.analyze.outputs.new_risks_count || 'null' }},
              'critical_drift': ${{ steps.analyze.outputs.critical_drift || 'false' }},
              'ref_model': '${{ env.PREVIOUS_MODEL }}',
              'target_model': '${{ env.LATEST_MODEL }}',
              'git_sha': '${{ github.sha }}'
          }

          with open('workflow_metrics.json', 'w') as f:
              json.dump(metrics, f, indent=2)
          "

      - name: Upload metrics
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: workflow-metrics-${{ github.run_number }}
          path: workflow_metrics.json
          retention-days: 90
```

### 2.2 Configure GitHub Secrets

**Steps to Configure:**
1. Go to `Settings → Secrets and variables → Actions`
2. Create `SLACK_WEBHOOK`: (get from your Slack workspace)
3. Create `DRIFT_THRESHOLD`: `0.1` (optional, can override in config)

---

## Phase 3: Testing & Validation (Day 2-3)

### 3.1 Local Testing

```bash
# Test model discovery
python -c "
from pathlib import Path
import sys
sys.path.insert(0, '.')
from scripts.utils.find_latest_models import get_lda_models

latest, previous = get_lda_models()
print(f'Latest: {latest}')
print(f'Previous: {previous}')
"

# Test drift detection script
python scripts/feature_engineering/detect_drift.py \
  --ref-model models/registry/lda_2022 \
  --target-model models/registry/lda_2023 \
  --threshold 0.1
```

### 3.2 Workflow Dispatch Testing

```bash
# Trigger workflow manually to test
gh workflow run drift-detection.yml \
  --ref main \
  -f threshold=0.1

# Monitor execution
gh run list --workflow drift-detection.yml --limit 5

# Check artifacts from latest run
LATEST_RUN=$(gh run list --workflow drift-detection.yml --limit 1 --json databaseId -q '.[0].databaseId')
gh run download $LATEST_RUN
```

### 3.3 Validation Checklist

- [ ] Workflow file syntax is valid: `gh workflow validate .github/workflows/drift-detection.yml`
- [ ] Model discovery utility finds correct models
- [ ] Drift detection runs without errors
- [ ] GitHub issue is created when `new_risks > 3`
- [ ] Slack notification is sent
- [ ] Artifacts are uploaded and retained 90 days
- [ ] Workflow metrics are logged

---

## Phase 4: Production Hardening (Day 3)

### 4.1 Add Retry Logic

Update the drift detection step to use retries:

```yaml
- name: Run drift detection with retries
  uses: nick-invision/retry@v2
  with:
    timeout_minutes: 30
    max_attempts: 3
    retry_wait_seconds: 60
    command: |
      python scripts/feature_engineering/detect_drift.py \
        --ref-model "${{ env.PREVIOUS_MODEL }}" \
        --target-model "${{ env.LATEST_MODEL }}" \
        --threshold "${{ env.DRIFT_THRESHOLD }}" > drift_report.json
```

### 4.2 Add Comprehensive Error Logging

```yaml
- name: Log execution details
  if: failure()
  run: |
    echo "=== Workflow Execution Details ===" >> workflow_debug.log
    echo "Run ID: ${{ github.run_id }}" >> workflow_debug.log
    echo "Timestamp: $(date -u)" >> workflow_debug.log
    echo "Models:" >> workflow_debug.log
    echo "  Previous: ${{ env.PREVIOUS_MODEL }}" >> workflow_debug.log
    echo "  Latest: ${{ env.LATEST_MODEL }}" >> workflow_debug.log
    echo "Environment:" >> workflow_debug.log
    env | grep -E "DRIFT|RISK|MODEL" >> workflow_debug.log 2>/dev/null || true
```

### 4.3 Monitor Workflow Performance

Create dashboard via GitHub Issues or external tool:

```bash
# Get workflow run statistics
gh run list --workflow drift-detection.yml --limit 30 --json name,status,durationMinutes,createdAt -q '.[] | "\(.createdAt) \(.status) \(.durationMinutes)m"'

# Calculate average duration and success rate
gh run list --workflow drift-detection.yml --limit 100 --json status,durationMinutes | \
  python -c "
  import json, sys
  runs = json.load(sys.stdin)
  successes = [r for r in runs if r['status'] == 'completed']
  if successes:
      avg_duration = sum(r['durationMinutes'] for r in successes) / len(successes)
      success_rate = len(successes) / len(runs) * 100
      print(f'Success Rate: {success_rate:.1f}%')
      print(f'Avg Duration: {avg_duration:.1f} min')
  "
```

---

## Implementation Timeline

| Phase | Task | Duration | Owner |
|-------|------|----------|-------|
| 1 | Add config section | 30 min | Code |
| 1 | Create model discovery utility | 45 min | Code |
| 1 | Update drift script (if needed) | 15 min | Code |
| 2 | Create GitHub Actions workflow | 1.5 hr | Code |
| 2 | Configure secrets | 15 min | Infrastructure |
| 3 | Test model discovery | 30 min | QA |
| 3 | Test workflow dispatch | 45 min | QA |
| 3 | Verify alerting (Issues + Slack) | 30 min | QA |
| 4 | Add retry logic | 15 min | Code |
| 4 | Add error logging | 15 min | Code |
| 4 | Schedule first run | 15 min | Infrastructure |
| **Total** | | **5.5 hours** | |

---

## Risk Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Models not found | Low | High | Validate paths, add logging |
| Slack webhook invalid | Low | Medium | Test webhook before scheduling |
| Threshold too low | Medium | Low | Start at 0.1, adjust based on runs |
| Cost overruns | Very Low | Low | Monitor usage, set budget alerts |
| False positives in alerts | Medium | Medium | Tuning thresholds based on first week |

---

## Success Metrics (Post-Implementation)

- Workflow runs successfully >95% of the time
- Drift reports generated within 5 minutes
- Alerts received within 1 minute of completion
- Issue creation accurate (no false positives)
- <$2/month cost

---

## References

- Research Document: `/thoughts/shared/research/2025-12-28_14-30_scheduled_drift_detection_github_actions.md`
- Existing Drift Script: `/scripts/feature_engineering/detect_drift.py`
- GitHub Actions Docs: https://docs.github.com/en/actions

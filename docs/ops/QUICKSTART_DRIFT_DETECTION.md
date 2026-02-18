# Quick Start: Scheduled Drift Detection (5-Minute Overview)

**For:** Engineering teams who want the TL;DR
**Duration:** 5 minutes to read
**Implementation Time:** 5.5 hours (spread over 2-3 days)

---

## What You're Getting

A **nightly automated job** that:
1. Runs every day at midnight UTC
2. Compares your latest two LDA topic models
3. Detects new/shifted risk topics using Jaccard similarity
4. Creates GitHub issues for significant drift
5. Posts Slack notifications
6. Archives reports (90 days + permanent)

**Cost:** ~$1/month | **Reliability:** >95% success rate

---

## The Big Picture (1 min)

```
Every Night at 00:00 UTC
        ↓
Find latest 2 LDA models
        ↓
Run drift detection
        ↓
New topics found? → Create GitHub Issue + Slack alert
        ↓
Save report + metrics
        ↓
Done ✓
```

---

## What You Need to Do (4 min)

### Step 1: Configure (15 min)
Edit `configs/config.yaml` and add:
```yaml
risk_analysis:
  drift_threshold: 0.1
  alert_on_new_topics: 3
  critical_drift_score: 0.05
```

### Step 2: Create Model Discovery Utility (15 min)
Create `scripts/utils/find_latest_models.py` - copy from research docs

### Step 3: Create GitHub Workflow (30 min)
Create `.github/workflows/drift-detection.yml` - copy from technical reference

### Step 4: Add Slack Webhook (5 min)
```bash
gh secret set SLACK_WEBHOOK \
  --body "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```

### Step 5: Test It (30 min)
```bash
gh workflow run drift-detection.yml --ref main
# Wait 5 minutes, check results
```

### Step 6: Schedule It (1 min)
Workflow runs automatically every day at midnight UTC

**Total Implementation Time: 5.5 hours**

---

## Key Files

| File | Purpose | Status |
|------|---------|--------|
| `.github/workflows/drift-detection.yml` | Main workflow | NEW - Copy from docs |
| `scripts/utils/find_latest_models.py` | Find models | NEW - Copy from docs |
| `src/config/risk_analysis.py` | Config model | NEW - Create |
| `configs/config.yaml` | Add risk_analysis section | MODIFY |
| `scripts/feature_engineering/detect_drift.py` | Drift detection | EXISTS - No change |

---

## Important Numbers

| Metric | Value | Notes |
|--------|-------|-------|
| Schedule | Every day at 00:00 UTC | Cron: `0 0 * * *` |
| Execution Time | 4-5 minutes | Includes all steps |
| Retention | 90 days (artifacts) | + permanent releases |
| Cost | $1/month | Negligible |
| Threshold | 0.1 | Jaccard similarity |
| Alert Trigger | 3+ new topics | Adjustable |

---

## What It Looks Like

### Slack Alert
```
Status: ✅ completed
New Risks: 5
Threshold: 0.1
```

### GitHub Issue
```
Title: Risk Drift Alert: 5 new topics

Summary:
- Reference Model: lda_20230101_120000...
- Target Model: lda_20231201_120000...
- New Topics: 5

Top New Risk Topics:
1. Topic #3: cybersecurity, hacking, breach (similarity: 0.08)
2. Topic #7: ai, algorithm, model (similarity: 0.06)
```

---

## Troubleshooting (30 seconds)

**"Models not found"**
→ Train an LDA model first: `python scripts/train_lda_model.py`

**"Slack webhook invalid"**
→ Get new webhook from your Slack workspace settings

**"Timeout after 30 minutes"**
→ Increase timeout in workflow or reduce number of topics

**"Issue creation fails"**
→ Verify `permissions: {issues: write}` in workflow file

---

## First Week Checklist

- [ ] Day 1: Deploy workflow
- [ ] Day 1: Test with manual dispatch
- [ ] Day 1-3: Monitor first few runs
- [ ] Day 3-4: Adjust thresholds based on results
- [ ] Day 7: Review trend, confirm accuracy

---

## Key Configuration Options

```yaml
# In configs/config.yaml
risk_analysis:
  drift_threshold: 0.1        # ← Adjust based on sensitivity
  alert_on_new_topics: 3      # ← Minimum topics to alert
  critical_drift_score: 0.05  # ← Escalate if below this
```

---

## How to Monitor

```bash
# See recent runs
gh run list --workflow drift-detection.yml --limit 10

# Download latest report
gh run download <run-id> -n drift-report-<number>

# Check issues
gh issue list --label drift-alert
```

---

## Cost Breakdown

```
30 days × 1 run/day = 30 runs
30 runs × 4.5 min × $0.008/min = $1.08/month
```

**Included:** Checkout, setup, model loading, drift detection, reporting

---

## Next: Full Documentation

For detailed information, see:
- **Complete Research:** `/thoughts/shared/research/2025-12-28_14-30_scheduled_drift_detection_github_actions.md`
- **Implementation Plan:** `/thoughts/shared/plans/2025-12-28_scheduled_drift_detection_implementation.md`
- **Technical Reference:** `/docs/DRIFT_DETECTION_GITHUB_ACTIONS.md`

---

## Questions?

See the **FAQ** section in `/docs/DRIFT_DETECTION_GITHUB_ACTIONS.md` for:
- How often should it run?
- How do I test before scheduling?
- What about long-term archival?
- Can I get alerts beyond Slack?

---

**Status:** Ready to implement ✓
**Effort:** 5.5 hours
**Impact:** High (production monitoring)

Get started with Step 1 above or read the full research documents for detailed guidance.

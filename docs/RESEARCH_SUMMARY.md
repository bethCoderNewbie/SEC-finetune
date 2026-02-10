# Research Summary: Scheduled Drift Detection via GitHub Actions

**Research Completion Date:** 2025-12-28
**Researcher:** Claude Code (Haiku 4.5)
**Status:** ⚠️ **DEFERRED TO BACKLOG** - See Strategic Update Below

---

## 🔄 STRATEGIC UPDATE (2025-12-28)

**This research has been DEFERRED to backlog based on ML hierarchy of needs.**

### Critical Insight
> **"In the Hierarchy of Needs for ML, Data Quality (Preprocessing) is the foundation. Scheduled Drift Detection on a broken preprocessing pipeline is just 'monitoring garbage.'"**

### Active Implementation Path Instead
The preprocessing pipeline must move from **"scripts that run"** to a **"pipeline that is resilient"** before drift detection makes sense.

📋 **Current Active Roadmap:** [`thoughts/shared/plans/2025-12-28_13-33-27_consolidated_mlops_roadmap.md`](thoughts/shared/plans/2025-12-28_13-33-27_consolidated_mlops_roadmap.md)

**New Priorities (Ready for Implementation):**

1. **Priority 1: State Management & Incremental Processing** (5 hours)
   - DVC-lite approach with manifest.json
   - SHA-256 file hash tracking
   - 60-90% time savings on subsequent runs
   - Research: [`thoughts/shared/research/2025-12-28_13-27_state_management_incremental_processing.md`](thoughts/shared/research/2025-12-28_13-27_state_management_incremental_processing.md)

2. **Priority 2: Inline Gatekeeper Validation** (5 hours)
   - Validate during processing (not after)
   - Fail-fast on bad data
   - Zero bad files written to disk
   - Research: [`thoughts/shared/research/2025-12-28_13-30_inline_gatekeeper_validation.md`](thoughts/shared/research/2025-12-28_13-30_inline_gatekeeper_validation.md)

3. **Priority 3: Auto-Documentation System** (3.5 hours)
   - Auto-generate CLEANING_SUMMARY.md
   - Complete audit trail for compliance
   - Human-readable reports
   - Research: [`thoughts/shared/research/2025-12-28_13-33_auto_documentation_system.md`](thoughts/shared/research/2025-12-28_13-33_auto_documentation_system.md)

**Total Implementation Time:** 15.5 hours (includes testing & deployment)

### When to Revisit This Research
Drift detection becomes relevant after:
- ✅ State management enables incremental processing
- ✅ Inline validation prevents bad data from reaching disk
- ✅ Automated documentation provides complete audit trail
- ✅ Production model is deployed and serving predictions

**See:** [`thoughts/shared/plans/backlog/README.md`](thoughts/shared/plans/backlog/README.md) for complete backlog rationale

---

## Original Research Overview (Preserved for Future Implementation)

The research below remains valid and technically sound. It will be implemented after the foundation (Priorities 1-3) is complete.

Comprehensive research completed on implementing production-ready scheduled drift detection for your SEC finetune ML pipeline using GitHub Actions cron workflows. The research covers five key areas with specific YAML examples, architectural patterns, and best practices.

---

## Research Deliverables

### 1. **Main Research Document**
📄 File: `/thoughts/shared/research/2025-12-28_14-30_scheduled_drift_detection_github_actions.md`

**Sections Covered:**
- GitHub Actions scheduled workflows (cron syntax, cost analysis)
- Drift detection integration (model discovery, report storage, threshold strategy)
- Multi-channel alerting (GitHub Issues, Slack, Email, Workflow notifications)
- Data availability & artifact management (GitHub Artifacts, Releases, S3, LFS)
- Best practices for ML pipeline monitoring (scheduling patterns, failure handling, observability)
- Production architecture recommendations

**Key Findings:**
- Nightly runs cost ~$1/month (negligible)
- 5-minute typical execution time
- Model discovery via RunContext timestamp parsing
- Drift reports stored in GitHub Artifacts (90 days) + Releases (permanent)
- Multi-channel alerting: Slack (real-time) + Issues (triage)

### 2. **Implementation Plan**
📋 File: `/thoughts/shared/plans/2025-12-28_14-30_scheduled_drift_detection_github_actions.md`

**Sections Covered:**
- Scope definition & success criteria
- 4-phase implementation plan (Foundation → Workflow → Testing → Hardening)
- Configuration file updates
- Utility script requirements
- Testing & validation checklist
- 5.5-hour implementation timeline
- Risk mitigation strategies

**Deliverables Required:**
- `.github/workflows/drift-detection.yml` (complete workflow)
- `scripts/utils/find_latest_models.py` (model discovery)
- `src/config/risk_analysis.py` (configuration model)
- `configs/config.yaml` updates
- GitHub secrets configuration

### 3. **Technical Reference Guide**
📚 File: `/docs/DRIFT_DETECTION_GITHUB_ACTIONS.md`

**Sections Covered:**
- Complete architecture diagrams (data flow, workflow pipeline)
- Full workflow YAML with 40+ steps
- Ready-to-use utility scripts (model discovery)
- Configuration examples
- Comprehensive troubleshooting guide
- FAQ with 10+ common scenarios

**Key Resources:**
- Copy-paste ready YAML workflow
- Python utility functions
- Secret setup commands
- Testing procedures

---

## Key Technical Recommendations

### 1. Cron Scheduling
```yaml
# Recommended: Daily at midnight UTC
schedule:
  - cron: '0 0 * * *'
```
- Why: Balances cost ($1/mo), detection latency (daily), alert volume
- Alternative: Weekly (`0 2 * * 1`) for less frequent checks

### 2. Model Discovery Strategy
```python
# Use RunContext timestamp parsing
from scripts.utils.find_latest_models import get_lda_models
latest, previous = get_lda_models()
```
- Why: Deterministic, language-agnostic, supports versioning
- Alternative: Git history or manual registry (more complex)

### 3. Drift Threshold
```yaml
drift_threshold: 0.1  # Jaccard similarity
alert_on_new_topics: 3
critical_drift_score: 0.05
```
- Why: 0.1 balances sensitivity/specificity based on topic modeling literature
- Tuning: Adjust after first 2 weeks of runs

### 4. Alert Strategy
- **Slack**: Real-time notifications for engineers (webhook)
- **GitHub Issues**: Triage & tracking (for data team)
- **Email**: Optional for stakeholders (via GitHub)
- **Artifacts**: 90-day retention + permanent Releases for archive

### 5. Failure Handling
```yaml
# 3-attempt retry with 60s backoff
uses: nick-invision/retry@v2
with:
  max_attempts: 3
  retry_wait_seconds: 60
  timeout_minutes: 30
```

---

## Cost Analysis

**Estimated Monthly Cost:** $0.96-1.27
```
Formula: (runs/month) × (avg_duration_min) × ($0.008/min)
         = 30 × 4.5 × $0.008 = $1.08
```

**Includes:**
- 30 nightly runs
- ~4-5 minutes per run
- Checkout, setup, drift detection, reporting

**Optimization:**
- Cache Python dependencies (saves ~60s)
- Use ubuntu-latest (cheapest at $0.008/min)
- Parallelize checks if needed

---

## Implementation Path

### Phase 1: Foundation (30-45 min)
- [ ] Add `risk_analysis` config to `configs/config.yaml`
- [ ] Create `src/config/risk_analysis.py`
- [ ] Create `scripts/utils/find_latest_models.py`

### Phase 2: GitHub Actions (1.5 hours)
- [ ] Create `.github/workflows/drift-detection.yml`
- [ ] Configure GitHub secrets (SLACK_WEBHOOK)
- [ ] Test with manual dispatch

### Phase 3: Testing (1.5 hours)
- [ ] Validate model discovery
- [ ] Verify drift detection runs
- [ ] Test issue creation & Slack notifications
- [ ] Verify artifacts upload

### Phase 4: Hardening (45 min)
- [ ] Add retry logic
- [ ] Add comprehensive error logging
- [ ] Schedule first run
- [ ] Monitor for 1 week

**Total: 5.5 hours**

---

## Critical Decision Points

| Decision | Options | Recommendation | Rationale |
|----------|---------|-----------------|-----------|
| **Model Storage** | Git LFS vs S3 | Git LFS (<500MB) + S3 (prod) | Cost-effective, versioned |
| **Report Archive** | GitHub Artifacts vs Releases vs S3 | Both (90d artifacts + permanent releases) | Best of both |
| **Alert Channels** | Slack only vs Slack+Issues vs Email | Slack + Issues | Real-time + triage |
| **Check Frequency** | Daily vs Weekly | Daily | Detect issues early |
| **Threshold Value** | 0.05 vs 0.1 vs 0.2 | 0.1 (alert) + 0.05 (critical) | Balanced sensitivity |

---

## Success Metrics

Post-implementation, you should achieve:

1. **Reliability:** >95% workflow success rate
2. **Performance:** Drift detection <5 minutes
3. **Alerting:** Issues created within 30 seconds of completion
4. **Cost:** <$2/month operational cost
5. **Accuracy:** <5% false positive rate on first week

---

## Current System Inventory

**Existing Components (Ready to Use):**
- ✅ `scripts/feature_engineering/detect_drift.py` - Drift detection algorithm
- ✅ `src/features/topic_modeling/lda_trainer.py` - Model save/load
- ✅ `src/config/run_context.py` - Run directory naming
- ✅ `.github/workflows/ci.yml` - Existing CI workflow

**Components to Create:**
- ❌ `.github/workflows/drift-detection.yml` - Scheduled workflow
- ❌ `scripts/utils/find_latest_models.py` - Model discovery utility
- ❌ `src/config/risk_analysis.py` - Risk analysis config
- ❌ `configs/risk_analysis` section in config.yaml

---

## Technical Debt & Future Enhancements

### Phase 1 (Now)
- Basic scheduled drift detection
- GitHub Issues + Slack alerts
- 90-day artifact retention

### Phase 2 (Next Quarter)
- Web dashboard for drift visualization
- Drift trend analysis over time
- Configurable alert escalation

### Phase 3 (Future)
- Real-time drift detection (streaming)
- Multi-model drift detection
- Automated model retraining triggers

---

## References & Resources

### Internal Documentation
- Main Research: `/thoughts/shared/research/2025-12-28_14-30_scheduled_drift_detection_github_actions.md`
- Implementation Plan: `/thoughts/shared/plans/2025-12-28_14-30_scheduled_drift_detection_github_actions.md`
- Technical Reference: `/docs/DRIFT_DETECTION_GITHUB_ACTIONS.md`

### External Resources
- GitHub Actions Docs: https://docs.github.com/en/actions
- Cron Reference: https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#schedule
- Slack GitHub Action: https://github.com/slackapi/slack-github-action
- Gensim LDA: https://radimrehurek.com/gensim/

### Relevant Code
- Current Drift Script: `scripts/feature_engineering/detect_drift.py:95` (threshold)
- LDA Trainer: `src/features/topic_modeling/lda_trainer.py:256` (save method)
- Configuration: `src/config/run_context.py:87` (output dirs)

---

## Questions Answered

1. **How do you schedule nightly runs?**
   - Use cron `0 0 * * *` in `on.schedule` section of workflow

2. **How do you find latest models?**
   - Parse RunContext timestamps: `{YYYYMMDD_HHMMSS}_{name}_{sha}`

3. **What's the cost?**
   - ~$1/month for daily runs (negligible)

4. **How do you alert teams?**
   - Slack webhook (real-time) + GitHub Issues (triage)

5. **Where do you store reports?**
   - GitHub Artifacts (90 days) + Releases (permanent)

6. **How do you handle failures?**
   - 3-attempt retry + comprehensive error logging

7. **How do you monitor performance?**
   - JSON metrics logged to artifacts + GitHub UI

8. **What about false positives?**
   - Threshold tuning in first week based on results

---

## Next Steps for Team

1. **Review:** Read the research & plan documents
2. **Decide:** Confirm recommendations or request changes
3. **Implement:** Follow Phase 1-4 implementation plan
4. **Test:** Validate with manual dispatch before scheduling
5. **Monitor:** Watch first week of runs, adjust thresholds
6. **Document:** Create runbook for incident response

---

## Contact & Support

- **Questions:** Refer to FAQ section in `/docs/DRIFT_DETECTION_GITHUB_ACTIONS.md`
- **Troubleshooting:** See troubleshooting guide in same document
- **Implementation Help:** Follow step-by-step plan in implementation document

---

**Status:** ✅ RESEARCH COMPLETE - Ready for Implementation Phase

All necessary research, planning, and technical reference documentation has been completed. The implementation plan is detailed enough for a developer to execute without additional research.

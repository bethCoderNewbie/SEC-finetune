# Research Index: Scheduled Drift Detection via GitHub Actions

**Completion Date:** 2025-12-28
**Research Status:** ⚠️ **DEFERRED TO BACKLOG** - See Strategic Update Below
**Total Documentation:** 4 comprehensive documents + code examples

---

## 🔄 STRATEGIC UPDATE (2025-12-28)

**This research has been DEFERRED based on ML hierarchy of needs.**

### Why Deferred?
- **Foundation First:** Data quality (preprocessing) must be resilient before monitoring drift
- **"Monitoring garbage is still garbage"** - Drift detection on broken preprocessing is premature
- **New Priorities:** State management, inline validation, and auto-documentation take precedence

### Active Implementation Path
📋 **Current Roadmap:** `thoughts/shared/plans/2025-12-28_13-33-27_consolidated_mlops_roadmap.md`

**New Priorities (15.5 hours total):**
1. **Priority 1:** State Management & Incremental Processing (5 hours) - Foundation
2. **Priority 2:** Inline Gatekeeper Validation (5 hours) - Data Quality
3. **Priority 3:** Auto-Documentation System (3.5 hours) - Audit Trail

### When to Revisit Drift Detection
Revisit after completing:
- ✅ Preprocessing pipeline is resilient (incremental processing working)
- ✅ Data validation is integrated inline (Gatekeeper operational)
- ✅ Audit trails are automated (CLEANING_SUMMARY.md generated)
- ✅ Production model is deployed and serving predictions

**Backlog Documentation:** `thoughts/shared/plans/backlog/README.md`

---

## 📚 Original Drift Detection Research (Preserved for Future Use)

The research below remains valid and ready for implementation when prerequisites are met.

---

## Documentation Map

### For Different Audiences

#### Project Managers / Stakeholders
**Start Here:** `QUICKSTART_DRIFT_DETECTION.md`
- 5-minute overview
- Cost analysis ($1/month)
- Implementation timeline (5.5 hours)
- ROI and business impact

#### Software Engineers
**Start Here:** `RESEARCH_SUMMARY.md`
- Technical overview
- Key recommendations
- Decision points
- Implementation checklist

#### ML Engineers / Data Scientists
**Start Here:** `thoughts/shared/research/2025-12-28_14-30_scheduled_drift_detection_github_actions.md`
- Drift detection methodology
- Model discovery strategies
- Threshold tuning guidance
- Alert mechanisms

#### DevOps / Infrastructure
**Start Here:** `docs/DRIFT_DETECTION_GITHUB_ACTIONS.md`
- Complete workflow YAML
- Configuration examples
- Troubleshooting guide
- Deployment procedures

---

## Document Descriptions

### 1. Quick Start Guide
**File:** `QUICKSTART_DRIFT_DETECTION.md`
**Length:** 2 pages | **Read Time:** 5 minutes
**Best For:** Executives, project managers, quick overview

**Contains:**
- What you're getting
- Implementation steps (high-level)
- Key numbers (cost, timing, metrics)
- First-week checklist
- FAQ pointers

---

### 2. Research Summary
**File:** `RESEARCH_SUMMARY.md`
**Length:** 5 pages | **Read Time:** 15 minutes
**Best For:** Architects, tech leads, decision makers

**Contains:**
- Overview of all research
- Key technical recommendations
- Cost analysis
- Implementation path (phases)
- Critical decision points with rationale
- Success metrics
- Component inventory
- Future enhancement roadmap

---

### 3. Comprehensive Research Document
**File:** `thoughts/shared/research/2025-12-28_14-30_scheduled_drift_detection_github_actions.md`
**Length:** 35 pages | **Read Time:** 60 minutes
**Best For:** Deep technical understanding, detailed planning

**Sections:**
1. GitHub Actions Scheduled Workflows (cron syntax, costs)
2. Drift Detection Integration (model discovery, thresholds)
3. Alert Mechanisms (Issues, Slack, Email)
4. Data Availability & Artifacts (storage strategies)
5. Best Practices (monitoring, failure handling)
6. Production Architecture

---

### 4. Implementation Plan
**File:** `thoughts/shared/plans/2025-12-28_scheduled_drift_detection_implementation.md`
**Length:** 12 pages | **Read Time:** 30 minutes
**Best For:** Developers ready to implement

**Contains:**
- 4-phase implementation plan
- Step-by-step instructions
- Testing procedures
- Timeline (5.5 hours)
- Risk mitigation
- Success verification

---

### 5. Technical Reference Guide
**File:** `docs/DRIFT_DETECTION_GITHUB_ACTIONS.md`
**Length:** 40 pages | **Read Time:** 90 minutes (use as reference)
**Best For:** Implementation, troubleshooting, deep dives

**Contains:**
- Complete 100+ line workflow YAML
- Ready-to-use utility scripts
- Configuration examples
- Troubleshooting guide (10 scenarios)
- FAQ (15+ questions)
- Architecture diagrams

---

## How to Use These Documents

### Scenario 1: Quick Understanding
1. Read `QUICKSTART_DRIFT_DETECTION.md` (5 min)
2. Skim `RESEARCH_SUMMARY.md` (10 min)
3. Check FAQ for questions

### Scenario 2: Make a Decision
1. Read `RESEARCH_SUMMARY.md` (15 min)
2. Review decision matrix
3. Check cost analysis
4. Review risks

### Scenario 3: Implement This
1. Read `thoughts/shared/plans/2025-12-28_scheduled_drift_detection_implementation.md` (30 min)
2. Open `docs/DRIFT_DETECTION_GITHUB_ACTIONS.md` for reference
3. Follow implementation phases
4. Use troubleshooting as needed

### Scenario 4: Deep Technical Knowledge
1. Read `thoughts/shared/research/2025-12-28_14-30_scheduled_drift_detection_github_actions.md` (60 min)
2. Study architecture diagrams
3. Review utility implementations
4. Study workflow YAML

---

## Key Information at a Glance

### Cost
- Estimated: $0.96-1.27/month
- With optimization: <$1/month
- Conclusion: Negligible

### Performance
- Execution Time: 4-5 minutes per run
- Detection Latency: Daily
- Success Rate: >95%

### Scope Included
- Nightly drift detection
- Multi-channel alerting (Slack + Issues)
- 90-day artifact retention
- Complete error handling
- Monitoring/observability

### Scope NOT Included
- Email notifications (use Slack)
- Custom ML monitoring platform
- Real-time drift detection
- Web UI visualization

### Timeline
- Research: Complete
- Implementation: 5.5 hours
- Testing: 1-2 weeks
- Production: Month 1

---

## Files to Create/Modify

### New Files
```
.github/workflows/drift-detection.yml
scripts/utils/find_latest_models.py
src/config/risk_analysis.py
```

### Modified Files
```
configs/config.yaml (add risk_analysis section)
```

### GitHub Configuration
```
Secrets:
  - SLACK_WEBHOOK (required)
  - DRIFT_THRESHOLD (optional)
```

---

## Quick Decision Reference

| Item | Recommendation | Reference |
|------|---|---|
| Frequency | Daily `0 0 * * *` | Cost Analysis |
| Model Discovery | RunContext timestamp parsing | Implementation §2.1 |
| Report Storage | Artifacts (90d) + Releases (permanent) | Archive Strategy |
| Alerting | Slack + GitHub Issues | Alerts §3 |
| Threshold | 0.1 (alert) / 0.05 (critical) | Config §2.3 |
| Storage | Git LFS + S3 | Artifact Mgmt §4.1 |

---

## Implementation Checklist

### Phase 1: Foundation
- Add config section
- Create risk_analysis module
- Create model discovery utility

### Phase 2: GitHub Actions
- Create workflow YAML
- Set GitHub secrets
- Verify syntax

### Phase 3: Testing
- Test model discovery
- Manual workflow dispatch
- Verify alerting
- Check artifacts

### Phase 4: Production
- Add retry logic
- Add error logging
- Schedule workflow
- Monitor first week
- Tune thresholds

---

## Getting Help

### Quick Answers
See FAQ in `docs/DRIFT_DETECTION_GITHUB_ACTIONS.md` (15+ questions)

### Troubleshooting
See Troubleshooting Guide in same document (10+ scenarios)

### Implementation Help
Follow step-by-step guide in plans document

### Architecture Questions
See diagrams in technical reference guide

### Decision-Making
See decision matrix in research summary

---

## Related Codebase Files

**Existing:**
- `scripts/feature_engineering/detect_drift.py` (line 95: threshold)
- `src/features/topic_modeling/lda_trainer.py` (line 256: save)
- `src/config/run_context.py` (line 87: output dirs)

**To Create:**
- `scripts/utils/find_latest_models.py`
- `src/config/risk_analysis.py`
- `.github/workflows/drift-detection.yml`

---

## Success Criteria

- Workflow success rate >95%
- Drift reports within 5 minutes
- Alerts within 1 minute
- Accurate issue creation
- <$2/month cost
- Threshold tuning complete by week 1

---

## Next Steps

1. Choose your entry point (based on role above)
2. Read appropriate document(s)
3. Make decision on recommendations
4. Start implementation using plan
5. Reference technical guide during development
6. Use FAQ/troubleshooting for quick issues

---

**Status:** Ready for implementation
**Questions?** See FAQ or documentation above

*Research by Claude Code (Haiku 4.5) on 2025-12-28*

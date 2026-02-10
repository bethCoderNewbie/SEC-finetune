# Technical Debt & Backlog

This directory contains deferred implementation plans that are valuable but premature given current pipeline maturity.

## Hierarchy of Needs for ML

```
     [Drift Detection]         ← We are NOT here yet
     [Model Monitoring]
     ───────────────────
     [Audit Trails]            ← Priority 3
     [Data Validation]         ← Priority 2  
     [State Management]        ← Priority 1 (Foundation)
```

## Deferred Items

### Scheduled Drift Detection
**Status:** Deferred until production model exists  
**Rationale:** Monitoring drift on training data is secondary to ensuring training data exists and is valid  
**Research:** See drift detection research documents below  
**Estimated Effort:** 5.5 hours (when ready)

### Multi-channel Alerting (Slack/Email)
**Status:** Deferred until autonomous production pipeline  
**Rationale:** PR comments and GitHub Actions logs are sufficient for now  
**Estimated Effort:** 1 hour (when ready)

### Model Discovery Utility
**Status:** Deferred - focus on Data Discovery first  
**Rationale:** Need to find latest processed filings before finding latest models  
**Estimated Effort:** 45 minutes (when ready)

## When to Revisit

These items should be reconsidered when:
- ✅ Preprocessing pipeline is resilient (incremental processing working)
- ✅ Data validation is integrated inline (Gatekeeper operational)
- ✅ Audit trails are automated (CLEANING_SUMMARY.md generated)
- ✅ Production model is deployed and serving predictions

Until then: **"Monitoring garbage is still garbage."**

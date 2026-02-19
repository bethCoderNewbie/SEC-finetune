---
id: research/2026-02-18_23-00-00_prd_cross_review_critique
title: "Gap Analysis & V&V Audit — PRD-001 through PRD-004"
standard: IEEE 1028 (Technical Review & Inspection) + ISO/IEC/IEEE 29148
date: 2026-02-18T23:00:00-06:00
author: bethCoderNewbie <beth88.career@gmail.com>
git_sha: d027985
branch: main
revision: v2 — revised per IEEE 1028 blameless-audit standard
context: >
  Four PRDs reviewed together as a set. Current operational intent: double-check PRD-001
  completion, verify PRD-002 state and begin implementation. PRD-003 and PRD-004 are DRAFT
  — not yet in active implementation.
---

# Gap Analysis & V&V Audit — PRD-001 through PRD-004

## Executive Summary — Impact Matrix

This table is the decision-gate summary. Items marked **Blocking** must be resolved before
the PRD-002 implementation sprint begins.

| Risk Category | Count | Primary Impact | Gate |
|:--------------|:-----:|:--------------|:-----|
| **Blocking** — implementation cannot proceed | 3 | Sentiment architecture (C-1), Taxonomy (C-3), JSONL output (G-04) | PRD-002 Phase 2 |
| **Feasibility** — targets unachievable on stated hardware | 2 | Throughput 35× over CPU budget (F-1); annotation volume 58+ hrs unplanned (F-2) | Phase 3 + PRD-004 Phase 2 |
| **Unverified** — implementation exists but KPI not measured | 3 | Parse ≥95%, text-loss < 5%, segmenter correctness | PRD-001 exit |
| **Process** — phase gates marked done without evidence | 4 | PRD-001 JSONL ✅, PRD-001 classifier ✅, PRD-002 Phase 1 complete, schema version | Audit integrity |
| **Documentation** — spec inconsistencies or missing artefacts | 6 | Story mapping, missing dep, wrong metric, status conflict | Sprint planning |

---

## Severity Level Definitions

Applied throughout this document. Based on project impact, not subjective intensity.

| Level | Definition |
|:------|:-----------|
| **Critical** | Blocks release OR causes irreversible data loss OR requires full rework of a delivered component |
| **High** | Significant rework required (> 3 days) OR degrades a primary KPI below acceptance threshold |
| **Medium** | Technical debt or documentation inconsistency that will compound if not addressed before the next phase |
| **Low** | Minor inconsistency; correct opportunistically, not urgently |

---

## Current Operational State

| PRD | README Status | Frontmatter Status | Operational Intent |
|:----|:-------------|:-------------------|:------------------|
| PRD-001 | APPROVED | APPROVED | Completion verification — confirm all exit criteria are satisfied |
| PRD-002 | APPROVED | DRAFT | **Status conflict (D-4).** Verify current implementation state; begin Phase 2 |
| PRD-003 | DRAFT | DRAFT | Specced; not yet active |
| PRD-004 | DRAFT | DRAFT | Specced; not yet active |

The primary action surface is PRD-001 and PRD-002. PRD-003/004 findings are captured for
awareness and pre-implementation planning only.

---

## Part 1 — PRD-001 Verification Audit

Applying IEEE 1028 §6.4 (Inspection): each claimed exit criterion is assigned a V&V status
based on available evidence.

### V&V Status Vocabulary

| Status | Meaning |
|:-------|:--------|
| **Verified** | Satisfactory evidence exists; criterion is met |
| **Unverified** | Implementation exists; KPI not measured to statistical threshold |
| **Defect** | Implementation produces output but output does not satisfy the stated requirement |
| **Failed** | Implementation does not exist or is explicitly isolated from the pipeline |

### PRD-001 Exit Criteria — V&V Table

| Goal | PRD Claim | V&V Status | Evidence / Defect Reference |
|:-----|:----------|:-----------|:----------------------------|
| Parse ≥95% of HTML filings without crashing | ✅ | **Unverified** | Metric requires N ≥ 30 stratified sample. Current evidence: N = 1 (AAPL_10K_2021). DLQ mechanism implemented. Statistical significance not established. (→ PRD-002 G-01) |
| Extract Item 1A with < 5% character loss | ✅ | **Unverified** | Validated on `AAPL_10K_2021` only. Cross-filing variance and edge-case coverage unknown. (→ PRD-002 G-02) |
| Segment risk text into atomic classifiable statements | ✅ | **Defect** | `RiskSegmenter` produces bounded-length segments. PRD-003 identifies ToC contamination in 175/309 files (56.6%) and abbreviation-boundary misfires. Requirement specifies quality, not only presence. (→ PRD-003 G-01, G-03) |
| Classify each segment at confidence ≥ 0.7 | ✅ | **Failed** | `src/analysis/inference.py` exists and classifies in isolation. It is not wired into `process_batch()`. No output file from a batch run contains classifier labels. (→ PRD-002 G-12) |
| Output JSONL compatible with HuggingFace `datasets` | ✅ | **Failed** | Pipeline emits per-filing JSON (`version: "1.0"`). No JSONL serialisation path exists. `datasets.load_dataset("json", ...)` compatibility is unconfirmed. (→ PRD-002 G-04, OQ-8) |
| Pipeline resumable via `--resume` | ✅ | **Verified** | `CheckpointManager` + `ResumeFilter` + `--resume` flag implemented and tested. |
| ≥ 186 unit tests passing | ✅ | **Verified** | 660 tests collected (superset of 186). 2 collection errors present; 186 baseline is exceeded. |

### Interpretation

Two exit criteria have a **Failed** status — meaning the implementation does not satisfy the
requirement at all. These are not measurement gaps; they are missing or disconnected code.
Three criteria are **Unverified** — they require a measurement run, not new engineering.

**Recommended action before PRD-002 Phase 2 begins:**

- Resolve the two **Failed** items (classifier integration, JSONL output). These are also
  PRD-002 Phase 2 exit criteria; fixing them closes both audits simultaneously.
- Schedule a measurement run on ≥ 30 stratified filings to generate evidence for the three
  **Unverified** items. Record results in `reports/baseline_kpi.json`; update the PRD-001 KPI table.

---

## Part 2 — PRD-002 Current State Verification

### Confirmed Implemented (Verified)

| Goal | Evidence |
|:-----|:---------|
| G-05 Resumable pipeline | `CheckpointManager` + `ResumeFilter` + `--resume` |
| G-08 Memory-aware adaptive timeout | `MemorySemaphore` + `FileCategory` (Small/Medium/Large) |
| G-09 Dead Letter Queue | `DeadLetterQueue`; drain on final run |
| G-10 Stamped run directories | `{YYYYMMDD_HHMMSS}_preprocessing_{sha}/` |
| G-11 Inline QA / quarantine | `HealthCheckValidator` + `process_and_validate()` |

### Phase 2 Implementation Gaps

| Goal | V&V Status | Gap Description | Phase 2 Blocking |
|:-----|:-----------|:----------------|:----------------|
| G-04 JSONL output | Failed | `save_to_json()` only; no `save_to_jsonl()`; HF compatibility unconfirmed | Yes |
| G-12 Classifier in batch | Failed | `inference.py` isolated; `process_batch()` produces unlabelled output | Yes |
| G-13 CLI sector filter | Failed | `--sic` / `--ticker` argparse flags absent | Yes |
| G-14 NLP features inline | Failed | `src/features/` sentiment/readability/topic modules not merged into output record | Yes |

### Phase 2 Exit Criteria — Implementation Mapping

| Criterion | Target File | Required Change |
|:----------|:------------|:----------------|
| Every segment labeled | `run_preprocessing_pipeline.py` → `process_batch()` | Import and invoke `inference.py` post-segmentation; attach `risk_label` and `confidence` to each `RiskSegment` |
| JSONL output | `src/preprocessing/models/segmented_risks.py` | Add `save_to_jsonl()` method; validate with `datasets.load_dataset("json", data_files=...)` |
| ≥ 100 filing throughput benchmark | None (measurement run) | Instrument wall time; confirm < 2s/filing; log to `reports/throughput_benchmark.json` |
| Fix 2 test collection errors | `tests/test_pipeline_global_workers.py`, `tests/test_validator_fix.py` | Resolve `ZeroDivisionError` and global worker import; all 660 tests must pass cleanly |
| `--sic` / `--ticker` CLI filter | `run_preprocessing_pipeline.py` | Add argparse arguments; pre-filter file list before `ParallelProcessor` dispatch |
| Schema `version` field aligned | `src/preprocessing/models/` | Set `"version": "2.0"`; update CHANGELOG; close OQ-8 |
| > 80% line coverage | CI (not yet configured) | `pytest --cov`; identify uncovered modules |
| Inference latency ≤ 500ms P95 | `src/analysis/inference.py` | Benchmark on 100-segment sample; log to `reports/inference_latency.json` |

### Story Mapping Defects in PRD-002 Goals Table

These are documentation errors with no code impact, but they corrupt sprint traceability.

| Goal | Current Mapping | Defect | Correct Mapping |
|:-----|:----------------|:-------|:----------------|
| G-06 (throughput 10K/2hr) | `US-021` | US-021 is competitive benchmarking (EP-7). Throughput is a pipeline performance concern. | Unmap or link to US-011 (anchor parse performance) |
| G-12 (classifier integration) | `US-022` | US-022 is supplier risk screening (EP-7). No story currently owns classifier integration. | Create new story or re-scope US-008 (NLP features inline) |

---

## Part 3 — Architecture Decision Requests

These are specification conflicts that will be embedded into code if not resolved before
implementation begins. Framed as decision requests with trade-off analysis.

### ADR-REQUEST-001 (Critical): Sentiment Analysis — Classifier Feature vs. Pipeline Output

**Conflict source:**
- PRD-001 §6.5 (lines 219–221): FinBERT embeddings + LM sentiment counts + readability +
  LDA topic vector are concatenated into a hybrid classification head. Sentiment is a
  **model input**.
- PRD-002 §2 design constraint (line 64): "Sentiment features are pipeline outputs, not
  classifier inputs." Sentiment is a **model output / observability signal**.

These are mutually exclusive architectures. The decision determines what `process_batch()`
must produce and whether `src/features/` must be invoked during training data generation.

| | Option A — Hybrid Head (PRD-001 §6.5) | Option B — Text-Only Fine-Tune (PRD-002) |
|:-|:--------------------------------------|:-----------------------------------------|
| **Architecture** | FinBERT embeddings + engineered features → concat → classification head | Standard FinBERT fine-tune (PEFT/LoRA or full) |
| **Theoretical ceiling** | Higher (domain features supplement embeddings) | Lower but sufficient for MVP F1 target |
| **Implementation complexity** | Custom training loop; requires feature extraction at train time | HuggingFace `Trainer` compatible; standard pipeline |
| **Inference latency** | Higher (features must be computed per segment at inference) | Lower (single forward pass) |
| **Iteration speed** | Slow (two systems to tune) | Fast |

**Recommendation:** Adopt Option B (PRD-002). The hybrid head complexity is premature for
an MVP targeting Macro F1 > 0.72. FinBERT pre-trained on financial text is a strong enough
prior to reach MVP threshold without engineered features. Revisit Option A in a future PRD
if F1 plateaus.

**Required artefact:** ADR-008 — "Sentiment Analysis Role: Pipeline Output vs. Classifier Feature." Mark PRD-001 §6 as superseded in its frontmatter once decided.

---

### ADR-REQUEST-002 (Critical): Text Cleaning Depth — Two-Pass Architecture Required

**Conflict source:** PRD-001 §6.2 (lines 163–168) specifies a single cleaning pipeline
that includes lowercase normalization, punctuation removal, stop word removal, and
lemmatization. These steps are required for TF-IDF and LDA feature extraction.

They are destructive to FinBERT fine-tuning.

**Why this matters — data lineage:**

```
Raw HTML (EDGAR)
        │
        ▼ structural_clean()          ← BERT-safe pass
        │   Strip HTML artifacts, ToC, tables, page numbers,
        │   whitespace normalization, ASCII escape sequences.
        │   Case and morphology PRESERVED.
        │
        ├──────────────────────────────────────────────────────┐
        │                                                      │
        ▼ Path A — FinBERT fine-tuning                        ▼ Path B — TF-IDF / LDA features
        input_text (str)                                      feature_clean()
        "We are exposed to significant                          lowercase → lemmatize →
         cybersecurity threats..."                              stop word removal →
                                                               tokenize → vectorize
        Tokenized by FinBERT WordPiece.                       "expos significant cybersecur
        Case signals preserved ("U.S.", "SEC").                 threat..."
        Morphological suffixes preserved
        ("-ing", "-tion", "-ial").

        [Embedding → Classification Head]                     [TF-IDF matrix / LDA topics]
```

If the current `TextCleaner` output (post-lemmatization) is used as `input_text` for
fine-tuning, training on morphologically-destroyed text will degrade FinBERT performance
relative to training on clean prose. The model was pre-trained on unlemmatized financial
filings; lemmatized fine-tuning data creates a distribution mismatch.

**Recommended resolution:** Refactor `TextCleaner` into two explicit passes. Keep the
existing aggressive normalization under `feature_clean()` for TF-IDF/LDA. Add `structural_clean()`
producing the `input_text` field. Document the fork in the Data Dictionary with field
lineage.

**Required artefact:** ADR-009 — "TextCleaner Two-Pass Architecture." Data Dictionary
update with `input_text` lineage section.

---

### ADR-REQUEST-003 (High): Risk Taxonomy Reduction — 12 Classes to 8 Classes

**Conflict source:** `src/analysis/taxonomies/risk_taxonomy.yaml` implements a 12-class
taxonomy (PRD-001/002). PRD-004 §3.2 defines a new 8-class taxonomy with different
category boundaries. No class mapping exists.

**Unmapped PRD-001 classes:**

| PRD-001 Class | PRD-004 Candidate | Notes |
|:-------------|:-----------------|:------|
| `Human Capital` | None | Not represented. Absorb into `other` or add `people_risk`? |
| `Product/Service` | `market` (partial) | Quality/recall risk ≠ market competition risk |
| `Reputation` | `esg` (partial) | Reputational exposure from non-ESG sources (litigation, fraud) not covered |

**Impact on current sprint:** If `inference.py` is wired into `process_batch()` using
the 12-class schema now, every output record in the corpus will carry 12-class labels.
PRD-004 Phase 2 will require a full re-classification pass, making the PRD-002 integration
work partially throwaway. The taxonomy decision is cheap to make now; expensive after
corpus-scale output files exist.

**Recommended resolution:**
1. Adopt the PRD-004 8-class taxonomy as authoritative.
2. Define the explicit mapping from 12 → 8 classes (including unmapped classes).
3. Update `risk_taxonomy.yaml` before wiring the classifier into `process_batch()`.
4. Write ADR-010 documenting the reduction rationale and mapping table.

---

### C-4 (Medium): Schema `version` Field Mismatch

PRD-001 specified `"version": "2.0"`. Code emits `"version": "1.0"` (PRD-002 OQ-8).
No downstream PRD resolves this.

**Resolution:** Set `"version": "2.0"` in the `SegmentedRisks` model as part of the JSONL
implementation work. Update CHANGELOG. Close OQ-8.

---

## Part 4 — Feasibility Analysis (PRD-003 / PRD-004 Awareness)

Not blocking current sprint. Required reading before PRD-003 Phase 4 and PRD-004 planning.

### F-1 (Critical): Compute Resource Budget — Throughput Target Exceeds CPU Capacity

The current architecture cannot satisfy the defined throughput KPI on unspecified hardware.

**Resource Budget Breakdown:**

| Processing Stage | PRD Target | CPU Reality | Source |
|:-----------------|:-----------|:------------|:-------|
| Parse (HTML → segments) | ≤ 3s per filing (PRD-003 Phase 4 target) | 34s median today | PRD-003 §1, `extractor.py` |
| Classify (per segment, P95) | ≤ 500ms | ≤ 500ms (CPU, isolated) | PRD-002 §3.2 |
| Segments per filing (median) | — | ~45 (AAPL reference) | PRD-001 schema example |
| **Inference per filing (CPU)** | — | **500ms × 45 = 22.5s** | Derived |
| **Total per filing (with anchor seek)** | 720ms | **~25.5s** | Derived |

**Gap to Target:**

| Metric | PRD Target (PRD-001/002) | CPU Reality | Gap Factor |
|:-------|:------------------------|:------------|:----------:|
| Latency per filing | 720ms | ~25,500ms | **35× slower** |
| Batch time (10,000 filings) | 2 hours | ~70 hours | **35× slower** |

**Constraint:** The `p95 ≤ 500ms` per-segment inference target is only achievable with CUDA
acceleration and batched inference. PRD-002 §4.1 states "local GPU or cloud node (not yet
specified)." The throughput exit criterion in Phase 3 cannot be evaluated until this
infrastructure decision is made.

**Required action:** Resolve OQ-5, OQ-9, and OQ-10 together in a single compute
architecture ADR before any Phase 3 throughput gate is written or scheduled.

---

### F-2 (High): Annotation Volume — Labor Estimate Exceeds Planned Capacity

**PRD-004 Phase 1 gate:** ≥ 500 human-reviewed segments per non-`other` category.
7 non-`other` categories → minimum **3,500 labeled segments**.

**Annotation resource budget:**

| Parameter | Estimate | Basis |
|:----------|:---------|:------|
| Corpus size | ~13,905 segments | 309 filings × 45 segments |
| Required labels | 3,500 (25% of corpus) | PRD-004 Phase 1 gate |
| Labeling rate | ~60 segments/hour | Segment read + dropdown correction |
| **Total labor** | **~58 hours** | Derived |
| HITL labeler mode | Live EDGAR fetch per session | PRD-004 §4.2 |
| Offline batch mode | Not specified | — |

58 hours of annotation with a live-fetch-only interface and no timeline estimate is an
unplanned labor commitment that will delay the Phase 2 fine-tuning gate.

**Required actions before PRD-004 Phase 1 implementation:**
1. Add offline annotation mode to `labeler_app.py` design — load segments from
   `data/raw/` instead of live EDGAR fetch.
2. Define an annotation timeline and rate estimate in PRD-004 Phase 1.
3. Validate whether 500 examples/category is sufficient for Macro F1 > 0.72 empirically
   before committing Phase 1 scope. This is an open research question (PRD-004 Q-04).

---

### F-3 (Medium): Anchor Seek — Fallback Rate Unquantified

**PRD-003 Phase 4 claim:** Hybrid anchor seek reduces parse time from 34s → ≤ 3s (11×
speedup). This assumes EDGAR filings contain machine-readable ToC anchor links.

Pre-2017 filings and some smaller filers use non-standard HTML structures without named
anchors. If 30–40% of the 887-filing target corpus lacks anchors and falls back to full
parse, the effective corpus speedup is 6× at best — reducing 8.4 hours to ~4.5 hours,
not the ~45-minute implied speedup.

**Recommended prerequisite:** Before implementing Phase 4, run a coverage scan on the
existing 309-filing corpus to validate the anchor assumption:

```bash
python -c "
from bs4 import BeautifulSoup
import glob

results = []
for f in glob.glob('data/raw/*.html'):
    html = open(f, encoding='utf-8', errors='replace').read()
    soup = BeautifulSoup(html, 'html.parser')
    has_anchor = bool(soup.find('a', string=lambda s: s and '1A' in s))
    results.append({'file': f, 'has_anchor': has_anchor})

n = len(results)
coverage = sum(r['has_anchor'] for r in results) / n
print(f'Anchor coverage: {coverage:.1%} ({n} files scanned)')
"
```

Gate Phase 4 implementation on the result. If anchor coverage < 70%, revise the speedup
claim and the Phase 4 gate before committing engineering time.

---

## Part 5 — Documentation Anomalies

| ID | Severity | PRD(s) | Anomaly | Required Fix |
|:---|:---------|:-------|:--------|:-------------|
| D-1 | Low | PRD-003 §7 | US-014 (semantic deduplication) linked from G-05 in PRD-003 but absent from §7 user story table. Story exists at `stories/US-014_semantic_deduplication.md`. | Add US-014 row to PRD-003 §7 |
| D-2 | Medium | PRD-003 Fix 4 | `datasketch` required for MinHash LSH but not declared in `requirements*.txt` or any PRD runtime dep list. Will break clean install. | Add `datasketch>=1.1.0` to requirements before Fix 4 implementation |
| D-3 | Medium | PRD-004 Phase 4 | Step 4.3 schedules "Add SIC code to `SegmentedRisks.metadata`" as new engineering work. `sic_code` already flows from `SECFilingParser` through all pipeline stages per PRD-002 §7.1 and appears in the PRD-001 output schema example. | Verify `SegmentedRisks` Pydantic model and a sample output file before scheduling this as an engineering task |
| D-4 | Low | PRD-002 | README shows `APPROVED`; frontmatter shows `DRAFT`. Frontmatter is the per-document source of truth. | Update README to `DRAFT` |
| D-5 | Medium | PRD-002 Phase 1 | Phase 1 marked **Complete** with one open exit criterion: "Model outperforms baseline heuristic by > 10% F1 — not yet measured." A phase with an open exit criterion is not complete. | Move criterion to Phase 2 (where classifier integration is scoped) or mark Phase 1 ⚠️ Conditionally Complete with the F1 benchmark deferred |
| D-6 | Low | PRD-003 Phase 3 | Phase 3 gate requires "Gunning Fog ≥ 10.0 on all processed segments." Gunning Fog measures text reading complexity, not sentence boundary correctness. A correctly split short sentence lowers the score. The gate does not validate the fix it is supposed to gate. | Replace with the unit test criterion from PRD-003 §5.3: "`U.S. economy` not split; `end of paragraph. Next` correctly split." Retain Gunning Fog in §9 Data & Metrics as an observational metric only |

---

## Part 6 — Action Plan

Severity levels applied per definitions in §2. Every action links to the anomaly it closes.

### Immediate — PRD-001 / PRD-002 Sprint

| # | Type | Action | Closes | Owner |
|:--|:-----|:-------|:-------|:------|
| 1 | Decision | Write ADR-008: sentiment analysis role (pipeline output vs. classifier feature). Annotate PRD-001 §6 as superseded once decided. | C-1 | Architect |
| 2 | Decision | Write ADR-009: TextCleaner two-pass architecture. Specify `structural_clean()` vs. `feature_clean()`. Update Data Dictionary with `input_text` lineage. | C-2 | Architect + Data Eng |
| 3 | Decision | Write ADR-010: 12-class → 8-class taxonomy reduction with explicit class mapping. Update `risk_taxonomy.yaml` before wiring classifier into batch. | C-3 | Architect |
| 4 | Code | Add `save_to_jsonl()` to `SegmentedRisks`; validate with `datasets.load_dataset("json", ...)`. Set `"version": "2.0"`. | G-04, C-4, OQ-8 | Data Eng |
| 5 | Code | Wire `inference.py` into `process_batch()` after ADR-010 (taxonomy) is resolved. Attach `risk_label` and `confidence` to each `RiskSegment` in batch output. | G-12, PRD-001 classifier claim | ML Eng |
| 6 | Measure | Run batch on ≥ 30 stratified filings (≥ 5 SIC sectors, 2019–2024). Record parse success rate and text-loss rate in `reports/baseline_kpi.json`. Update PRD-001 KPI table. | PRD-001 Unverified items | Data Eng |
| 7 | Code | Fix 2 test collection errors (`test_pipeline_global_workers.py`, `test_validator_fix.py`). All 660 tests must pass cleanly before Phase 2 exit. | PRD-002 Phase 2 | Eng |
| 8 | Code | Add `--sic` / `--ticker` argparse flags; pre-filter file list before `ParallelProcessor` dispatch. | G-13, US-004 | Eng |
| 9 | Doc | Update PRD-002 README status to `DRAFT`. | D-4 | Author |
| 10 | Doc | Move "Model outperforms baseline by > 10% F1" from Phase 1 to Phase 2 exit criteria, or mark Phase 1 ⚠️ Conditionally Complete. | D-5 | Author |

### Before PRD-003 Implementation Begins

| # | Type | Action | Closes | Owner |
|:--|:-----|:-------|:-------|:------|
| 11 | Measure | Run anchor coverage scan (script in §4 / F-3) on 309-filing corpus. Gate Phase 4 implementation on result. | F-3 | Data Eng |
| 12 | Doc | Add US-014 row to PRD-003 §7 user story table. | D-1 | Author |
| 13 | Doc | Add `datasketch>=1.1.0` to runtime dependencies. | D-2 | Eng |
| 14 | Doc | Replace Gunning Fog from Phase 3 gate with unit-test criterion from PRD-003 §5.3. | D-6 | Author |

### Before PRD-004 Implementation Begins

| # | Type | Action | Closes | Owner |
|:--|:-----|:-------|:-------|:------|
| 15 | Decision | Write compute architecture ADR resolving OQ-5 / OQ-9 / OQ-10 together. Specify GPU access plan before any Phase 3 throughput gate is scheduled. | F-1 | Architect + FinOps |
| 16 | Design | Add offline annotation mode to `labeler_app.py` design: load segments from `data/raw/` instead of live EDGAR fetch. | F-2 | ML Eng |
| 17 | Design | Add annotation timeline and rate estimate to PRD-004 Phase 1. | F-2 | Product |
| 18 | Verify | Check `SegmentedRisks` Pydantic model and a sample output JSON for `sic_code` before scheduling PRD-004 Phase 4 Step 4.3. | D-3 | Data Eng |

---

## Master Anomaly Register

| ID | Type | Severity | PRDs | Open Question / ADR | Blocks |
|:---|:-----|:---------|:-----|:--------------------|:-------|
| C-1 | Architecture conflict | Critical | PRD-001 ↔ PRD-002 | → ADR-008 | PRD-002 Phase 2 |
| C-2 | Architecture conflict | Critical | PRD-001 ↔ PRD-002 | → ADR-009 | Fine-tuning quality |
| C-3 | Architecture conflict | High | PRD-001/002 ↔ PRD-004 | → ADR-010 | Classifier integration |
| C-4 | Specification defect | Medium | PRD-001 → PRD-004 | OQ-8 | Schema consumers |
| D-1 | Documentation gap | Low | PRD-003 §7 | — | — |
| D-2 | Missing dependency | Medium | PRD-003 | — | PRD-003 Fix 4 install |
| D-3 | False scope item | Medium | PRD-004 Phase 4 | — | Wasted sprint capacity |
| D-4 | Documentation inconsistency | Low | PRD-002 | — | — |
| D-5 | False phase completion | Medium | PRD-002 Phase 1 | — | Phase gate integrity |
| D-6 | Wrong quality metric | Low | PRD-003 Phase 3 | — | Phase gate integrity |
| F-1 | Infeasible target | Critical | PRD-001/002 | OQ-5/OQ-9/OQ-10 → ADR | Phase 3 throughput gate |
| F-2 | Unplanned labor | High | PRD-004 Phase 1 | PRD-004 Q-04 | Fine-tuning timeline |
| F-3 | Unvalidated assumption | Medium | PRD-003 Phase 4 | — | Anchor seek speedup claim |

---

*IEEE 1028 Gap Analysis & V&V Audit — PRD-001 through PRD-004*
*Commit: d027985 · Branch: main · Date: 2026-02-18 · Revision: v2*

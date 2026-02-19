---
id: research/2026-02-18_23-00-00_prd_cross_review_critique
title: PRD-001 → PRD-004 Cross-Review — Contradictions, Feasibility Gaps & Recommended Actions
date: 2026-02-18T23:00:00-06:00
author: bethCoderNewbie <beth88.career@gmail.com>
git_sha: d027985
branch: main
context: >
  Four PRDs reviewed together as a set. Current operational intent: double-check PRD-001
  completion, verify PRD-002 state and begin implementation. PRD-003 and PRD-004 are DRAFT
  — not yet in active implementation.
---

# PRD-001 → PRD-004 Cross-Review

## Current Status & Context

| PRD | Status | Operational Intent |
|:----|:-------|:------------------|
| PRD-001 | APPROVED | **Double-check completion** — verify all ✅ goals are actually implemented |
| PRD-002 | APPROVED (README) / DRAFT (frontmatter) | **Verify state, begin implementation** |
| PRD-003 | DRAFT | Specced; not yet active |
| PRD-004 | DRAFT | Specced; not yet active |

The primary action surface right now is PRD-001 and PRD-002. PRD-003 and PRD-004 issues are
documented for awareness but do not require resolution before current sprint work begins.

---

## Part 1 — PRD-001 Completion Audit

### What PRD-001 claims is complete (✅ checkboxes)

| Goal | Claim | Verification Required |
|:-----|:------|:----------------------|
| Parse ≥95% of HTML 10-K/10-Q filings without crashing | ✅ | G-01 in PRD-002 says "not yet measured — requires ≥30 filings". **Claimed complete; actually unmeasured.** |
| Extract Item 1A with < 5% character loss | ✅ | G-02 in PRD-002 says "not validated — tested on AAPL_10K_2021 only". **One-filing anecdote, not validated at corpus scale.** |
| Segment risk text into atomic classifiable statements | ✅ | `RiskSegmenter` implemented. Bounds enforced. But PRD-003 identifies ToC contamination in 56.6% of files and abbreviation splits — the segmenter produces output, not necessarily correct output. |
| Classify each segment at confidence ≥ 0.7 | ✅ | G-12 in PRD-002: "`src/analysis/inference.py` exists but is not wired into `process_batch()`". **Classifier exists but is not integrated. This ✅ is wrong.** |
| Output JSONL compatible with HuggingFace | ✅ | G-04 in PRD-002: "Outputs JSON, not JSONL. HuggingFace compatibility not confirmed." **The founding deliverable is marked done and is not done.** |
| Pipeline resumable | ✅ | `CheckpointManager` + `ResumeFilter` + `--resume`. Confirmed. |
| ≥186 unit tests passing | ✅ | PRD-002 says 660 collected, 2 collection errors. The 186 baseline is met. |

**PRD-001 honest completion status:**

| Item | Real Status |
|:-----|:-----------|
| Parse ≥95% | ⚠️ Unmeasured — DLQ works but KPI never measured on ≥30-filing sample |
| Item 1A extraction < 5% loss | ⚠️ Validated on one filing (AAPL_10K_2021) only |
| Segmentation | ⚠️ Produces segments; data quality defects confirmed (PRD-003) |
| Classifier integrated | ❌ `inference.py` not wired to batch pipeline |
| JSONL output | ❌ Emits JSON (v1.0); HuggingFace compatibility unconfirmed |
| Resumable pipeline | ✅ |
| 186 tests | ✅ (now 660 collected) |

**Recommendation:** Before starting PRD-002 implementation, close the two ❌ items — they are
PRD-001 exit criteria that were never actually met. The two ⚠️ items need measurement, not
new code. Run the batch on ≥30 stratified filings, measure parse success and text-loss; log
the numbers in a new `reports/` artefact and update PRD-001 KPI table.

---

## Part 2 — PRD-002 Verification (Current State vs. Spec)

### Status metadata conflict
PRD-002 README says `APPROVED`. PRD-002 frontmatter says `DRAFT`. Pick one.
Recommendation: Keep `DRAFT` — PRD-002 Phase 2 (Engineering MVP) is not complete.

### Goals that are genuinely ✅ in PRD-002

These appear implemented and can be taken at face value:

- G-05 Resumable pipeline (`CheckpointManager` + `ResumeFilter`)
- G-08 Memory-aware adaptive timeout (`MemorySemaphore` + `FileCategory`)
- G-09 Dead Letter Queue (`DeadLetterQueue`)
- G-10 Stamped run dirs with git SHA
- G-11 Inline QA validation / quarantine (`HealthCheckValidator`)

### Goals that are ❌ in PRD-002 — the implementation gap list

| Goal | Gap | Blocking Phase 2? |
|:-----|:----|:-----------------|
| G-04 JSONL output | `save_to_json()` only; no `save_to_jsonl()`; HuggingFace load not confirmed | **Yes** |
| G-12 Classifier in batch | `src/analysis/inference.py` exists, not wired to `process_batch()` | **Yes** |
| G-13 CLI sector filter | `--sic` / `--ticker` flags not implemented | **Yes** |
| G-14 NLP features inline | Sentiment, readability, topic features exist in `src/features/`; not merged into output record | **Yes** |

### PRD-002 Phase 2 exit criteria — actionable list

These are the criteria for declaring Phase 2 done, mapped to the code change required:

| Criterion | File to change | What to do |
|:----------|:--------------|:-----------|
| Every segment labeled (classifier integrated) | `scripts/data_preprocessing/run_preprocessing_pipeline.py` → `process_batch()` | Import and call `src/analysis/inference.py` after segmentation step |
| Output JSONL | `src/preprocessing/models/` (`SegmentedRisks`) | Add `save_to_jsonl()` method; confirm `datasets.load_dataset("json", ...)` parses the output |
| Throughput benchmark | none — run test | Process ≥100 filings; measure wall time; confirm < 2s/filing |
| Fix 2 test collection errors | `tests/test_pipeline_global_workers.py`, `tests/test_validator_fix.py` | Resolve `ZeroDivisionError` and global worker import errors |
| `--sic` / `--ticker` CLI flag | `scripts/data_preprocessing/run_preprocessing_pipeline.py` | Add argparse args; pre-filter file list before dispatching to ParallelProcessor |
| Schema version resolved | `src/preprocessing/models/` + PRD-001 | Align `"version"` field: pick "1.0" or "2.0", update PRD-001, update code |
| > 80% line coverage | CI | Run `pytest --cov`; identify uncovered modules |
| Inference latency ≤ 500ms P95 | `src/analysis/inference.py` | Benchmark on 100-segment sample; log in `reports/inference_latency.json` |

### Wrong story mappings in PRD-002 (data errors, not implementation gaps)

- G-06 (throughput 10K/2hr) is mapped to `US-021` — US-021 is competitive benchmarking. Should be unmapped or mapped to US-011.
- G-12 (classifier integration) is mapped to `US-022` — US-022 is supplier risk screening. No story currently covers classifier integration. Consider adding or re-using US-008.

---

## Part 3 — Contradictions Requiring Resolution Before Implementation

These are bugs in the spec, not the code. They must be resolved before writing implementation
code or they will embed the contradiction into the codebase.

### C-1 (Critical): Sentiment as Classifier Feature vs. Pipeline Output

- **PRD-001 §6.5** (line 219–221): FinBERT embeddings + LM sentiment + readability + LDA topic
  vector are concatenated into a hybrid classification head.
- **PRD-002 §2 design constraint** (line 64): "Sentiment features are pipeline outputs, not classifier inputs."

These are mutually exclusive architectural decisions. Resolving this determines what
`process_batch()` must produce.

**Recommended resolution:** Decide which architecture to pursue:
- Option A (PRD-001): Hybrid feature model — more complex, potentially higher ceiling F1.
  Requires merging `src/features/` into training feature vector.
- Option B (PRD-002): Text-only FinBERT fine-tune — simpler, standard PEFT approach.
  Sentiment features are observability outputs only.

Write an ADR after deciding. The PRD-001 §6 section should be annotated as superseded if
Option B is chosen.

### C-2 (Critical): Text Cleaning Depth Destroys FinBERT Input

PRD-001 §6.2 (lines 163–168) specifies lowercase, punctuation removal, stop word removal,
and **lemmatization** as cleaning steps. These are appropriate for TF-IDF/LDA feature
extraction only.

FinBERT (and any BERT-variant) is case-sensitive. Lemmatization corrupts its subword
tokenizer ("running" → "run" removes the `-ing` morphological signal that BERT's
attention heads use). If `TextCleaner`'s output is the `input_text` field sent to
fine-tuning, training on lemmatized text will degrade classifier performance vs.
training on clean prose.

**Recommended resolution:** Split cleaning into two passes:
- `structural_clean()` — strip HTML artifacts, ToC, tables, page numbers, whitespace
  normalization. This is the `input_text` for FinBERT fine-tuning.
- `feature_clean()` — additionally lowercase, lemmatize, remove stop words. Used only
  as input to TF-IDF vectorizer and LDA topic model.

Document the distinction in the Data Dictionary.

### C-3 (High): 12-Class Taxonomy (PRD-001/002) vs. 8-Class Taxonomy (PRD-004)

The existing zero-shot classifier (`src/analysis/inference.py`) is trained on a 12-class
taxonomy defined in `src/analysis/taxonomies/risk_taxonomy.yaml`. PRD-004 defines a
different 8-class taxonomy (`cybersecurity`, `regulatory`, `financial`, `supply_chain`,
`market`, `esg`, `macro`, `other`).

No mapping exists between the two schemas. Three PRD-001 classes have no obvious home:
- `Human Capital` → not in PRD-004 taxonomy
- `Product/Service` → possibly `market`?
- `Reputation` → possibly `esg`?

**Impact on current work:** If PRD-002 implementation wires the existing 12-class
`inference.py` into `process_batch()`, every output record will carry 12-class labels.
PRD-004 Phase 2 will then need to re-classify everything under the 8-class taxonomy,
making the PRD-002 classifier integration work partially throwaway.

**Recommended resolution (before wiring classifier into batch):**
1. Decide which taxonomy is authoritative — the 8-class PRD-004 taxonomy is better
   scoped for business use cases and should win.
2. Update `risk_taxonomy.yaml` to the 8-class schema.
3. Write an ADR (ADR-008) documenting the class reduction and the mapping.
4. Then wire `inference.py` into `process_batch()` using the 8-class taxonomy.

This change is cheap now (before integration); expensive after thousands of output files
exist with 12-class labels.

### C-4 (Medium): Schema `version` Field Mismatch

PRD-001 specified `"version": "2.0"`. Code emits `"version": "1.0"` (PRD-002 OQ-8).
Neither PRD-003 nor PRD-004 resolves this.

**Recommended resolution:** Bump to `"version": "2.0"` in code as part of PRD-002
JSONL implementation. Record the bump in CHANGELOG. Close OQ-8.

---

## Part 4 — Feasibility Risks (PRD-003 and PRD-004 Awareness)

These are not blocking current work but should inform PRD-003/004 implementation planning.

### F-1 (Critical): Throughput Target Is Infeasible on CPU

PRD-001/002 target: 10,000 filings in < 2 hours = 720ms/filing.
PRD-002 §3.2: Classifier latency P95 < 500ms *per segment*.
AAPL 10-K: ~45 segments.
CPU math: 500ms × 45 segments = 22.5s inference per filing + 3s parse (PRD-003 target) = ~25s/filing.
At 25s/filing: 10,000 filings = ~70 hours on CPU.

The throughput gate cannot be met without GPU parallelism or batched inference.
PRD-002 §4.1 says "local GPU or cloud node (not yet specified)." This decision must be made
before the Phase 3 exit criteria are meaningful.

**Recommended resolution:** Add a compute architecture ADR (or resolve OQ-5 / OQ-9 / OQ-10
together in one ADR) before any Phase 3 planning begins. In the meantime, benchmark on CPU
for ≥100 filings to establish the real baseline.

### F-2 (High): PRD-004 Annotation Bottleneck

Phase 1 gate requires ≥ 500 human-reviewed segments per non-`other` category = 3,500 segments.
At ~60 segments/hour: ~58 hours of annotation labor.
The HITL labeler fetches live from EDGAR per session — no offline batch mode.
No annotation timeline or rate estimate exists in the PRD.

**Recommended resolution:**
1. Add offline annotation mode to labeler design (load from local `data/raw/` instead of
   live EDGAR fetch).
2. Estimate annotation timeline and add it to PRD-004 Phase 1 before implementation begins.
3. Consider whether 500/category is enough — empirical validation needed before Phase 2.

### F-3 (Medium): Anchor Seek Fallback Rate Unknown (PRD-003)

The 11x speedup claim (34s → 3s) depends on EDGAR anchor structure. Pre-2017 filings and
some filers use non-standard ToC structures. If 30–40% of filings fall back to full parse,
the speedup is far less than claimed.

**Recommended resolution:** Before committing to the Phase 4 gate, run a one-time anchor
coverage scan on the existing 309-filing corpus:
```bash
python -c "
from bs4 import BeautifulSoup
import glob, json
results = []
for f in glob.glob('data/raw/*.html'):
    html = open(f, encoding='utf-8', errors='replace').read()
    soup = BeautifulSoup(html, 'html.parser')
    has_anchor = bool(soup.find('a', string=lambda s: s and '1A' in s))
    results.append({'file': f, 'has_anchor': has_anchor})
coverage = sum(r['has_anchor'] for r in results) / len(results)
print(f'Anchor coverage: {coverage:.1%} ({len(results)} files)')
"
```
Gate the Phase 4 anchor seek work on the result.

---

## Part 5 — Documentation Gaps

### D-1: Missing US-014 in PRD-003 §7

PRD-003 G-05 covers segment-level deduplication. US-014 (`semantic_deduplication`) is the
story for this goal in the README/EP-3. PRD-003's §7 user story table lists US-009, US-010,
US-011, US-012 only. US-014 is missing.

**Fix:** Add US-014 row to PRD-003 §7 table.

### D-2: `datasketch` Undeclared Dependency

PRD-003 Fix 4 requires `datasketch` for MinHash LSH. Not in `requirements*.txt` or PRD-001/002
runtime deps. Will break a clean install.

**Fix:** Add `datasketch>=1.1.0` to requirements before PRD-003 Fix 4 implementation.

### D-3: SIC Code in PRD-004 Phase 4 May Already Exist

PRD-004 Phase 4, Step 4.3 schedules adding SIC code to `SegmentedRisks.metadata`. But
`sic_code` flows through from `SECFilingParser` per PRD-002 §7.1, and appears in the
PRD-001 output schema example at the top level.

**Fix:** Check actual `SegmentedRisks` Pydantic model and a sample output file before
scheduling this as an engineering task.

### D-4: PRD-002 Status Conflict (README vs. Frontmatter)

README says PRD-002 `APPROVED`. Frontmatter says `DRAFT`. Frontmatter is the source of truth.

**Fix:** Update README to show PRD-002 as `DRAFT`.

### D-5: PRD-002 Phase 1 Marked Complete With Open Exit Criterion

Phase 1 exit criterion: "Model outperforms baseline heuristic by > 10% F1 — **not yet measured**."
Phase 1 is marked **Complete**.

**Fix:** Move this criterion to Phase 2 (where classifier integration is happening), or mark
Phase 1 as ⚠️ Conditionally Complete with the F1 benchmark deferred.

### D-6: Gunning Fog Is the Wrong Quality Gate for PRD-003 Phase 3

PRD-003 G-03 Phase 3 gate: "Gunning Fog ≥ 10.0 on all processed segments."
Gunning Fog measures text complexity (reading difficulty), not sentence boundary correctness.
A correctly split short sentence lowers Gunning Fog. These are orthogonal.

**Fix:** The correct gate is the unit test criterion already listed in PRD-003 §5.3:
"`U.S. economy` not split; `end of paragraph. Next` correctly split."
Remove the Gunning Fog condition from the phase gate; keep it in Data & Metrics as an
observational metric only.

---

## Part 6 — Recommended Action Plan

### Immediate (PRD-001 / PRD-002 work in flight)

1. **[doc] Resolve PRD-002 status conflict** — update README to `DRAFT`, or decide to mark it
   `APPROVED` only after Phase 2 exits.

2. **[decision] Resolve C-1 (sentiment architecture)** — write ADR-008 for "sentiment as
   classifier feature vs. output." This determines whether `process_batch()` must collect
   feature vectors during segmentation.

3. **[decision] Resolve C-3 (taxonomy)** — write ADR-009 for "12-class → 8-class taxonomy
   reduction with class mapping." Do this before wiring `inference.py` into batch; otherwise
   the integration work is partially throwaway.

4. **[code] Fix the two genuine PRD-001 ❌ items** (classifier not integrated, no JSONL
   output) — these are PRD-001 exit criteria that were mischecked. They are also PRD-002
   Phase 2 exit criteria. Implement together.

5. **[measure] PRD-001 KPI baseline** — run batch on ≥30 stratified filings; record parse
   success rate and text-loss rate in `reports/baseline_kpi.json`; update PRD-001 KPI table.

6. **[code] Fix 2 test collection errors** (`test_pipeline_global_workers.py`,
   `test_validator_fix.py`) — these are blocking the "all tests pass in CI" Phase 2
   criterion.

7. **[code] Implement `--sic` / `--ticker` CLI filter** — straightforward argparse addition;
   blocks G-13 and US-004.

8. **[code] Resolve schema `version` field** — pick "2.0", update code, close OQ-8.

### Before PRD-003 Implementation Begins

9. **[measure] Anchor coverage scan** — run the one-liner above on 309 filings; confirm
   anchor seek is worth building before committing to Phase 4.

10. **[doc] Add US-014 to PRD-003 §7 user story table.**

11. **[doc] Add `datasketch` to runtime dependencies.**

12. **[doc] Fix PRD-003 Phase 3 gate** — remove Gunning Fog; use unit test criterion.

### Before PRD-004 Implementation Begins

13. **[decision] Taxonomy ADR** (ADR-009, same as item 3) — must be done before Phase 1
    label bootstrapping or annotation UI work.

14. **[design] Offline annotation mode** for `labeler_app.py` — local `data/raw/` loading
    instead of live EDGAR fetch; required for 58+ hours of annotation to be practical.

15. **[verify] SIC code in schema** — check `SegmentedRisks` Pydantic model before
    scheduling Phase 4 Step 4.3.

16. **[decision] Compute architecture** (OQ-5/OQ-9/OQ-10) — resolve in one ADR before any
    Phase 3 (PRD-002) or Phase 5-6 (PRD-004) throughput gates are meaningful.

---

## Contradiction & Gap Reference Table

| ID | Type | Severity | PRDs | Status | Blocks |
|:---|:-----|:---------|:-----|:-------|:-------|
| C-1 | Contradiction | Critical | PRD-001 ↔ PRD-002 | Open | PRD-002 Phase 2 |
| C-2 | Contradiction | Critical | PRD-001 ↔ PRD-002 | Open | Fine-tuning quality |
| C-3 | Contradiction | High | PRD-001/002 ↔ PRD-004 | Open | Classifier integration |
| C-4 | Contradiction | Medium | PRD-001 → PRD-004 | Open (OQ-8) | Schema consumers |
| D-1 | Doc gap | Low | PRD-003 §7 | US-014 missing | — |
| D-2 | Missing dep | Medium | PRD-003 | `datasketch` undeclared | PRD-003 Fix 4 install |
| D-3 | False gap | Medium | PRD-004 Phase 4 | SIC may exist | Wasted sprint |
| D-4 | Doc inconsistency | Low | PRD-002 | README vs. frontmatter | — |
| D-5 | False completion | Medium | PRD-002 Phase 1 | Open exit criterion | Phase gate integrity |
| D-6 | Wrong metric | Low | PRD-003 Phase 3 | Wrong quality gate | Phase gate integrity |
| F-1 | Infeasible | Critical | PRD-001/002 | No compute decision | Phase 3 throughput gate |
| F-2 | Infeasible | High | PRD-004 Phase 1 | No annotation plan | Fine-tuning timeline |
| F-3 | Infeasible (risk) | Medium | PRD-003 Phase 4 | Fallback rate unknown | Speedup claim validity |

---

*Research document generated from full read of PRD-001 through PRD-004 and README index.*
*Commit: d027985 · Branch: main · Date: 2026-02-18*

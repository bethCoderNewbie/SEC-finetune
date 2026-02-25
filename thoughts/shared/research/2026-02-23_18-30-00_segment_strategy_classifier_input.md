---
title: "Segment Strategy for Classifier Input — Context, Quality, and Token Compliance"
date: 2026-02-23
time: "18:30:00"
author: beth
git_commit: cd7dc5a
branch: main
status: PHASE_A_COMPLETE_FRAME_SHIFT
last_updated: 2026-02-24
update_git_commit: 0872eb3
phase_a_complete: true
frame_shift: boilerplate_contamination_not_length
related_research:
  - 2026-02-19_14-22-00_huggingface_classifier_input_formats.md
  - 2026-02-23_17-35_data_quality_validation.md
related_prd: PRD-004_Business_Intelligence_Use_Cases.md
---

# Segment Strategy for Classifier Input — Research Proposal

## Status Update (2026-02-24, git `0872eb3`)

**Upper-bound problem (>380 words) — CLOSED.** RFC-003 Option A was implemented
and documented in ADR-012. `max_segment_words: 380` is now the active ceiling in
`RiskSegmenter._split_long_segments`; the char gate (`max_segment_length`) remains
dormant at `999999999999`. See §2 for corrected full-corpus numbers.

**Lower-bound problem — Phase A COMPLETE; problem frame revised (2026-02-24).**
Phase A root-cause profiling executed on full corpus (607,463 segments / 4,423 filings,
run `20260223_182806`). The original S1–S4 framing (merge/filter sub-20-word segments) is
**obsolete**: sub-20-word segments number only 39 (0.01%) at full scale; `_merge_short_segments`
already handles them. The real problem is **boilerplate content contamination**: 52.7% of
≤100-word segments (499,089 total, 82.2% of corpus) are duplicate non-risk-factor text —
auditor language, financial statement headers, cross-section navigation — leaking through
an under-powered `_is_non_risk_content` filter. The §5 strategies and §6 rubric have been
revised accordingly. See §7 Phase A results and §2 Key Observation 5 for detail.

**Implementation note — S2 already exists:** `RiskSegmenter._merge_short_segments`
(added in commit `3ef72af`, `src/preprocessing/segmenter.py:300–328`) is already a
greedy forward-merge that matches Strategy S2. It runs inside the segmenter, not as
a separate post-segmentation transform. The §7 Phase B plan must be revised
accordingly (see §7 update below).

---

## 1. Motivation

Two independent constraints now collide at the segmentation layer:

**Constraint A — Classifier input (from `huggingface_classifier_input_formats.md`)**
- DeBERTa-v3-base (recommended): max **512 tokens** → ≈ **379 words** at 1.35 tok/word
- Quality gate §10: `word_count ≥ 20` ("segments below this will almost always route to
  `other` via QR-03")
- Each segment must be **one complete, self-contained risk statement** — atomic enough for
  a 9-class single-label head

**Constraint B — Pipeline quality gate (from `health_check.yaml` rev 2)**
- `50 ≤ char_count ≤ 2000` (blocking)
- `word_count ≥ 20` (blocking)
- `≥ 1 segment per filing` (blocking)

The pipeline and the classifier agree on the 20-word floor. They diverge on the ceiling:
the pipeline caps at 2000 chars (≈ 350–400 words), while DeBERTa's 512-token hard limit
truncates anything over ~379 words. ~~silently, without any current gate~~ **→ RESOLVED
2026-02-24: `max_segment_words: 380` gate deployed (RFC-003 Option A, ADR-012).**

---

## 2. Corpus Reality (run `20260223_172129`, 1,468 segments across 6 section files)

### Word count distribution

| Bracket | Count | % | Classification risk |
|---------|-------|---|---------------------|
| 0–9 words | 0 | 0.0% | — |
| **10–19 words** | **331** | **22.5%** | **FAIL quality gate — too short to classify** |
| 20–49 words | 645 | 43.9% | Ideal atomic range ✓ |
| 50–99 words | 320 | 21.8% | Good ✓ |
| 100–199 words | 143 | 9.7% | Fine ✓ |
| 200–379 words | 28 | 1.9% | Approaching ceiling, watch |
| **380+ words** | **1** | **0.1%** | **Truncation risk (marginal)** |

### Char count distribution

| Bracket | Count | % | Notes |
|---------|-------|---|-------|
| 50–99 chars | 158 | 10.8% | Mostly maps to 10-19 word segments |
| 100–499 chars | 1,026 | 69.9% | Target zone — one paragraph statement |
| 500–999 chars | 199 | 13.6% | Long but within all limits |
| 1,000–1,999 chars | 79 | 5.4% | Within 2000-char ceiling |
| **≥ 2,000 chars** | **6** | **0.4%** | WARN — over char ceiling |

### Full-corpus update (run `20260223_182806`, 607,463 segments / 4,423 filings)

Source: `reports/word_count_dist.json`, timestamp `2026-02-24T14:41:15`.

**Descriptive statistics:** mean=68.4 · median=48 · p95=**182** · max=3,232 · min=6

| Bucket | Count | % | Note |
|--------|-------|---|------|
| ≤100 | 499,089 | 82.2% | |
| 101–200 | 84,612 | 13.9% | |
| 201–300 | 16,633 | 2.7% | |
| 301–380 | 3,863 | 0.6% | ← Option A ceiling |
| 381–420 | 1,015 | 0.2% | |
| 421–500 | 1,058 | 0.2% | |
| >500 | 1,193 | 0.2% | |

**Threshold summary:**

| Threshold | Count | Rate | Status |
|-----------|-------|------|--------|
| >350 words | 4,277 | 0.70% | |
| **>380 words** | **3,266** | **0.54%** | **WARN → RFC-003 Option A deployed** |
| >420 words | 2,251 | 0.37% | |
| >500 words | 1,193 | 0.20% | |

Over-limit (>380 words): **3,266 / 607,463 = 0.54%**. Gate now active: `max_segment_words: 380` (ADR-012).

### Key observations

1. ~~**The short-segment problem dominates**~~ **REVISED (2026-02-24):** The 22.5%
   sub-20-word rate was a small-sample artefact. At full corpus scale the sub-20-word
   population is **39 segments (0.01%)**. `_merge_short_segments` already handles these.
   The length-based S1–S4 strategy frame is obsolete; see Observation 5.

2. ~~**The 512-token ceiling is not yet a practical problem**~~
   **CORRECTED (2026-02-24):** At full corpus scale, **3,266 segments (0.54%) exceed
   380 words** — not 1 segment (0.1%) as the small sample suggested. The WARN threshold
   was triggered; RFC-003 Option A was deployed (ADR-012). The gate is now active.

3. **The sweet spot is already large**: 65.7% of segments (20–99 words) in the small
   sample are in the ideal range. The full-corpus p95 of 182 words confirms the
   distribution is heavily concentrated below 200 words.

4. **ModernBERT's 8,192-token window adds no practical benefit**: p95=182 words
   at full scale; 0.54% exceed 380 words, well below the 5% contingency trigger
   (PRD-002 §4.1 OQ-3). DeBERTa-v3-base confirmed (ADR-008, ADR-012).

5. **NEW (2026-02-24) — The real problem is boilerplate contamination, not segment
   length.** Phase A descriptive analysis (`reports/short_segment_analysis.json`,
   `reports/short_segment_patterns.tsv`) shows:
   - **52.7% duplicate rate** in the ≤100-word population (263,064 / 499,089 rows share
     a text preview with at least one other segment)
   - Uniqueness *rises* with word count: 26.8% unique at 1-10 words → 53.7% at 76-100
     words — shorter segments are disproportionately boilerplate
   - Top contamination sources: auditor opinion language ("projections of any evaluation
     of effectiveness…", 655 repeats), "Table of Contents" navigation text, financial
     statement headers ("Notes to Consolidated Financial Statements", 73–93 repeats per
     variant), and **"REPORT OF MANAGEMENT RESPONSIBILITIES"** (5,241 segments, 13.3% unique)
   - `_is_non_risk_content` (`segmenter.py:337-368`) filters only 5 surface patterns
     and misses all of the above
   - The contamination suggests section boundary over-capture upstream (Stage 3 section
     extractor pulling adjacent non-Item-1A content); the segmenter cannot distinguish
     these without either stronger heuristics or upstream boundary correction

---

## 3. The Core Tensions

### Tension 1 — Atomicity vs. Context

A 20-word segment like:
> "The following regulatory changes may adversely affect our operations."

is atomic (one thought) but contextually weak — the classifier cannot reliably distinguish
`regulatory` from `macro` or `other` without knowing which regulations or operations.

Adding the **subsection title as a prefix** ("Item 1A — Cybersecurity Risk Factors:")
shifts the context window without changing segment boundaries. This is the **context
injection** approach.

Alternatively, **merging** the transition sentence with its following body paragraph
creates a longer, richer atomic unit — but at the cost of one training example becoming
a potential multi-topic segment.

### Tension 2 — Merging short segments vs. losing atomicity

A 15-word header ("We face risks related to data security and unauthorized access to
systems.") adjacent to a 35-word body paragraph forms a coherent 50-word unit. But if
the header appears before two different paragraphs, merging it with one severs its
relationship with the other.

Merge blindly → lose atomicity; don't merge → fail the 20-word gate.

### Tension 3 — Char ceiling vs. word ceiling

The pipeline caps segments at 2,000 chars; the classifier's true ceiling is ~379 words.
At typical prose density (5–6 chars/word), 379 words ≈ 1,900–2,300 chars — meaning the
char ceiling (2,000) and word ceiling (~379) are **nearly coincident for normal prose**
but diverge for dense technical text (abbreviations, codes) or padded text (long URLs,
table cell remnants).

A segment with 200 words but 2,100 chars (long chemical names, accession numbers) would
pass the word gate but fail the char gate. Investigation must confirm whether the 6
over-char segments are genuinely over-limit or are legacy data artefacts.

### Tension 4 — Sentence splitting granularity

The current `RiskSegmenter` (`src/preprocessing/segmenter.py`) splits on semantic breaks
or section headers. The 10-19 word segments may originate from:
- **Header nodes** included as text (subsection titles leaking into segment content)
- **Sentence-splitter over-splitting** (short transitional sentences)
- **List items** that are syntactically complete but semantically incomplete
- **Boilerplate fragments** ("See also Part II, Item 8.")

Understanding the *type* of short segment determines the right fix: filter vs. merge vs.
prefix-inject.

---

## 4. Research Questions

### RQ-1 — Short segment root cause
What node types (`TopSectionTitle`, `TitleElement`, `TextElement`, table cells) produce
the 331 short (10-19 word) segments? What fraction are: (a) subsection headers leaked as
content, (b) transitional/boilerplate sentences, (c) genuine risk statements that happen
to be brief?

**Why it matters:** Headers should be filtered or repurposed as context prefixes, not
trained on as standalone examples. Boilerplate should be removed. Genuine brief statements
are valid training data and should be merged with neighbours.

### RQ-2 — Context injection vs. segment merging
For the 20-49 word "sweet spot" segments, does prepending the parent subsection title
as a prefix (e.g., `[Cybersecurity Risks] We are subject to...`) measurably improve
classification confidence in zero-shot inference? Or does it add noise and dilute the
primary risk signal?

**Why it matters:** Context injection is non-destructive (segments stay atomic, word counts
unchanged) but adds tokens. Merging is destructive (collapses neighbouring segments,
reduces total example count).

### RQ-3 — Merge strategy boundary conditions
If merging short segments with adjacent ones, what are the correct boundary rules?

Candidate boundary conditions:
- (a) **Subsection boundary only**: never merge across `parent_subsection` changes
- (b) **Word-count target**: merge until combined `word_count ≥ 20`; stop before 380 words
- (c) **Semantic similarity**: merge only if cosine similarity ≥ threshold (existing
  `similarity_threshold=0.5` in `RiskSegmenter`)
- (d) **Order-preserving greedy**: scan forward, accumulate until threshold met or
  boundary crossed — simple and deterministic

**Why it matters:** The merging rule determines how many examples survive, their length
distribution, and whether merged segments are multi-topic (which breaks single-label
classification).

### RQ-4 — Token budget under DeBERTa's 512 ceiling
What is the actual token distribution (not word count) when the corpus is run through
`DebertaV2TokenizerFast`? SentencePiece Unigram with 128K vocab tends to produce
**fewer tokens per word** than WordPiece for financial text (fewer OOV splits). The
380-word proxy may be conservative — actual safe word limit may be 400–420 words.

Specific sub-questions — **ANSWERED (Phase A Task 3, 2026-02-24, full corpus):**
- p95 = **226 tokens**, p99 = **399 tokens** (full 607,463-segment corpus)
- 360–512 token danger zone: **5,736 segments (0.94%)**; over-512: **2,713 (0.45%)**
- The 380-word proxy is conservative: p99 is only 399 tokens, meaning 99% of all
  segments fit within the 512-token budget with headroom. The ceiling need not be relaxed.

**Why it matters:** If actual token usage is 10-15% below the 512 cap for typical
SEC prose, the 380-word ceiling is overly conservative and should be relaxed, freeing
some long segments from splitting.

### RQ-5 — Classifier sensitivity to segment length
At inference time (zero-shot with `ProsusAI/finbert`), what is the confidence distribution
for segments in each word-count bracket? The hypothesis from §10 of the classifier doc is
that segments < 20 words "almost always route to `other` via QR-03 (confidence < 0.70)".

Measuring this confirms whether the 20-word floor is *correct* or whether the effective
minimum is higher (25-30 words) or lower (15 words for highly specific risk language like
"GDPR non-compliance penalties").

---

## 5. Strategies to Evaluate

> **2026-02-24 Frame Revision:** S1 and S2 were designed for a sub-20-word length problem
> that does not exist at full corpus scale (0.01%). S2 is already implemented and working.
> The operative problem is **boilerplate content contamination** in the ≤100-word population.
> Strategies are re-assessed below in light of Phase A findings. A new strategy (S5) is
> added to address the actual problem. S3 remains valid as a signal enrichment mechanism.

### ~~Strategy S1 — Filter + hard merge~~ (DEPRIORITISED)
> **Status:** Near-vacuous at full scale. Affects only 39 segments (0.01%). The word-count
> floor gate already exists in `health_check.yaml`. No implementation work needed.

### ~~Strategy S2 — Greedy forward-merge~~ (ALREADY IMPLEMENTED)
> **Status:** `RiskSegmenter._merge_short_segments` (`segmenter.py:307-335`, commit `3ef72af`)
> implements S2 exactly. It is running in production and handling the 39 sub-20-word
> segments. No further S2 work is needed. Evaluation of its behaviour is complete.

### Strategy S3 — Context prefix injection (still valid; scope narrowed)
1. Keep all segments as-is
2. Prepend `[{parent_subsection}]` to each segment text at tokenization time

**Revised scope:** S3 is no longer needed to rescue short segments (S2 handles them).
Its remaining value is **classifier signal enrichment** for segments in the 20-50 word
range where the subsection title adds meaningful topical context. `parent_subsection`
fill rate = 100%, so the "not always available" con is eliminated.

**Pros:** Non-destructive; free classification signal; fill rate obstacle removed
**Cons:** Adds tokens (typically 4-8) to every segment; requires tokenizer-time injection;
does not address boilerplate contamination

### ~~Strategy S4 — Hybrid filter + merge + prefix~~ (PARTIALLY SUPERSEDED)
> **Status:** The merge and prefix components are covered by S2 (done) and S3 (narrowed).
> The header-filter component (step 1) is the only novel element, and it requires
> `node_type` metadata that is not persisted in `RiskSegment`. This is now subsumed by S5.

### Strategy S5 — Boilerplate content filter (NEW — addresses actual problem)
1. Expand `_is_non_risk_content` (`segmenter.py:337-368`) with pattern-based detection
   informed by `reports/short_segment_patterns.tsv` (top-500 repeated patterns)
2. Target contamination classes identified in Phase A:
   - Auditor opinion fragments ("projections of any evaluation of effectiveness…")
   - Financial statement navigation ("Table of Contents…Notes to Consolidated…")
   - Adjacent-section headers ("REPORT OF MANAGEMENT RESPONSIBILITIES", Item 1B boilerplate)
   - Cross-reference-only sentences ("See Part II, Item 8")
3. Investigate upstream source: determine which `section_identifier` values in the
   processed JSON files produce the contaminated segments — if the over-capture is in
   Stage 3 (section extractor), fix belongs there rather than in the segmenter

**Pros:** Addresses root cause directly; pattern list is data-driven from Phase A;
does not require schema changes; reduces corpus duplication rate
**Cons:** Pattern matching may have false positives (genuine risk statements that happen
to use auditor-adjacent phrasing); upstream fix in Stage 3 is cleaner but requires
separate investigation (OQ-6)

---

## 6. Evaluation Rubric

> **2026-02-24 Revision:** Rubric updated to reflect the Phase A frame shift from
> length-based to content-quality-based criteria. Struck-through rows are obsolete.

Each strategy must be measured against these criteria. Investigation should produce
a table for each strategy:

| Criterion | Target | Measurement | Status |
|-----------|--------|-------------|--------|
| Segments remaining after boilerplate filter | ≥ 60% of pre-filter count | count post-S5 | pending |
| min_word_count_rate post-strategy | 0.0 | `HealthCheckValidator.check_run()` | S2 live; 0.0 expected |
| Per-class example count ≥ 500 (PRD-004 gate) | all 9 classes | post-annotation label counts | pending annotation |
| ~~Merged segment multi-topic rate < 5%~~ | ~~< 5%~~ | ~~manual spot-check of 50 merged~~ | **DROPPED** — merging affects 0.01% of corpus; criterion is vacuous |
| **Boilerplate leak rate** | < 5% of surviving segments | match against `short_segment_patterns.tsv` top-100 patterns | pending S5 |
| **Text deduplication rate** | < 30% duplicate `text_preview` across corpus | rerun `analyse_short_segments.py` post-S5 | currently 52.7% — needs reduction |
| **Section source validation** | 0% of segments with `parent_subsection` matching non-Item-1A titles | group by `parent_subsection` in processed JSON | pending OQ-6 investigation |
| 95th pct token count under DeBERTa tokenizer | ≤ 400 tokens | `reports/token_profile.json` | **PASS — p95 = 226 tokens** |
| QR-03 routing rate on short segments (FinBERT zero-shot) | < 10% routed to `other` | inference sweep | pending Phase C |
| ~~`parent_subsection` coverage ≥ 90%~~ | ~~≥ 90%~~ | ~~schema check~~ | **MET** — 100% fill rate; criterion retired |

---

## 7. Investigation Plan

### Phase A — Root cause profiling ✅ COMPLETE (2026-02-24)

**Scripts written and executed on run `20260223_182806` (607,463 segments / 4,423 filings):**
- `scripts/validation/data_quality/diagnose_short_segments.py` — Tasks 1 + 2
- `scripts/validation/data_quality/token_profile.py` — Task 3
- `scripts/validation/data_quality/analyse_short_segments.py` — descriptive analysis of ≤100-word population

**Task 1 — Short segment sample:** COMPLETE
- 10-19 word bracket: **39 segments / 607,463 (0.01%)** — not 22.5% as the 1,468-segment
  sample suggested. Small-sample rate was a corpus artefact.
- Bracket expanded to ≤100 words to capture the meaningful population:
  **499,089 segments (82.16%)** of the full corpus.
- Output: `reports/short_segment_sample.tsv` (499,089 rows + header, with `word_bracket` column)

**Task 2 — `parent_subsection` fill rate:** COMPLETE
- **100% fill rate** across all 607,463 segments (0 nulls).
- OQ-1 answered: S3/S4 context injection is viable for the entire corpus — no degraded
  no-op cases due to missing subsection anchors.

**Task 3 — Token profile under `DebertaV2TokenizerFast`:** COMPLETE
- Output: `reports/token_profile.json`

| Stat | Value |
|------|-------|
| p50  | 58 tokens |
| p95  | **226 tokens** |
| p99  | 399 tokens |
| Max  | 3,886 tokens |
| Min  | 11 tokens |

| Zone | Count | % |
|------|-------|---|
| Danger zone 360–512 tok | 5,736 | 0.94% |
| Over-512 (silent truncation) | 2,713 | 0.45% |

**§9.3 gate: PASS** — p95 = 226 tokens (well under 400 target).

**Additional — Descriptive analysis of ≤100-word population:**
- Output: `reports/short_segment_analysis.json`, `reports/short_segment_patterns.tsv`
- **52.7% duplication rate** in the ≤100-word set (263,064 / 499,089 rows share a text preview
  with at least one other segment)
- Uniqueness rate *rises with word count*: 26.8% unique at 1-10 words → 53.7% at 76-100 words,
  confirming that very short segments are predominantly boilerplate
- Top repeated patterns: auditor boilerplate ("projections of any evaluation of effectiveness…"),
  "Table of Contents" navigation text, financial statement headers
- `REPORT OF MANAGEMENT RESPONSIBILITIES` (5,241 segments, 13.3% unique) is near-pure boilerplate;
  contrast `Human Capital` (2,145 segments, 64.7% unique) — mostly original risk text in same bracket
- **OQ-1 CLOSED**: all segments have `parent_subsection`; S3/S4 prefix injection is universally applicable

**Expected output (original):** A 3-row table (header%, transitional%, genuine-brief%) + token histogram
**Actual output:** Token histogram delivered. The 3-row manual categorisation table requires
human review of `reports/short_segment_sample.tsv` (fill `category` column).

### Phase B — Boilerplate contamination investigation + S5 filter (1-2 sessions)

> **2026-02-24 full reframe:** Phase B is no longer about S3/S4 prototyping for
> sub-20-word segments. S2 is implemented and working. S3 is a valid follow-on for
> signal enrichment but is not blocking. The Phase B priority is now diagnosing and
> filtering the boilerplate contamination identified in Phase A.

**Task B1 — Section source diagnosis (OQ-6)**

Determine which `section_identifier` values in the processed batch produce the
contaminated segments. The hypothesis is that non-Item-1A section identifiers
(`part1item1b`, `part2item7`, `part2item8`, etc.) are being included in runs that
should only process Item 1A risk factors, or that Item 1A extraction boundaries
are drifting into adjacent sections.

```bash
# Group segments by section_identifier via filing filename stem
# e.g. WFC_10K_2025_part1item1b_segmented.json → section = part1item1b
# Count and dedupe-rate per section type
```

If contamination is concentrated in specific `section_identifier` values → fix belongs
in the pipeline dispatch config (which section types are included in a given run),
not in `_is_non_risk_content`.

If contamination cuts across all section types → fix belongs in `_is_non_risk_content`.

**Task B2 — Expand `_is_non_risk_content` (S5, if B1 confirms in-segmenter fix)**

Extend `segmenter.py:337-368` with pattern-based detection against Phase A findings:
- Auditor opinion fragments (`reports/short_segment_patterns.tsv` rows 1–10)
- Financial statement navigation ("Table of Contents", "Notes to Consolidated")
- Adjacent-section headers whose text matches known non-risk titles
- Cross-reference-only fragments (existing `_CROSS_REF_DROP_PAT` — extend similarly)

Patterns must be length-gated (e.g. `len(text.split()) < N`) to avoid false positives
on genuine risk paragraphs that happen to reference auditor standards.

**Task B3 — S3 context prefix injection (signal enrichment, lower priority)**

If B1/B2 raise corpus quality to acceptable dedup rate (<30%), prototype
`InjectSubsectionPrefix` as a tokenizer-time wrapper. `parent_subsection` = 100%
filled so no no-op cases. This is not blocking for Phase C.

**Do NOT modify:**
- `RiskSegment` model (node_type requires ADR and schema migration — out of scope)
- `_merge_short_segments` (S2 — working correctly, do not touch)

### Phase C — Validation sweep (1 session)

1. Re-run `check_preprocessing_batch.py` on the transformed output
2. All 6 section files should pass `min_word_count_rate = 0.0`
3. Run FinBERT zero-shot on 100 sampled segments (before and after transform) — measure
   QR-03 routing rate to `other`
4. Report retention rate and length distribution shift

---

## 8. Scope

### In scope
- Root cause analysis of 10-19 word segments in the current corpus (Phase A)
- Token profiling under DeBERTa tokenizer (Phase A task 3)
- Evaluation of existing S2 (`_merge_short_segments`) against Phase A findings
- Context prefix injection prototype (S3) and hybrid filter (S4) if S2 is insufficient
- ~~Updated `min_segment_words` config field~~ **already existed; `max_segment_words: 380` added (ADR-012)**

### Out of scope
- Changes to `RiskSegmenter` sentence-splitting logic (separate story)
- Persisting `node_type` in `RiskSegment` (requires ADR and schema migration)
- Fine-tuning any classifier (Phase 2; this is pre-training data preparation)
- JSONL annotation pipeline changes (those come after this strategy is selected)

---

## 9. Success Criteria

The winning strategy is selected when all of the following hold on the
`20260223_182806` run (or a fresh equivalent run post-S5):

1. `min_word_count_rate = 0.0` on all section files — **already met** (S2 running)
2. ~~Segment retention ≥ 80% of 331 short segments~~ **REVISED:** Corpus retention
   ≥ 60% of pre-filter segment count after S5 boilerplate filtering. Framed as
   retention of valid content, not preservation of short segments.
3. 95th percentile token count ≤ 400 under `DebertaV2TokenizerFast` — **already met**
   (p95 = 226 tokens, `reports/token_profile.json`)
4. ~~Manual review of 50 post-merge segments: multi-topic rate < 5%~~ **DROPPED.**
   Merging affects 0.01% of corpus. Replaced by: boilerplate leak rate < 5% on a
   random sample of 100 post-S5 segments (manual spot-check against Phase A pattern list)
5. `over_limit_word_rate = 0.0` in health check — enforced automatically by
   `max_segment_words: 380` in `_split_long_segments` (RFC-003 Option A, ADR-012)
6. **NEW:** Text deduplication rate < 30% in the post-S5 ≤100-word population
   (currently 52.7%; target requires removing the auditor / navigation boilerplate
   classes identified in Phase A)

---

## 10. Open Questions

| ID | Question | Blocker for |
|----|----------|-------------|
| ~~OQ-1~~ | ~~What fraction of 10-19 word segments have `parent_subsection = None`?~~ **CLOSED 2026-02-24**: fill rate = **100%** across all 607,463 segments. S3/S4 context injection is viable for the entire corpus. | ~~S3, S4~~ |
| ~~OQ-2~~ | ~~Does greedy forward-merge respect filing order correctly?~~ **CLOSED 2026-02-24**: S2 is implemented and running in production. Each JSON file is a single filing; merge cannot cross filing boundaries by construction. | ~~S2~~ |
| ~~OQ-3~~ | ~~Is `chunk_id` format stable enough post-merge?~~ **DEPRIORITISED**: S2 merges within the segmenter before `chunk_id` is assigned (`segment_extracted_section` assigns IDs after `segment_risks` returns). Merged segments receive a single sequential ID; no composite ID is needed. | ~~S2~~ |
| OQ-4 | Are the 6 over-char (≥2000) segments structural artefacts (table cells, footnotes) or genuine long risk paragraphs that should be split? At full corpus scale, max word count is 3,232 — confirming the long tail is real. `max_segment_words: 380` will split these; the char gate remains dormant. | All strategies |
| OQ-5 | At what word count does FinBERT zero-shot confidence reliably exceed 0.70 for known-topic segments? This empirically sets the actual minimum, which may differ from the theoretical 20-word gate. | Phase C |
| OQ-6 | **NEW** — Which `section_identifier` values are the primary source of boilerplate contamination? Is the over-capture happening in Stage 3 section extraction (wrong section boundaries) or in the run dispatch config (wrong sections included)? The answer determines whether S5 fix belongs in `_is_non_risk_content` or upstream. | S5, Phase B |
| OQ-7 | **NEW** — After applying S5 boilerplate filter, does the per-class example count still meet PRD-004's ≥500 target for all 9 risk categories? Filtering 52.7% of the ≤100-word population could reduce annotation-eligible segments significantly. | S5 retention gate |

---
title: "Segment Strategy for Classifier Input — Context, Quality, and Token Compliance"
date: 2026-02-23
time: "18:30:00"
author: beth
git_commit: cd7dc5a
branch: main
status: PROPOSAL
related_research:
  - 2026-02-19_14-22-00_huggingface_classifier_input_formats.md
  - 2026-02-23_17-35_data_quality_validation.md
related_prd: PRD-004_Business_Intelligence_Use_Cases.md
---

# Segment Strategy for Classifier Input — Research Proposal

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
truncates anything over ~379 words — silently, without any current gate.

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

### Key observations

1. **The short-segment problem dominates**: 22.5% of segments fail the 20-word gate.
   Token overflow (380+ words) affects 0.1% — essentially solved.

2. **The 512-token ceiling is not yet a practical problem**: Only 1 segment exceeds 380
   words in this corpus. The RFC-003 Option A design for `over_limit_word_rate` is correct
   as a forward-looking guard but not an immediate priority.

3. **The sweet spot is already large**: 65.7% of segments (20–99 words) are in the ideal
   range for atomic single-label classification.

4. **ModernBERT's 8,192-token window adds no practical benefit**: With a max of ~380 words
   observed, there is no corpus-level justification to pay ModernBERT's 149M-parameter cost
   over DeBERTa-v3-base (86M). The contingency trigger (>5% segments exceeding 390 words)
   is not met.

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

Specific sub-questions:
- What is the 95th/99th percentile token length in the current 1,468-segment corpus?
- How many segments are between 360–512 tokens (truncation risk zone)?
- For the 28 segments in the 200-379 word range, what is their actual token count?

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

Four candidate strategies, evaluated against a shared rubric in §6:

### Strategy S1 — Filter + hard merge (simplest)
1. Remove segments where `word_count < 20` (drop or quarantine)
2. If removal produces a filing with 0 segments → FAIL
3. Accept the corpus reduction

**Pros:** Zero implementation risk; existing gates enforce it
**Cons:** Loses 22.5% of corpus (331 segments); may drop genuinely valuable brief statements;
reduces training data below PRD-004's per-class minimums

### Strategy S2 — Greedy forward-merge (recommended to investigate first)
1. Scan segments in order within each filing/subsection boundary
2. Accumulate a "buffer" until combined `word_count ≥ 20`
3. Emit merged segment; reset buffer
4. At subsection boundary, emit whatever is in the buffer regardless of length

**Pros:** Preserves all text; deterministic; respects subsection context
**Cons:** Merged segments may be multi-topic (reduces label purity); increases average
segment length, shifting the distribution toward the 50-99 word bracket

### Strategy S3 — Context prefix injection (non-destructive)
1. Keep all segments as-is (including 10-19 word segments)
2. Prepend `[{parent_subsection}]` to each segment text at tokenization time
3. Lower the effective word-count gate for segments with strong subsection context:
   subsection-prefixed 10-word segment may be equivalent to a bare 15-word segment

**Pros:** Non-destructive; no corpus reshaping; subsection titles add
free classification signal
**Cons:** Requires tokenizer changes; subsection titles not always available
(`parent_subsection` is `Optional[str]` in `RiskSegment`); doesn't resolve the
fundamental brevity problem for segments without a subsection parent

### Strategy S4 — Hybrid: filter headers + merge orphans + prefix body
1. Identify segments that are subsection headers (node_type=`TitleElement`, length<40 chars)
   → repurpose as context, do NOT include in training data
2. Merge remaining sub-20-word segments with forward neighbour using S2 greedy logic
3. Prepend subsection title prefix to all segments with a known `parent_subsection`

**Pros:** Addresses root causes differently per segment type; likely best data quality
**Cons:** Most complex; requires node-type metadata to survive into the output schema
(currently not persisted in `RiskSegment`)

---

## 6. Evaluation Rubric

Each strategy must be measured against these criteria. Investigation should produce
a table for each strategy:

| Criterion | Target | Measurement |
|-----------|--------|-------------|
| Segments remaining after strategy | ≥ 80% retention | count |
| min_word_count_rate post-strategy | 0.0 | `HealthCheckValidator.check_run()` |
| Per-class example count ≥ 500 (PRD-004 gate) | all 9 classes | post-annotation label counts |
| Merged segment multi-topic rate | < 5% | manual spot-check of 50 random merged segments |
| 95th pct token count under DeBERTa tokenizer | ≤ 400 tokens | actual tokenization |
| QR-03 routing rate on short segments (FinBERT zero-shot) | < 10% routed to `other` for known-label segments | inference sweep |
| `parent_subsection` coverage | ≥ 90% segments with known subsection | schema check |

---

## 7. Investigation Plan

### Phase A — Root cause profiling (1 session)

**Files to read:**
- `src/preprocessing/segmenter.py` — full read, understand all splitting paths
- `src/preprocessing/models/segmentation.py:14-30` — `RiskSegment.chunk_id`, `parent_subsection`
- A sample of the 331 short segments: extract and classify by type

**Tasks:**
1. Write a diagnostic script that samples 50 random segments from the 10-19 word bracket,
   prints `(chunk_id, parent_subsection, word_count, text[:100])`, and manually categorises
   each as: header / transitional / boilerplate / genuine-brief-risk
2. Measure `parent_subsection` fill rate across all 1,468 segments (how many have a known
   subsection vs. `None`)
3. Run the current corpus through `DebertaV2TokenizerFast` and report p50/p95/p99 token
   lengths and the count in the 360-512 token danger zone

**Expected output:** A 3-row table (header%, transitional%, genuine-brief%) + token histogram

### Phase B — Strategy prototyping (1-2 sessions)

**Target:** implement S2 (greedy merge) and S4 (hybrid) as post-segmentation transforms,
NOT as changes to the segmenter itself. The transform runs after `SegmentedRisks` is built,
before `save_to_json()`.

**Files to modify:**
- New file: `src/preprocessing/segment_transform.py` — contains `MergeShortSegments`,
  `InjectSubsectionPrefix` transforms
- `src/config/preprocessing.py` — add `min_segment_words: int = 20` to `PreprocessingConfig`
  so the merge threshold is configurable

**Do NOT modify:**
- `src/preprocessing/segmenter.py` — the segmenter produces its output; transforms operate
  on the output
- `RiskSegment` model — adding node_type to the schema is a separate ADR (out of scope here)

### Phase C — Validation sweep (1 session)

1. Re-run `check_preprocessing_batch.py` on the transformed output
2. All 6 section files should pass `min_word_count_rate = 0.0`
3. Run FinBERT zero-shot on 100 sampled segments (before and after transform) — measure
   QR-03 routing rate to `other`
4. Report retention rate and length distribution shift

---

## 8. Scope

### In scope
- Root cause analysis of 10-19 word segments in the current 1,468-segment corpus
- Token profiling under DeBERTa tokenizer
- Greedy merge transform (S2) implementation and validation
- Context prefix injection prototype (S3)
- Updated `min_segment_words` config field

### Out of scope
- Changes to `RiskSegmenter` sentence-splitting logic (separate story)
- Persisting `node_type` in `RiskSegment` (requires ADR and schema migration)
- Fine-tuning any classifier (Phase 2; this is pre-training data preparation)
- JSONL annotation pipeline changes (those come after this strategy is selected)

---

## 9. Success Criteria

The winning strategy is selected when all of the following hold on the
`20260223_172129` run (or a fresh equivalent run):

1. `min_word_count_rate = 0.0` on all section files (blocking gate passes)
2. Segment retention ≥ 80% (i.e., ≤ 294 of the 331 short segments are merged,
   not dropped)
3. 95th percentile token count ≤ 400 under `DebertaV2TokenizerFast`
4. Manual review of 50 post-merge segments: multi-topic rate < 5%
5. No new `over_limit_word_rate` violations introduced by merging

---

## 10. Open Questions

| ID | Question | Blocker for |
|----|----------|-------------|
| OQ-1 | What fraction of 10-19 word segments have `parent_subsection = None`? Without a subsection anchor, S3/S4 context injection degrades to no-op. | S3, S4 |
| OQ-2 | Does greedy forward-merge respect filing order correctly in multi-section output files (which aggregate across many filings)? Merge must not cross filing boundaries. | S2, S4 |
| OQ-3 | Is `chunk_id` format ("1A_001") stable enough to reconstruct filing provenance post-merge? A merged segment needs a composite `chunk_id` to remain traceable. | S2, S4 |
| OQ-4 | Are the 6 over-char (≥2000) segments structural artefacts (table cells, footnotes) or genuine long risk paragraphs that should be split? | All strategies |
| OQ-5 | At what word count does FinBERT zero-shot confidence reliably exceed 0.70 for known-topic segments? This empirically sets the actual minimum, which may differ from the theoretical 20-word gate. | S1 (sets the filter threshold) |

---
title: "Ingestion & Normalization Pipeline — Gap Analysis"
date: 2026-02-24
commit: 997a10101f7fa5ce1794bc90061ab707d3fe10ce
branch: main
author: bethCoderNewbie <beth88.career@gmail.com>
topic: Ingestion, Layout Analysis, Contextual Enrichment, LLM Extraction, Validation
amended: 2026-02-24
amendments:
  - "Step 2 Layout Analysis: updated with RFC-006 findings — LayoutLM/DocLayNet/Detectron2 ruled out as architecturally mismatched to HTML-native EDGAR filings; rule-based Option A (A1 ListItem, A2a H-labels, A3 paragraph boundaries) adopted instead"
  - "Complexity matrix row 2 updated: effort downgraded from Low-High to Low (~230 LoC)"
  - "Recommended Next Steps Phase A/B updated to reference RFC-006 sub-options"
  - "What Conflicts section: ML visual layout model entry reclassified as wrong-tool-for-context, not an ADR conflict"
related_rfc: docs/architecture/rfc/RFC-006_layout_analysis_model_evaluation.md
---

# Gap Analysis: Proposed 5-Step Pipeline vs. Current State

## Proposed Pipeline (Target State)

| Step | Name | Description |
|------|------|-------------|
| 1 | Ingestion & Normalization | Pull raw HTML **or XBRL** from EDGAR; XBRL for structured financials, HTML for narrative (MD&A, Notes, Risk Factors) |
| 2 | Layout Analysis | Pass document through a layout model to tag every text block: Title, H1, H2, List Item, Table |
| 3 | Contextual Enrichment | Append full parent hierarchy to every child node |
| 4 | LLM Extraction | Prompt an LLM with specific instructions (e.g., "Extract forward-looking supply chain risk statements → JSON array") |
| 5 | Validation | Deterministic scripts + optional secondary LLM to validate types and detect hallucinations |

---

## Current Pipeline (Implemented State)

```
Stage 0 — sgml_manifest.py     SGML byte index (10 ms, < 10 KB manifest)
Stage 1 — pre_seeker.py        ToC anchor pre-seek → HTML slice (50 ms, ~50–200 KB)
Stage 2 — parser.py            sec-parser v0.54.0 → ParsedFiling (elements + tree + metadata)
Stage 3 — extractor.py         SECSectionExtractor → ExtractedSection (text + subsections + metadata)
Stage 3.5 — cleaning.py        TextCleaner → cleaned text (whitespace, ToC artifacts, HTML tags)
Stage 4 — segmenter.py         RiskSegmenter → SegmentedRisks (JSON chunks, RFC-003 word ceiling)
```

---

## Step 1: Ingestion & Normalization

### What Exists

| Capability | Implementation | File | Quality |
|------------|---------------|------|---------|
| EDGAR SGML container parsing | `extract_sgml_manifest()` — byte-indexed scan, no full load | `sgml_manifest.py:57` | Production-ready |
| HTML wrapper stripping | Locates `<SEC-HEADER>` by byte search; skips HTML preamble | `sgml_manifest.py:85` | Production-ready |
| Multi-encoding fallback | UTF-8 → windows-1252 → latin-1 | `pre_seeker.py:205` | Production-ready |
| Narrative HTML extraction | Pre-seek returns 50–200 KB slice for Item 1A, MD&A | `pre_seeker.py:46` | Production-ready |
| iXBRL (Inline XBRL) handling | sec-parser handles embedded `<ix:*>` tags natively | `parser.py:90` | Handled by dependency |
| EDGAR download | sec-downloader v≥0.10.0 (referenced in PRD-002) | `requirements.txt` | Exists as library |
| Byte-range extraction | `extract_document()` reads only target document bytes | `sgml_manifest.py:130` | Production-ready |
| Accession number / CIK / SIC | Extracted from `<SEC-HEADER>` and DEI ix:hidden block | `sgml_manifest.py:163`, `parser.py:356` | Production-ready |

### Gaps

| Gap | Severity | Detail |
|-----|----------|--------|
| **Pure XBRL instance document extraction** | High | `sgml_manifest.py` indexes `<TYPE>XBRL INSTANCE DOCUMENT` byte offsets, but nothing **parses** the XBRL `.xml` to extract structured financial tags (revenue, EPS, segment data). The data sits at `manifest.xbrl_instance_offset` but is never consumed. |
| **EDGAR API orchestration** | Medium | Files are manually downloaded to `data/raw/`. No automated EDGAR full-text search (EFTS) or CIK-based filing enumeration is wired into the pipeline. The downloader library is a dep but has no integration module. |
| **Normalization schema** | Medium | There is no unified "NormalizedDocument" output model. Each stage emits its own Pydantic model (SGMLManifest → ParsedFiling → ExtractedSection → SegmentedRisks). Consumers of the ingested data must chain all 4 stages manually. |
| **8-K / proxy statement support** | Low | Non-goal per PRD-002/PRD-004. Only 10-K/10-Q supported. |
| **Filing index (MetaLinks.json, FilingSummary.xml)** | Low | ADR-010 notes these are addressable but not yet consumed. |

### Complexity to Close Gaps

- **XBRL parsing**: Medium-High. Requires `arelle` or `python-xbrl` library + schema to map XBRL concepts to a normalized dict. ~200-400 LoC + test suite. Deferred in all current PRDs.
- **EDGAR orchestration**: Medium. Wire `sec-downloader` into a new `ingestor.py` module with filing enumeration by CIK/date-range/form-type. ~150-250 LoC.
- **NormalizedDocument model**: Low. Add a new Pydantic model wrapping the chain. Naming/schema design is the main effort.

---

## Step 2: Layout Analysis

### What Exists

| Capability | Implementation | File | Quality |
|------------|---------------|------|---------|
| Text block classification | `sec-parser` emits: `TextElement`, `TitleElement`, `TableElement`, `TableOfContentsElement`, `PageHeaderElement` | `parser.py:90` | Rule-based, not model-based |
| Title depth | `TitleElement.level` is a **CSS-style-appearance index** (0 = first unique bold style encountered in the filing), not a semantic H-label. Audit across 50 filings: level=0 is a subsection heading in 92.9% of occurrences — not Part/Item (RFC-006 OQ-2). | `extractor.py:302` | Present but not cross-filing comparable |
| Table detection | `isinstance(node.semantic_element, sp.TableElement)` (inline) | `extractor.py:368` | Production-ready |
| ToC detection | `TableOfContentsElement` + `TOC_PATTERNS_COMPILED` (7 patterns) | `extractor.py:445`, `constants.py` | Heuristic-quality |
| Page header removal | `PAGE_HEADER_PATTERN` regex; Stage 3 post-filter | `extractor.py:376`, `constants.py` | Production-ready |
| Section taxonomy | `SectionIdentifier` enum — 14 10-K sections, 8 10-Q sections | `constants.py` | Production-ready |
| iXBRL inline tags | sec-parser handles embedded `<ix:*>` tags natively; `parser.py:26` monkey-patches `get_approx_table_metrics` (NoneType/th-only table fix, unrelated to XBRL) | `parser.py:26` | Functional |

### Gaps

| Gap | Severity | Detail |
|-----|----------|--------|
| **List Item type** | High | No `ListItemElement` type. Bulleted/numbered lists inside Risk Factors are parsed as generic `TextElement`. **Corpus audit (961 files, 2026-02-25):** `<li>`/`<ul>`/`<ol>` tags — **0% of corpus**. Unicode bullet chars (`•`, `·`, `▪`) embedded directly in TextElement text — **94.1%**. `(N)` parenthetical prefix — 27.3%. Only 3.3% of filings use pure flowing paragraphs. Detection must use text-content regex, not HTML tag inspection (RFC-006 OQ-1). |
| **H1 / H2 / H3 explicit labels** | Medium | `TitleElement.level` is a **document-relative** integer assigned by `TitleClassifier._unique_styles_by_order` (CSS-style-appearance order within a single filing). Level 0 = first unique bold/large-font style encountered — not a canonical H1. The same section heading can be `level=0` in one filing and `level=1` in another. Not comparable across filings without normalization. |
| **Paragraph boundary detection** | Medium | `TextElementMerger` in sec-parser reassembles `<span>`-fragmented text but does not record `<p>` tag seam positions. The segmenter splits by double newlines as a lossy proxy. |
| **Model-based layout analysis** | Resolved/Low | **RFC-006 finding: visual layout models (LayoutLM, DocLayNet, Detectron2) are architecturally mismatched to HTML-native EDGAR filings.** These models require HTML→PDF rendering → page image → bounding box extraction before inference, adding 20–120 min rendering time per corpus run plus GPU dependency. For HTML-native documents, inline CSS signals (already extracted by `TitleClassifier`) are strictly more accurate than pixel inference. Rule-based post-processing enhancements (RFC-006 Option A) close all three gaps above without new dependencies. See `docs/architecture/rfc/RFC-006_layout_analysis_model_evaluation.md`. |
| **Figure / Image blocks** | Low | No image extraction. Inline `<img>` tags are ignored. For EDGAR HTML filings this is minor; for PDF-converted filings it would be a gap. |

### Complexity to Close Gaps

> **RFC-006 concluded:** Rule-based post-processing (Option A) is the correct approach for HTML-native filings. Visual layout models are not recommended. Text-classifier ML (Option B) is deferred until labeled training data exists.

**RFC-006 Option A sub-options, in priority order:**

- **A1 — List Item detection** (~40 LoC, revised): Apply `_BULLET_PREFIX_PAT` regex to `node.text`. ~~`node.html_tag.name in ('li',)`~~ — `<li>` tags have 0% corpus coverage (OQ-1 audit). Pattern must use `\s*` (not `\s+`) after bullet char: EDGAR emits `•word` with no space. Tag matching elements with `is_list_item: True` in the `elements` dict.
- **A2a — H-label normalization** (~80 LoC): Anchor H1/H2 to `TopSectionTitle` nodes (already classified by sec-parser). `TitleElement` level integers are filing-relative CSS indices — level=0 is a subsection heading 92.9% of the time (OQ-2 audit, 50 filings). A2b (level-threshold) is ruled out. A2a structural anchoring via `TopSectionTitle` is the only viable approach.
- **A3 — Paragraph boundary annotation** (~50 LoC): BS4 pass on `node.html_tag` to record `<p>` tag boundary offsets as `boundaries: List[int]` in the elements dict. Operates on merged `TextElement` outputs; no conflict with `TextElementMerger` (OQ-4 confirmed).

| Sub-option | LoC | New deps | GPU | Risk | Notes |
|------------|-----|----------|-----|------|-------|
| A1 ListItem detection | ~40 | None | No | Low | `<li>` branch removed (0% corpus); `•word` no-space pattern |
| A2a H-label normalization | ~80 | None | No | Low | A2b ruled out by OQ-2 audit |
| A3 paragraph boundaries | ~50 | None | No | Low | OQ-4 confirmed no conflict |
| **Total Option A** | **~170** | **None** | **No** | **Low** | |

### Project-Level Benefits by RFC-006 Sub-option

> Benefits are stated in terms of downstream pipeline stages, training data quality, and unblocking dependencies — not just the local layout fix.

#### A1 — ListItem detection (~40 LoC, revised after OQ-1 audit)

**Corpus reality (961 files, 2026-02-25):** 94.1% of filings encode list entries as `TextElement` nodes beginning with a unicode bullet char (`•word` with no space), not `<li>` tags (0% corpus coverage). Without A1, these are split by spaCy sentence boundaries — cutting mid-list when a single bullet entry spans multiple sentences. With A1:

- **Segmentation quality (Step 4 input):** Each bullet-prefixed `TextElement` becomes a natural segment boundary. `RiskSegmenter` can emit one segment per bullet entry, reducing `short_segment_rate` and orphaned-fragment artifacts. Directly improves the primary training data quality KPI.
- **LLM extraction (Step 4):** Bullet entries are semantically self-contained risk statements. Prompting a model with one bullet per chunk (vs. a mid-sentence fragment) reduces ambiguity and hallucination risk.
- **Validation (Step 5):** Lower `short_segment_rate` means fewer DLQ entries caused by segmentation failures (complements G-01 DLQ root-cause fix).

No other pipeline stage is blocked on A1, but it raises the quality floor for all downstream work.

#### A2a — H-label normalization, structural anchoring (~80 LoC)

`TitleElement.level` is a CSS-style-appearance index, not a semantic H-label. **OQ-2 audit (50 filings, 2026-02-25): level=0 is a subsection heading in 92.9% of occurrences** — titles like `"Overview"`, `"Results of Operations"`, `"Basis for Opinion"`. `ITEM 1A. RISK FACTORS` was observed at level=3 in one filing. A2b (level-threshold) is definitively ruled out. With A2a (`TopSectionTitle` structural anchor → filing-invariant H1/H2/H3 mapping):

- **Contextual enrichment (Step 3, RFC-007 D1/D2):** The `ancestors` breadcrumb field (RFC-007 Decision D1-B) requires title-type labels to be meaningful. Filing-invariant H-labels mean a breadcrumb like `["Item 1A", "H2: Supply Chain Risk", "H3: Procurement"]` is comparable across all filings, not just within one. **A2a is a prerequisite for RFC-007 D2 (ancestors schema) to carry useful structural information.**
- **Corpus-level analysis:** Cross-filing aggregation of heading structure (e.g., "which filings have 3+ levels of subsection nesting in Item 1A?") becomes possible. This informs corpus curation for the annotation effort (PRD-002 G-16).
- **LLM prompts (Step 4):** Including the H-level in the prompt context ("H2 section: Supply Chain Risk > H3 subsection: Procurement disruption") gives the LLM richer structural grounding, reducing the chance of confusing sibling sections.

#### A2b — H-label normalization, level-threshold (**RULED OUT**)

**Invalidated by OQ-2 corpus audit (2026-02-25).** The assumption that level=0 ≈ Part/Item heading is false: 92.9% of level=0 nodes are subsection headings. No downstream benefit can be realized from a mapping that is wrong for 93% of inputs. A2b is removed from scope.

#### A3 — Paragraph boundary annotation (~50 LoC)

`TextElementMerger` in sec-parser reassembles `<span>`-fragmented text but does not record `<p>` tag seam positions. The segmenter currently uses double-newline as a paragraph-boundary proxy. With A3 (`boundaries: List[int]` of `<p>` tag offsets in merged text):

- **Segmentation precision (Step 4 input):** Splitting at true `<p>` boundaries instead of double-newline heuristics reduces mid-paragraph cuts for filings that use `<p>` tags without blank lines between them (common in older iXBRL HTML).
- **Chunk coherence:** More coherent chunks → better embedding quality for downstream retrieval-augmented workflows (fine-tuning, semantic search). Also reduces the probability that a sentence-boundary split from spaCy cuts inside a parenthetical clause that spans `<p>` tags.
- **Lowest priority of Option A:** A1 and A2a deliver higher ROI per LoC. A3 is a tertiary refinement recommended for Phase B after A1/A2a are validated in production.

#### Option B — Fine-tuned text classifier (deferred)

No immediate project benefit. Requires: (a) A1/A2a/A3 implemented and production failures documented, (b) labeled EDGAR element dataset (PRD-002 G-16, ≥500 examples/archetype). If eventually adopted, provides robustness to unusual CSS patterns (~5% edge case filings) where rule-based approaches misclassify. **Defer until Option A production metrics show a ceiling.**

#### Option C — Visual layout models (not recommended)

No project benefit for the current corpus. Would add 20–120 minutes of headless-Chrome rendering + GPU inference per corpus run, require bounding-box → HTML re-mapping (estimated 15–25% alignment error), and conflict with ADR-002 (sec-parser pin), ADR-003 (CPU-only worker pool), and ADR-010 Rule 1 (no HTML modification before sec-parser). Architecturally correct only for pre-2000 scanned/image EDGAR filings, which are out of scope for all current PRDs.

---

## Step 3: Contextual Enrichment

### What Exists

| Capability | Implementation | File | Quality |
|------------|---------------|------|---------|
| 2-level hierarchy | `parent_subsection` field on every `RiskSegment`; maps to nearest preceding `TitleElement` | `segmenter.py:370` (Fix 6B) | Production-ready |
| node_subsections list | `ExtractedSection.node_subsections` carries `(node_text, subsection_title)` tuples in doc order | `extractor.py:393` | Production-ready |
| Section identifier | `chunk_id` (e.g., `1A_001`) encodes section + ordinal | `segmenter.py:176` | Production-ready |
| Document-level metadata | Company, CIK, SIC, form type, fiscal year, accession number on every chunk | `segmenter.py:segment_extracted_section` | Production-ready |
| Amendment / filer category | `amendment_flag`, `entity_filer_category` from DEI ix:hidden (ADR-011) | `parser.py:421` | Production-ready |

### Gaps

| Gap | Severity | Detail |
|-----|----------|--------|
| **Full document tree ancestry** | High | Current hierarchy is 2-level: `{section} → {subsection}`. The proposed pipeline wants full breadcrumb: `Document > Part I > Item 1A > Subsection > Paragraph`. The `sec-parser` tree (`sp.TreeNode`) provides this, but it is not serialized into the output JSON. |
| **Node-level parent pointers** | Medium | Each `RiskSegment` only carries the nearest ancestor subsection. There is no list of all ancestor titles (depth-traversal path). Implementing "append parent hierarchy to every child node" as specified requires walking the `sp.TreeNode` parent chain during extraction. |
| **Cross-section linking** | Low | No mechanism to link a risk factor chunk to the relevant MD&A passage or Notes section that discusses the same topic. |
| **Enrichment for non-risk sections** | Low | `parent_subsection` is only populated for risk factor segments. MD&A segments (if extracted) would have no subsection enrichment today. |

### Complexity to Close Gaps

- **Full breadcrumb serialization**: Medium. In `extractor.py:_extract_section_content()`, walk `sp.TreeNode.parent` chain for each element, collect title ancestors, add `ancestors: List[str]` to output model. ~150 LoC + model change.
- **Node-level parent pointers in JSON schema**: Low. Add `ancestors` list field to `RiskSegment` and `SegmentedRisks`. Backward-compatible if default `[]`. ~50 LoC.
- **Cross-section linking**: High. Would require multi-section extraction (ADR-011 Rule 9 path) + a linking/coref step. Out of scope for current PRDs.

---

## Step 4: LLM Extraction

### What Exists

| Capability | Implementation | File | Quality |
|------------|---------------|------|---------|
| Zero-shot classifier planned | `facebook/bart-large-mnli` in `configs/config.yaml` | `configs/config.yaml:38` | Config only; not wired |
| Fine-tuned encoder planned | `ProsusAI/finbert` (default), ADR-008 decision | `configs/config.yaml:35` | Not wired into pipeline |
| Risk archetype taxonomy | 9 archetypes defined in PRD-002 §2.2 | PRD-002 | Schema only; no SASB files exist |
| Synthetic data design | RFC-001 Q4 selects tokenizer-aware truncation; LLM synthetic data mentioned in PRD-002 §2.1.2 | RFC-001, PRD-002 | Design only |
| Chunked text as classifier input | Each `RiskSegment.text` ≤ 380 words / ~512 tokens — sized for encoder input | `segmenter.py:432` | Production-ready as input to a classifier |

### Gaps

> **This is the largest gap. LLM extraction does not exist at any layer of the current pipeline.**

| Gap | Severity | Detail |
|-----|----------|--------|
| **No LLM API integration** | Critical | There is no module that calls an LLM (Claude, GPT-4, Gemini) to extract structured data from chunks. The pipeline produces text chunks only. |
| **No structured extraction prompts** | Critical | No prompt templates for specific extraction tasks (e.g., "extract forward-looking statements regarding supply chain risks"). |
| **No JSON extraction schema** | Critical | `SegmentedRisks` JSON schema stores raw text. There is no `extracted_facts` or `structured_output` field. |
| **Classifier not wired** | High | Even the simpler task (classify chunks by risk archetype) is blocked: `process_batch()` has no classifier call (PRD-002 G-12). Blocked on SASB taxonomy files (G-15) which do not exist. |
| **No information extraction vs. classification distinction** | High | Current design treats everything as classification (risk archetype labeling). The proposed step is information extraction ("output JSON array of forward-looking statements") — a different task requiring different prompting strategy and output schema. |
| **Hallucination risk** | High | Any LLM extraction step introduces hallucination. Current pipeline is deterministic (regex + rule-based). |
| **SASB taxonomy files missing** | High | `sasb_sics_mapping.json` and `archetype_to_sasb.yaml` do not exist (PRD-002 G-15). Classifier cannot run without them. |
| **Annotation corpus missing** | High | ≥500 examples/archetype required for fine-tuning (PRD-002 G-16). Not built. |
| **No streaming / async LLM calls** | Medium | If LLM extraction is added for 959 filings × N chunks each, synchronous calls would be prohibitively slow. Need async batching. |
| **Cost model** | Medium | No cost estimation for LLM extraction at scale (e.g., per-filing token budget). |

### Complexity to Close Gaps

- **Classifier wiring (G-12)**: Medium. Requires SASB taxonomy files first (G-15). Once files exist: add `ClassifierStage` to `pipeline.py`, call `bart-large-mnli` or `finbert` on each chunk, store `archetype` label in `RiskSegment`. ~300 LoC.
- **SASB taxonomy files (G-15)**: Medium. Schema defined in RFC-002. Data sourced from SASB.org standards. Manual curation + code to load them. ~100 LoC + data curation effort.
- **LLM extraction module (new)**: High. New `src/extraction/llm_extractor.py`:
  - Prompt template system (`jinja2` or f-strings)
  - Claude API / Anthropic SDK integration
  - Pydantic output schema for extracted facts
  - Retry logic, rate limiting
  - ~400-600 LoC + prompt engineering effort
- **Full information extraction pipeline**: Very High. Requires: schema design per extraction target, prompt engineering per target, few-shot examples, output validation. Estimated 4-8 weeks depending on number of extraction targets.

---

## Step 5: Validation

### What Exists

| Capability | Implementation | File | Quality |
|------------|---------------|------|---------|
| 20+ statistical quality gates | `HealthCheckValidator` + `health_check.yaml` | `configs/qa_validation/health_check.yaml` | Production-ready |
| Dead Letter Queue | `CheckpointManager` + `DeadLetterQueue` (ADR-005) | `src/utils/` | Production-ready |
| Segment-level type checks | empty_segment_rate, short_segment_rate, min_word_count_rate, over_limit_word_rate | `health_check.yaml` | Production-ready |
| Identity completeness | cik_present_rate, company_name_present_rate (blocking) | `health_check.yaml` | Production-ready |
| Duplicate detection | SHA-256 exact dedup (PRD-003 Fix 7) | Planned | Not yet implemented |
| HTML artifact check | html_artifact_rate == 0.0 (blocking gate) | `health_check.yaml` | Production-ready |
| Stamped run dirs | Git SHA + timestamp on every output (ADR-007) | `src/utils/` | Production-ready |

### Gaps

| Gap | Severity | Detail |
|-----|----------|--------|
| **No semantic validation of LLM output** | Critical | The entire current validation layer is structural/statistical. If an LLM extraction step is added, there is no mechanism to check whether the extracted JSON fields correspond to actual content in the source text. |
| **No hallucination detection** | Critical | No secondary LLM or rule-based checker exists to verify extracted facts against source. |
| **No cross-validation** | High | No comparison between extracted JSON values and verifiable fields (e.g., does the extracted "company name" match the CIK-registered name from EDGAR?). |
| **DLQ success rate below KPI** | High | Current parse success rate is 89.8% (PRD-002 G-01, KPI = 95%). 98 DLQ failures unresolved. Root cause is mixed: section contamination (81.5% corpus), encoding issues, pre-seek failures. |
| **No section contamination gate** | High | 81.5% of current corpus contains non-`part1item1a` content (PRD-002 OQ-PRD-1). Fix 2A removes ToC but full section boundary accuracy is not gated. |
| **Segment-level deduplication** | Medium | SHA-256 exact dedup planned (PRD-003 Fix 7); MinHash near-dedup (G-05) also planned. Neither is implemented. |
| **JSONL output** | Medium | Output is nested JSON (PRD-002 G-04 blocked). Fine-tuning pipelines expect JSONL. |
| **No LLM output type validation** | Medium | If LLM returns `{"risk_type": "Supply Chain", "statement": "..."}`, there is no Pydantic model to enforce the schema of extracted facts. |

### Complexity to Close Gaps

- **DLQ success rate (G-01)**: High. Root cause is multi-factor (section detection precision, pre-seek fallback rate, ToC contamination). Requires investigation per DLQ entry. ~1-2 weeks.
- **JSONL output (G-04)**: Low. Change `save_to_json()` to emit JSONL in `segmentation.py`. ~50 LoC.
- **Semantic validation via secondary LLM**: Very High. Would require: prompt to verify extracted claim against source passage, scoring rubric, threshold configuration. Adds latency and cost per extracted fact. ~300-500 LoC + prompt engineering.
- **Pydantic schema for extracted facts**: Medium. Define per-extraction-target Pydantic models, wire into validation pipeline. ~200 LoC.

---

## Summary: Complexity Matrix

| Pipeline Step | Existing Coverage | Gap Severity | Implementation Effort |
|--------------|-------------------|-------------|----------------------|
| **1. Ingestion & Normalization** | 85% — HTML/SGML complete; XBRL indexing done | XBRL parsing, EDGAR orchestration missing | Medium (2-3 weeks) |
| **2. Layout Analysis** | 65% — sec-parser semantic types exist; no H1/H2 labels, no ListItem | Missing list detection, paragraph boundaries, H-label normalization — all closable with rule-based post-processing (RFC-006 Option A). Visual ML models are architecturally mismatched. A2b ruled out by audit. | Low (~170 LoC, no new deps — RFC-006 OQs resolved 2026-02-25) |
| **3. Contextual Enrichment** | 50% — 2-level hierarchy exists; no full ancestry | Full breadcrumb serialization missing | Medium (1-2 weeks) |
| **4. LLM Extraction** | 5% — classifier planned but not wired; no extraction | Entire extraction layer absent | Very High (6-10 weeks) |
| **5. Validation** | 70% — statistical gates strong; no semantic validation | LLM output validation, hallucination detection absent | High (3-5 weeks for LLM validation layer) |

---

## Critical Path Assessment

### What Must Happen First (Unblocked Work)

1. **JSONL output** (G-04) — 1 day. Unblocks fine-tuning pipeline consumers.
2. **EDGAR downloader integration** — 3 days. Allows automated corpus expansion.
3. **Full breadcrumb serialization** (Step 3) — 1 week. No ADR change needed; purely additive.
4. **SASB taxonomy files** (G-15) — 1 week of curation. Unblocks G-12 classifier wiring.

### What Is Blocked

- **Classifier wiring** (G-12): Blocked on G-15 (taxonomy files).
- **LLM extraction**: Blocked on Step 2 (layout analysis) and Step 3 (contextual enrichment) being sufficiently complete to provide high-quality, context-rich inputs to the LLM prompt.
- **Hallucination validation**: Blocked on LLM extraction existing.
- **Segment deduplication**: Blocked on PRD-003 Fixes 4/7 (not yet scheduled).

### What Conflicts with Current Architecture

- **ML visual layout model** (DocLayNet / LayoutLM / Detectron2): **RFC-006 determined these are not conflicts to resolve but wrong tools entirely.** They operate on rendered page images and require HTML→PDF rendering + GPU inference. For HTML-native EDGAR filings, inline CSS is a more accurate signal than pixel inference. RFC-006 recommends rule-based Option A instead. No ADR change required.
- **Secondary validation LLM**: Adds latency and cost to what is currently a deterministic pipeline. Requires budget decision and async infrastructure changes.
- **XBRL structured extraction**: The current pipeline treats XBRL only as "iXBRL HTML to be parsed by sec-parser." A dedicated XBRL extractor would be a parallel pathway (structured financials vs. narrative text), not a replacement.

---

## Recommended Next Steps

### Phase A — Immediate (Days 1-5)
1. **Fix G-04**: Change `SegmentedRisks.save_to_json()` to support `.jsonl` output mode.
2. **Wire EDGAR downloader**: New `src/ingestion/edgar_downloader.py` wrapping `sec-downloader`.
3. **Layout Analysis Option A1 + A2a** (RFC-006, OQs resolved 2026-02-25): Add `ListItem` detection (unicode bullet `•word` regex — `<li>` tags absent from corpus) and H-label normalization (structural anchoring via `TopSectionTitle` — A2b ruled out by OQ-2 audit) in `extractor.py`. ~120 LoC (A1 ~40 + A2a ~80), no new deps.
4. **Add ancestors field**: Extend `RiskSegment` and serialization with `ancestors: List[str]` from tree walk.

### Phase B — Short-Term (Weeks 2-4)
5. **SASB taxonomy files**: Curate `sasb_sics_mapping.json` and `archetype_to_sasb.yaml` (RFC-002).
6. **Layout Analysis Option A3** (RFC-006): Add `<p>` boundary annotation to elements dict in `extractor.py`. ~50 LoC.
7. **Close G-01 DLQ failures**: Audit top-10 DLQ entries; identify root cause clusters; patch pre-seeker or extractor.

### Phase C — Medium-Term (Weeks 5-10)
8. **Wire classifier** (G-12): Add `ClassifierStage` to pipeline.
9. **LLM extraction module**: Design prompt templates + Pydantic output schema per extraction target; integrate Claude API.
10. **Segment dedup** (PRD-003 Fixes 7 + G-05).

### Phase D — Long-Term (Weeks 10+)
11. **XBRL structured extraction**: Parallel pathway via `arelle`; normalized financial fact model.
12. **Hallucination validation**: Secondary LLM or retrieval-based verification.
13. **Annotation corpus** (G-16): Build ≥500 examples/archetype for fine-tuning.

---

## Working Paths vs. Broken Paths

| | File:Line | Status |
|--|-----------|--------|
| SGML manifest extraction | `sgml_manifest.py:57` | Working |
| HTML pre-seek (Strategy A ToC) | `pre_seeker.py:104` | Working |
| HTML pre-seek (Strategy B proximity) | `pre_seeker.py:156` | Working (~5% fallback) |
| Full document parse (Rule 7 fallback) | `parser.py:195` | Working |
| DEI ix:hidden extraction (ADR-011) | `parser.py:421` | Working |
| TitleElement section finding (5 strategies) | `extractor.py:186` | Working |
| Fix 6A parent subsection mapping | `extractor.py:393` | Working |
| RFC-003 word-count ceiling | `segmenter.py:432` | Working |
| XBRL instance document parsing | `sgml_manifest.py:manifest.doc_xbrl_instance` (DocumentEntry) | **Indexed but never consumed** |
| Classifier call in `process_batch()` | `pipeline.py` | **Missing — G-12 blocked** |
| JSONL output | `segmentation.py:save_to_json()` | **Missing — G-04 blocked** |
| SASB taxonomy files | `configs/` | **Files do not exist — G-15** |
| LLM extraction | — | **No implementation exists** |
| Segment deduplication | — | **Planned; not implemented** |
| Hallucination validation | — | **No implementation exists** |

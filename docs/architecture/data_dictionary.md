# Data Dictionary: SEC Risk Factor Pipeline Output

**Last updated:** 2026-02-23
**Schema version:** 2.1 (as emitted by `_build_output_data()` in `run_preprocessing_pipeline.py`)
**Output location:** `data/processed/{YYYYMMDD_HHMMSS}_preprocessing_{git_sha}/{stem}_{section_id}_segmented.json`
**Cardinality:** One file per section per filing. A 10-K filing produces up to 7 files
(one per section in `configs/config.yaml sec_sections["10-K"]`). Absent sections produce
no file — they are not written, not null-filled.

---

## Output File Naming

| Token | Description | Example |
|:------|:------------|:--------|
| `{stem}` | Input filename without extension | `AAPL_10K_2021` |
| `{section_id}` | Section identifier from config | `part1item1a`, `part2item7` |
| Pattern | `{stem}_{section_id}_segmented.json` | `AAPL_10K_2021_part1item1a_segmented.json` |

Intermediate files (written when `--save-intermediates` is set):

| Stage | Suffix | Location |
|:------|:-------|:---------|
| Parsed | `{stem}_parsed.json` | `{run_dir}/parsed/` |
| Extracted | `{stem}_{section_id}_extracted.json` | `{run_dir}/extracted/` |
| Cleaned | `{stem}_{section_id}_cleaned.json` | `{run_dir}/extracted/` |

---

## Top-Level Record (v2.1 schema)

Written by `_build_output_data()` (`scripts/data_preprocessing/run_preprocessing_pipeline.py`).

| Field | Type | Description | Source / Logic | Nullable |
|:------|:-----|:------------|:---------------|:---------|
| `version` | `str` | Schema version. Currently `"2.1"`. | Hard-coded in `_build_output_data()` | No |
| `filing_name` | `str` | Input filename (with extension). E.g., `"AAPL_10K_2021.html"`. | `input_file.name` | No |
| `document_info` | `object` | Filing-level identity fields including DEI sub-dict. See sub-fields below. | `_build_output_data()` | No |
| `processing_metadata` | `object` | How this file was processed. See sub-fields below. | `_build_output_data()` | No |
| `section_metadata` | `object` | Which section this file covers. See sub-fields below. | `_build_output_data()` | No |
| `num_segments` | `int` | Count of segments in this file. Equals `len(segments)`. | `SegmentedRisks.total_segments` | No |
| `sentiment_analysis_enabled` | `bool` | Whether Loughran-McDonald sentiment was run. `false` when `--no-sentiment` is passed. | `_worker_analyzer is not None` | No |
| `aggregate_sentiment` | `object` | Batch-level sentiment averages. **Only present when `sentiment_analysis_enabled == true`.** | Mean of per-segment ratios | Conditionally absent |
| `segments` | `array[Segment]` | List of text chunks. See Segment schema below. | `RiskSegmenter` | No — empty array if no chunks |

### `document_info` sub-fields

Filing-level identity. All scalar fields are nullable when not present in the EDGAR header or XBRL block.

| Field | Type | Description | Source | Nullable |
|:------|:-----|:------------|:-------|:---------|
| `company_name` | `str` | Company name from EDGAR SEC-HEADER. E.g., `"Apple Inc."`. | `SegmentedRisks.company_name` ← `SGMLHeader.company_name` | Yes |
| `ticker` | `str` | Stock ticker symbol from DEI or SGML. E.g., `"AAPL"`. | `SegmentedRisks.ticker` ← `ParsedFiling.metadata['ticker']` | Yes |
| `cik` | `str` | EDGAR Central Index Key. E.g., `"0000320193"`. | `SegmentedRisks.cik` ← `SGMLHeader.cik` | Yes |
| `sic_code` | `str` | SIC code. E.g., `"3571"`. | `SegmentedRisks.sic_code` ← `SGMLHeader.sic_code` | Yes |
| `sic_name` | `str` | SIC industry name. E.g., `"ELECTRONIC COMPUTERS"`. | `SegmentedRisks.sic_name` ← `SGMLHeader.sic_name` | Yes |
| `form_type` | `str` | SEC form type. E.g., `"10-K"`. | `SegmentedRisks.form_type` ← `ParsedFiling.form_type.value` | Yes |
| `fiscal_year` | `str` | 4-digit fiscal year derived from `period_of_report`. | `SegmentedRisks.fiscal_year` ← `ExtractedSection.metadata['fiscal_year']` | Yes |
| `accession_number` | `str` | EDGAR accession number. E.g., `"0000320193-21-000105"`. | `SegmentedRisks.accession_number` ← `SGMLHeader.accession_number` | Yes |
| `filed_as_of_date` | `str` | Filing date in YYYYMMDD. | `SegmentedRisks.filed_as_of_date` ← `SGMLHeader.filed_as_of_date` | Yes |
| `amendment_flag` | `bool` | `true` if this is an amendment (10-K/A). `null` when absent from DEI. | `SegmentedRisks.amendment_flag` ← DEI Tier-1 | Yes |
| `entity_filer_category` | `str` | SEC filer size category. E.g., `"Large accelerated filer"`. | `SegmentedRisks.entity_filer_category` ← DEI Tier-1 | Yes |
| `ein` | `str` | IRS Employer Identification Number. | `SegmentedRisks.ein` ← SGML or DEI Tier-1 | Yes |
| `dei` | `object` | Tier-2 XBRL `ix:hidden` fields. Empty object `{}` when block is absent. | `SegmentedRisks.metadata['dei']` ← `ExtractedSection.metadata['dei']` ← `ParsedFiling.metadata['dei']` | No (empty `{}`) |

#### `document_info.dei` sub-fields

Populated by `parser._extract_metadata()` from the `ix:hidden` XBRL DEI block.
Present when the filing includes inline XBRL; empty dict `{}` otherwise.

| Field | Type | Description |
|:------|:-----|:------------|
| `EntityRegistrantName` | `str` | Full legal registrant name (may differ from SGML `company_name`). |
| `DocumentPeriodEndDate` | `str` | Period-of-report label as printed in the filing (e.g., `"November 1"`). |
| `SecurityExchangeName` | `str` | Exchange name. E.g., `"Nasdaq Global Select Market"`. |
| `EntityWellKnownSeasonedIssuer` | `str` | `"Yes"` or `"No"`. |
| `IcfrAuditorAttestationFlag` | `str` | `"True"` or `"False"`. |
| `EntityIncorporationStateCountryCode` | `str` | State/country of incorporation. E.g., `"Massachusetts"`. |
| `Security12bTitle` | `str` | Security title registered under Section 12(b). |
| `EntityFilerCategory` | `str` | Filer size category (DEI variant; see also `entity_filer_category` above). |

### `processing_metadata` sub-fields

| Field | Type | Description | Source |
|:------|:-----|:------------|:-------|
| `parser_version` | `str` | Pipeline schema version. Currently `"1.0"`. | Hard-coded |
| `finbert_model` | `str` | FinBERT model name used (or planned) for classification. | `settings.models.default_model` |
| `chunking_strategy` | `str` | Segmentation approach. Currently `"sentence_level"`. | Hard-coded |
| `max_tokens_per_chunk` | `int` | Token cap per chunk for downstream model input. Currently `512`. | Hard-coded |

### `section_metadata` sub-fields

| Field | Type | Description | Source |
|:------|:-----|:------------|:-------|
| `identifier` | `str` | Machine key for this section. E.g., `"part1item1a"`. | `SegmentedRisks.section_identifier` |
| `title` | `str` | Human-readable section title. E.g., `"Item 1A. Risk Factors"`. | `SegmentedRisks.section_title` |
| `cleaning_settings` | `object` | Cleaning flags applied to the text before segmentation. | `settings.preprocessing.*` |
| `cleaning_settings.removed_html_tags` | `bool` | | `settings.preprocessing.remove_html_tags` |
| `cleaning_settings.normalized_whitespace` | `bool` | | `settings.preprocessing.normalize_whitespace` |
| `cleaning_settings.removed_page_numbers` | `bool` | | `settings.preprocessing.remove_page_numbers` |
| `cleaning_settings.discarded_tables` | `bool` | Tables are always excluded from segmented text. | Hard-coded `true` |
| `stats.total_chunks` | `int` | Number of segments in this section. | `SegmentedRisks.total_segments` |
| `stats.num_tables` | `int` | Tables encountered in the section (discarded). | `SegmentedRisks.metadata["element_type_counts"]["TableElement"]` |

---

## Segment Object

Each element of the `segments` array.

| Field | Type | Description | Source / Logic | Constraints |
|:------|:-----|:------------|:---------------|:------------|
| `id` | `str` | Chunk identifier. Format: `{SECTION_PREFIX}_{NNN}`. E.g., `"1A_001"`. | `RiskSegment.chunk_id` | Unique per file |
| `parent_subsection` | `str` | Text of the nearest preceding `TitleElement` heading within this section. `null` if the segment precedes all headings. | `RiskSegmenter._resolve_subsection()` — resolved against `ExtractedSection.node_subsections` | Yes |
| `ancestors` | `List[str]` | Ordered outermost→innermost heading breadcrumb. `ancestors[0]` is the section title; `ancestors[-1]` semantically corresponds to `parent_subsection`. `[]` for cover-page nodes in full-doc fallback. Normalized: `\xa0` → space, whitespace collapsed, max 120 chars per entry, max 6 entries. | `SECSectionExtractor._build_ancestor_map()` → `RiskSegmenter._resolve_ancestors()` | No (empty list default) |
| `text` | `str` | Cleaned segment text. HTML tags removed; Unicode normalised. | `TextCleaner.clean_text()` → `RiskSegmenter` | Must be > 50 chars (QA rule) |
| `length` | `int` | Character count of `text`. | `RiskSegment.char_count` | ≥ 0 |
| `word_count` | `int` | Whitespace-delimited token count of `text`. | `RiskSegment.word_count` | ≥ 0 |
| `sentiment` | `object` | Loughran-McDonald word counts and ratios. **Only present when `sentiment_analysis_enabled == true`.** | `SentimentAnalyzer.extract_features_batch()` | Conditionally absent |

### `sentiment` sub-object fields (when present)

| Field | Type | Description |
|:------|:-----|:------------|
| `negative_count` | `int` | Count of Loughran-McDonald negative words |
| `positive_count` | `int` | Count of positive words |
| `uncertainty_count` | `int` | Count of uncertainty words |
| `litigious_count` | `int` | Count of litigious words |
| `constraining_count` | `int` | Count of constraining words |
| `negative_ratio` | `float` | `negative_count / total_words` |
| `positive_ratio` | `float` | `positive_count / total_words` |
| `uncertainty_ratio` | `float` | `uncertainty_count / total_words` |
| `litigious_ratio` | `float` | `litigious_count / total_words` |
| `constraining_ratio` | `float` | `constraining_count / total_words` |
| `total_sentiment_words` | `int` | Sum of all sentiment word counts |
| `sentiment_word_ratio` | `float` | `total_sentiment_words / total_words` |

---

## Fields NOT Yet Present (Planned)

### Classifier outputs (Phase 2 — PRD-002 §2.2)

| Field | Type | Description | Blocking PRD Goal |
|:------|:-----|:------------|:------------------|
| `risk_label` | `str` | Risk category from 12-class taxonomy. | G-13, Phase 2 Gate |
| `confidence` | `float` | Classifier confidence [0, 1]. | G-13, Phase 2 Gate |
| `label_source` | `str` | `"model"` or `"heuristic"`. | §4.2 Serving Strategy |

### Model fields not yet passed to output

These fields exist in `SegmentedRisks` (`src/preprocessing/models/segmentation.py`) or
`RiskSegment` but are not serialised by `_build_output_data()`. They are available
in-memory through the pipeline.

| Field | Model | Description | Why absent from output |
|:------|:------|:------------|:-----------------------|
| `section_identifier` | `SegmentedRisks` | Machine key e.g. `"part1item1a"` | Serialised in `section_metadata.identifier` instead |

### SGMLManifest fields not yet passed to SegmentedRisks

Available from `SGMLManifest.header` but not propagated to the model or output.

| Field | Description |
|:------|:------------|
| `sec_file_number` | SEC file number, e.g. `"001-36743"` |
| `fiscal_year_end` | MMDD, e.g. `"0924"` (Sep 24) |
| `document_count` | Number of embedded documents (88–684) |
| `state_of_incorporation` | Two-letter state code (~95% coverage) |

---

## Validation Rules

Enforced by `HealthCheckValidator` (`src/config/qa_validation.py`),
configured in `configs/qa_validation/health_check.yaml`.
A failing **blocking** rule prevents the output file from being written.

| Rule | Field | Threshold | Blocking | Config Key |
|:-----|:------|:----------|:---------|:-----------|
| No empty segments | `text` | `len(text) > 0` for 100% of segments | Yes | `empty_segment_rate == 0.0` |
| Short segment rate | `text` | ≤ 5% of segments with `char_count < 50` | No (warn at 10%) | `short_segment_rate ≤ 0.05` |
| No HTML artifacts | `text` | 0% of segments contain HTML tags | Yes | `html_artifact_rate == 0.0` |
| CIK present | `cik` | 100% of records have non-null CIK | Yes | `cik_present_rate >= 1.0` |
| Company name present | `company_name` | 100% of records have non-null company name | Yes | `company_name_present_rate >= 1.0` |
| SIC code present | `sic_code` | ≥ 95% of records | No | `sic_code_present_rate >= 0.95` |
| No duplicates | filing hash | 0% duplicate filings in a batch | Yes | `duplicate_rate == 0.0` |
| Risk keywords | `text` | At least one risk-related keyword | No | `risk_keyword_present == true` |
| Min file size | raw HTML | Input file ≥ 100 KB | Yes | `min_file_size_kb >= 100` |
| Max file size (standard) | raw HTML | ≤ 50 MB for non-financial SIC | No | `max_file_size_mb_standard <= 50` |
| Max file size (financials) | raw HTML | ≤ 150 MB for SIC 6000–6799 | No | `max_file_size_mb_financial <= 150` |
| Amendment flag check | `amendment_flag` | Must not be an amendment. `None` → SKIP. | Yes | `amendment_flag_not_amended <= 0.0` |

---

## Lineage Diagram

```
EDGAR SGML container (.html)
    │  (downloaded by sec-downloader or placed in data/raw/)
    ▼
Stage 0: extract_sgml_manifest()  [sgml_manifest.py]
    │  Extracts: SGMLHeader (company_name, cik, sic_code, sic_name, accession_number,
    │            filed_as_of_date, fiscal_year_end, sec_file_number, document_count,
    │            state_of_incorporation, ein)
    │  Builds: DocumentEntry list with byte offsets for all 88–684 embedded docs
    ▼
Stage 0 (DEI): extract_document() on doc_10k → _DEI_PAT finditer  [parser._extract_metadata]
    │  Tier-1: ticker, amendment_flag (bool), entity_filer_category, ein (→ merges with SGML)
    │  Tier-2: EntityRegistrantName, DocumentPeriodEndDate, SecurityExchangeName, …
    │           (stored in metadata["dei"])
    ▼
Stage 1: AnchorPreSeeker.seek()  [pre_seeker.py]  — ADR-011 Rule 9 dispatch:
    │  • section_id supplied (single-section caller):
    │      Locates target ToC anchor → end anchor; returns ~50–200 KB HTML slice
    │  • section_id=None (multi-section caller — default):
    │      Skipped entirely; full Document 1 HTML passed to Stage 2
    │      (Rule 7 fallback path — always taken for batch multi-section extraction)
    ▼
Stage 2: Edgar10QParser.parse()  [sec-parser==0.54.0]
    │  Input: unmodified HTML (slice or full Document 1 — structural invariants intact)
    │  Output: flat semantic element list (filing.tree.nodes)
    ▼
Stage 3: SECSectionExtractor._find_section_node() + _extract_section_content()
    │  • _find_section_node(): iterates tree.nodes; matches TopSectionTitle / TitleElement
    │    nodes by identifier attribute, SECTION_PATTERNS regex, or text-key matching
    │  • _extract_section_content(): drops TitleElement nodes matching PAGE_HEADER_PATTERN
    │  • Extracts: section_title, text, subsections, elements for each requested section
    ▼
TextCleaner  [cleaning.py]
    │  Removes HTML artifacts, normalises Unicode, strips page numbers
    ▼
RiskSegmenter  [segmenter.py]
    │  Splits cleaned text into chunks; assigns chunk_id (e.g. "1A_001")
    │  Tracks parent_subsection (nearest preceding TitleElement)
    ▼
_build_output_data()  [run_preprocessing_pipeline.py:302]
    │  Serialises to v2.1 schema (document_info + processing_metadata + section_metadata)
    │  One file per section: {stem}_{section_id}_segmented.json
    ▼
HealthCheckValidator  [src/config/qa_validation.py]
    │  Blocking rules quarantine output before write
    ▼
data/processed/{run_dir}/{stem}_{section_id}_segmented.json
```

---

## Example Record (v2.1 schema)

```json
{
  "version": "2.1",
  "filing_name": "AAPL_10K_2021.html",
  "document_info": {
    "company_name": "Apple Inc.",
    "ticker": "AAPL",
    "cik": "0000320193",
    "sic_code": "3571",
    "sic_name": "ELECTRONIC COMPUTERS",
    "form_type": "10-K",
    "fiscal_year": "2021",
    "accession_number": "0000320193-21-000105",
    "filed_as_of_date": "20211029",
    "amendment_flag": false,
    "entity_filer_category": "Large accelerated filer",
    "ein": "94-2404110",
    "dei": {
      "EntityRegistrantName": "Apple Inc.",
      "DocumentPeriodEndDate": "September 25",
      "SecurityExchangeName": "Nasdaq Global Select Market",
      "EntityWellKnownSeasonedIssuer": "Yes",
      "IcfrAuditorAttestationFlag": "True",
      "EntityIncorporationStateCountryCode": "California",
      "Security12bTitle": "Common Stock, $0.00001 par value per share",
      "EntityFilerCategory": "Large accelerated filer"
    }
  },
  "processing_metadata": {
    "parser_version": "1.0",
    "finbert_model": "ProsusAI/finbert",
    "chunking_strategy": "sentence_level",
    "max_tokens_per_chunk": 512
  },
  "section_metadata": {
    "identifier": "part1item1a",
    "title": "Item 1A. Risk Factors",
    "cleaning_settings": {
      "removed_html_tags": true,
      "normalized_whitespace": true,
      "removed_page_numbers": true,
      "discarded_tables": true
    },
    "stats": {
      "total_chunks": 136,
      "num_tables": 0
    }
  },
  "num_segments": 136,
  "sentiment_analysis_enabled": false,
  "segments": [
    {
      "id": "1A_001",
      "parent_subsection": "Competition",
      "text": "The Company faces intense competition in all areas of its business...",
      "length": 195,
      "word_count": 33
    }
  ]
}
```

**Note on the `SegmentedRisks.save_to_json()` method:** This method exists on the
`SegmentedRisks` model (`src/preprocessing/models/segmentation.py`) and emits a
different nested schema (`document_info / processing_metadata / section_metadata / chunks`,
version `"1.0"`). It is NOT the primary output writer for the preprocessing pipeline.
It is called only by `SECPreprocessingPipeline.process_filing()` in the library path
(used by `process_risk_factors()` and direct API callers). Downstream consumers should
prefer the v2.0 flat schema from `_build_output_data()` unless calling the pipeline
library directly.

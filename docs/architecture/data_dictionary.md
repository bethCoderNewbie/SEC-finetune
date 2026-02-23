# Data Dictionary: SEC Risk Factor Pipeline Output

**Last updated:** 2026-02-22
**Schema version:** 1.0 (as emitted by `SegmentedRisks.save_to_json()`)
**Output location:** `data/processed/{YYYYMMDD_HHMMSS}_preprocessing_{git_sha}/{stem}_segmented_risks.json`
**Format:** JSON (one file per filing; JSONL conversion planned — see PRD-002 §8)

---

## Top-Level Record

| Field | Type | Description | Source / Logic | Nullable |
|:------|:-----|:------------|:---------------|:---------|
| `version` | `str` | Schema version. Currently `"1.0"`. | Hard-coded in `SegmentedRisks.save_to_json()` | No |
| `filing_name` | `str` | Input filename stem, with `_segmented` suffix stripped. E.g., `"AAPL_10K_2021"` | Derived from output path in `save_to_json()` | No |
| `num_segments` | `int` | Total number of risk segments extracted. Equals `total_segments`. | `len(self.segments)` | No |
| `total_segments` | `int` | Duplicate of `num_segments`. Present for backwards compat. | `SegmentedRisks.__init__` | No |
| `sic_code` | `str` | Standard Industrial Classification code. 4-digit string, e.g., `"3571"`. | Stage 0: `SGMLManifest.header.sic_code` — regex on `<SEC-HEADER>` (`sgml_manifest.py`) | Yes — null if EDGAR header absent |
| `sic_name` | `str` | Human-readable SIC industry name. E.g., `"ELECTRONIC COMPUTERS"`. | Stage 0: `SGMLManifest.header.sic_name` | Yes |
| `cik` | `str` | EDGAR Central Index Key. Zero-padded 10-digit string. E.g., `"0000320193"`. | Stage 0: `SGMLManifest.header.cik` | Yes |
| `ticker` | `str` | Stock ticker symbol. E.g., `"AAPL"`. | Stage 0 (DEI): `ix:nonNumeric name="dei:TradingSymbol"` regex on full Document 1 HTML (`parser._extract_metadata`) | Yes — not all filings include ticker |
| `company_name` | `str` | Company name as registered with SEC. E.g., `"APPLE INC"`. | Stage 0: `SGMLManifest.header.company_name` | Yes |
| `form_type` | `str` | SEC form type. One of `"10-K"`, `"10-Q"`. | Passed via CLI `--form-type` argument | Yes |
| `fiscal_year` | `str` | 4-digit fiscal year, e.g., `"2021"`. | Stage 0: first 4 chars of `CONFORMED PERIOD OF REPORT` in `<SEC-HEADER>` | Yes |
| `accession_number` | `str` | EDGAR accession number. E.g., `"0000320193-21-000105"`. | Stage 0: `ACCESSION NUMBER:` line in `<SEC-HEADER>` | No — 100% coverage |
| `filed_as_of_date` | `str` (YYYYMMDD) | Date the filing was submitted to EDGAR. E.g., `"20211029"`. | Stage 0: `FILED AS OF DATE:` in `<SEC-HEADER>` | No — 100% coverage |
| `section_title` | `str` | Title of the extracted section. E.g., `"Item 1A. Risk Factors"`. | `SECSectionExtractor` — first `TitleElement` of matched section | Yes |
| `segments` | `array[Segment]` | List of individual risk segments. See Segment schema below. | `RiskSegmenter` | No — empty array if no segments found |
| `metadata` | `object` | Reserved for future pipeline metadata. Currently `{}`. | `SegmentedRisks` default | No |

---

## New Top-Level Fields (from `SGMLManifest.header` — ADR-010)

These fields are emitted in `document_info` of `SegmentedRisks.save_to_json()`.

| Field | Type | Description | Source / Logic | Nullable |
|:------|:-----|:------------|:---------------|:---------|
| `accession_number` | `str` | EDGAR accession number. E.g., `"0000320193-21-000105"`. | Stage 0: `ACCESSION NUMBER:` line in `<SEC-HEADER>` | No — 100% coverage |
| `filed_as_of_date` | `str` (YYYYMMDD) | Date the filing was submitted to EDGAR. E.g., `"20211029"`. | Stage 0: `FILED AS OF DATE:` in `<SEC-HEADER>` | No — 100% coverage |
| `amendment_flag` | `bool` | `false` = original filing; `true` = amendment. Amended filings are quarantined by the blocking QA rule `amendment_flag_not_amended`. | Stage 0 (DEI): `ix:nonNumeric name="dei:AmendmentFlag"`. Normalised to Python `bool`; `None` for pre-iXBRL filings. | Yes — `None` for filings without `<ix:hidden>` block |
| `entity_filer_category` | `str` | SEC filer size category. E.g., `"Large accelerated filer"`. Used for corpus stratification. | Stage 0 (DEI): `ix:nonNumeric name="dei:EntityFilerCategory"` | Yes |
| `fiscal_year_end` | `str` (MMDD) | Month and day of fiscal year end. E.g., `"0924"` (Sep 24). | Stage 0: `FISCAL YEAR ENDING:` in `<SEC-HEADER>` | Yes — occasionally absent |
| `sec_file_number` | `str` | SEC file number. E.g., `"001-36743"`. | Stage 0: `FILE NUMBER:` in `<SEC-HEADER>` | No — 100% coverage |
| `document_count` | `int` | Number of embedded documents in the SGML container (88–684, mean 152). | Stage 0: `PUBLIC DOCUMENT COUNT:` in `<SEC-HEADER>` | No |
| `state_of_incorporation` | `str` | Two-letter state code. E.g., `"CA"`. | Stage 0: `STATE OF INCORPORATION:` in `<SEC-HEADER>` | Yes — ~95% coverage |
| `ein` | `str` | IRS Employer Identification Number, hyphen-formatted. E.g., `"04-2348234"`. | Stage 0 (DEI): `dei:EntityTaxIdentificationNumber` (primary, ~100% for iXBRL filings) falling back to SGML `IRS NUMBER:` (~12% coverage) per ADR-011. | Yes — `None` only for pre-iXBRL filings without SGML EIN |

---

## DEI Metadata Sub-dict (`metadata.dei`)

Populated from the `<ix:hidden>` block present in every modern iXBRL Document 1 filing.
Available on `SegmentedRisks.metadata["dei"]` (in-memory) and in `metadata.dei` if you
add it to your pipeline's output schema. All values are raw strings or `None`.

| Key | DEI Tag | Description |
|:----|:--------|:------------|
| `EntityRegistrantName` | `dei:EntityRegistrantName` | Registrant name as filed with SEC |
| `DocumentPeriodEndDate` | `dei:DocumentPeriodEndDate` | Period of report end date (YYYY-MM-DD) |
| `EntityIncorporationStateCountryCode` | `dei:EntityIncorporationStateCountryCode` | State/country of incorporation (two-letter) |
| `SecurityExchangeName` | `dei:SecurityExchangeName` | Exchange where primary security is listed |
| `EntityWellKnownSeasonedIssuer` | `dei:EntityWellKnownSeasonedIssuer` | WKSI status (`"Yes"` / `"No"`) |
| `IcfrAuditorAttestationFlag` | `dei:IcfrAuditorAttestationFlag` | Whether ICFR auditor attestation is included |
| `Security12bTitle` | `dei:Security12bTitle` | Title of securities registered under Section 12(b) |

---

## Segment Object

Each element of the `segments` array.

| Field | Type | Description | Source / Logic | Constraints |
|:------|:-----|:------------|:---------------|:------------|
| `index` | `int` | Zero-based position of this segment within the filing's risk section. | `RiskSegmenter` — assigned in order of appearance | ≥ 0; unique per filing |
| `text` | `str` | Cleaned risk segment text. HTML tags removed; Unicode normalized. | `TextCleaner.clean_text()` → `RiskSegmenter` | Must be > 50 chars (QA rule: `short_segment_rate ≤ 5%`) |
| `word_count` | `int` | Number of whitespace-delimited tokens in `text`. | `len(text.split())` in `RiskSegment.__init__` | ≥ 0; auto-computed if not provided |
| `char_count` | `int` | Number of characters in `text` (including spaces). | `len(text)` in `RiskSegment.__init__` | ≥ 0; auto-computed if not provided |

---

## Fields NOT Yet Present (Planned)

These fields are required by PRD-002 §2.2 but are not emitted by the current pipeline.

| Field | Type | Description | Blocking PRD Goal |
|:------|:-----|:------------|:------------------|
| `risk_label` | `str` | Risk category from 12-class taxonomy. | G-13, Phase 2 Gate |
| `confidence` | `float` | Classifier confidence [0, 1]. | G-13, Phase 2 Gate |
| `label_source` | `str` | `"model"` or `"heuristic"` — which system assigned the label. | §4.2 Serving Strategy |

---

## Validation Rules

These rules are enforced by `HealthCheckValidator` (`src/config/qa_validation.py`) and
configured in `configs/qa_validation/health_check.yaml`. A failing **blocking** rule quarantines
the output file (it is not written to the production run directory).

| Rule | Field | Threshold | Blocking | Config Key |
|:-----|:------|:----------|:---------|:-----------|
| No empty segments | `text` | `len(text) > 0` for 100% of segments | Yes | `empty_segment_rate == 0.0` |
| Short segment rate | `text` | ≤ 5% of segments with `char_count < 50` | No (warn at 10%) | `short_segment_rate ≤ 0.05` |
| No HTML artifacts | `text` | 0% of segments contain HTML tags | Yes | `html_artifact_rate == 0.0` |
| CIK present | `cik` | 100% of records have non-null CIK | Yes | `cik_present_rate >= 1.0` |
| Company name present | `company_name` | 100% of records have non-null company name | Yes | `company_name_present_rate >= 1.0` |
| SIC code present | `sic_code` | ≥ 95% of records (warn at 90%) | No | `sic_code_present_rate >= 0.95` |
| No duplicates | filing hash | 0% duplicate filings in a batch | Yes | `duplicate_rate == 0.0` |
| Risk keywords | `text` | At least one risk-related keyword in section | No | `risk_keyword_present == true` |
| Min file size | raw HTML | Input file ≥ 100 KB | Yes | `min_file_size_kb >= 100` |
| Max file size (standard) | raw HTML | ≤ 50 MB for non-financial SIC | No | `max_file_size_mb_standard <= 50` |
| Max file size (financials) | raw HTML | ≤ 150 MB for SIC 6000–6799 | No | `max_file_size_mb_financial <= 150` |
| Amendment flag check | `amendment_flag` | Filing must not be an amendment (`amendment_flag == false`). Amended filings are quarantined. `None` (pre-iXBRL) → SKIP, not FAIL. | Yes | `amendment_flag_not_amended <= 0.0` |

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
Stage 0 (DEI): extract_document() on doc_10k → generalised _DEI_PAT finditer  [parser._extract_metadata]
    │  Tier-1: ticker, amendment_flag (bool), entity_filer_category, ein (→ merges with SGML)
    │  Tier-2: EntityRegistrantName, DocumentPeriodEndDate, EntityIncorporationStateCountryCode,
    │          SecurityExchangeName, EntityWellKnownSeasonedIssuer, IcfrAuditorAttestationFlag,
    │          Security12bTitle  (stored in metadata["dei"])
    │  Also: fiscal_year (CONFORMED PERIOD OF REPORT) from SGML header
    ▼
Stage 1: AnchorPreSeeker.seek()  [pre_seeker.py]
    │  Input: manifest.doc_10k byte range → full Document 1 HTML
    │  Locates: target section ToC anchor → end anchor (next section)
    │  Output: raw, unmodified ~50–200 KB HTML slice  (or full doc1 on fallback)
    ▼
Stage 2: Edgar10QParser.parse()  [sec-parser==0.54.0]
    │  Input: unmodified HTML slice (structural invariants intact)
    │  Output: semantic element list
    ▼
Stage 3: SECSectionExtractor._extract_section_content()
    │  Drops: TitleElement nodes matching PAGE_HEADER_PATTERN
    │  Extracts: section_title, text, subsections, elements for Item 1A
    ▼
TextCleaner → RiskSegmenter → SegmentedRisks.save_to_json() → HealthCheckValidator
```

---

## Example Record

```json
{
  "version": "1.0",
  "filing_name": "AAPL_10K_2021",
  "num_segments": 54,
  "total_segments": 54,
  "sic_code": "3571",
  "sic_name": "ELECTRONIC COMPUTERS",
  "cik": "0000320193",
  "ticker": "AAPL",
  "company_name": "APPLE INC",
  "form_type": "10-K",
  "fiscal_year": "2021",
  "accession_number": "0000320193-21-000105",
  "filed_as_of_date": "20211029",
  "section_title": "Item 1A. Risk Factors",
  "segments": [
    {
      "index": 0,
      "text": "The Company faces intense competition in all areas of its business. The markets for the Company's products and services are highly competitive and subject to rapid technological change.",
      "word_count": 33,
      "char_count": 195
    }
  ],
  "metadata": {}
}
```

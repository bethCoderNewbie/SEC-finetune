# Data Dictionary: SEC Risk Factor Pipeline Output

**Last updated:** 2026-02-18
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
| `sic_code` | `str` | Standard Industrial Classification code. 4-digit string, e.g., `"3571"`. | `sec-parser` EDGAR header extraction → `SECFilingParser` | Yes — null if EDGAR header absent |
| `sic_name` | `str` | Human-readable SIC industry name. E.g., `"ELECTRONIC COMPUTERS"`. | `sec-parser` EDGAR header | Yes |
| `cik` | `str` | EDGAR Central Index Key. Zero-padded 10-digit string. E.g., `"0000320193"`. | `sec-parser` EDGAR header | Yes |
| `ticker` | `str` | Stock ticker symbol. E.g., `"AAPL"`. | `sec-parser` EDGAR header | Yes — not all filings include ticker |
| `company_name` | `str` | Company name as registered with SEC. E.g., `"APPLE INC"`. | `sec-parser` EDGAR header | Yes |
| `form_type` | `str` | SEC form type. One of `"10-K"`, `"10-Q"`. | Passed via CLI `--form-type` argument | Yes |
| `section_title` | `str` | Title of the extracted section. E.g., `"Item 1A. Risk Factors"`. | `SECSectionExtractor` — first `TitleElement` of matched section | Yes |
| `segments` | `array[Segment]` | List of individual risk segments. See Segment schema below. | `RiskSegmenter` | No — empty array if no segments found |
| `metadata` | `object` | Reserved for future pipeline metadata. Currently `{}`. | `SegmentedRisks` default | No |

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
| `filing_date` | `str` (ISO 8601) | Date the filing was submitted to EDGAR. | §2.2 Feature Requirements |
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

---

## Lineage Diagram

```
EDGAR HTML filing
    │  (downloaded by sec-downloader or placed in data/raw/)
    ▼
SECFilingParser (sec-parser==0.54.0)
    │  Extracts: cik, sic_code, sic_name, ticker, company_name from <SEC-HEADER>
    ▼
SECSectionExtractor
    │  Extracts: section_title, text, subsections, elements for Item 1A
    ▼
TextCleaner
    │  Removes: HTML tags, page number artifacts, Unicode noise
    │  Produces: cleaned_text (str)
    ▼
RiskSegmenter (all-MiniLM-L6-v2, cosine threshold=0.5)
    │  Splits cleaned_text into atomic segments
    │  Assigns: index, word_count, char_count per segment
    ▼
SegmentedRisks.save_to_json()
    │  Writes: {stem}_segmented_risks.json
    ▼
HealthCheckValidator
    │  Validates all rules above; quarantines failures
    ▼
data/processed/{run_dir}/   ← production output
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

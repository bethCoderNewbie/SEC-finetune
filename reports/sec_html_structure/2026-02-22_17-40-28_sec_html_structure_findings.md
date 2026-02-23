# SEC 10-K HTML Structure — Analysis Report

**Generated:** 2026-02-22 17:40:28  
**Files analyzed:** 1  
**Mode:** specific files: DDOG_10K_2021  
**Data source:** `data/raw/*.html` (EDGAR full-submission text files)

---

## Executive Summary

Analyzed **1 EDGAR full-submission text files** from the corpus. Key observations:

- Each file is an **SGML container** embedding 107–107 separate documents (mean 107).
- File sizes range from **16.7 MB to 16.7 MB** (mean 16.7 MB). The main 10-K iXBRL body is 5.4 MB on average.
- All 1 files have `MetaLinks.json` (0%) and `FilingSummary.xml` (100%).
- **All 23 DEI iXBRL tags** were fully present in 0/1 files. Tags with <100% presence are noted in §4.
- The SGML header provides reliable metadata for all core fields except `ein` (present in 0% of files). Use `dei:EntityTaxIdentificationNumber` instead.

---

## 1. File Size Distribution

### 1.1 Total file size (SGML container)

```
min=16.7  max=16.7  mean=16.7  median=16.7  p95=16.7 MB
```

### 1.2 Main 10-K iXBRL body size

```
min=5.4  max=5.4  mean=5.4  median=5.4  p95=5.4 MB
```

The main 10-K body is the only document passed to `sec-parser`. Its size relative to the container explains why `sec-parser` is unaware of the other 106 embedded documents per filing.

### 1.3 Per-file breakdown

| File | Size (MB) | Docs | Main 10-K (MB) | R*.htm sheets |
|------|-----------|------|----------------|---------------|
| `DDOG_10K_2021` | 16.7 | 107 | 5.41 | 86 |

---

## 2. Embedded Document Type Distribution

Aggregated counts and sizes across all analyzed files.

| Type | Total Count | Files Present | Total Size (MB) | Avg per file |
|------|-------------|---------------|-----------------|--------------|
| `XML` | 89 | 1/1 | 4.87 | 89.0 |
| `GRAPHIC` | 2 | 1/1 | 0.16 | 2.0 |
| `10-K` | 1 | 1/1 | 5.41 | 1.0 |
| `EX-10.14` | 1 | 1/1 | 0.32 | 1.0 |
| `EX-21.1` | 1 | 1/1 | 0.01 | 1.0 |
| `EX-23.1` | 1 | 1/1 | 0.00 | 1.0 |
| `EX-31.1` | 1 | 1/1 | 0.03 | 1.0 |
| `EX-31.2` | 1 | 1/1 | 0.03 | 1.0 |
| `EX-32.1` | 1 | 1/1 | 0.01 | 1.0 |
| `EX-32.2` | 1 | 1/1 | 0.01 | 1.0 |
| `EX-101.INS` | 1 | 1/1 | 3.61 | 1.0 |
| `EX-101.SCH` | 1 | 1/1 | 0.08 | 1.0 |
| `EX-101.CAL` | 1 | 1/1 | 0.10 | 1.0 |
| `EX-101.DEF` | 1 | 1/1 | 0.32 | 1.0 |
| `EX-101.LAB` | 1 | 1/1 | 0.69 | 1.0 |
| `EX-101.PRE` | 1 | 1/1 | 0.55 | 1.0 |
| `EXCEL` | 1 | 1/1 | 0.17 | 1.0 |
| `ZIP` | 1 | 1/1 | 0.36 | 1.0 |

**Notes:**
- `XML` documents are primarily `R*.htm` XBRL financial statement sheets — by far the most numerous type.
- `GRAPHIC` documents are UUencoded images (not base64). Count grows with filing complexity.
- `EX-101.*` exhibits (SCH/CAL/DEF/LAB/PRE) appear exactly once per filing.
- `JSON` = `MetaLinks.json` (XBRL element catalogue). Always exactly 1 per filing.

### 2.1 R*.htm XBRL Sheet Counts

```
min=86.0  max=86.0  mean=86.0  median=86.0  p95=86.0 sheets
```

The number of XBRL sheets grows with filing complexity and year. More subsidiary segments, geographic breakouts, and disclosure tables each generate additional sheets.

---

## 3. SGML Header Metadata Coverage

Fields extracted from the `<SEC-HEADER>` block at the top of each file.

| Field | Present | Coverage | Notes |
|-------|---------|----------|-------|
| `accession_number` | 1/1 | 100% | Unique filing ID (not yet extracted by pipeline) |
| `cik` | 1/1 | 100% | SEC CIK — zero-padded 10 digits |
| `company_name` | 1/1 | 100% | All-caps legal name |
| `document_count` | 1/1 | 100% | Total embedded docs; varies 83–367 in this sample |
| `filed_as_of_date` | 1/1 | 100% | YYYYMMDD filing date |
| `fiscal_year` | 1/1 | 100% | Derived from `period_of_report[:4]` |
| `fiscal_year_end` | 1/1 | 100% | MMDD format (e.g. `0925` = Sep 25) |
| `form_type` | 1/1 | 100% | Under FILING VALUES block; always `10-K` |
| `period_of_report` | 1/1 | 100% | YYYYMMDD — primary source for `fiscal_year` |
| `sec_file_number` | 1/1 | 100% | Exchange registration number |
| `sic_code` | 1/1 | 100% | Parsed from `sic_full` |
| `sic_full` | 1/1 | 100% | Raw string: `NAME [code]` |
| `sic_name` | 1/1 | 100% | Parsed from `sic_full` |
| `state_of_incorporation` | 1/1 | 100% | Two-letter code |
| `submission_type` | 1/1 | 100% | Always `10-K` |

> ⚠️ = field not present in all analyzed files; do not rely on it without a fallback.

---

## 4. DEI iXBRL Tag Coverage

Tags extracted from `<ix:hidden>` inside the main 10-K document body. These are richer than the SGML header and include fields unavailable anywhere else (ticker, exchange, shares outstanding, filer category).

| Tag | Present | Coverage | Notes |
|-----|---------|----------|-------|
| `EntityCentralIndexKey` | 0/1 | 0% ⚠️ | Duplicates SGML CIK; useful cross-check |
| `TradingSymbol` | 0/1 | 0% ⚠️ | **Ticker** — only source; two format variants |
| `EntityRegistrantName` | 0/1 | 0% ⚠️ | Formatted name with punctuation (vs all-caps SGML) |
| `DocumentFiscalYearFocus` | 0/1 | 0% ⚠️ | Year as integer string |
| `DocumentFiscalPeriodFocus` | 0/1 | 0% ⚠️ | Always `FY` for 10-K |
| `DocumentType` | 0/1 | 0% ⚠️ | Always `10-K` |
| `DocumentPeriodEndDate` | 0/1 | 0% ⚠️ | Human-readable date (may contain HTML entities) |
| `EntityIncorporationStateCountryCode` | 0/1 | 0% ⚠️ | Full state name (vs two-letter SGML code) |
| `EntityTaxIdentificationNumber` | 0/1 | 0% ⚠️ | EIN with hyphen — **reliable; use over SGML `ein`** |
| `EntityAddressAddressLine1` | 0/1 | 0% ⚠️ | Street address |
| `EntityAddressCityOrTown` | 0/1 | 0% ⚠️ | City |
| `EntityAddressStateOrProvince` | 0/1 | 0% ⚠️ | State code |
| `EntityAddressPostalZipCode` | 0/1 | 0% ⚠️ | ZIP code |
| `CityAreaCode` | 0/1 | 0% ⚠️ | Phone area code |
| `LocalPhoneNumber` | 0/1 | 0% ⚠️ | Local phone number |
| `Security12bTitle` | 0/1 | 0% ⚠️ | Security description; absent for non-12b filers |
| `SecurityExchangeName` | 0/1 | 0% ⚠️ | Exchange; absent for non-12b filers |
| `EntityWellKnownSeasonedIssuer` | 0/1 | 0% ⚠️ | WKSI status: Yes/No |
| `EntityFilerCategory` | 0/1 | 0% ⚠️ | Large accelerated / accelerated / non-accelerated |
| `EntityPublicFloat` | 0/1 | 0% ⚠️ | Market cap at mid-year; formatting varies |
| `EntityCommonStockSharesOutstanding` | 0/1 | 0% ⚠️ | Share count at recent date |
| `AmendmentFlag` | 0/1 | 0% ⚠️ | True/False/false — case varies across filers |
| `IcfrAuditorAttestationFlag` | 0/1 | 0% ⚠️ | SOX 404(b); may be HTML entity (☑/☐) |

> ⚠️ = tag absent in at least one filing. For 12b registration fields (`Security12bTitle`, `SecurityExchangeName`, `TradingSymbol`), absence indicates the company may not have a listed security (e.g. holding companies, foreign private issuers).

---

## 5. Corpus Composition

### 5.1 SIC Code Distribution (top 15)

| SIC | Count | % of sample |
|-----|-------|-------------|
| 7372 — SERVICES-PREPACKAGED SOFTWARE | 1 | 100% |

### 5.2 Fiscal Year Distribution

| Fiscal Year | Count | Bar |
|-------------|-------|-----|
| 2020 | 1 | █ |

### 5.3 Filing Lag Distribution

Days elapsed between `CONFORMED PERIOD OF REPORT` (fiscal year end) and `FILED AS OF DATE`. Large accelerated filers must file within 60 days; accelerated filers within 75 days; others within 90 days.

```
min=60.0  max=60.0  mean=60.0  median=60.0  p95=60.0 days
```

| File | Period End | Filed | Lag (days) |
|------|-----------|-------|------------|
| `DDOG_10K_2021` | 20201231 | 20210301 | 60 |

### 5.4 DEI Value Distributions

Actual values extracted from `<ix:hidden>` — not just presence, but what the values are across the sample.

---

## 6. Key Findings

**F1 — EDGAR files are SGML containers, not HTML.**  
Each `.html` file is a flat concatenation of 107–107 embedded documents delimited by `<DOCUMENT>` tags. The `sec-parser` library only processes Document 1 (the iXBRL 10-K body). All other documents — including XBRL financials, exhibits, and MetaLinks.json — are invisible to it.

**F2 — Two parallel, redundant metadata sources exist.**  
The SGML `<SEC-HEADER>` block (plain text, always ~80 lines) and the `<ix:hidden>` DEI block inside the main 10-K HTML body both carry company identity data. The SGML header is faster to parse (no HTML parsing required). The DEI block is richer (ticker, exchange, shares, filer category) and provides a more reliable EIN.

**F3 — EIN is unreliable in the SGML header.**  
`ein` was present in only 0/1 (0%) SGML headers, but `dei:EntityTaxIdentificationNumber` was present in 0/1 (0%) DEI blocks. Always prefer the DEI source for EIN.

**F4 — 23 DEI tag(s) are not universally present.**  
`EntityCentralIndexKey` (0/1), `TradingSymbol` (0/1), `EntityRegistrantName` (0/1), `DocumentFiscalYearFocus` (0/1), `DocumentFiscalPeriodFocus` (0/1), `DocumentType` (0/1), `DocumentPeriodEndDate` (0/1), `EntityIncorporationStateCountryCode` (0/1), `EntityTaxIdentificationNumber` (0/1), `EntityAddressAddressLine1` (0/1), `EntityAddressCityOrTown` (0/1), `EntityAddressStateOrProvince` (0/1), `EntityAddressPostalZipCode` (0/1), `CityAreaCode` (0/1), `LocalPhoneNumber` (0/1), `Security12bTitle` (0/1), `SecurityExchangeName` (0/1), `EntityWellKnownSeasonedIssuer` (0/1), `EntityFilerCategory` (0/1), `EntityPublicFloat` (0/1), `EntityCommonStockSharesOutstanding` (0/1), `AmendmentFlag` (0/1), `IcfrAuditorAttestationFlag` (0/1). These are absent for companies without a Section 12(b) registration (e.g. exchange-listed security). Always guard with `.get()`.

**F6 — File size variance is large.**  
Mean=16.7 MB, stdev=0.0 MB (outlier threshold: mean+1σ = 16.7 MB). Files above threshold: none. Large files drive slower parse times in `sec-parser`.

**F7 — R*.htm sheet count is the primary driver of file size.**  
Sheets range from 86 to 86 per filing (mean 86). More sheets = more XBRL financial disclosures. This grows over time as reporting standards require more granular segment breakouts.

**F8 — MetaLinks.json and FilingSummary.xml are present in every file.**  
Both were found in 0/1 and 1/1 files respectively. MetaLinks.json is the authoritative XBRL element dictionary (FASB definitions, calculation trees, presentation hierarchy). FilingSummary.xml maps every R*.htm sheet to its human-readable name and `MenuCategory` (Statements/Notes/Details/etc.).

---

## 7. Extraction Gap: Available vs. Currently Extracted

What the pipeline currently extracts vs. what the raw files contain.

| Data Field | Source | Extracted | Notes |
|------------|--------|-----------|-------|
| `company_name` | SGML header | ✓ | All-caps; DEI `EntityRegistrantName` has proper casing |
| `cik` | SGML header | ✓ |  |
| `sic_code` | SGML header | ✓ |  |
| `sic_name` | SGML header | ✓ |  |
| `ticker (TradingSymbol)` | DEI iXBRL | ✓ | Two format variants in corpus |
| `fiscal_year` | SGML header | ✓ | Derived from `period_of_report[:4]` |
| `period_of_report` | SGML header | ✓ |  |
| `ein` | SGML header | ✗ | Use DEI source; SGML unreliable |
| `state_of_incorporation` | SGML header | ✗ | SGML=2-letter code; DEI=full name |
| `fiscal_year_end (MMDD)` | SGML header | ✗ | e.g. `0925` = Sep 25 |
| `accession_number` | SGML header | ✗ | Unique filing ID for EDGAR API lookups |
| `sec_file_number` | SGML header | ✗ |  |
| `exchange (Nasdaq/NYSE)` | DEI iXBRL | ✗ | In DEI as `SecurityExchangeName` |
| `shares_outstanding` | DEI iXBRL | ✗ | In DEI as `EntityCommonStockSharesOutstanding` |
| `public_float` | DEI iXBRL | ✗ | In DEI as `EntityPublicFloat`; formatting varies |
| `filer_category` | DEI iXBRL | ✗ | In DEI as `EntityFilerCategory` |
| `amendment_flag` | DEI iXBRL | ✗ | In DEI as `AmendmentFlag` |
| `FASB element definitions` | MetaLinks.json | ✗ | MetaLinks.json — definitions, calc tree, presentation |
| `all financial facts` | XBRL instance XML | ✗ | XBRL instance XML — all tagged monetary/numeric values |
| `calculation tree` | EX-101.CAL/MetaLinks | ✗ | EX-101.CAL or MetaLinks `calculation` field |
| `named financial statements` | FilingSummary.xml | ✗ | FilingSummary.xml — R*.htm name + MenuCategory |
| `company charts/logos` | GRAPHIC documents | ✗ | GRAPHIC documents — UUencoded; rarely needed |

**7/22 fields currently extracted** (32% coverage).

---

---

## 9. Patterns & Correlations

Observations derived from the sample. Run `--sample 50` or `--all` to strengthen statistical confidence.

### 9.1 Company Coverage

- **Unique tickers:** 1
- **Tickers with multiple filing years:** 0

### 9.2 File Size vs. Complexity Correlations

Pearson r between key metrics (closer to ±1.0 = stronger linear relationship):

| Pair | Pearson r | Interpretation |
|------|-----------|----------------|
| File size vs R*.htm sheet count | N/A | N/A |
| File size vs total document count | N/A | N/A |
| R*.htm count vs total documents | N/A | N/A |
| Main 10-K body size vs total file size | N/A | N/A |

### 9.3 Industry Complexity by SIC Code

Average file size and R*.htm sheet count grouped by SIC code (only SIC codes with ≥2 filings shown).

*(No SIC codes appear ≥2 times in this sample — run with a larger sample.)*

### 9.4 Filing Lag by Filer Category

| Filer Category | N | Min days | Max days | Mean days |
|----------------|---|----------|----------|-----------|
| unknown | 1 | 60 | 60 | 60 |

### 9.5 Fiscal Year Trend: R*.htm Sheet Count

Do filings get more complex over time?

| Fiscal Year | N | Min | Max | Mean R*.htm |
|-------------|---|-----|-----|-------------|
| 2020 | 1 | 86 | 86 | 86 |

*Report generated by `scripts/eda/sec_html_structure_explorer.py`*
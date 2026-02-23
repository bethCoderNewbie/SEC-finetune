# SEC 10-K HTML Structure — Analysis Report

**Generated:** 2026-02-22 17:33:12  
**Files analyzed:** 1  
**Mode:** specific files: ABT_10K_2021  
**Data source:** `data/raw/*.html` (EDGAR full-submission text files)

---

## Executive Summary

Analyzed **1 EDGAR full-submission text files** from the corpus. Key observations:

- Each file is an **SGML container** embedding 128–128 separate documents (mean 128).
- File sizes range from **21.4 MB to 21.4 MB** (mean 21.4 MB). The main 10-K iXBRL body is 4.3 MB on average.
- All 1 files have `MetaLinks.json` (100%) and `FilingSummary.xml` (100%).
- **All 23 DEI iXBRL tags** were fully present in 1/1 files. Tags with <100% presence are noted in §4.
- The SGML header provides reliable metadata for all core fields except `ein` (present in 0% of files). Use `dei:EntityTaxIdentificationNumber` instead.

---

## 1. File Size Distribution

### 1.1 Total file size (SGML container)

```
min=21.4  max=21.4  mean=21.4  median=21.4  p95=21.4 MB
```

### 1.2 Main 10-K iXBRL body size

```
min=4.3  max=4.3  mean=4.3  median=4.3  p95=4.3 MB
```

The main 10-K body is the only document passed to `sec-parser`. Its size relative to the container explains why `sec-parser` is unaware of the other 127 embedded documents per filing.

### 1.3 Per-file breakdown

| File | Size (MB) | Docs | Main 10-K (MB) | R*.htm sheets |
|------|-----------|------|----------------|---------------|
| `ABT_10K_2021` | 21.4 | 128 | 4.28 | 96 |

---

## 2. Embedded Document Type Distribution

Aggregated counts and sizes across all analyzed files.

| Type | Total Count | Files Present | Total Size (MB) | Avg per file |
|------|-------------|---------------|-----------------|--------------|
| `XML` | 100 | 1/1 | 9.78 | 100.0 |
| `10-K` | 1 | 1/1 | 4.28 | 1.0 |
| `EX-10.2` | 1 | 1/1 | 0.16 | 1.0 |
| `EX-10.56` | 1 | 1/1 | 0.16 | 1.0 |
| `EX-10.57` | 1 | 1/1 | 0.16 | 1.0 |
| `EX-10.58` | 1 | 1/1 | 0.06 | 1.0 |
| `EX-10.59` | 1 | 1/1 | 0.06 | 1.0 |
| `EX-10.60` | 1 | 1/1 | 0.17 | 1.0 |
| `EX-10.61` | 1 | 1/1 | 0.17 | 1.0 |
| `EX-10.62` | 1 | 1/1 | 0.07 | 1.0 |
| `EX-10.63` | 1 | 1/1 | 0.07 | 1.0 |
| `EX-10.66` | 1 | 1/1 | 0.01 | 1.0 |
| `EX-10.68` | 1 | 1/1 | 0.08 | 1.0 |
| `EX-10.74` | 1 | 1/1 | 0.12 | 1.0 |
| `EX-10.75` | 1 | 1/1 | 0.75 | 1.0 |
| `EX-21` | 1 | 1/1 | 0.57 | 1.0 |
| `EX-23.1` | 1 | 1/1 | 0.01 | 1.0 |
| `EX-31.1` | 1 | 1/1 | 0.01 | 1.0 |
| `EX-31.2` | 1 | 1/1 | 0.01 | 1.0 |
| `EX-32.1` | 1 | 1/1 | 0.01 | 1.0 |
| `EX-32.2` | 1 | 1/1 | 0.01 | 1.0 |
| `EX-101.SCH` | 1 | 1/1 | 0.09 | 1.0 |
| `EX-101.CAL` | 1 | 1/1 | 0.10 | 1.0 |
| `EX-101.DEF` | 1 | 1/1 | 0.41 | 1.0 |
| `EX-101.LAB` | 1 | 1/1 | 0.97 | 1.0 |
| `EX-101.PRE` | 1 | 1/1 | 0.72 | 1.0 |
| `EXCEL` | 1 | 1/1 | 0.21 | 1.0 |
| `JSON` | 1 | 1/1 | 1.14 | 1.0 |
| `ZIP` | 1 | 1/1 | 1.00 | 1.0 |

**Notes:**
- `XML` documents are primarily `R*.htm` XBRL financial statement sheets — by far the most numerous type.
- `GRAPHIC` documents are UUencoded images (not base64). Count grows with filing complexity.
- `EX-101.*` exhibits (SCH/CAL/DEF/LAB/PRE) appear exactly once per filing.
- `JSON` = `MetaLinks.json` (XBRL element catalogue). Always exactly 1 per filing.

### 2.1 R*.htm XBRL Sheet Counts

```
min=96.0  max=96.0  mean=96.0  median=96.0  p95=96.0 sheets
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
| `EntityCentralIndexKey` | 1/1 | 100% | Duplicates SGML CIK; useful cross-check |
| `TradingSymbol` | 1/1 | 100% | **Ticker** — only source; two format variants |
| `EntityRegistrantName` | 1/1 | 100% | Formatted name with punctuation (vs all-caps SGML) |
| `DocumentFiscalYearFocus` | 1/1 | 100% | Year as integer string |
| `DocumentFiscalPeriodFocus` | 1/1 | 100% | Always `FY` for 10-K |
| `DocumentType` | 1/1 | 100% | Always `10-K` |
| `DocumentPeriodEndDate` | 1/1 | 100% | Human-readable date (may contain HTML entities) |
| `EntityIncorporationStateCountryCode` | 1/1 | 100% | Full state name (vs two-letter SGML code) |
| `EntityTaxIdentificationNumber` | 1/1 | 100% | EIN with hyphen — **reliable; use over SGML `ein`** |
| `EntityAddressAddressLine1` | 1/1 | 100% | Street address |
| `EntityAddressCityOrTown` | 1/1 | 100% | City |
| `EntityAddressStateOrProvince` | 1/1 | 100% | State code |
| `EntityAddressPostalZipCode` | 1/1 | 100% | ZIP code |
| `CityAreaCode` | 1/1 | 100% | Phone area code |
| `LocalPhoneNumber` | 1/1 | 100% | Local phone number |
| `Security12bTitle` | 1/1 | 100% | Security description; absent for non-12b filers |
| `SecurityExchangeName` | 1/1 | 100% | Exchange; absent for non-12b filers |
| `EntityWellKnownSeasonedIssuer` | 1/1 | 100% | WKSI status: Yes/No |
| `EntityFilerCategory` | 1/1 | 100% | Large accelerated / accelerated / non-accelerated |
| `EntityPublicFloat` | 1/1 | 100% | Market cap at mid-year; formatting varies |
| `EntityCommonStockSharesOutstanding` | 1/1 | 100% | Share count at recent date |
| `AmendmentFlag` | 1/1 | 100% | True/False/false — case varies across filers |
| `IcfrAuditorAttestationFlag` | 1/1 | 100% | SOX 404(b); may be HTML entity (☑/☐) |

> ⚠️ = tag absent in at least one filing. For 12b registration fields (`Security12bTitle`, `SecurityExchangeName`, `TradingSymbol`), absence indicates the company may not have a listed security (e.g. holding companies, foreign private issuers).

---

## 5. Corpus Composition

### 5.1 SIC Code Distribution (top 15)

| SIC | Count | % of sample |
|-----|-------|-------------|
| 2834 — PHARMACEUTICAL PREPARATIONS | 1 | 100% |

### 5.2 Fiscal Year Distribution

| Fiscal Year | Count | Bar |
|-------------|-------|-----|
| 2020 | 1 | █ |

### 5.3 Filing Lag Distribution

Days elapsed between `CONFORMED PERIOD OF REPORT` (fiscal year end) and `FILED AS OF DATE`. Large accelerated filers must file within 60 days; accelerated filers within 75 days; others within 90 days.

```
min=50.0  max=50.0  mean=50.0  median=50.0  p95=50.0 days
```

| File | Period End | Filed | Lag (days) |
|------|-----------|-------|------------|
| `ABT_10K_2021` | 20201231 | 20210219 | 50 |

### 5.4 DEI Value Distributions

Actual values extracted from `<ix:hidden>` — not just presence, but what the values are across the sample.

**Filer Category** (`EntityFilerCategory`):

| Value | Count | % |
|-------|-------|---|
| Large Accelerated Filer | 1 | 100% |

**Exchange Listed On** (`SecurityExchangeName`):

| Value | Count | % |
|-------|-------|---|
| New York Stock Exchange | 1 | 100% |

**Well-Known Seasoned Issuer (WKSI)** (`EntityWellKnownSeasonedIssuer`):

| Value | Count | % |
|-------|-------|---|
| Yes | 1 | 100% |

**State of Incorporation** (`EntityIncorporationStateCountryCode`):

| Value | Count | % |
|-------|-------|---|
| Illinois | 1 | 100% |

**HQ State** (`EntityAddressStateOrProvince`):

| Value | Count | % |
|-------|-------|---|
| Illinois | 1 | 100% |

---

## 6. Key Findings

**F1 — EDGAR files are SGML containers, not HTML.**  
Each `.html` file is a flat concatenation of 128–128 embedded documents delimited by `<DOCUMENT>` tags. The `sec-parser` library only processes Document 1 (the iXBRL 10-K body). All other documents — including XBRL financials, exhibits, and MetaLinks.json — are invisible to it.

**F2 — Two parallel, redundant metadata sources exist.**  
The SGML `<SEC-HEADER>` block (plain text, always ~80 lines) and the `<ix:hidden>` DEI block inside the main 10-K HTML body both carry company identity data. The SGML header is faster to parse (no HTML parsing required). The DEI block is richer (ticker, exchange, shares, filer category) and provides a more reliable EIN.

**F3 — EIN is unreliable in the SGML header.**  
`ein` was present in only 0/1 (0%) SGML headers, but `dei:EntityTaxIdentificationNumber` was present in 1/1 (100%) DEI blocks. Always prefer the DEI source for EIN.

**F4 — All 23 DEI tags were present in 100% of the 1 analyzed files.**  
Coverage may drop when extending to the full 961-file corpus.

**F6 — File size variance is large.**  
Mean=21.4 MB, stdev=0.0 MB (outlier threshold: mean+1σ = 21.4 MB). Files above threshold: none. Large files drive slower parse times in `sec-parser`.

**F7 — R*.htm sheet count is the primary driver of file size.**  
Sheets range from 96 to 96 per filing (mean 96). More sheets = more XBRL financial disclosures. This grows over time as reporting standards require more granular segment breakouts.

**F8 — MetaLinks.json and FilingSummary.xml are present in every file.**  
Both were found in 1/1 and 1/1 files respectively. MetaLinks.json is the authoritative XBRL element dictionary (FASB definitions, calculation trees, presentation hierarchy). FilingSummary.xml maps every R*.htm sheet to its human-readable name and `MenuCategory` (Statements/Notes/Details/etc.).

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

## 8. XBRL Instance Document Analysis

Parsed from `*_htm.xml` — the machine-readable equivalent of all financial statement values. Three structural gaps in naive parsing are corrected here.

### 8.1 Context Period Types

The XBRL 2003 schema defines three period types: `instant`, `duration`, and `forever`. A naive parser that only checks for `startDate`/`endDate` silently misclassifies `forever` contexts (used for entity-level facts with no time dimension).

| File | instant | duration | forever | total |
|------|---------|----------|---------|-------|
| `ABT_10K_2021` | 284 | 358 | 0 | 642 |

### 8.2 Unit Types: Simple vs. Divide

Units can be a plain `<measure>` (e.g. `iso4217:USD`) or a ratio `<divide>` (e.g. USD/share for EPS facts). A parser that only reads direct `<measure>` children of `<unit>` silently returns an empty string for all divide units.

| File | measure units | divide units | divide examples |
|------|---------------|--------------|-----------------|
| `ABT_10K_2021` | 6 | 1 | `Unit_Divide_USD_shares_SQDT0HCbHkCUk3xnC9ehow` (iso4217:USD / shares) |

### 8.3 Fact Precision Attribute: `decimals` vs. `precision`

The schema allows either `decimals` or `precision` on numeric facts — they are mutually exclusive alternatives. Modern filings use `decimals` exclusively. Older filings (pre-2010) may use `precision`. `decimals=INF` means exact value (used for integer share counts and similar).

> **Semantics:** `decimals="-6"` does **not** mean the value is in millions. The raw XML value is always in base units (USD). `decimals=-6` means the value is accurate to the nearest 10⁶ — it is a precision indicator, not a scale factor.

| File | facts | decimals | precision | INF |
|------|-------|----------|-----------|-----|
| `ABT_10K_2021` | 1826 | 1651 | 0 | 70 |

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
| Large Accelerated Filer | 1 | 50 | 50 | 50 |

### 9.5 Fiscal Year Trend: R*.htm Sheet Count

Do filings get more complex over time?

| Fiscal Year | N | Min | Max | Mean R*.htm |
|-------------|---|-----|-----|-------------|
| 2020 | 1 | 96 | 96 | 96 |

*Report generated by `scripts/eda/sec_html_structure_explorer.py`*
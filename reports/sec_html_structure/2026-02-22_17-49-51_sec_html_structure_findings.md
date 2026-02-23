# SEC 10-K HTML Structure — Analysis Report

**Generated:** 2026-02-22 17:49:51  
**Files analyzed:** 2  
**Mode:** specific files: AAPL_10K_2021, DDOG_10K_2021  
**Data source:** `data/raw/*.html` (EDGAR full-submission text files)

---

## Executive Summary

Analyzed **2 EDGAR full-submission text files** from the corpus. Key observations:

- Each file is an **SGML container** embedding 88–107 separate documents (mean 98).
- File sizes range from **10.5 MB to 16.7 MB** (mean 13.6 MB). The main 10-K iXBRL body is 3.7 MB on average.
- All 2 files have `MetaLinks.json` (50%) and `FilingSummary.xml` (100%).
- **All 23 DEI iXBRL tags** were fully present in 1/2 files. Tags with <100% presence are noted in §4.
- The SGML header provides reliable metadata for all core fields except `ein` (present in 0% of files). Use `dei:EntityTaxIdentificationNumber` instead.

---

## 1. File Size Distribution

### 1.1 Total file size (SGML container)

```
min=10.5  max=16.7  mean=13.6  median=13.6  p95=16.7 MB
```

### 1.2 Main 10-K iXBRL body size

```
min=2.1  max=5.4  mean=3.7  median=3.7  p95=5.4 MB
```

The main 10-K body is the only document passed to `sec-parser`. Its size relative to the container explains why `sec-parser` is unaware of the other 96 embedded documents per filing.

### 1.3 Per-file breakdown

| File | Size (MB) | Docs | Main 10-K (MB) | R*.htm sheets |
|------|-----------|------|----------------|---------------|
| `DDOG_10K_2021` | 16.7 | 107 | 5.41 | 86 |
| `AAPL_10K_2021` | 10.5 | 88 | 2.05 | 67 |

---

## 2. Embedded Document Type Distribution

Aggregated counts and sizes across all analyzed files.

| Type | Total Count | Files Present | Total Size (MB) | Avg per file |
|------|-------------|---------------|-----------------|--------------|
| `XML` | 160 | 2/2 | 9.44 | 80.0 |
| `GRAPHIC` | 4 | 2/2 | 0.42 | 2.0 |
| `10-K` | 2 | 2/2 | 7.46 | 1.0 |
| `EX-21.1` | 2 | 2/2 | 0.02 | 1.0 |
| `EX-23.1` | 2 | 2/2 | 0.01 | 1.0 |
| `EX-31.1` | 2 | 2/2 | 0.04 | 1.0 |
| `EX-31.2` | 2 | 2/2 | 0.04 | 1.0 |
| `EX-32.1` | 2 | 2/2 | 0.02 | 1.0 |
| `EX-101.SCH` | 2 | 2/2 | 0.14 | 1.0 |
| `EX-101.CAL` | 2 | 2/2 | 0.26 | 1.0 |
| `EX-101.DEF` | 2 | 2/2 | 0.58 | 1.0 |
| `EX-101.LAB` | 2 | 2/2 | 1.50 | 1.0 |
| `EX-101.PRE` | 2 | 2/2 | 1.04 | 1.0 |
| `EXCEL` | 2 | 2/2 | 0.31 | 1.0 |
| `ZIP` | 2 | 2/2 | 1.04 | 1.0 |
| `EX-4.1` | 1 | 1/2 | 0.12 | 1.0 |
| `JSON` | 1 | 1/2 | 0.83 | 1.0 |
| `EX-10.14` | 1 | 1/2 | 0.32 | 1.0 |
| `EX-32.2` | 1 | 1/2 | 0.01 | 1.0 |
| `EX-101.INS` | 1 | 1/2 | 3.61 | 1.0 |

**Notes:**
- `XML` documents are primarily `R*.htm` XBRL financial statement sheets — by far the most numerous type.
- `GRAPHIC` documents are UUencoded images (not base64). Count grows with filing complexity.
- `EX-101.*` exhibits (SCH/CAL/DEF/LAB/PRE) appear exactly once per filing.
- `JSON` = `MetaLinks.json` (XBRL element catalogue). Always exactly 1 per filing.

### 2.1 R*.htm XBRL Sheet Counts

```
min=67.0  max=86.0  mean=76.5  median=76.5  p95=86.0 sheets
```

The number of XBRL sheets grows with filing complexity and year. More subsidiary segments, geographic breakouts, and disclosure tables each generate additional sheets.

---

## 3. SGML Header Metadata Coverage

Fields extracted from the `<SEC-HEADER>` block at the top of each file.

| Field | Present | Coverage | Notes |
|-------|---------|----------|-------|
| `accession_number` | 2/2 | 100% | Unique filing ID (not yet extracted by pipeline) |
| `cik` | 2/2 | 100% | SEC CIK — zero-padded 10 digits |
| `company_name` | 2/2 | 100% | All-caps legal name |
| `document_count` | 2/2 | 100% | Total embedded docs; varies 83–367 in this sample |
| `filed_as_of_date` | 2/2 | 100% | YYYYMMDD filing date |
| `fiscal_year` | 2/2 | 100% | Derived from `period_of_report[:4]` |
| `fiscal_year_end` | 2/2 | 100% | MMDD format (e.g. `0925` = Sep 25) |
| `form_type` | 2/2 | 100% | Under FILING VALUES block; always `10-K` |
| `period_of_report` | 2/2 | 100% | YYYYMMDD — primary source for `fiscal_year` |
| `sec_file_number` | 2/2 | 100% | Exchange registration number |
| `sic_code` | 2/2 | 100% | Parsed from `sic_full` |
| `sic_full` | 2/2 | 100% | Raw string: `NAME [code]` |
| `sic_name` | 2/2 | 100% | Parsed from `sic_full` |
| `state_of_incorporation` | 2/2 | 100% | Two-letter code |
| `submission_type` | 2/2 | 100% | Always `10-K` |

> ⚠️ = field not present in all analyzed files; do not rely on it without a fallback.

---

## 4. DEI iXBRL Tag Coverage

Tags extracted from `<ix:hidden>` inside the main 10-K document body. These are richer than the SGML header and include fields unavailable anywhere else (ticker, exchange, shares outstanding, filer category).

| Tag | Present | Coverage | Notes |
|-----|---------|----------|-------|
| `EntityCentralIndexKey` | 1/2 | 50% ⚠️ | Duplicates SGML CIK; useful cross-check |
| `TradingSymbol` | 1/2 | 50% ⚠️ | **Ticker** — only source; two format variants |
| `EntityRegistrantName` | 1/2 | 50% ⚠️ | Formatted name with punctuation (vs all-caps SGML) |
| `DocumentFiscalYearFocus` | 1/2 | 50% ⚠️ | Year as integer string |
| `DocumentFiscalPeriodFocus` | 1/2 | 50% ⚠️ | Always `FY` for 10-K |
| `DocumentType` | 1/2 | 50% ⚠️ | Always `10-K` |
| `DocumentPeriodEndDate` | 1/2 | 50% ⚠️ | Human-readable date (may contain HTML entities) |
| `EntityIncorporationStateCountryCode` | 1/2 | 50% ⚠️ | Full state name (vs two-letter SGML code) |
| `EntityTaxIdentificationNumber` | 1/2 | 50% ⚠️ | EIN with hyphen — **reliable; use over SGML `ein`** |
| `EntityAddressAddressLine1` | 1/2 | 50% ⚠️ | Street address |
| `EntityAddressCityOrTown` | 1/2 | 50% ⚠️ | City |
| `EntityAddressStateOrProvince` | 1/2 | 50% ⚠️ | State code |
| `EntityAddressPostalZipCode` | 1/2 | 50% ⚠️ | ZIP code |
| `CityAreaCode` | 1/2 | 50% ⚠️ | Phone area code |
| `LocalPhoneNumber` | 1/2 | 50% ⚠️ | Local phone number |
| `Security12bTitle` | 1/2 | 50% ⚠️ | Security description; absent for non-12b filers |
| `SecurityExchangeName` | 1/2 | 50% ⚠️ | Exchange; absent for non-12b filers |
| `EntityWellKnownSeasonedIssuer` | 1/2 | 50% ⚠️ | WKSI status: Yes/No |
| `EntityFilerCategory` | 1/2 | 50% ⚠️ | Large accelerated / accelerated / non-accelerated |
| `EntityPublicFloat` | 1/2 | 50% ⚠️ | Market cap at mid-year; formatting varies |
| `EntityCommonStockSharesOutstanding` | 1/2 | 50% ⚠️ | Share count at recent date |
| `AmendmentFlag` | 1/2 | 50% ⚠️ | True/False/false — case varies across filers |
| `IcfrAuditorAttestationFlag` | 1/2 | 50% ⚠️ | SOX 404(b); may be HTML entity (☑/☐) |

> ⚠️ = tag absent in at least one filing. For 12b registration fields (`Security12bTitle`, `SecurityExchangeName`, `TradingSymbol`), absence indicates the company may not have a listed security (e.g. holding companies, foreign private issuers).

---

## 5. Corpus Composition

### 5.1 SIC Code Distribution (top 15)

| SIC | Count | % of sample |
|-----|-------|-------------|
| 3571 — ELECTRONIC COMPUTERS | 1 | 50% |
| 7372 — SERVICES-PREPACKAGED SOFTWARE | 1 | 50% |

### 5.2 Fiscal Year Distribution

| Fiscal Year | Count | Bar |
|-------------|-------|-----|
| 2020 | 1 | █ |
| 2021 | 1 | █ |

### 5.3 Filing Lag Distribution

Days elapsed between `CONFORMED PERIOD OF REPORT` (fiscal year end) and `FILED AS OF DATE`. Large accelerated filers must file within 60 days; accelerated filers within 75 days; others within 90 days.

```
min=34.0  max=60.0  mean=47.0  median=47.0  p95=60.0 days
```

| File | Period End | Filed | Lag (days) |
|------|-----------|-------|------------|
| `AAPL_10K_2021` | 20210925 | 20211029 | 34 |
| `DDOG_10K_2021` | 20201231 | 20210301 | 60 |

### 5.4 DEI Value Distributions

Actual values extracted from `<ix:hidden>` — not just presence, but what the values are across the sample.

**Filer Category** (`EntityFilerCategory`):

| Value | Count | % |
|-------|-------|---|
| Large accelerated filer | 1 | 50% |

**Exchange Listed On** (`SecurityExchangeName`):

| Value | Count | % |
|-------|-------|---|
| The Nasdaq Stock Market LLC | 1 | 50% |

**Well-Known Seasoned Issuer (WKSI)** (`EntityWellKnownSeasonedIssuer`):

| Value | Count | % |
|-------|-------|---|
| Yes | 1 | 50% |

**State of Incorporation** (`EntityIncorporationStateCountryCode`):

| Value | Count | % |
|-------|-------|---|
| California | 1 | 50% |

**HQ State** (`EntityAddressStateOrProvince`):

| Value | Count | % |
|-------|-------|---|
| California | 1 | 50% |

---

## 6. Key Findings

**F1 — EDGAR files are SGML containers, not HTML.**  
Each `.html` file is a flat concatenation of 88–107 embedded documents delimited by `<DOCUMENT>` tags. The `sec-parser` library only processes Document 1 (the iXBRL 10-K body). All other documents — including XBRL financials, exhibits, and MetaLinks.json — are invisible to it.

**F2 — Two parallel, redundant metadata sources exist.**  
The SGML `<SEC-HEADER>` block (plain text, always ~80 lines) and the `<ix:hidden>` DEI block inside the main 10-K HTML body both carry company identity data. The SGML header is faster to parse (no HTML parsing required). The DEI block is richer (ticker, exchange, shares, filer category) and provides a more reliable EIN.

**F3 — EIN is unreliable in the SGML header.**  
`ein` was present in only 0/2 (0%) SGML headers, but `dei:EntityTaxIdentificationNumber` was present in 1/2 (50%) DEI blocks. Always prefer the DEI source for EIN.

**F4 — 23 DEI tag(s) are not universally present.**  
`EntityCentralIndexKey` (1/2), `TradingSymbol` (1/2), `EntityRegistrantName` (1/2), `DocumentFiscalYearFocus` (1/2), `DocumentFiscalPeriodFocus` (1/2), `DocumentType` (1/2), `DocumentPeriodEndDate` (1/2), `EntityIncorporationStateCountryCode` (1/2), `EntityTaxIdentificationNumber` (1/2), `EntityAddressAddressLine1` (1/2), `EntityAddressCityOrTown` (1/2), `EntityAddressStateOrProvince` (1/2), `EntityAddressPostalZipCode` (1/2), `CityAreaCode` (1/2), `LocalPhoneNumber` (1/2), `Security12bTitle` (1/2), `SecurityExchangeName` (1/2), `EntityWellKnownSeasonedIssuer` (1/2), `EntityFilerCategory` (1/2), `EntityPublicFloat` (1/2), `EntityCommonStockSharesOutstanding` (1/2), `AmendmentFlag` (1/2), `IcfrAuditorAttestationFlag` (1/2). These are absent for companies without a Section 12(b) registration (e.g. exchange-listed security). Always guard with `.get()`.

**F6 — File size variance is large.**  
Mean=13.6 MB, stdev=4.4 MB (outlier threshold: mean+1σ = 18.0 MB). Files above threshold: none. Large files drive slower parse times in `sec-parser`.

**F7 — R*.htm sheet count is the primary driver of file size.**  
Sheets range from 67 to 86 per filing (mean 76). More sheets = more XBRL financial disclosures. This grows over time as reporting standards require more granular segment breakouts.

**F8 — MetaLinks.json and FilingSummary.xml are present in every file.**  
Both were found in 1/2 and 2/2 files respectively. MetaLinks.json is the authoritative XBRL element dictionary (FASB definitions, calculation trees, presentation hierarchy). FilingSummary.xml maps every R*.htm sheet to its human-readable name and `MenuCategory` (Statements/Notes/Details/etc.).

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

Parsed from `*_htm.xml` (XBRL instance document) or, when absent, from the main iXBRL 10-K HTM directly (inline XBRL). Source column distinguishes the two. Three structural gaps in naive parsing are corrected here.

### 8.1 Context Period Types

The XBRL 2003 schema defines three period types: `instant`, `duration`, and `forever`. A naive parser that only checks for `startDate`/`endDate` silently misclassifies `forever` contexts (used for entity-level facts with no time dimension).

| File | Source | instant | duration | forever | total |
|------|--------|---------|----------|---------|-------|
| `AAPL_10K_2021` | instance XML | 117 | 109 | 0 | 226 |
| `DDOG_10K_2021` | EX-101.INS | 124 | 112 | 0 | 236 |

### 8.2 Unit Types: Simple vs. Divide

Units can be a plain `<measure>` (e.g. `iso4217:USD`) or a ratio `<divide>` (e.g. USD/share for EPS facts). A parser that only reads direct `<measure>` children of `<unit>` silently returns an empty string for all divide units.

| File | Source | measure units | divide units | divide examples |
|------|--------|---------------|--------------|-----------------|
| `AAPL_10K_2021` | instance XML | 8 | 1 | `usdPerShare` (iso4217:USD / shares) |
| `DDOG_10K_2021` | EX-101.INS | 7 | 1 | `U_iso4217USD_xbrlishares` (iso4217:USD / xbrli:shares) |

### 8.3 Fact Precision Attribute: `decimals` vs. `precision`

The schema allows either `decimals` or `precision` on numeric facts — they are mutually exclusive alternatives. Modern filings use `decimals` exclusively. Older filings (pre-2010) may use `precision`. `decimals=INF` means exact value (used for integer share counts and similar).

> **Semantics:** `decimals="-6"` does **not** mean the value is in millions. The raw XML value is always in base units (USD). `decimals=-6` means the value is accurate to the nearest 10⁶ — it is a precision indicator, not a scale factor.

| File | Source | facts | decimals | precision | INF |
|------|--------|-------|----------|-----------|-----|
| `AAPL_10K_2021` | instance XML | 1191 | 1032 | 0 | 34 |
| `DDOG_10K_2021` | EX-101.INS | 1072 | 884 | 0 | 131 |

---

---

## 9. Patterns & Correlations

Observations derived from the sample. Run `--sample 50` or `--all` to strengthen statistical confidence.

### 9.1 Company Coverage

- **Unique tickers:** 2
- **Tickers with multiple filing years:** 0

### 9.2 File Size vs. Complexity Correlations

Pearson r between key metrics (closer to ±1.0 = stronger linear relationship):

| Pair | Pearson r | Interpretation |
|------|-----------|----------------|
| File size vs R*.htm sheet count | +1.00 | strong positive (+1.00) |
| File size vs total document count | +1.00 | strong positive (+1.00) |
| R*.htm count vs total documents | +1.00 | strong positive (+1.00) |
| Main 10-K body size vs total file size | +1.00 | strong positive (+1.00) |

### 9.3 Industry Complexity by SIC Code

Average file size and R*.htm sheet count grouped by SIC code (only SIC codes with ≥2 filings shown).

*(No SIC codes appear ≥2 times in this sample — run with a larger sample.)*

### 9.4 Filing Lag by Filer Category

| Filer Category | N | Min days | Max days | Mean days |
|----------------|---|----------|----------|-----------|
| Large accelerated filer | 1 | 34 | 34 | 34 |
| unknown | 1 | 60 | 60 | 60 |

### 9.5 Fiscal Year Trend: R*.htm Sheet Count

Do filings get more complex over time?

| Fiscal Year | N | Min | Max | Mean R*.htm |
|-------------|---|-----|-----|-------------|
| 2020 | 1 | 86 | 86 | 86 |
| 2021 | 1 | 67 | 67 | 67 |

*Report generated by `scripts/eda/sec_html_structure_explorer.py`*
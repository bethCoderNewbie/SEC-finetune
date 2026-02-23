# SEC 10-K HTML Structure — Analysis Report

**Generated:** 2026-02-22 17:11:39  
**Files analyzed:** 1  
**Mode:** specific files: AAPL_10K_2021  
**Data source:** `data/raw/*.html` (EDGAR full-submission text files)

---

## Executive Summary

Analyzed **1 EDGAR full-submission text files** from the corpus. Key observations:

- Each file is an **SGML container** embedding 88–88 separate documents (mean 88).
- File sizes range from **10.5 MB to 10.5 MB** (mean 10.5 MB). The main 10-K iXBRL body is 2.1 MB on average.
- All 1 files have `MetaLinks.json` (100%) and `FilingSummary.xml` (100%).
- **All 23 DEI iXBRL tags** were fully present in 1/1 files. Tags with <100% presence are noted in §4.
- The SGML header provides reliable metadata for all core fields except `ein` (present in 0% of files). Use `dei:EntityTaxIdentificationNumber` instead.

---

## 1. File Size Distribution

### 1.1 Total file size (SGML container)

```
min=10.5  max=10.5  mean=10.5  median=10.5  p95=10.5 MB
```

### 1.2 Main 10-K iXBRL body size

```
min=2.1  max=2.1  mean=2.1  median=2.1  p95=2.1 MB
```

The main 10-K body is the only document passed to `sec-parser`. Its size relative to the container explains why `sec-parser` is unaware of the other 87 embedded documents per filing.

### 1.3 Per-file breakdown

| File | Size (MB) | Docs | Main 10-K (MB) | R*.htm sheets |
|------|-----------|------|----------------|---------------|
| `AAPL_10K_2021` | 10.5 | 88 | 2.05 | 67 |

---

## 2. Embedded Document Type Distribution

Aggregated counts and sizes across all analyzed files.

| Type | Total Count | Files Present | Total Size (MB) | Avg per file |
|------|-------------|---------------|-----------------|--------------|
| `XML` | 71 | 1/1 | 4.56 | 71.0 |
| `GRAPHIC` | 2 | 1/1 | 0.26 | 2.0 |
| `10-K` | 1 | 1/1 | 2.05 | 1.0 |
| `EX-4.1` | 1 | 1/1 | 0.12 | 1.0 |
| `EX-21.1` | 1 | 1/1 | 0.01 | 1.0 |
| `EX-23.1` | 1 | 1/1 | 0.01 | 1.0 |
| `EX-31.1` | 1 | 1/1 | 0.01 | 1.0 |
| `EX-31.2` | 1 | 1/1 | 0.01 | 1.0 |
| `EX-32.1` | 1 | 1/1 | 0.01 | 1.0 |
| `EX-101.SCH` | 1 | 1/1 | 0.06 | 1.0 |
| `EX-101.CAL` | 1 | 1/1 | 0.15 | 1.0 |
| `EX-101.DEF` | 1 | 1/1 | 0.26 | 1.0 |
| `EX-101.LAB` | 1 | 1/1 | 0.82 | 1.0 |
| `EX-101.PRE` | 1 | 1/1 | 0.49 | 1.0 |
| `EXCEL` | 1 | 1/1 | 0.15 | 1.0 |
| `JSON` | 1 | 1/1 | 0.83 | 1.0 |
| `ZIP` | 1 | 1/1 | 0.69 | 1.0 |

**Notes:**
- `XML` documents are primarily `R*.htm` XBRL financial statement sheets — by far the most numerous type.
- `GRAPHIC` documents are UUencoded images (not base64). Count grows with filing complexity.
- `EX-101.*` exhibits (SCH/CAL/DEF/LAB/PRE) appear exactly once per filing.
- `JSON` = `MetaLinks.json` (XBRL element catalogue). Always exactly 1 per filing.

### 2.1 R*.htm XBRL Sheet Counts

```
min=67.0  max=67.0  mean=67.0  median=67.0  p95=67.0 sheets
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
| 3571 — ELECTRONIC COMPUTERS | 1 | 100% |

### 5.2 Fiscal Year Distribution

| Fiscal Year | Count | Bar |
|-------------|-------|-----|
| 2021 | 1 | █ |

---

## 6. Key Findings

**F1 — EDGAR files are SGML containers, not HTML.**  
Each `.html` file is a flat concatenation of 88–88 embedded documents delimited by `<DOCUMENT>` tags. The `sec-parser` library only processes Document 1 (the iXBRL 10-K body). All other documents — including XBRL financials, exhibits, and MetaLinks.json — are invisible to it.

**F2 — Two parallel, redundant metadata sources exist.**  
The SGML `<SEC-HEADER>` block (plain text, always ~80 lines) and the `<ix:hidden>` DEI block inside the main 10-K HTML body both carry company identity data. The SGML header is faster to parse (no HTML parsing required). The DEI block is richer (ticker, exchange, shares, filer category) and provides a more reliable EIN.

**F3 — EIN is unreliable in the SGML header.**  
`ein` was present in only 0/1 (0%) SGML headers, but `dei:EntityTaxIdentificationNumber` was present in 1/1 (100%) DEI blocks. Always prefer the DEI source for EIN.

**F4 — All 23 DEI tags were present in 100% of the 1 analyzed files.**  
Coverage may drop when extending to the full 961-file corpus.

**F6 — File size variance is large.**  
Mean=10.5 MB, stdev=0.0 MB (outlier threshold: mean+1σ = 10.5 MB). Files above threshold: none. Large files drive slower parse times in `sec-parser`.

**F7 — R*.htm sheet count is the primary driver of file size.**  
Sheets range from 67 to 67 per filing (mean 67). More sheets = more XBRL financial disclosures. This grows over time as reporting standards require more granular segment breakouts.

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
| `AAPL_10K_2021` | 117 | 109 | 0 | 226 |

### 8.2 Unit Types: Simple vs. Divide

Units can be a plain `<measure>` (e.g. `iso4217:USD`) or a ratio `<divide>` (e.g. USD/share for EPS facts). A parser that only reads direct `<measure>` children of `<unit>` silently returns an empty string for all divide units.

| File | measure units | divide units | divide examples |
|------|---------------|--------------|-----------------|
| `AAPL_10K_2021` | 8 | 1 | `usdPerShare` (iso4217:USD / shares) |

### 8.3 Fact Precision Attribute: `decimals` vs. `precision`

The schema allows either `decimals` or `precision` on numeric facts — they are mutually exclusive alternatives. Modern filings use `decimals` exclusively. Older filings (pre-2010) may use `precision`. `decimals=INF` means exact value (used for integer share counts and similar).

> **Semantics:** `decimals="-6"` does **not** mean the value is in millions. The raw XML value is always in base units (USD). `decimals=-6` means the value is accurate to the nearest 10⁶ — it is a precision indicator, not a scale factor.

| File | facts | decimals | precision | INF |
|------|-------|----------|-----------|-----|
| `AAPL_10K_2021` | 1191 | 1032 | 0 | 34 |

---

*Report generated by `scripts/eda/sec_html_structure_explorer.py`*
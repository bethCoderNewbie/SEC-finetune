# SEC 10-K HTML Structure — Analysis Report

**Generated:** 2026-02-22 16:54:12  
**Files analyzed:** 20  
**Mode:** random sample of 20 files (seed=42)  
**Data source:** `data/raw/*.html` (EDGAR full-submission text files)

---

## Executive Summary

Analyzed **20 EDGAR full-submission text files** from the corpus. Key observations:

- Each file is an **SGML container** embedding 83–367 separate documents (mean 160).
- File sizes range from **7.1 MB to 102.8 MB** (mean 33.8 MB). The main 10-K iXBRL body is 6.4 MB on average.
- All 20 files have `MetaLinks.json` (100%) and `FilingSummary.xml` (100%).
- **All 23 DEI iXBRL tags** were fully present in 19/20 files. Tags with <100% presence are noted in §4.
- The SGML header provides reliable metadata for all core fields except `ein` (present in 15% of files). Use `dei:EntityTaxIdentificationNumber` instead.

---

## 1. File Size Distribution

### 1.1 Total file size (SGML container)

```
min=7.1  max=102.8  mean=33.8  median=23.3  p95=102.8 MB
```

### 1.2 Main 10-K iXBRL body size

```
min=1.4  max=26.2  mean=6.4  median=4.0  p95=26.2 MB
```

The main 10-K body is the only document passed to `sec-parser`. Its size relative to the container explains why `sec-parser` is unaware of the other 159 embedded documents per filing.

### 1.3 Per-file breakdown

| File | Size (MB) | Docs | Main 10-K (MB) | R*.htm sheets |
|------|-----------|------|----------------|---------------|
| `AEP_10K_2022` | 102.8 | 163 | 26.24 | 76 |
| `DHR_10K_2022` | 92.5 | 367 | 4.05 | 116 |
| `C_10K_2021` | 87.5 | 238 | 20.76 | 197 |
| `AFL_10K_2023` | 48.6 | 180 | 10.52 | 151 |
| `AFL_10K_2021` | 45.3 | 170 | 9.98 | 149 |
| `BIIB_10K_2026` | 26.1 | 216 | 4.29 | 168 |
| `AXP_10K_2026` | 24.5 | 160 | 5.08 | 137 |
| `BBY_10K_2025` | 24.4 | 106 | 6.93 | 83 |
| `BA_10K_2022` | 23.7 | 163 | 4.36 | 141 |
| `CRWD_10K_2024` | 23.5 | 161 | 2.31 | 74 |
| `VZ_10K_2025` | 23.1 | 157 | 3.94 | 126 |
| `ORCL_10K_2024` | 22.8 | 101 | 5.32 | 84 |
| `RTX_10K_2025` | 21.1 | 133 | 3.86 | 109 |
| `RTX_10K_2024` | 20.5 | 133 | 3.88 | 111 |
| `HRL_10K_2025` | 17.9 | 139 | 3.21 | 117 |
| `MU_10K_2024` | 17.5 | 143 | 2.20 | 106 |
| `PG_10K_2022` | 16.4 | 113 | 3.33 | 88 |
| `CAH_10K_2022` | 16.1 | 128 | 3.29 | 101 |
| `META_10K_2023` | 15.3 | 138 | 2.88 | 92 |
| `ROST_10K_2024` | 7.1 | 83 | 1.38 | 61 |

---

## 2. Embedded Document Type Distribution

Aggregated counts and sizes across all analyzed files.

| Type | Total Count | Files Present | Total Size (MB) | Avg per file |
|------|-------------|---------------|-----------------|--------------|
| `XML` | 2367 | 20/20 | 299.05 | 118.3 |
| `GRAPHIC` | 440 | 20/20 | 97.97 | 22.0 |
| `10-K` | 20 | 20/20 | 127.83 | 1.0 |
| `EX-101.SCH` | 20 | 20/20 | 4.58 | 1.0 |
| `JSON` | 20 | 20/20 | 30.55 | 1.0 |
| `ZIP` | 20 | 20/20 | 33.52 | 1.0 |
| `EX-101.CAL` | 19 | 19/20 | 2.87 | 1.0 |
| `EX-101.DEF` | 19 | 19/20 | 15.40 | 1.0 |
| `EX-101.LAB` | 19 | 19/20 | 27.43 | 1.0 |
| `EX-101.PRE` | 19 | 19/20 | 20.92 | 1.0 |
| `EX-23` | 17 | 11/20 | 0.05 | 1.5 |
| `EXCEL` | 17 | 17/20 | 5.76 | 1.0 |
| `EX-31.1` | 16 | 16/20 | 0.17 | 1.0 |
| `EX-31.2` | 16 | 16/20 | 0.17 | 1.0 |
| `EX-32.1` | 12 | 12/20 | 0.07 | 1.0 |
| `EX-21` | 11 | 11/20 | 0.52 | 1.0 |
| `EX-24` | 11 | 4/20 | 0.20 | 2.8 |
| `EX-31.A` | 8 | 1/20 | 0.08 | 8.0 |
| `EX-31.B` | 8 | 1/20 | 0.08 | 8.0 |
| `EX-32.A` | 8 | 1/20 | 0.03 | 8.0 |
| `EX-32.B` | 8 | 1/20 | 0.03 | 8.0 |
| `EX-32.2` | 8 | 8/20 | 0.04 | 1.0 |
| `EX-21.1` | 7 | 7/20 | 0.36 | 1.0 |
| `EX-23.1` | 6 | 6/20 | 0.04 | 1.0 |
| `EX-32` | 5 | 5/20 | 0.04 | 1.0 |
| `EX-19.1` | 3 | 3/20 | 0.46 | 1.0 |
| `EX-23.01` | 3 | 3/20 | 0.02 | 1.0 |
| `EX-19` | 3 | 3/20 | 0.24 | 1.0 |
| `EX-4.6` | 2 | 2/20 | 0.05 | 1.0 |
| `EX-99.1` | 2 | 2/20 | 0.05 | 1.0 |
| `EX-97.1` | 2 | 2/20 | 0.06 | 1.0 |
| `EX-21.01` | 2 | 2/20 | 0.08 | 1.0 |
| `EX-31.01` | 2 | 2/20 | 0.03 | 1.0 |
| `EX-32.01` | 2 | 2/20 | 0.02 | 1.0 |
| `EX-99.01` | 2 | 2/20 | 0.98 | 1.0 |
| `EX-10.5` | 2 | 2/20 | 0.07 | 1.0 |
| `EX-10.8` | 2 | 2/20 | 0.12 | 1.0 |
| `EX-10.12` | 2 | 2/20 | 0.13 | 1.0 |
| `EX-97` | 2 | 2/20 | 0.08 | 1.0 |
| `EX-31.3` | 2 | 2/20 | 0.02 | 1.0 |
| `EX-10.D` | 1 | 1/20 | 0.07 | 1.0 |
| `EX-95` | 1 | 1/20 | 0.01 | 1.0 |
| `EX-10.29` | 1 | 1/20 | 0.02 | 1.0 |
| `EX-10.30` | 1 | 1/20 | 0.07 | 1.0 |
| `EX-10.33` | 1 | 1/20 | 0.02 | 1.0 |
| `EX-10.34` | 1 | 1/20 | 0.02 | 1.0 |
| `EX-10.35` | 1 | 1/20 | 0.02 | 1.0 |
| `EX-10.37` | 1 | 1/20 | 0.02 | 1.0 |
| `EX-4.5` | 1 | 1/20 | 0.12 | 1.0 |
| `EX-10.14` | 1 | 1/20 | 0.32 | 1.0 |
| `EX-10.16` | 1 | 1/20 | 0.11 | 1.0 |
| `EX-10.14.6` | 1 | 1/20 | 0.05 | 1.0 |
| `EX-10.20` | 1 | 1/20 | 0.03 | 1.0 |
| `EX-10.21` | 1 | 1/20 | 0.09 | 1.0 |
| `EX-3.01` | 1 | 1/20 | 2.96 | 1.0 |
| `EX-4.29` | 1 | 1/20 | 0.12 | 1.0 |
| `EX-18.01` | 1 | 1/20 | 0.00 | 1.0 |
| `EX-24.01` | 1 | 1/20 | 0.07 | 1.0 |
| `EX-31.02` | 1 | 1/20 | 0.01 | 1.0 |
| `EX-4.15` | 1 | 1/20 | 0.22 | 1.0 |
| `EX-10.4` | 1 | 1/20 | 0.05 | 1.0 |
| `EX-10.6` | 1 | 1/20 | 0.24 | 1.0 |
| `EX-10.7` | 1 | 1/20 | 0.23 | 1.0 |
| `EX-10.19` | 1 | 1/20 | 0.00 | 1.0 |
| `EX-22.1` | 1 | 1/20 | 0.01 | 1.0 |
| `EX-10.22` | 1 | 1/20 | 0.04 | 1.0 |
| `EX-10.23` | 1 | 1/20 | 0.04 | 1.0 |
| `EX-24.1` | 1 | 1/20 | 0.09 | 1.0 |
| `EX-10.2(A)` | 1 | 1/20 | 0.18 | 1.0 |
| `EX-10.2(B)` | 1 | 1/20 | 0.01 | 1.0 |
| `EX-4.10` | 1 | 1/20 | 0.08 | 1.0 |
| `EX-4.11` | 1 | 1/20 | 0.07 | 1.0 |
| `EX-10.10` | 1 | 1/20 | 0.02 | 1.0 |
| `EX-10.13` | 1 | 1/20 | 0.03 | 1.0 |
| `EX-31` | 1 | 1/20 | 0.02 | 1.0 |
| `EX-10.31` | 1 | 1/20 | 0.24 | 1.0 |
| `EX-10.70` | 1 | 1/20 | 0.15 | 1.0 |
| `EX-4.G` | 1 | 1/20 | 0.25 | 1.0 |

**Notes:**
- `XML` documents are primarily `R*.htm` XBRL financial statement sheets — by far the most numerous type.
- `GRAPHIC` documents are UUencoded images (not base64). Count grows with filing complexity.
- `EX-101.*` exhibits (SCH/CAL/DEF/LAB/PRE) appear exactly once per filing.
- `JSON` = `MetaLinks.json` (XBRL element catalogue). Always exactly 1 per filing.

### 2.1 R*.htm XBRL Sheet Counts

```
min=61.0  max=197.0  mean=114.3  median=110.0  p95=197.0 sheets
```

The number of XBRL sheets grows with filing complexity and year. More subsidiary segments, geographic breakouts, and disclosure tables each generate additional sheets.

---

## 3. SGML Header Metadata Coverage

Fields extracted from the `<SEC-HEADER>` block at the top of each file.

| Field | Present | Coverage | Notes |
|-------|---------|----------|-------|
| `accession_number` | 20/20 | 100% | Unique filing ID (not yet extracted by pipeline) |
| `cik` | 20/20 | 100% | SEC CIK — zero-padded 10 digits |
| `company_name` | 20/20 | 100% | All-caps legal name |
| `document_count` | 20/20 | 100% | Total embedded docs; varies 83–367 in this sample |
| `ein` | 3/20 | 15% ⚠️ | **Unreliable** — only present in some filings; use DEI instead |
| `filed_as_of_date` | 20/20 | 100% | YYYYMMDD filing date |
| `fiscal_year` | 20/20 | 100% | Derived from `period_of_report[:4]` |
| `fiscal_year_end` | 20/20 | 100% | MMDD format (e.g. `0925` = Sep 25) |
| `form_type` | 20/20 | 100% | Under FILING VALUES block; always `10-K` |
| `period_of_report` | 20/20 | 100% | YYYYMMDD — primary source for `fiscal_year` |
| `sec_file_number` | 20/20 | 100% | Exchange registration number |
| `sic_code` | 20/20 | 100% | Parsed from `sic_full` |
| `sic_full` | 20/20 | 100% | Raw string: `NAME [code]` |
| `sic_name` | 20/20 | 100% | Parsed from `sic_full` |
| `state_of_incorporation` | 19/20 | 95% ⚠️ | Two-letter code |
| `submission_type` | 20/20 | 100% | Always `10-K` |

> ⚠️ = field not present in all analyzed files; do not rely on it without a fallback.

---

## 4. DEI iXBRL Tag Coverage

Tags extracted from `<ix:hidden>` inside the main 10-K document body. These are richer than the SGML header and include fields unavailable anywhere else (ticker, exchange, shares outstanding, filer category).

| Tag | Present | Coverage | Notes |
|-----|---------|----------|-------|
| `EntityCentralIndexKey` | 20/20 | 100% | Duplicates SGML CIK; useful cross-check |
| `TradingSymbol` | 19/20 | 95% ⚠️ | **Ticker** — only source; two format variants |
| `EntityRegistrantName` | 20/20 | 100% | Formatted name with punctuation (vs all-caps SGML) |
| `DocumentFiscalYearFocus` | 20/20 | 100% | Year as integer string |
| `DocumentFiscalPeriodFocus` | 20/20 | 100% | Always `FY` for 10-K |
| `DocumentType` | 20/20 | 100% | Always `10-K` |
| `DocumentPeriodEndDate` | 20/20 | 100% | Human-readable date (may contain HTML entities) |
| `EntityIncorporationStateCountryCode` | 20/20 | 100% | Full state name (vs two-letter SGML code) |
| `EntityTaxIdentificationNumber` | 20/20 | 100% | EIN with hyphen — **reliable; use over SGML `ein`** |
| `EntityAddressAddressLine1` | 20/20 | 100% | Street address |
| `EntityAddressCityOrTown` | 20/20 | 100% | City |
| `EntityAddressStateOrProvince` | 20/20 | 100% | State code |
| `EntityAddressPostalZipCode` | 20/20 | 100% | ZIP code |
| `CityAreaCode` | 20/20 | 100% | Phone area code |
| `LocalPhoneNumber` | 20/20 | 100% | Local phone number |
| `Security12bTitle` | 19/20 | 95% ⚠️ | Security description; absent for non-12b filers |
| `SecurityExchangeName` | 19/20 | 95% ⚠️ | Exchange; absent for non-12b filers |
| `EntityWellKnownSeasonedIssuer` | 20/20 | 100% | WKSI status: Yes/No |
| `EntityFilerCategory` | 20/20 | 100% | Large accelerated / accelerated / non-accelerated |
| `EntityPublicFloat` | 20/20 | 100% | Market cap at mid-year; formatting varies |
| `EntityCommonStockSharesOutstanding` | 20/20 | 100% | Share count at recent date |
| `AmendmentFlag` | 20/20 | 100% | True/False/false — case varies across filers |
| `IcfrAuditorAttestationFlag` | 20/20 | 100% | SOX 404(b); may be HTML entity (☑/☐) |

> ⚠️ = tag absent in at least one filing. For 12b registration fields (`Security12bTitle`, `SecurityExchangeName`, `TradingSymbol`), absence indicates the company may not have a listed security (e.g. holding companies, foreign private issuers).

---

## 5. Corpus Composition

### 5.1 SIC Code Distribution (top 15)

| SIC | Count | % of sample |
|-----|-------|-------------|
| 6321 — ACCIDENT & HEALTH INSURANCE | 2 | 10% |
| 7372 — SERVICES-PREPACKAGED SOFTWARE | 2 | 10% |
| 3724 — AIRCRAFT ENGINES & ENGINE PARTS | 2 | 10% |
| 4911 — ELECTRIC SERVICES | 1 | 5% |
| 6199 — FINANCE SERVICES | 1 | 5% |
| 3721 — AIRCRAFT | 1 | 5% |
| 5731 — RETAIL-RADIO TV & CONSUMER ELECTRONICS STORES | 1 | 5% |
| 2836 — BIOLOGICAL PRODUCTS (NO DIAGNOSTIC SUBSTANCES) | 1 | 5% |
| 5122 — WHOLESALE-DRUGS PROPRIETARIES & DRUGGISTS' SUNDRIES | 1 | 5% |
| 6021 — NATIONAL COMMERCIAL BANKS | 1 | 5% |
| 3823 — INDUSTRIAL INSTRUMENTS FOR MEASUREMENT, DISPLAY, AND CONTROL | 1 | 5% |
| 2011 — MEAT PACKING PLANTS | 1 | 5% |
| 7370 — SERVICES-COMPUTER PROGRAMMING, DATA PROCESSING, ETC. | 1 | 5% |
| 3674 — SEMICONDUCTORS & RELATED DEVICES | 1 | 5% |
| 2840 — SOAP, DETERGENT, CLEANING PREPARATIONS, PERFUMES, COSMETICS | 1 | 5% |

### 5.2 Fiscal Year Distribution

| Fiscal Year | Count | Bar |
|-------------|-------|-----|
| 2020 | 2 | ██ |
| 2021 | 3 | ███ |
| 2022 | 4 | ████ |
| 2023 | 1 | █ |
| 2024 | 6 | ██████ |
| 2025 | 4 | ████ |

---

## 6. Key Findings

**F1 — EDGAR files are SGML containers, not HTML.**  
Each `.html` file is a flat concatenation of 83–367 embedded documents delimited by `<DOCUMENT>` tags. The `sec-parser` library only processes Document 1 (the iXBRL 10-K body). All other documents — including XBRL financials, exhibits, and MetaLinks.json — are invisible to it.

**F2 — Two parallel, redundant metadata sources exist.**  
The SGML `<SEC-HEADER>` block (plain text, always ~80 lines) and the `<ix:hidden>` DEI block inside the main 10-K HTML body both carry company identity data. The SGML header is faster to parse (no HTML parsing required). The DEI block is richer (ticker, exchange, shares, filer category) and provides a more reliable EIN.

**F3 — EIN is unreliable in the SGML header.**  
`ein` was present in only 3/20 (15%) SGML headers, but `dei:EntityTaxIdentificationNumber` was present in 20/20 (100%) DEI blocks. Always prefer the DEI source for EIN.

**F4 — 3 DEI tag(s) are not universally present.**  
`TradingSymbol` (19/20), `Security12bTitle` (19/20), `SecurityExchangeName` (19/20). These are absent for companies without a Section 12(b) registration (e.g. exchange-listed security). Always guard with `.get()`.

**F5 — SGML header fields with <100% presence:** `ein` (3/20), `state_of_incorporation` (19/20).

**F6 — File size variance is large.**  
Mean=33.8 MB, stdev=27.8 MB (outlier threshold: mean+1σ = 61.6 MB). Files above threshold: `AEP_10K_2022` (102.8 MB), `C_10K_2021` (87.5 MB), `DHR_10K_2022` (92.5 MB). Large files drive slower parse times in `sec-parser`.

**F7 — R*.htm sheet count is the primary driver of file size.**  
Sheets range from 61 to 197 per filing (mean 114). More sheets = more XBRL financial disclosures. This grows over time as reporting standards require more granular segment breakouts.

**F8 — MetaLinks.json and FilingSummary.xml are present in every file.**  
Both were found in 20/20 and 20/20 files respectively. MetaLinks.json is the authoritative XBRL element dictionary (FASB definitions, calculation trees, presentation hierarchy). FilingSummary.xml maps every R*.htm sheet to its human-readable name and `MenuCategory` (Statements/Notes/Details/etc.).

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

*Report generated by `scripts/eda/sec_html_structure_explorer.py`*
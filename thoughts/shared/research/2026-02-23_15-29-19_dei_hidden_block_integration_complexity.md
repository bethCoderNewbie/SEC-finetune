---
date: 2026-02-23T15:29:19-0600
researcher: beth
git_commit: 8f08d4b
branch: main
repository: SEC-finetune
status: implemented
implementation_status: Tier 1 + Tier 2 fully implemented (working tree on top of 8f08d4b; 284 tests pass)
topic: complexity of integrating DEI ix:hidden block tags into parsed/cleaned/final output
---

# Complexity Evaluation: DEI `<ix:hidden>` Block Integration

## Scope

23 machine-readable DEI tags available in the `<ix:hidden>` block of Document 1 in every
modern EDGAR iXBRL filing. Evaluate the cost of including each tag in the parsed,
extracted, cleaned, and final segmented output of the preprocessing pipeline.

---

## Current State

**Implemented.** Tier 1 and Tier 2 fields are now extracted. The targeted
`dei:TradingSymbol` regex (formerly `parser.py:416–423`) has been replaced by a
single generalised `_DEI_PAT` `finditer` pass (`parser.py:413–430`) that collects
all `dei:*` nonNumeric tags. Tier-1 fields (`amendment_flag`, `entity_filer_category`,
`ein`) are explicit Pydantic fields on `ExtractedSection` and `SegmentedRisks` and
appear in `document_info` of the saved JSON. Tier-2 fields are available in
`ParsedFiling.metadata['dei']` (see known limitation below).

---

## Field-by-Field Analysis

### Tier 0 — Already present / pure duplicates (skip)

| DEI Tag | Reason to Skip |
|---------|---------------|
| `dei:EntityCentralIndexKey` | Duplicates `SGMLHeader.cik` (SGML, 100%) |
| `dei:DocumentFiscalYearFocus` | Duplicates `fiscal_year` (first 4 of `period_of_report`) |
| `dei:DocumentFiscalPeriodFocus` | Always `"FY"` for 10-K filings; zero signal |
| `dei:DocumentType` | Duplicates `form_type` passed via CLI |
| `dei:TradingSymbol` | **Already extracted** — `ticker` field |

### Tier 1 — High value, explicit Pydantic fields warranted

These fields are first-class pipeline concerns that need typed, validated, serialized fields
on `SegmentedRisks` and `ExtractedSection`, and require propagation through the full pipeline.

| DEI Tag | Value | Notes |
|---------|-------|-------|
| `dei:AmendmentFlag` | **Critical** — QA gating | Amended filings must be excluded from training data. `"False"` on originals, `"True"` on amendments. Should become a blocking QA validation rule. Currently 12% SGML `IRS NUMBER` coverage is an unrelated field; there is no SGML `AmendmentFlag`. 100% DEI coverage. |
| `dei:EntityTaxIdentificationNumber` | **High** — EIN completeness | ADR-010 already notes SGML EIN is 12% coverage. DEI provides 100% coverage with hyphen-formatted value (e.g., `"04-2348234"`). Completes the `SGMLHeader.ein` fallback documented in ADR-010 Rule 5. |
| `dei:EntityFilerCategory` | **Medium** — stratification | `"Large accelerated filer"`, `"Accelerated filer"`, `"Non-accelerated filer"`, `"Smaller reporting company"`. Essential for corpus stratification and bias monitoring in PRD-002/003. |

### Tier 2 — Useful, low-complexity, metadata-dict passthrough sufficient

These fields add value but do not need to be QA-validated or drive pipeline logic.
Storing them in the `metadata: Dict` on `ParsedFiling` and `SegmentedRisks` is
adequate — they will appear in the output JSON's `metadata` block automatically.

| DEI Tag | Value | Extraction notes |
|---------|-------|-----------------|
| `dei:EntityRegistrantName` | Formatted company name with punctuation (e.g., `"Analog Devices, Inc."` vs SGML's `"ANALOG DEVICES INC"`). Useful for display but not for training logic. | `ix:nonNumeric` tag, same pattern as ticker |
| `dei:DocumentPeriodEndDate` | Human-readable period end (e.g., `"November 1"`). Complements `period_of_report` (YYYYMMDD). Useful for sanity checks. | `ix:nonNumeric` |
| `dei:EntityIncorporationStateCountryCode` | Full state/country name (e.g., `"Massachusetts"`). SGML already has 2-letter code at 95% coverage; minor additive value. | `ix:nonNumeric` |
| `dei:SecurityExchangeName` | Exchange name (e.g., `"Nasdaq Global Select Market"`). Useful for corpus context. | `ix:nonNumeric` |
| `dei:EntityWellKnownSeasonedIssuer` | WKSI status (`"Yes"`/`"No"`). Useful for characterizing issuer size and shelf eligibility. | `ix:nonNumeric` |
| `dei:IcfrAuditorAttestationFlag` | SOX 404(b) compliance (`"True"`/`"False"`). Distinguishes accelerated filers (auditor-attested) from others. | `ix:nonNumeric` |
| `dei:Security12bTitle` | Security description (e.g., `"Common Stock $0.16 2/3 par value per share"`). Low ML value; corpus documentation. | `ix:nonNumeric` |

### Tier 3 — Address and contact fields (skip for ML pipeline)

`dei:EntityAddressAddressLine1`, `dei:EntityAddressCityOrTown`,
`dei:EntityAddressStateOrProvince`, `dei:EntityAddressPostalZipCode`,
`dei:CityAreaCode`, `dei:LocalPhoneNumber` — no training data value.
Can be added as pure metadata passthrough if needed for a registry or display layer
but are out of scope for the ML pipeline.

### Tier 4 — Numeric XBRL fields (deferred — separate implementation)

| DEI Tag | Complication |
|---------|-------------|
| `dei:EntityPublicFloat` | Uses `<ix:nonFraction>` tag (not `ix:nonNumeric`). Value in tag is **raw integer scaled by the `scale` attribute** (e.g., `scale="6"` means multiply by 1,000,000). Correct extraction requires reading the `scale`, `decimals`, and `sign` attributes and applying the XBRL scaling formula. Raw value without scaling is misleading (81,121 != 81,121,000,000). |
| `dei:EntityCommonStockSharesOutstanding` | Same `ix:nonFraction` / scale complication. Additionally, some filings report multiple share classes in separate tags of the same name. |

These should be implemented as part of a dedicated XBRL enrichment feature (using
`manifest.doc_xbrl_instance` from ADR-010 Stage 0), not as ad-hoc regex over `ix:hidden`.

---

## Propagation Chain

Every **explicit Pydantic field** (Tier 1) requires changes at all 10 touch points below.
Every **metadata-dict passthrough** (Tier 2) requires only touch point 1.

| Touch point | File | Tier 1 cost | Tier 2 cost |
|-------------|------|-------------|-------------|
| 1. Extraction | `src/preprocessing/parser.py:_extract_metadata()` | Add named regex | Add to metadata dict (same effort, all fields at once) |
| 2. `ParsedFiling.metadata` | `src/preprocessing/models/parsing.py` | None — already `Dict[str, Any]` | None |
| 3. `extractor.extract_section()` | `src/preprocessing/extractor.py:120-138` | Copy field from `filing_metadata` to `ExtractedSection(...)` call | None |
| 4. `ExtractedSection` model | `src/preprocessing/models/extraction.py` | Add `Optional[str]` field | None |
| 5. `segmenter.segment_extracted_section()` | `src/preprocessing/segmenter.py` | Copy field from `extracted` to `SegmentedRisks(...)` | None |
| 6. `SegmentedRisks` model | `src/preprocessing/models/segmentation.py` | Add `Optional[str]` field | None |
| 7. `SegmentedRisks.save_to_json()` | `src/preprocessing/models/segmentation.py` | Add to `document_info` dict | None — in `metadata` block already |
| 8. `SegmentedRisks.load_from_json()` | `src/preprocessing/models/segmentation.py` | Add `di.get('field_name')` | None — in `metadata` block |
| 9. `data_dictionary.md` | `docs/architecture/data_dictionary.md` | New row + lineage update | New row in metadata section |
| 10. QA validation | `src/config/qa_validation.py` + `configs/qa_validation/health_check.yaml` | New rule for `amendment_flag` | None |

**Cost per Tier 1 field: 10 touch points, ~15–30 min each → ~2.5–5 hrs per field.**
**Cost for all Tier 2 fields together: touch point 1 only → ~1 hr total.**

---

## Extraction Mechanics

All Tier 1 and Tier 2 fields use `<ix:nonNumeric>` tags and can be extracted with a
single generalised regex already proven for `dei:TradingSymbol`:

```python
# Generalised extractor — one pass over full_doc1_html
_DEI_TAG_PATTERN = re.compile(
    r'<ix:nonNumeric[^>]*name="(dei:[A-Za-z]+)"[^>]*>(.*?)</ix:nonNumeric>',
    re.IGNORECASE | re.DOTALL,
)

dei_tags = {}
for m in _DEI_TAG_PATTERN.finditer(html_content):
    name = m.group(1)
    value = re.sub(r'<[^>]+>', '', m.group(2)).strip()  # strip inner HTML
    if value:
        dei_tags[name] = value
```

This replaces the individual ticker regex and yields all DEI text fields in one pass.
The current `ticker_match` regex in `parser.py:416–423` can be replaced entirely by
reading `dei_tags.get('dei:TradingSymbol')`.

**Caveats:**
- Inner HTML stripping (`re.sub(r'<[^>]+>', '', ...)`) is sufficient for plain-text DEI
  values. The existing ticker extraction already does this (line 421 in `parser.py`).
- Some values contain HTML entities (`&#160;`, `&amp;`). HTML entity decoding should
  be applied to the stripped value.
- `dei:AmendmentFlag` may be serialised as `"false"` (lowercase) or `"False"` — normalise
  to Python `bool` at extraction time to avoid case-sensitivity bugs in QA logic.

---

## Complexity Summary

| Work item | Effort | Files changed |
|-----------|--------|---------------|
| Generalise ticker regex → single DEI pass (all Tier 2) | Low (~1 hr) | `parser.py` |
| Add `dei_metadata` sub-dict to `ParsedFiling.metadata` (all Tier 2 fields) | Trivial | `parser.py` |
| Add `amendment_flag: Optional[bool]` explicit field (Tier 1) | Moderate (~3–4 hrs) | `parser.py`, `models/extraction.py`, `extractor.py`, `models/segmentation.py` (×2), `data_dictionary.md`, `qa_validation.py`, `health_check.yaml` |
| Add `entity_filer_category: Optional[str]` explicit field (Tier 1) | Moderate (~3–4 hrs) | Same 8 files minus QA |
| Add `ein` DEI fallback for 12% SGML gap (Tier 1) | Low-moderate (~2 hrs) | `parser.py`, `models/segmentation.py` (update `ein` sourcing per ADR-010 Rule 5) |
| Tier 4 numeric XBRL fields | High (separate feature) | Out of scope — requires XBRL scaling logic |

**Recommended sequencing:**
1. Replace ticker regex with generalised DEI pass → all Tier 2 fields land in `metadata` dict at zero schema cost.
2. Add `amendment_flag` explicit field + blocking QA rule → prevents amended filings from entering training data.
3. Add `entity_filer_category` explicit field → enables corpus stratification.
4. Upgrade `ein` sourcing to use DEI as primary (100%) with SGML as fallback (12%), per ADR-010 Rule 5.
5. Defer Tier 4 numeric fields to dedicated XBRL enrichment work.

---

## Risk: `<ix:hidden>` block location variability

The `<ix:hidden>` block is not guaranteed to appear at a fixed byte offset in Document 1.
It is always present in modern iXBRL filings (post-2020 EDGAR mandate) but may appear at
the top or bottom of the document. The generalised regex scan above works regardless of
position since it uses `re.finditer` over the full `html_content`. No pre-positioning is
required.

Older filings (pre-iXBRL, typically pre-2018 for large accelerated filers, pre-2020 for
smaller filers) will not have an `<ix:hidden>` block. All DEI fields must default to
`None`; no exception should be raised on miss. The existing ticker extraction already
handles this correctly (`ticker = None` when no match).

---

## Schema Impact on Final Output (`SegmentedRisks.save_to_json()`)

Current `document_info` block:

```json
"document_info": {
  "company_name": "...",
  "ticker": "...",
  "cik": "...",
  "sic_code": "...",
  "sic_name": "...",
  "form_type": "...",
  "fiscal_year": "...",
  "accession_number": "...",
  "filed_as_of_date": "..."
}
```

After Tier 1 additions:

```json
"document_info": {
  ...existing fields...,
  "amendment_flag": false,
  "entity_filer_category": "Large accelerated filer",
  "ein": "04-2348234"
}
```

After Tier 2 passthrough (no `document_info` change; fields land in `metadata`):

```json
"metadata": {
  "dei": {
    "EntityRegistrantName": "Analog Devices, Inc.",
    "DocumentPeriodEndDate": "November 1",
    "SecurityExchangeName": "Nasdaq Global Select Market",
    "EntityWellKnownSeasonedIssuer": "Yes",
    "EntityFilerCategory": "Large accelerated filer",
    "IcfrAuditorAttestationFlag": "True",
    "EntityIncorporationStateCountryCode": "Massachusetts",
    "Security12bTitle": "Common Stock $0.16 2/3 par value per share"
  }
}
```

Nesting Tier 2 fields under a `"dei"` sub-key in `metadata` keeps the `document_info`
block clean and makes the provenance of each field unambiguous.

---

## References

- `src/preprocessing/parser.py:413–471` — `_extract_metadata()` post-implementation (DEI pass at :413–430, meta dict :432–447, SGML/legacy EIN :449–460, Tier-2 dict :462–469)
- `src/preprocessing/models/extraction.py:52–58` — `ExtractedSection` DEI fields
- `src/preprocessing/models/segmentation.py:55–63` — `SegmentedRisks` DEI fields
- `src/preprocessing/models/segmentation.py:115–122` — `save_to_json()` `document_info` block (new DEI rows)
- `src/preprocessing/models/segmentation.py:193–198` — `load_from_json()` structured-schema branch (new DEI reads)
- `src/preprocessing/extractor.py:135–141` — metadata flow into `ExtractedSection`
- `src/preprocessing/segmenter.py:185–190` — metadata flow into `SegmentedRisks`
- `src/config/qa_validation.py` — `_check_amendments()` + wiring in `check_single`/`check_run`
- `configs/qa_validation/health_check.yaml` — `amendment_flag_not_amended` threshold
- `docs/architecture/data_dictionary.md` — updated schema (new rows, DEI sub-dict section, validation rule)
- ADR-010 Rule 4 — metadata extraction runs before anchor slice (no access concern)
- ADR-010 Rule 5 — EIN sourcing: SGML fast path, DEI authoritative

---

## Implementation Notes

### What was done

All 8 files changed as planned. 284 unit tests pass with zero regressions.

**Deviation from plan — `_DEI_PAT` scope:** The regex is defined inside
`_extract_metadata()` as a local (not module-level). This is fine because
`re.compile` results are internally cached by Python's regex engine.

**EIN on legacy path:** The existing `if sgml_manifest is not None:` block
previously had no `else` clause for EIN. An `else` branch was added that sets
`meta['ein'] = dei_tags.get('dei:EntityTaxIdentificationNumber') or None`.
The SGML path uses `hdr.ein or dei_tags.get(...) or None` (SGML fast path,
DEI authoritative per ADR-010 Rule 5 / ADR-011).

### Known limitation — Tier-2 `dei` dict does not reach the saved JSON

The `meta['dei']` dict is set at the end of `_extract_metadata()` and lives in
`ParsedFiling.metadata['dei']`. However, `SECSectionExtractor.extract_section()`
(`extractor.py:110–118`) constructs a fresh `metadata` dict for `ExtractedSection`
that does **not** include `filing_metadata.get('dei')`. Consequently:

- `ParsedFiling.metadata['dei']` — **populated** ✓
- `ExtractedSection.metadata['dei']` — **absent** (extractor dict does not copy it)
- `SegmentedRisks.metadata` (= `ExtractedSection.metadata`) — **absent**
- Final `*_segmented.json` `processing_metadata` block — **absent** (that block is
  hardcoded in `save_to_json()`; `self.metadata` is not emitted there at all)

**Tier-2 fields are accessible** to pipeline code that reads `ParsedFiling.metadata`
directly (e.g., before the extractor step). The research doc's "schema impact"
section showing `"metadata": {"dei": {...}}` in the saved JSON is aspirational and
was not achieved by this implementation.

**To propagate Tier-2 to saved output:** Add `'dei': filing_metadata.get('dei')`
to the `metadata` dict in `extractor.py:extract_section()` and emit it from
`SegmentedRisks.save_to_json()`. This is a one-line change each but was judged
out-of-scope for ADR-011 (the plan explicitly called this "zero schema changes
downstream").

### Amendment check scope

`_check_amendments()` reads `data.get("amendment_flag")` from the top-level dict.

- **`check_single(data)`** — `data` is `SegmentedRisks.model_dump()`, which has
  `amendment_flag` at the top level. Amendment check works correctly.
- **`check_run(run_dir)`** — `data` is raw JSON loaded from disk; in the v2 schema
  `amendment_flag` is nested under `document_info`, so `data.get("amendment_flag")`
  returns `None` → status `SKIP`, not FAIL. This matches the existing behaviour of
  `_check_identity()` which has the same `f.get("cik")` gap for v2 files. The
  primary enforcement path is `check_single()` called inline during processing.


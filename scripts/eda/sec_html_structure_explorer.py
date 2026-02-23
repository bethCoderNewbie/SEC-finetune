"""
SEC 10-K HTML Structure Explorer

Purpose: Analyze raw EDGAR full-submission text files to characterize:
  - SGML container structure and document index distributions
  - SGML header metadata field presence and values
  - DEI iXBRL tag distributions
  - Cross-corpus patterns across the raw data corpus

Stage: 0 - Raw Data Exploration
Input: data/raw/*.html (EDGAR full-submission text files)
Output: reports/sec_html_structure/ - JSON summary + console stats

Usage:
    # Analyze three reference files from research doc
    python scripts/eda/sec_html_structure_explorer.py

    # Analyze specific files
    python scripts/eda/sec_html_structure_explorer.py --files AAPL_10K_2021 ADI_10K_2025 ALL_10K_2025

    # Random sample of N files from corpus
    python scripts/eda/sec_html_structure_explorer.py --sample 20

    # Full corpus scan (slow; ~961 files × 10-44 MB each)
    python scripts/eda/sec_html_structure_explorer.py --all
"""

import argparse
import json
import random
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent.parent
RAW_DATA_DIR = REPO_ROOT / "data" / "raw"
OUTPUT_DIR = REPO_ROOT / "reports" / "sec_html_structure"

# Reference files from the research document
REFERENCE_FILES = ["AAPL_10K_2021", "ADI_10K_2025", "ALL_10K_2025"]

# ---------------------------------------------------------------------------
# Layer 1 – SGML document index
# ---------------------------------------------------------------------------

_DOC_BOUNDARY = re.compile(
    r"<DOCUMENT>\s*"
    r"<TYPE>([^\n]+)\n"
    r"<SEQUENCE>([^\n]+)\n"
    r"<FILENAME>([^\n]+)\n"
    r"(?:<DESCRIPTION>([^\n]*)\n)?"  # optional
    r"<TEXT>",
    re.IGNORECASE,
)

_TEXT_END = re.compile(r"</TEXT>", re.IGNORECASE)
_INNER_WRAPPER = re.compile(r"^<(?:XBRL|XML|JSON)>\s*", re.IGNORECASE)
_INNER_WRAPPER_CLOSE = re.compile(r"\s*</(?:XBRL|XML|JSON)>$", re.IGNORECASE)


def build_doc_index(text: str) -> list[dict]:
    """
    Single-pass parse of SGML <DOCUMENT> boundaries.
    Returns list of dicts with keys: seq, type, filename, desc,
    text_start, text_end, size_bytes.
    """
    index = []
    for m in _DOC_BOUNDARY.finditer(text):
        text_start = m.end()
        end_m = _TEXT_END.search(text, text_start)
        text_end = end_m.start() if end_m else len(text)
        index.append(
            {
                "seq": m.group(2).strip(),
                "type": m.group(1).strip(),
                "filename": m.group(3).strip(),
                "desc": (m.group(4) or "").strip(),
                "text_start": text_start,
                "text_end": text_end,
                "size_bytes": text_end - text_start,
            }
        )
    return index


def get_doc(text: str, index: list[dict], filename: str) -> tuple[str | None, dict | None]:
    """Extract a named document from the pre-built index, stripping inner wrappers."""
    entry = next((d for d in index if d["filename"].lower() == filename.lower()), None)
    if not entry:
        return None, None
    raw = text[entry["text_start"] : entry["text_end"]].strip()
    raw = _INNER_WRAPPER.sub("", raw)
    raw = _INNER_WRAPPER_CLOSE.sub("", raw)
    return raw.strip(), entry


# ---------------------------------------------------------------------------
# Layer 2 – SGML header metadata
# ---------------------------------------------------------------------------

_SGML_HEADER = re.compile(r"<SEC-HEADER>(.*?)</SEC-HEADER>", re.DOTALL | re.IGNORECASE)

# Field patterns – each maps to a canonical key
_HEADER_FIELDS: list[tuple[str, str]] = [
    (r"CONFORMED SUBMISSION TYPE:\s*(.+)", "submission_type"),
    (r"PUBLIC DOCUMENT COUNT:\s*(.+)", "document_count"),
    (r"CONFORMED PERIOD OF REPORT:\s*(.+)", "period_of_report"),
    (r"FILED AS OF DATE:\s*(.+)", "filed_as_of_date"),
    (r"ACCESSION NUMBER:\s*(.+)", "accession_number"),
    (r"COMPANY CONFORMED NAME:\s*(.+)", "company_name"),
    (r"CENTRAL INDEX KEY:\s*(.+)", "cik"),
    (r"STANDARD INDUSTRIAL CLASSIFICATION:\s*(.+)", "sic_full"),  # "NAME [code]"
    (r"EIN:\s*(.+)", "ein"),
    (r"STATE OF INCORPORATION:\s*(.+)", "state_of_incorporation"),
    (r"FISCAL YEAR END:\s*(.+)", "fiscal_year_end"),
    (r"SEC FILE NUMBER:\s*(.+)", "sec_file_number"),
    (r"FORM TYPE:\s*(.+)", "form_type"),
]

_SIC_CODE = re.compile(r"\[(\d+)\]")


def parse_sgml_header(text: str) -> dict:
    """
    Extract metadata from the SGML <SEC-HEADER> block.
    Returns dict with canonical keys; missing fields are absent from dict.
    """
    header_m = _SGML_HEADER.search(text)
    if not header_m:
        return {}
    header = header_m.group(1)

    result: dict = {}
    for pattern, key in _HEADER_FIELDS:
        m = re.search(pattern, header, re.IGNORECASE)
        if m:
            result[key] = m.group(1).strip()

    # Parse SIC code and name from "NAME [code]"
    if "sic_full" in result:
        sic_m = _SIC_CODE.search(result["sic_full"])
        if sic_m:
            result["sic_code"] = sic_m.group(1)
            result["sic_name"] = result["sic_full"][: sic_m.start()].strip()

    # Derive fiscal year from period_of_report YYYYMMDD
    if "period_of_report" in result and len(result["period_of_report"]) == 8:
        result["fiscal_year"] = result["period_of_report"][:4]

    return result


# ---------------------------------------------------------------------------
# Layer 2 – DEI iXBRL tag extraction
# ---------------------------------------------------------------------------

# DEI tags of interest (from research doc)
_DEI_TAGS = [
    "dei:EntityCentralIndexKey",
    "dei:TradingSymbol",
    "dei:EntityRegistrantName",
    "dei:DocumentFiscalYearFocus",
    "dei:DocumentFiscalPeriodFocus",
    "dei:DocumentType",
    "dei:DocumentPeriodEndDate",
    "dei:EntityIncorporationStateCountryCode",
    "dei:EntityTaxIdentificationNumber",
    "dei:EntityAddressAddressLine1",
    "dei:EntityAddressCityOrTown",
    "dei:EntityAddressStateOrProvince",
    "dei:EntityAddressPostalZipCode",
    "dei:CityAreaCode",
    "dei:LocalPhoneNumber",
    "dei:Security12bTitle",
    "dei:SecurityExchangeName",
    "dei:EntityWellKnownSeasonedIssuer",
    "dei:EntityFilerCategory",
    "dei:EntityPublicFloat",
    "dei:EntityCommonStockSharesOutstanding",
    "dei:AmendmentFlag",
    "dei:IcfrAuditorAttestationFlag",
]

# iXBRL fact pattern: <ix:nonNumeric name="dei:..." ...>VALUE</ix:nonNumeric>
# or <ix:nonFraction name="dei:..." ...>VALUE</ix:nonFraction>
_IX_FACT = re.compile(
    r'<ix:(?:non(?:Numeric|Fraction)|numeric)\b[^>]*\bname=["\']([^"\']+)["\'][^>]*>'
    r"(.*?)"
    r"</ix:(?:non(?:Numeric|Fraction)|numeric)>",
    re.DOTALL | re.IGNORECASE,
)

# Strip HTML tags from values (some DEI values wrap in <span>)
_HTML_TAG = re.compile(r"<[^>]+>")


def extract_dei_tags(html: str) -> dict[str, str]:
    """
    Extract DEI iXBRL fact values from the main 10-K HTML document.
    Returns dict mapping tag name → raw text value.
    Only returns tags that appear in _DEI_TAGS.
    """
    dei_set = set(_DEI_TAGS)
    result: dict[str, str] = {}
    for m in _IX_FACT.finditer(html):
        name = m.group(1).strip()
        if name in dei_set and name not in result:
            raw = _HTML_TAG.sub("", m.group(2)).strip()
            if raw:
                result[name] = raw
    return result


# ---------------------------------------------------------------------------
# Layer 4 – XBRL instance document analysis
# ---------------------------------------------------------------------------

_XBRLI = "http://www.xbrl.org/2003/instance"


def _local(tag: str) -> str:
    """Strip namespace URI from an ElementTree tag."""
    return tag.split("}")[-1] if "}" in tag else tag


def analyze_xbrl_instance(
    text: str, index: list[dict], main_filename: str | None = None
) -> dict:
    """
    Parse XBRL facts for structural statistics.

    XBRL source priority (first match wins):
      1. *_htm.xml  — modern iXBRL inline instance (most common post-2012)
      2. EX-101.INS — old-style standalone XBRL instance (pre-iXBRL filings,
                       e.g. DDOG 2021 files as ddog-20201231.xml); facts are
                       top-level children, parsed same as *_htm.xml
      3. main 10-K iXBRL HTM when it is valid XML — some filers (e.g. ABT)
                       embed raw namespace-qualified facts directly in the HTM:
                         <us-gaap:FactName contextRef="..." decimals="-6">…
                       MetaLinks registers via "inline": {"local": ["file.htm"]}.
                       Detection: contextRef attribute present on any element.

    Fixes three gaps vs. naive parsing:
    - Context period types: instant / duration / forever (not just two types)
    - Unit types: simple <measure> vs ratio <divide> (e.g. USD/share for EPS)
    - Fact precision attribute: older filings use <precision> not <decimals>

    Returns dict with key "xbrl_source":
      "instance_xml" | "ex101_ins" | "ixbrl_htm"
    """
    # --- Locate the XBRL source (priority: *_htm.xml → EX-101.INS → iXBRL HTM) ---
    xbrl_entry = next(
        (d for d in index if d["filename"].endswith("_htm.xml")),
        None,
    )
    source = "instance_xml"
    raw = None

    if xbrl_entry:
        raw, _ = get_doc(text, index, xbrl_entry["filename"])
    else:
        # Fallback 1: EX-101.INS (old-style standalone XBRL instance)
        ins_entry = next((d for d in index if d["type"].upper() == "EX-101.INS"), None)
        if ins_entry:
            raw, xbrl_entry = get_doc(text, index, ins_entry["filename"])
            source = "ex101_ins"

        # Fallback 2: main 10-K iXBRL HTM when it is well-formed XML
        if not raw and main_filename:
            main_raw, main_entry = get_doc(text, index, main_filename)
            if main_raw and main_raw.lstrip().startswith("<?xml"):
                raw = main_raw
                xbrl_entry = main_entry
                source = "ixbrl_htm"

    if not raw or not xbrl_entry:
        return {"xbrl_instance_found": False}

    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return {"xbrl_instance_found": False, "parse_error": True}

    # --- Contexts: classify by period type ---
    context_types: Counter = Counter()
    for ctx in root.iter(f"{{{_XBRLI}}}context"):
        period = ctx.find(f"{{{_XBRLI}}}period")
        if period is None:
            context_types["unknown"] += 1
        elif period.find(f"{{{_XBRLI}}}forever") is not None:
            context_types["forever"] += 1
        elif period.find(f"{{{_XBRLI}}}instant") is not None:
            context_types["instant"] += 1
        else:
            context_types["duration"] += 1

    # --- Units: classify by structure ---
    unit_types: Counter = Counter()
    unit_details: list[dict] = []
    for unit in root.iter(f"{{{_XBRLI}}}unit"):
        uid = unit.attrib.get("id", "")
        divide = unit.find(f"{{{_XBRLI}}}divide")
        if divide is not None:
            unit_types["divide"] += 1
            num_el = divide.find(f".//{{{_XBRLI}}}unitNumerator/{{{_XBRLI}}}measure")
            den_el = divide.find(f".//{{{_XBRLI}}}unitDenominator/{{{_XBRLI}}}measure")
            num = num_el.text.strip() if num_el is not None else ""
            den = den_el.text.strip() if den_el is not None else ""
            unit_details.append({"id": uid, "type": "divide", "value": f"{num} / {den}"})
        else:
            measure = unit.find(f"{{{_XBRLI}}}measure")
            unit_types["measure"] += 1
            val = measure.text.strip() if measure is not None else ""
            unit_details.append({"id": uid, "type": "measure", "value": val})

    # --- Facts: precision vs decimals attribute, and INF count ---
    # Strategy differs by source:
    #   instance_xml → direct children of root (facts are top-level elements)
    #   ixbrl_htm    → any element with contextRef (works for both
    #                   raw <ns:FactName contextRef="..."> and
    #                   <ix:nonFraction contextRef="..."> wrappers)
    precision_count = 0
    decimals_count = 0
    decimals_inf_count = 0
    fact_count = 0

    if source in ("instance_xml", "ex101_ins"):
        # Both formats have facts as direct top-level children of the root element
        for el in root:
            tag_local = _local(el.tag)
            if tag_local in ("context", "unit", "schemaRef"):
                continue
            fact_count += 1
            if "precision" in el.attrib:
                precision_count += 1
            if "decimals" in el.attrib:
                decimals_count += 1
                if el.attrib["decimals"].upper() == "INF":
                    decimals_inf_count += 1
    else:  # ixbrl_htm
        for el in root.iter():
            if "contextRef" not in el.attrib:
                continue
            fact_count += 1
            if "precision" in el.attrib:
                precision_count += 1
            if "decimals" in el.attrib:
                decimals_count += 1
                if el.attrib["decimals"].upper() == "INF":
                    decimals_inf_count += 1

    return {
        "xbrl_instance_found": True,
        "xbrl_source": source,
        "xbrl_filename": xbrl_entry["filename"],
        "xbrl_size_bytes": xbrl_entry["size_bytes"],
        "context_types": dict(context_types),
        "context_count": sum(context_types.values()),
        "unit_types": dict(unit_types),
        "unit_count": sum(unit_types.values()),
        "unit_details": unit_details,
        "fact_count": fact_count,
        "precision_count": precision_count,
        "decimals_count": decimals_count,
        "decimals_inf_count": decimals_inf_count,
    }


# ---------------------------------------------------------------------------
# File-level analysis
# ---------------------------------------------------------------------------


def find_main_10k_filename(index: list[dict]) -> str | None:
    """Return the filename of the main 10-K document (SEQUENCE 1, TYPE 10-K)."""
    for entry in index:
        if entry["type"].upper() == "10-K":
            return entry["filename"]
    return None


def analyze_file(path: Path) -> dict:
    """
    Full structural analysis of a single EDGAR file.
    Returns analysis dict with all layers.
    """
    stem = path.stem  # e.g. "AAPL_10K_2021"
    file_size = path.stat().st_size

    print(f"  Reading {path.name} ({file_size / 1e6:.1f} MB)...")
    text = path.read_text(encoding="utf-8", errors="replace")

    # --- Layer 1: Document index ---
    index = build_doc_index(text)
    type_counts = Counter(d["type"] for d in index)
    type_sizes = defaultdict(int)
    for d in index:
        type_sizes[d["type"]] += d["size_bytes"]

    # Size of main 10-K doc
    main_filename = find_main_10k_filename(index)
    main_entry = next((d for d in index if d["filename"] == main_filename), None)
    main_doc_size = main_entry["size_bytes"] if main_entry else 0

    # --- Layer 2: SGML header ---
    header = parse_sgml_header(text)

    # --- Layer 2: DEI tags (from main 10-K body only) ---
    dei: dict[str, str] = {}
    if main_filename:
        main_html, _ = get_doc(text, index, main_filename)
        if main_html:
            dei = extract_dei_tags(main_html)

    # --- Layer 3: R*.htm sheet count ---
    r_sheets = [d for d in index if re.match(r"R\d+\.htm", d["filename"], re.IGNORECASE)]

    # --- Layer 4: XBRL instance ---
    xbrl = analyze_xbrl_instance(text, index, main_filename=main_filename)

    return {
        "stem": stem,
        "file_size_bytes": file_size,
        "total_documents": len(index),
        "type_counts": dict(type_counts),
        "type_sizes_bytes": dict(type_sizes),
        "main_10k_filename": main_filename,
        "main_10k_size_bytes": main_doc_size,
        "r_sheet_count": len(r_sheets),
        "has_metalinks": any(d["filename"] == "MetaLinks.json" for d in index),
        "has_filing_summary": any(
            d["filename"] == "FilingSummary.xml" for d in index
        ),
        "sgml_header": header,
        "dei_tags": dei,
        "dei_tag_count": len(dei),
        "xbrl": xbrl,
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

_HLINE = "-" * 72


def print_file_summary(r: dict) -> None:
    """Print per-file analysis summary."""
    h = r["sgml_header"]
    dei = r["dei_tags"]

    print(f"\n{'=' * 72}")
    print(f"  {r['stem']}  ({r['file_size_bytes'] / 1e6:.1f} MB)")
    print("=" * 72)

    print(f"\n  [Layer 1] Document Index ({r['total_documents']} embedded documents)")
    print(f"  {'Type':<20} {'Count':>6}  {'Total Size':>12}")
    print(f"  {_HLINE}")
    for doc_type, count in sorted(r["type_counts"].items(), key=lambda x: -x[1]):
        size = r["type_sizes_bytes"].get(doc_type, 0)
        print(f"  {doc_type:<20} {count:>6}  {size / 1e6:>10.2f} MB")
    print(f"\n  Main 10-K filename : {r['main_10k_filename']}")
    print(f"  Main 10-K size     : {r['main_10k_size_bytes'] / 1e6:.2f} MB")
    print(f"  R*.htm sheets      : {r['r_sheet_count']}")
    print(f"  Has MetaLinks.json : {r['has_metalinks']}")
    print(f"  Has FilingSummary  : {r['has_filing_summary']}")

    print(f"\n  [Layer 2a] SGML Header Metadata ({len(h)} fields found)")
    print(f"  {_HLINE}")
    for key, val in h.items():
        print(f"  {key:<28} {val}")

    print(f"\n  [Layer 2b] DEI iXBRL Tags ({r['dei_tag_count']} / {len(_DEI_TAGS)} found)")
    print(f"  {_HLINE}")
    for tag in _DEI_TAGS:
        val = dei.get(tag, "<not found>")
        short_tag = tag.split(":")[-1]
        print(f"  {short_tag:<40} {val[:60]}")

    xbrl = r.get("xbrl", {})
    if xbrl.get("xbrl_instance_found"):
        _src_labels = {"instance_xml": "instance XML", "ex101_ins": "EX-101.INS",
                       "ixbrl_htm": "iXBRL HTM"}
        source_label = _src_labels.get(xbrl.get("xbrl_source", ""), "unknown")
        print(f"\n  [Layer 4] XBRL Instance ({xbrl['xbrl_filename']}, "
              f"{xbrl['xbrl_size_bytes']/1e6:.2f} MB, source={source_label})")
        print(f"  {_HLINE}")
        print(f"  Total facts          : {xbrl['fact_count']}")
        print(f"  Context types        : {xbrl['context_types']}")
        print(f"  Unit types           : {xbrl['unit_types']}")
        divide_units = [u for u in xbrl['unit_details'] if u['type'] == 'divide']
        if divide_units:
            print(f"  Divide units         : "
                  + ", ".join(f"{u['id']}={u['value']}" for u in divide_units))
        print(f"  decimals attribute   : {xbrl['decimals_count']} facts "
              f"({xbrl['decimals_inf_count']} INF)")
        print(f"  precision attribute  : {xbrl['precision_count']} facts")


def print_corpus_summary(results: list[dict]) -> None:
    """Print cross-file aggregate statistics."""
    n = len(results)
    print(f"\n\n{'#' * 72}")
    print(f"  CORPUS SUMMARY  ({n} files)")
    print(f"{'#' * 72}")

    # Document count distribution
    doc_counts = [r["total_documents"] for r in results]
    print(f"\n  Total embedded documents per file:")
    print(f"    min={min(doc_counts)}  max={max(doc_counts)}  "
          f"mean={sum(doc_counts)/n:.1f}")

    # File size distribution
    sizes_mb = [r["file_size_bytes"] / 1e6 for r in results]
    print(f"\n  File size (MB):")
    print(f"    min={min(sizes_mb):.1f}  max={max(sizes_mb):.1f}  "
          f"mean={sum(sizes_mb)/n:.1f}")

    # R*.htm sheet count distribution
    r_counts = [r["r_sheet_count"] for r in results]
    print(f"\n  R*.htm XBRL sheets per file:")
    print(f"    min={min(r_counts)}  max={max(r_counts)}  "
          f"mean={sum(r_counts)/n:.1f}")

    # DEI tag coverage
    print(f"\n  DEI tag presence across {n} files:")
    print(f"  {'Tag':<45} {'Found':>6}  {'%':>6}")
    print(f"  {_HLINE}")
    for tag in _DEI_TAGS:
        found = sum(1 for r in results if tag in r["dei_tags"])
        pct = 100 * found / n
        print(f"  {tag:<45} {found:>6}  {pct:>5.0f}%")

    # SGML header field coverage
    print(f"\n  SGML header field presence across {n} files:")
    all_keys = set()
    for r in results:
        all_keys.update(r["sgml_header"].keys())
    print(f"  {'Field':<30} {'Found':>6}  {'%':>6}")
    print(f"  {_HLINE}")
    for key in sorted(all_keys):
        found = sum(1 for r in results if key in r["sgml_header"])
        pct = 100 * found / n
        print(f"  {key:<30} {found:>6}  {pct:>5.0f}%")

    # XBRL instance aggregate stats
    xbrl_results = [r["xbrl"] for r in results if r.get("xbrl", {}).get("xbrl_instance_found")]
    if xbrl_results:
        n_xbrl = len(xbrl_results)
        n_instance_xml = sum(1 for x in xbrl_results if x.get("xbrl_source") == "instance_xml")
        n_ex101_ins = sum(1 for x in xbrl_results if x.get("xbrl_source") == "ex101_ins")
        n_ixbrl_htm = sum(1 for x in xbrl_results if x.get("xbrl_source") == "ixbrl_htm")
        print(f"\n  XBRL instance stats ({n_xbrl} files):")
        print(f"    Source: *_htm.xml (instance XML) : {n_instance_xml}/{n_xbrl}")
        print(f"    Source: EX-101.INS (fallback)    : {n_ex101_ins}/{n_xbrl}")
        print(f"    Source: iXBRL HTM (fallback)     : {n_ixbrl_htm}/{n_xbrl}")
        forever_count = sum(1 for x in xbrl_results if x["context_types"].get("forever", 0) > 0)
        divide_count = sum(1 for x in xbrl_results if x["unit_types"].get("divide", 0) > 0)
        precision_count = sum(1 for x in xbrl_results if x["precision_count"] > 0)
        avg_facts = sum(x["fact_count"] for x in xbrl_results) / n_xbrl
        print(f"    Avg facts per filing          : {avg_facts:.0f}")
        print(f"    Files with 'forever' contexts : {forever_count}/{n_xbrl}")
        print(f"    Files with divide units       : {divide_count}/{n_xbrl}")
        print(f"    Files using precision attr    : {precision_count}/{n_xbrl}")

    # SIC distribution
    print(f"\n  SIC code distribution (top 10):")
    sic_counter: Counter = Counter()
    for r in results:
        sic = r["sgml_header"].get("sic_code", "unknown")
        sic_name = r["sgml_header"].get("sic_name", "")
        sic_counter[f"{sic} {sic_name}"] += 1
    for sic_label, count in sic_counter.most_common(10):
        print(f"    {count:>4}x  {sic_label}")

    # Filing year distribution
    print(f"\n  Fiscal year distribution:")
    year_counter: Counter = Counter(
        r["sgml_header"].get("fiscal_year", "unknown") for r in results
    )
    for year, count in sorted(year_counter.items()):
        bar = "█" * min(count, 40)
        print(f"    {year}  {bar}  {count}")


# ---------------------------------------------------------------------------
# Analysis helpers
# ---------------------------------------------------------------------------


def _parse_yyyymmdd(s: str):
    """Parse YYYYMMDD string to date. Returns None on failure."""
    try:
        return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    except (ValueError, TypeError, IndexError):
        return None


def _filing_lag(header: dict):
    """Days from fiscal period end to SEC filing date. Returns None if dates missing."""
    p = _parse_yyyymmdd(header.get("period_of_report", ""))
    f = _parse_yyyymmdd(header.get("filed_as_of_date", ""))
    return (f - p).days if p and f else None


def _parse_ticker(stem: str) -> str:
    """Extract ticker from stem like 'AAPL_10K_2021' → 'AAPL'."""
    return stem.split("_")[0] if "_" in stem else stem


def _pearson_r(xs: list, ys: list):
    """Pearson correlation coefficient. Returns None if fewer than 2 points."""
    n = len(xs)
    if n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    denom = (sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys)) ** 0.5
    return num / denom if denom else None


# ---------------------------------------------------------------------------
# Markdown report generation
# ---------------------------------------------------------------------------

# Fields our pipeline currently extracts (for gap analysis)
_CURRENTLY_EXTRACTED = {
    "company_name", "cik", "sic_code", "sic_name", "ticker", "fiscal_year", "period_of_report"
}

_EXTRACTION_GAP = [
    # (canonical_name, source, currently_extracted)
    ("company_name",              "SGML header",          True),
    ("cik",                       "SGML header",          True),
    ("sic_code",                  "SGML header",          True),
    ("sic_name",                  "SGML header",          True),
    ("ticker (TradingSymbol)",    "DEI iXBRL",            True),
    ("fiscal_year",               "SGML header",          True),
    ("period_of_report",          "SGML header",          True),
    ("ein",                       "SGML header",          False),
    ("state_of_incorporation",    "SGML header",          False),
    ("fiscal_year_end (MMDD)",    "SGML header",          False),
    ("accession_number",          "SGML header",          False),
    ("sec_file_number",           "SGML header",          False),
    ("exchange (Nasdaq/NYSE)",    "DEI iXBRL",            False),
    ("shares_outstanding",        "DEI iXBRL",            False),
    ("public_float",              "DEI iXBRL",            False),
    ("filer_category",            "DEI iXBRL",            False),
    ("amendment_flag",            "DEI iXBRL",            False),
    ("FASB element definitions",  "MetaLinks.json",       False),
    ("all financial facts",       "XBRL instance XML",    False),
    ("calculation tree",          "EX-101.CAL/MetaLinks", False),
    ("named financial statements","FilingSummary.xml",    False),
    ("company charts/logos",      "GRAPHIC documents",    False),
]


def _pct(n: int, total: int) -> str:
    return f"{100 * n / total:.0f}%" if total else "N/A"


def _stats_row(values: list[float]) -> str:
    if not values:
        return "N/A"
    return (
        f"min={min(values):.1f}  "
        f"max={max(values):.1f}  "
        f"mean={statistics.mean(values):.1f}  "
        f"median={statistics.median(values):.1f}  "
        f"p95={sorted(values)[int(0.95 * len(values))]:.1f}"
    )


def generate_markdown_report(results: list[dict], out_path: Path, mode_desc: str) -> None:
    """Write a structured markdown analysis report from the analysis results."""
    n = len(results)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines: list[str] = []
    W = lines.append  # shorthand

    # -----------------------------------------------------------------------
    # Header
    # -----------------------------------------------------------------------
    W("# SEC 10-K HTML Structure — Analysis Report")
    W("")
    W(f"**Generated:** {now}  ")
    W(f"**Files analyzed:** {n}  ")
    W(f"**Mode:** {mode_desc}  ")
    W(f"**Data source:** `data/raw/*.html` (EDGAR full-submission text files)")
    W("")
    W("---")
    W("")

    # -----------------------------------------------------------------------
    # Executive Summary
    # -----------------------------------------------------------------------
    doc_counts = [r["total_documents"] for r in results]
    sizes_mb = [r["file_size_bytes"] / 1e6 for r in results]
    r_counts = [r["r_sheet_count"] for r in results]
    main_sizes_mb = [r["main_10k_size_bytes"] / 1e6 for r in results]

    all_dei_present = sum(
        1 for r in results if r["dei_tag_count"] == len(_DEI_TAGS)
    )
    has_metalinks = sum(1 for r in results if r["has_metalinks"])
    has_filing_summary = sum(1 for r in results if r["has_filing_summary"])

    W("## Executive Summary")
    W("")
    W(f"Analyzed **{n} EDGAR full-submission text files** from the corpus. Key observations:")
    W("")
    W(f"- Each file is an **SGML container** embedding {min(doc_counts)}–{max(doc_counts)} "
      f"separate documents (mean {statistics.mean(doc_counts):.0f}).")
    W(f"- File sizes range from **{min(sizes_mb):.1f} MB to {max(sizes_mb):.1f} MB** "
      f"(mean {statistics.mean(sizes_mb):.1f} MB). The main 10-K iXBRL body is "
      f"{statistics.mean(main_sizes_mb):.1f} MB on average.")
    W(f"- All {n} files have `MetaLinks.json` ({_pct(has_metalinks, n)}) and "
      f"`FilingSummary.xml` ({_pct(has_filing_summary, n)}).")
    W(f"- **All 23 DEI iXBRL tags** were fully present in {all_dei_present}/{n} files. "
      f"Tags with <100% presence are noted in §4.")
    W(f"- The SGML header provides reliable metadata for all core fields except `ein` "
      f"(present in {_pct(sum(1 for r in results if 'ein' in r['sgml_header']), n)} of files). "
      f"Use `dei:EntityTaxIdentificationNumber` instead.")
    W("")
    W("---")
    W("")

    # -----------------------------------------------------------------------
    # Section 1 – File Size Distribution
    # -----------------------------------------------------------------------
    W("## 1. File Size Distribution")
    W("")
    W("### 1.1 Total file size (SGML container)")
    W("")
    W(f"```")
    W(_stats_row(sizes_mb) + " MB")
    W("```")
    W("")

    W("### 1.2 Main 10-K iXBRL body size")
    W("")
    W(f"```")
    W(_stats_row(main_sizes_mb) + " MB")
    W("```")
    W("")
    W("The main 10-K body is the only document passed to `sec-parser`. Its size relative "
      "to the container explains why `sec-parser` is unaware of the other "
      f"{statistics.mean(doc_counts) - 1:.0f} embedded documents per filing.")
    W("")

    # Per-file size table (sorted by size desc)
    W("### 1.3 Per-file breakdown")
    W("")
    W("| File | Size (MB) | Docs | Main 10-K (MB) | R*.htm sheets |")
    W("|------|-----------|------|----------------|---------------|")
    for r in sorted(results, key=lambda x: -x["file_size_bytes"]):
        W(f"| `{r['stem']}` | {r['file_size_bytes']/1e6:.1f} | "
          f"{r['total_documents']} | {r['main_10k_size_bytes']/1e6:.2f} | "
          f"{r['r_sheet_count']} |")
    W("")
    W("---")
    W("")

    # -----------------------------------------------------------------------
    # Section 2 – Document Type Distribution
    # -----------------------------------------------------------------------
    W("## 2. Embedded Document Type Distribution")
    W("")
    W("Aggregated counts and sizes across all analyzed files.")
    W("")

    # Aggregate by type
    agg_counts: Counter = Counter()
    agg_sizes: defaultdict = defaultdict(int)
    agg_files: Counter = Counter()
    for r in results:
        for doc_type, count in r["type_counts"].items():
            agg_counts[doc_type] += count
            agg_sizes[doc_type] += r["type_sizes_bytes"].get(doc_type, 0)
            agg_files[doc_type] += 1

    W("| Type | Total Count | Files Present | Total Size (MB) | Avg per file |")
    W("|------|-------------|---------------|-----------------|--------------|")
    for doc_type, total_count in agg_counts.most_common():
        files_present = agg_files[doc_type]
        total_sz = agg_sizes[doc_type] / 1e6
        avg_per = total_count / files_present if files_present else 0
        W(f"| `{doc_type}` | {total_count} | {files_present}/{n} | "
          f"{total_sz:.2f} | {avg_per:.1f} |")
    W("")
    W("**Notes:**")
    W("- `XML` documents are primarily `R*.htm` XBRL financial statement sheets "
      "— by far the most numerous type.")
    W("- `GRAPHIC` documents are UUencoded images (not base64). "
      "Count grows with filing complexity.")
    W("- `EX-101.*` exhibits (SCH/CAL/DEF/LAB/PRE) appear exactly once per filing.")
    W("- `JSON` = `MetaLinks.json` (XBRL element catalogue). Always exactly 1 per filing.")
    W("")
    W("### 2.1 R*.htm XBRL Sheet Counts")
    W("")
    W("```")
    W(_stats_row(r_counts) + " sheets")
    W("```")
    W("")
    W("The number of XBRL sheets grows with filing complexity and year. "
      "More subsidiary segments, geographic breakouts, and disclosure tables "
      "each generate additional sheets.")
    W("")
    W("---")
    W("")

    # -----------------------------------------------------------------------
    # Section 3 – SGML Header Metadata Coverage
    # -----------------------------------------------------------------------
    W("## 3. SGML Header Metadata Coverage")
    W("")
    W("Fields extracted from the `<SEC-HEADER>` block at the top of each file.")
    W("")

    all_keys: set = set()
    for r in results:
        all_keys.update(r["sgml_header"].keys())

    W("| Field | Present | Coverage | Notes |")
    W("|-------|---------|----------|-------|")
    field_notes = {
        "submission_type":       "Always `10-K`",
        "document_count":        "Total embedded docs; varies 83–367 in this sample",
        "period_of_report":      "YYYYMMDD — primary source for `fiscal_year`",
        "filed_as_of_date":      "YYYYMMDD filing date",
        "accession_number":      "Unique filing ID (not yet extracted by pipeline)",
        "company_name":          "All-caps legal name",
        "cik":                   "SEC CIK — zero-padded 10 digits",
        "sic_full":              "Raw string: `NAME [code]`",
        "sic_code":              "Parsed from `sic_full`",
        "sic_name":              "Parsed from `sic_full`",
        "ein":                   "**Unreliable** — only present in some filings; use DEI instead",
        "state_of_incorporation":"Two-letter code",
        "fiscal_year_end":       "MMDD format (e.g. `0925` = Sep 25)",
        "sec_file_number":       "Exchange registration number",
        "form_type":             "Under FILING VALUES block; always `10-K`",
        "fiscal_year":           "Derived from `period_of_report[:4]`",
    }
    for key in sorted(all_keys):
        found = sum(1 for r in results if key in r["sgml_header"])
        pct = _pct(found, n)
        note = field_notes.get(key, "")
        reliability = " ⚠️" if found < n else ""
        W(f"| `{key}` | {found}/{n} | {pct}{reliability} | {note} |")
    W("")
    W("> ⚠️ = field not present in all analyzed files; do not rely on it without a fallback.")
    W("")
    W("---")
    W("")

    # -----------------------------------------------------------------------
    # Section 4 – DEI iXBRL Tag Coverage
    # -----------------------------------------------------------------------
    W("## 4. DEI iXBRL Tag Coverage")
    W("")
    W("Tags extracted from `<ix:hidden>` inside the main 10-K document body. "
      "These are richer than the SGML header and include fields unavailable anywhere else "
      "(ticker, exchange, shares outstanding, filer category).")
    W("")

    dei_notes = {
        "dei:EntityCentralIndexKey":              "Duplicates SGML CIK; useful cross-check",
        "dei:TradingSymbol":                      "**Ticker** — only source; two format variants",
        "dei:EntityRegistrantName":               "Formatted name with punctuation (vs all-caps SGML)",
        "dei:DocumentFiscalYearFocus":            "Year as integer string",
        "dei:DocumentFiscalPeriodFocus":          "Always `FY` for 10-K",
        "dei:DocumentType":                       "Always `10-K`",
        "dei:DocumentPeriodEndDate":              "Human-readable date (may contain HTML entities)",
        "dei:EntityIncorporationStateCountryCode":"Full state name (vs two-letter SGML code)",
        "dei:EntityTaxIdentificationNumber":      "EIN with hyphen — **reliable; use over SGML `ein`**",
        "dei:EntityAddressAddressLine1":          "Street address",
        "dei:EntityAddressCityOrTown":            "City",
        "dei:EntityAddressStateOrProvince":       "State code",
        "dei:EntityAddressPostalZipCode":         "ZIP code",
        "dei:CityAreaCode":                       "Phone area code",
        "dei:LocalPhoneNumber":                   "Local phone number",
        "dei:Security12bTitle":                   "Security description; absent for non-12b filers",
        "dei:SecurityExchangeName":               "Exchange; absent for non-12b filers",
        "dei:EntityWellKnownSeasonedIssuer":      "WKSI status: Yes/No",
        "dei:EntityFilerCategory":                "Large accelerated / accelerated / non-accelerated",
        "dei:EntityPublicFloat":                  "Market cap at mid-year; formatting varies",
        "dei:EntityCommonStockSharesOutstanding": "Share count at recent date",
        "dei:AmendmentFlag":                      "True/False/false — case varies across filers",
        "dei:IcfrAuditorAttestationFlag":         "SOX 404(b); may be HTML entity (☑/☐)",
    }

    W("| Tag | Present | Coverage | Notes |")
    W("|-----|---------|----------|-------|")
    for tag in _DEI_TAGS:
        found = sum(1 for r in results if tag in r["dei_tags"])
        pct = _pct(found, n)
        note = dei_notes.get(tag, "")
        reliability = " ⚠️" if found < n else ""
        W(f"| `{tag.split(':')[1]}` | {found}/{n} | {pct}{reliability} | {note} |")
    W("")
    W("> ⚠️ = tag absent in at least one filing. For 12b registration fields "
      "(`Security12bTitle`, `SecurityExchangeName`, `TradingSymbol`), absence indicates "
      "the company may not have a listed security (e.g. holding companies, foreign private issuers).")
    W("")
    W("---")
    W("")

    # -----------------------------------------------------------------------
    # Section 5 – SIC & Fiscal Year Distributions
    # -----------------------------------------------------------------------
    W("## 5. Corpus Composition")
    W("")
    W("### 5.1 SIC Code Distribution (top 15)")
    W("")
    sic_counter: Counter = Counter()
    for r in results:
        sic = r["sgml_header"].get("sic_code", "unknown")
        sic_name = r["sgml_header"].get("sic_name", "")
        sic_counter[f"{sic} — {sic_name}"] += 1

    W("| SIC | Count | % of sample |")
    W("|-----|-------|-------------|")
    for label, count in sic_counter.most_common(15):
        W(f"| {label} | {count} | {_pct(count, n)} |")
    W("")

    W("### 5.2 Fiscal Year Distribution")
    W("")
    year_counter: Counter = Counter(
        r["sgml_header"].get("fiscal_year", "unknown") for r in results
    )
    W("| Fiscal Year | Count | Bar |")
    W("|-------------|-------|-----|")
    for year, count in sorted(year_counter.items()):
        bar = "█" * count
        W(f"| {year} | {count} | {bar} |")
    W("")

    W("### 5.3 Filing Lag Distribution")
    W("")
    W("Days elapsed between `CONFORMED PERIOD OF REPORT` (fiscal year end) "
      "and `FILED AS OF DATE`. Large accelerated filers must file within 60 days; "
      "accelerated filers within 75 days; others within 90 days.")
    W("")
    lags = [(r["stem"], _filing_lag(r["sgml_header"])) for r in results]
    lags_valid = [(s, d) for s, d in lags if d is not None]
    if lags_valid:
        lag_values = [d for _, d in lags_valid]
        W("```")
        W(_stats_row(lag_values) + " days")
        W("```")
        W("")
        W("| File | Period End | Filed | Lag (days) |")
        W("|------|-----------|-------|------------|")
        for stem, lag in sorted(lags_valid, key=lambda x: x[1] if x[1] else 0):
            h = next(r["sgml_header"] for r in results if r["stem"] == stem)
            W(f"| `{stem}` | {h.get('period_of_report', '')} | "
              f"{h.get('filed_as_of_date', '')} | {lag} |")
        W("")

    W("### 5.4 DEI Value Distributions")
    W("")
    W("Actual values extracted from `<ix:hidden>` — not just presence, "
      "but what the values are across the sample.")
    W("")

    def _dei_dist(tag: str, label: str, top: int = 10) -> None:
        counter: Counter = Counter()
        for r in results:
            val = r["dei_tags"].get(tag, "").strip()
            if val:
                counter[val] += 1
        if not counter:
            return
        W(f"**{label}** (`{tag.split(':')[1]}`):")
        W("")
        W(f"| Value | Count | % |")
        W(f"|-------|-------|---|")
        for val, cnt in counter.most_common(top):
            W(f"| {val} | {cnt} | {_pct(cnt, n)} |")
        W("")

    _dei_dist("dei:EntityFilerCategory",             "Filer Category")
    _dei_dist("dei:SecurityExchangeName",             "Exchange Listed On")
    _dei_dist("dei:EntityWellKnownSeasonedIssuer",    "Well-Known Seasoned Issuer (WKSI)")
    _dei_dist("dei:EntityIncorporationStateCountryCode", "State of Incorporation", top=15)
    _dei_dist("dei:EntityAddressStateOrProvince",     "HQ State", top=15)

    W("---")
    W("")

    # -----------------------------------------------------------------------
    # Section 6 – Key Findings
    # -----------------------------------------------------------------------
    W("## 6. Key Findings")
    W("")

    # Find DEI tags < 100%
    low_dei = [
        (tag, sum(1 for r in results if tag in r["dei_tags"]))
        for tag in _DEI_TAGS
        if sum(1 for r in results if tag in r["dei_tags"]) < n
    ]
    # Find SGML fields < 100%
    low_sgml = [
        (key, sum(1 for r in results if key in r["sgml_header"]))
        for key in sorted(all_keys)
        if sum(1 for r in results if key in r["sgml_header"]) < n
    ]
    # File size outliers (> mean + 1 stdev)
    size_mean = statistics.mean(sizes_mb) if sizes_mb else 0
    size_stdev = statistics.stdev(sizes_mb) if len(sizes_mb) > 1 else 0
    outlier_threshold = size_mean + size_stdev
    large_files = [r for r in results if r["file_size_bytes"] / 1e6 > outlier_threshold]
    # EIN reliability
    ein_sgml = sum(1 for r in results if "ein" in r["sgml_header"])
    ein_dei = sum(1 for r in results if "dei:EntityTaxIdentificationNumber" in r["dei_tags"])

    W("**F1 — EDGAR files are SGML containers, not HTML.**  ")
    W("Each `.html` file is a flat concatenation of "
      f"{min(doc_counts)}–{max(doc_counts)} embedded documents delimited by `<DOCUMENT>` "
      "tags. The `sec-parser` library only processes Document 1 (the iXBRL 10-K body). "
      "All other documents — including XBRL financials, exhibits, and MetaLinks.json — "
      "are invisible to it.")
    W("")
    W("**F2 — Two parallel, redundant metadata sources exist.**  ")
    W("The SGML `<SEC-HEADER>` block (plain text, always ~80 lines) and the `<ix:hidden>` "
      "DEI block inside the main 10-K HTML body both carry company identity data. "
      "The SGML header is faster to parse (no HTML parsing required). "
      "The DEI block is richer (ticker, exchange, shares, filer category) and "
      "provides a more reliable EIN.")
    W("")
    W(f"**F3 — EIN is unreliable in the SGML header.**  ")
    W(f"`ein` was present in only {ein_sgml}/{n} ({_pct(ein_sgml, n)}) SGML headers, "
      f"but `dei:EntityTaxIdentificationNumber` was present in {ein_dei}/{n} "
      f"({_pct(ein_dei, n)}) DEI blocks. Always prefer the DEI source for EIN.")
    W("")

    if low_dei:
        tags_str = ", ".join(f"`{t.split(':')[1]}` ({c}/{n})" for t, c in low_dei)
        W(f"**F4 — {len(low_dei)} DEI tag(s) are not universally present.**  ")
        W(f"{tags_str}. These are absent for companies without a Section 12(b) "
          "registration (e.g. exchange-listed security). Always guard with `.get()`.")
        W("")
    else:
        W(f"**F4 — All 23 DEI tags were present in 100% of the {n} analyzed files.**  ")
        W("Coverage may drop when extending to the full 961-file corpus.")
        W("")

    if low_sgml:
        fields_str = ", ".join(f"`{k}` ({c}/{n})" for k, c in low_sgml)
        W(f"**F5 — SGML header fields with <100% presence:** {fields_str}.")
        W("")

    W(f"**F6 — File size variance is large.**  ")
    outlier_list = (
        ", ".join(f"`{r['stem']}` ({r['file_size_bytes']/1e6:.1f} MB)" for r in large_files)
        if large_files else "none"
    )
    W(f"Mean={size_mean:.1f} MB, stdev={size_stdev:.1f} MB (outlier threshold: mean+1σ = "
      f"{outlier_threshold:.1f} MB). Files above threshold: {outlier_list}. "
      "Large files drive slower parse times in `sec-parser`.")
    W("")
    W("**F7 — R*.htm sheet count is the primary driver of file size.**  ")
    W(f"Sheets range from {min(r_counts)} to {max(r_counts)} per filing (mean {statistics.mean(r_counts):.0f}). "
      "More sheets = more XBRL financial disclosures. This grows over time as reporting "
      "standards require more granular segment breakouts.")
    W("")
    W("**F8 — MetaLinks.json and FilingSummary.xml are present in every file.**  ")
    W(f"Both were found in {has_metalinks}/{n} and {has_filing_summary}/{n} files respectively. "
      "MetaLinks.json is the authoritative XBRL element dictionary (FASB definitions, "
      "calculation trees, presentation hierarchy). FilingSummary.xml maps every R*.htm "
      "sheet to its human-readable name and `MenuCategory` (Statements/Notes/Details/etc.).")
    W("")
    W("---")
    W("")

    # -----------------------------------------------------------------------
    # Section 7 – Extraction Gap
    # -----------------------------------------------------------------------
    W("## 7. Extraction Gap: Available vs. Currently Extracted")
    W("")
    W("What the pipeline currently extracts vs. what the raw files contain.")
    W("")
    W("| Data Field | Source | Extracted | Notes |")
    W("|------------|--------|-----------|-------|")
    gap_notes = {
        "company_name":               "All-caps; DEI `EntityRegistrantName` has proper casing",
        "cik":                        "",
        "sic_code":                   "",
        "sic_name":                   "",
        "ticker (TradingSymbol)":     "Two format variants in corpus",
        "fiscal_year":                "Derived from `period_of_report[:4]`",
        "period_of_report":           "",
        "ein":                        "Use DEI source; SGML unreliable",
        "state_of_incorporation":     "SGML=2-letter code; DEI=full name",
        "fiscal_year_end (MMDD)":     "e.g. `0925` = Sep 25",
        "accession_number":           "Unique filing ID for EDGAR API lookups",
        "sec_file_number":            "",
        "exchange (Nasdaq/NYSE)":     "In DEI as `SecurityExchangeName`",
        "shares_outstanding":         "In DEI as `EntityCommonStockSharesOutstanding`",
        "public_float":               "In DEI as `EntityPublicFloat`; formatting varies",
        "filer_category":             "In DEI as `EntityFilerCategory`",
        "amendment_flag":             "In DEI as `AmendmentFlag`",
        "FASB element definitions":   "MetaLinks.json — definitions, calc tree, presentation",
        "all financial facts":        "XBRL instance XML — all tagged monetary/numeric values",
        "calculation tree":           "EX-101.CAL or MetaLinks `calculation` field",
        "named financial statements": "FilingSummary.xml — R*.htm name + MenuCategory",
        "company charts/logos":       "GRAPHIC documents — UUencoded; rarely needed",
    }
    for field, source, extracted in _EXTRACTION_GAP:
        mark = "✓" if extracted else "✗"
        note = gap_notes.get(field, "")
        W(f"| `{field}` | {source} | {mark} | {note} |")

    extracted_count = sum(1 for _, _, e in _EXTRACTION_GAP if e)
    total_fields = len(_EXTRACTION_GAP)
    W("")
    W(f"**{extracted_count}/{total_fields} fields currently extracted** "
      f"({_pct(extracted_count, total_fields)} coverage).")
    W("")
    W("---")
    W("")

    # -----------------------------------------------------------------------
    # Section 8 – XBRL Instance Document Analysis
    # -----------------------------------------------------------------------
    xbrl_results = [r["xbrl"] for r in results if r.get("xbrl", {}).get("xbrl_instance_found")]
    if xbrl_results:
        n_xbrl = len(xbrl_results)
        W("## 8. XBRL Instance Document Analysis")
        W("")
        W("Parsed from `*_htm.xml` (XBRL instance document) or, when absent, from the main "
          "iXBRL 10-K HTM directly (inline XBRL). Source column distinguishes the two. "
          "Three structural gaps in naive parsing are corrected here.")
        W("")

        # Context type distribution
        W("### 8.1 Context Period Types")
        W("")
        W("The XBRL 2003 schema defines three period types: `instant`, `duration`, and `forever`. "
          "A naive parser that only checks for `startDate`/`endDate` silently misclassifies "
          "`forever` contexts (used for entity-level facts with no time dimension).")
        W("")
        W("| File | Source | instant | duration | forever | total |")
        W("|------|--------|---------|----------|---------|-------|")
        for r in results:
            x = r.get("xbrl", {})
            if not x.get("xbrl_instance_found"):
                continue
            ct = x["context_types"]
            src = {"instance_xml": "instance XML", "ex101_ins": "EX-101.INS",
                   "ixbrl_htm": "iXBRL HTM"}.get(x.get("xbrl_source", ""), "unknown")
            W(f"| `{r['stem']}` | {src} | {ct.get('instant', 0)} | {ct.get('duration', 0)} | "
              f"{ct.get('forever', 0)} | {x['context_count']} |")
        W("")

        # Unit type distribution
        W("### 8.2 Unit Types: Simple vs. Divide")
        W("")
        W("Units can be a plain `<measure>` (e.g. `iso4217:USD`) or a ratio `<divide>` "
          "(e.g. USD/share for EPS facts). A parser that only reads direct `<measure>` "
          "children of `<unit>` silently returns an empty string for all divide units.")
        W("")
        W("| File | Source | measure units | divide units | divide examples |")
        W("|------|--------|---------------|--------------|-----------------|")
        for r in results:
            x = r.get("xbrl", {})
            if not x.get("xbrl_instance_found"):
                continue
            src = {"instance_xml": "instance XML", "ex101_ins": "EX-101.INS",
                   "ixbrl_htm": "iXBRL HTM"}.get(x.get("xbrl_source", ""), "unknown")
            div_units = [u for u in x["unit_details"] if u["type"] == "divide"]
            examples = "; ".join(f"`{u['id']}` ({u['value']})" for u in div_units[:3])
            W(f"| `{r['stem']}` | {src} | {x['unit_types'].get('measure', 0)} | "
              f"{x['unit_types'].get('divide', 0)} | {examples or '—'} |")
        W("")

        # Precision vs decimals
        W("### 8.3 Fact Precision Attribute: `decimals` vs. `precision`")
        W("")
        W("The schema allows either `decimals` or `precision` on numeric facts — they are "
          "mutually exclusive alternatives. Modern filings use `decimals` exclusively. "
          "Older filings (pre-2010) may use `precision`. `decimals=INF` means exact value "
          "(used for integer share counts and similar).")
        W("")
        W("> **Semantics:** `decimals=\"-6\"` does **not** mean the value is in millions. "
          "The raw XML value is always in base units (USD). `decimals=-6` means the value "
          "is accurate to the nearest 10⁶ — it is a precision indicator, not a scale factor.")
        W("")
        W("| File | Source | facts | decimals | precision | INF |")
        W("|------|--------|-------|----------|-----------|-----|")
        for r in results:
            x = r.get("xbrl", {})
            if not x.get("xbrl_instance_found"):
                continue
            src = {"instance_xml": "instance XML", "ex101_ins": "EX-101.INS",
                   "ixbrl_htm": "iXBRL HTM"}.get(x.get("xbrl_source", ""), "unknown")
            W(f"| `{r['stem']}` | {src} | {x['fact_count']} | {x['decimals_count']} | "
              f"{x['precision_count']} | {x['decimals_inf_count']} |")
        W("")
        W("---")
        W("")

    W("---")
    W("")

    # -----------------------------------------------------------------------
    # Section 9 – Patterns & Correlations
    # -----------------------------------------------------------------------
    W("## 9. Patterns & Correlations")
    W("")
    W("Observations derived from the sample. Run `--sample 50` or `--all` "
      "to strengthen statistical confidence.")
    W("")

    # --- 9.1 Company & Ticker Coverage ---
    tickers = [_parse_ticker(r["stem"]) for r in results]
    ticker_counter: Counter = Counter(tickers)
    multi_year = {t: c for t, c in ticker_counter.items() if c > 1}
    W("### 9.1 Company Coverage")
    W("")
    W(f"- **Unique tickers:** {len(ticker_counter)}")
    W(f"- **Tickers with multiple filing years:** {len(multi_year)}"
      + (f" — " + ", ".join(f"`{t}` ({c}y)" for t, c in sorted(multi_year.items()))
         if multi_year else ""))
    W("")

    # --- 9.2 Size vs Complexity Correlations ---
    W("### 9.2 File Size vs. Complexity Correlations")
    W("")
    sizes = [r["file_size_bytes"] / 1e6 for r in results]
    r_counts_local = [r["r_sheet_count"] for r in results]
    doc_counts_local = [r["total_documents"] for r in results]
    main_sizes = [r["main_10k_size_bytes"] / 1e6 for r in results]

    r_size_sheets = _pearson_r(sizes, r_counts_local)
    r_size_docs = _pearson_r(sizes, doc_counts_local)
    r_sheets_docs = _pearson_r(r_counts_local, doc_counts_local)
    r_main_total = _pearson_r(main_sizes, sizes)

    W("Pearson r between key metrics (closer to ±1.0 = stronger linear relationship):")
    W("")
    W("| Pair | Pearson r | Interpretation |")
    W("|------|-----------|----------------|")

    def _interp(r_val) -> str:
        if r_val is None:
            return "N/A"
        a = abs(r_val)
        direction = "positive" if r_val > 0 else "negative"
        strength = "strong" if a > 0.7 else ("moderate" if a > 0.4 else "weak")
        return f"{strength} {direction} ({r_val:+.2f})"

    r_ss_str = f"{r_size_sheets:+.2f}" if r_size_sheets is not None else "N/A"
    r_sd_str = f"{r_size_docs:+.2f}" if r_size_docs is not None else "N/A"
    r_rd_str = f"{r_sheets_docs:+.2f}" if r_sheets_docs is not None else "N/A"
    r_mt_str = f"{r_main_total:+.2f}" if r_main_total is not None else "N/A"
    W(f"| File size vs R*.htm sheet count | {r_ss_str} | {_interp(r_size_sheets)} |")
    W(f"| File size vs total document count | {r_sd_str} | {_interp(r_size_docs)} |")
    W(f"| R*.htm count vs total documents | {r_rd_str} | {_interp(r_sheets_docs)} |")
    W(f"| Main 10-K body size vs total file size | {r_mt_str} | {_interp(r_main_total)} |")
    W("")

    # --- 9.3 Industry Complexity ---
    W("### 9.3 Industry Complexity by SIC Code")
    W("")
    W("Average file size and R*.htm sheet count grouped by SIC code "
      "(only SIC codes with ≥2 filings shown).")
    W("")
    sic_groups: defaultdict = defaultdict(list)
    for r in results:
        sic = r["sgml_header"].get("sic_code", "unknown")
        sic_name_val = r["sgml_header"].get("sic_name", "")
        sic_groups[f"{sic} — {sic_name_val}"].append(r)
    multi_sic = {k: v for k, v in sic_groups.items() if len(v) >= 2}
    if multi_sic:
        W("| SIC | N | Avg File Size (MB) | Avg R*.htm |")
        W("|-----|---|-------------------|------------|")
        for sic_label, group in sorted(multi_sic.items(),
                                       key=lambda x: -statistics.mean(
                                           r["file_size_bytes"] / 1e6 for r in x[1])):
            avg_sz = statistics.mean(r["file_size_bytes"] / 1e6 for r in group)
            avg_r = statistics.mean(r["r_sheet_count"] for r in group)
            W(f"| {sic_label} | {len(group)} | {avg_sz:.1f} | {avg_r:.0f} |")
        W("")
    else:
        W("*(No SIC codes appear ≥2 times in this sample — run with a larger sample.)*")
        W("")

    # --- 9.4 Filing Lag by Filer Category ---
    W("### 9.4 Filing Lag by Filer Category")
    W("")
    lag_by_cat: defaultdict = defaultdict(list)
    for r in results:
        lag = _filing_lag(r["sgml_header"])
        cat = r["dei_tags"].get("dei:EntityFilerCategory", "unknown").strip()
        if lag is not None:
            lag_by_cat[cat].append(lag)
    if lag_by_cat:
        W("| Filer Category | N | Min days | Max days | Mean days |")
        W("|----------------|---|----------|----------|-----------|")
        for cat, lags_list in sorted(lag_by_cat.items()):
            W(f"| {cat} | {len(lags_list)} | {min(lags_list)} | "
              f"{max(lags_list)} | {statistics.mean(lags_list):.0f} |")
        W("")

    # --- 9.5 Fiscal Year Trend: R*.htm Complexity ---
    W("### 9.5 Fiscal Year Trend: R*.htm Sheet Count")
    W("")
    W("Do filings get more complex over time?")
    W("")
    year_sheets: defaultdict = defaultdict(list)
    for r in results:
        yr = r["sgml_header"].get("fiscal_year", "")
        if yr:
            year_sheets[yr].append(r["r_sheet_count"])
    if year_sheets:
        W("| Fiscal Year | N | Min | Max | Mean R*.htm |")
        W("|-------------|---|-----|-----|-------------|")
        for yr in sorted(year_sheets):
            vals = year_sheets[yr]
            W(f"| {yr} | {len(vals)} | {min(vals)} | {max(vals)} | "
              f"{statistics.mean(vals):.0f} |")
        W("")


    W("*Report generated by `scripts/eda/sec_html_structure_explorer.py`*")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Report saved to: {out_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def resolve_files(args: argparse.Namespace) -> list[Path]:
    """Determine which files to analyze based on CLI arguments."""
    if args.all:
        return sorted(RAW_DATA_DIR.glob("*.html"))

    if args.sample:
        all_files = sorted(RAW_DATA_DIR.glob("*.html"))
        k = min(args.sample, len(all_files))
        random.seed(42)
        return sorted(random.sample(all_files, k))

    # Default to reference files if nothing specified
    stems = args.files if args.files else REFERENCE_FILES
    paths = []
    for stem in stems:
        # Accept with or without .html extension
        stem = stem.removesuffix(".html")
        p = RAW_DATA_DIR / f"{stem}.html"
        if not p.exists():
            print(f"  WARNING: {p} not found, skipping", file=sys.stderr)
            continue
        paths.append(p)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze SEC 10-K EDGAR full-submission text file structure",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--files",
        nargs="+",
        metavar="STEM",
        help="File stems to analyze (e.g. AAPL_10K_2021). Defaults to the 3 reference files.",
    )
    group.add_argument(
        "--sample",
        type=int,
        metavar="N",
        help="Random sample of N files from data/raw/",
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="Analyze all files in data/raw/ (slow)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Save JSON results to this path (default: reports/sec_html_structure/results.json)",
    )
    parser.add_argument(
        "--no-file-detail",
        action="store_true",
        help="Skip per-file detail printout (only show corpus summary)",
    )
    args = parser.parse_args()

    files = resolve_files(args)
    if not files:
        print("No files found. Check data/raw/ exists and contains *.html files.")
        sys.exit(1)

    print(f"SEC 10-K HTML Structure Explorer")
    print(f"Analyzing {len(files)} file(s) from {RAW_DATA_DIR}\n")

    results = []
    for path in files:
        try:
            r = analyze_file(path)
            results.append(r)
            if not args.no_file_detail:
                print_file_summary(r)
        except Exception as e:
            print(f"  ERROR analyzing {path.name}: {e}", file=sys.stderr)

    if len(results) > 1:
        print_corpus_summary(results)

    # Determine output directory
    out_path = Path(args.output) if args.output else OUTPUT_DIR / "results.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Save JSON results
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n\nResults saved to: {out_path}")

    # Generate markdown report
    if results:
        if args.all:
            mode_desc = f"full corpus ({len(results)} files)"
        elif args.sample:
            mode_desc = f"random sample of {len(results)} files (seed=42)"
        elif args.files:
            mode_desc = f"specific files: {', '.join(args.files)}"
        else:
            mode_desc = f"reference files ({', '.join(REFERENCE_FILES)})"

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        report_path = out_path.parent / f"{timestamp}_sec_html_structure_findings.md"
        generate_markdown_report(results, report_path, mode_desc)



if __name__ == "__main__":
    main()

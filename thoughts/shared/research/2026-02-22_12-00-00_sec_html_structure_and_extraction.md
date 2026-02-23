---
title: "SEC 10-K HTML File Structure, Metadata Patterns & Extraction Methods"
date: "2026-02-22"
commit: "b9fb777361d5efd1cfbb4678442a8ebacda17d9e"
branch: "main"
researcher: "beth"
files_analyzed:
  - data/raw/AAPL_10K_2021.html   # 10.0 MB, 88 docs
  - data/raw/ADI_10K_2025.html    # 13.1 MB, 117 docs
  - data/raw/ALL_10K_2025.html    # 44.3 MB, 262 docs
---

# SEC 10-K HTML File Structure, Metadata Patterns & Extraction Methods

## Research Questions

1. What is the physical structure of a raw EDGAR 10-K HTML file?
2. Where does every piece of useful metadata live inside it?
3. How do you extract specific sub-documents without reading the full file as a document?
4. What patterns are universal across all filings vs. company-specific?

---

## Key Finding: These Are Not HTML Files

Despite the `.html` extension, each file in `data/raw/` is an **EDGAR
full-submission text file** — a SGML container that embeds 88–262 separate
documents (HTML, XML, JSON, images, ZIP) concatenated inside a single file.
The parser (`sec-parser`) only uses the main 10-K iXBRL document (Doc 2).
The rest is invisible to it.

---

## Layer 1: The SGML Container Format

Every file starts with an SGML header block and then a flat sequence of
`<DOCUMENT>` entries:

```
<SEC-DOCUMENT>
<SEC-HEADER>
  ACCESSION NUMBER:         0000320193-21-000105
  CONFORMED SUBMISSION TYPE: 10-K
  PUBLIC DOCUMENT COUNT:    88
  CONFORMED PERIOD OF REPORT: 20210925
  FILED AS OF DATE:         20211029
  FILER:
    COMPANY DATA:
      COMPANY CONFORMED NAME:   Apple Inc.
      CENTRAL INDEX KEY:        0000320193
      STANDARD INDUSTRIAL CLASSIFICATION: ELECTRONIC COMPUTERS [3571]
      EIN:                      942404110
      STATE OF INCORPORATION:   CA
      FISCAL YEAR END:          0924
    FILING VALUES:
      FORM TYPE:      10-K
      SEC FILE NUMBER: 001-36743
    BUSINESS ADDRESS: ...
</SEC-HEADER>

<DOCUMENT>
<TYPE>10-K
<SEQUENCE>1
<FILENAME>aapl-20210925.htm
<DESCRIPTION>10-K
<TEXT>
  [iXBRL HTML content — the actual 10-K filing body]
</TEXT>
</DOCUMENT>

<DOCUMENT>
<TYPE>XML
<SEQUENCE>16
<FILENAME>R1.htm
<DESCRIPTION>IDEA: XBRL DOCUMENT
<TEXT>
  [HTML table — Cover Page]
</TEXT>
</DOCUMENT>

... (86 more documents)
```

### Document Boundary Pattern

```
<DOCUMENT>         ← start of embedded document
<TYPE>XML          ← document type
<SEQUENCE>16       ← sequential number
<FILENAME>R1.htm   ← addressable name
<DESCRIPTION>...   ← human description (optional)
<TEXT>             ← content start
  [content]
</TEXT>            ← content end
</DOCUMENT>        ← document end
```

For documents containing XBRL or XML, an additional inner wrapper appears:

```
<TEXT>
<XBRL>             ← inner wrapper (must be stripped on extraction)
  [XML/iXBRL content]
</XBRL>
</TEXT>
```

The full closing sequence for an XBRL-wrapped document is therefore:
```
  </html>
</XBRL>
</TEXT>
</DOCUMENT>
```

---

## Layer 2: The Two Identity Metadata Sources

Every filing provides company identity data in **two parallel, redundant locations**:

### Source A — SGML Header (lines 1–~80)

Plain text key-value pairs, always at the top of the file, always present:

| Field | Example | Notes |
|---|---|---|
| `COMPANY CONFORMED NAME` | `ANALOG DEVICES INC` | Full legal name |
| `CENTRAL INDEX KEY` | `0000006281` | Unique SEC identifier |
| `STANDARD INDUSTRIAL CLASSIFICATION` | `SEMICONDUCTORS & RELATED DEVICES [3674]` | SIC name + code in brackets |
| `EIN` | `042348234` | Federal tax ID |
| `STATE OF INCORPORATION` | `MA` | Two-letter state code |
| `FISCAL YEAR END` | `1101` | MMDD format |
| `CONFORMED PERIOD OF REPORT` | `20251101` | YYYYMMDD — source of `fiscal_year` |
| `FILED AS OF DATE` | `20251125` | Filing date |
| `CONFORMED SUBMISSION TYPE` | `10-K` | Always 10-K for this corpus |
| `PUBLIC DOCUMENT COUNT` | `117` | Total embedded documents |
| `ACCESSION NUMBER` | `0000006281-25-000153` | Unique filing identifier |
| `SEC FILE NUMBER` | `001-07819` | Exchange registration number |
| `FORM TYPE` | `10-K` | Under FILING VALUES |
| `STREET 1`, `CITY`, `STATE`, `ZIP` | address fields | Business and mail address |

**Parser coverage:** `parser.py:279–352` extracts: `company_name`, `cik`,
`sic_code`, `sic_name`, `fiscal_year`, `period_of_report` from this source.
`EIN`, `state_of_incorporation`, `fiscal_year_end`, `accession_number`,
`sec_file_number` are **not extracted**.

### Source B — DEI iXBRL Tags (inside main 10-K body)

Machine-readable structured tags inside the `<ix:hidden>` block of Doc 1.
Richer than the SGML header:

| Tag | Example Value | Notes |
|---|---|---|
| `dei:EntityCentralIndexKey` | `0000006281` | Duplicates SGML CIK |
| `dei:TradingSymbol` | `ADI` | **Ticker** — only here, not in SGML |
| `dei:EntityRegistrantName` | `Analog Devices, Inc.` | Formatted name with punctuation |
| `dei:DocumentFiscalYearFocus` | `2025` | Year as integer string |
| `dei:DocumentFiscalPeriodFocus` | `FY` | Always `FY` for 10-K |
| `dei:DocumentType` | `10-K` | Duplicates SGML |
| `dei:DocumentPeriodEndDate` | `November 1` | Human-readable end date |
| `dei:EntityIncorporationStateCountryCode` | `Massachusetts` | Full state name |
| `dei:EntityTaxIdentificationNumber` | `04-2348234` | EIN with hyphen |
| `dei:EntityAddressAddressLine1` | `One Analog Way,` | Street address |
| `dei:EntityAddressCityOrTown` | `Wilmington,` | City |
| `dei:EntityAddressStateOrProvince` | `MA` | State code |
| `dei:EntityAddressPostalZipCode` | `01887` | ZIP |
| `dei:CityAreaCode` | `781` | Phone area code |
| `dei:LocalPhoneNumber` | `935-5565` | Local phone |
| `dei:Security12bTitle` | `Common Stock $0.16 2/3 par value per share` | Security description |
| `dei:SecurityExchangeName` | `Nasdaq Global Select Market` | Exchange |
| `dei:EntityWellKnownSeasonedIssuer` | `Yes` | WKSI status |
| `dei:EntityFilerCategory` | `Large accelerated filer` | SEC filer category |
| `dei:EntityPublicFloat` | `81,121,000,000` | Market cap at mid-year |
| `dei:EntityCommonStockSharesOutstanding` | `489,654,097` | Share count |
| `dei:AmendmentFlag` | `False` | Whether this is an amendment |
| `dei:IcfrAuditorAttestationFlag` | `True` | SOX 404(b) compliance |

**Parser coverage:** Only `dei:TradingSymbol` is extracted (Fix 1F,
`parser.py:330`). All other DEI tags are unused.

---

## Layer 3: The Document Index — 88 to 262 Embedded Documents

Cross-corpus document type distribution:

| Type | AAPL 2021 | ADI 2025 | ALL 2025 | Purpose |
|---|---|---|---|---|
| Main 10-K (`10-K`) | 1 | 1 | 1 | The actual filing body (iXBRL) |
| `XML` (R*.htm) | 67 | ~85 | 217 | XBRL financial statement sheets |
| `GRAPHIC` (.jpg) | 2 | ~8 | 30 | Company charts/graphs (UUencoded) |
| `EX-101.SCH` | 1 | 1 | 1 | XBRL taxonomy extension schema |
| `EX-101.LAB` | 1 | 1 | 1 | Human-readable element labels |
| `EX-101.CAL` | 1 | 1 | 1 | Calculation relationships |
| `EX-101.DEF` | 1 | 1 | 1 | Axis/dimension definitions |
| `EX-101.PRE` | 1 | 1 | 1 | Presentation hierarchy |
| `JSON` (MetaLinks) | 1 | 1 | 1 | Full XBRL element catalogue |
| `EXCEL` | 1 | 1 | 1 | Financial_Report.xlsx |
| `ZIP` | 1 | 1 | 1 | Full XBRL bundle |
| `EX-4.1` + other exhibits | 6 | ~16 | ~7 | Legal exhibits |
| **Total** | **88** | **117** | **262** | |

The growth from 88 → 262 docs (AAPL 2021 → ALL 2025) is driven by more
`R*.htm` XBRL sheets and more graphic exhibits in more recent filings.

---

## Layer 4: The High-Value Structured Sub-Documents

These four files contain most of the structured data in the filing.
All are extractable by name using the SGML boundary method.

### 4.1 MetaLinks.json

The richest single document. Contains the **complete XBRL element catalogue**
for the entire filing.

**AAPL 2021 statistics:**

| Metric | Value |
|---|---|
| File size | 834 KB |
| Total XBRL elements | 633 |
| us-gaap standard elements | 482 |
| Company-custom elements | 95 (prefix: `aapl_`) |
| DEI elements | 37 |
| Standard taxonomy references | 686 (FASB ASC citations) |
| Financial reports mapped | 67 |
| Hidden iXBRL facts | 26 (22 us-gaap + 4 dei) |

**Structure:**
```json
{
  "version": "2.1",
  "instance": {
    "aapl-20210925.htm": {
      "axisCustom": 0, "axisStandard": 27, "contextCount": 226,
      "elementCount": 633, "keyCustom": 46, "keyStandard": 413,
      "memberCustom": 42, "memberStandard": 45, "segmentCount": 89,
      "unitCount": 9,
      "tag": {
        "us-gaap_AccountsPayableCurrent": {
          "localname": "AccountsPayableCurrent",
          "nsuri": "http://fasb.org/us-gaap/2021-01-31",
          "xbrltype": "monetaryItemType",
          "crdr": "credit",
          "calculation": {
            "http://www.apple.com/role/CONSOLIDATEDBALANCESHEETS": {
              "order": 1.0,
              "parentTag": "us-gaap_LiabilitiesCurrent",
              "weight": 1.0
            }
          },
          "presentation": ["http://www.apple.com/role/CONSOLIDATEDBALANCESHEETS"],
          "lang": {
            "en-us": {
              "role": {
                "documentation": "Carrying value as of the balance sheet date...",
                "label": "Accounts Payable, Current",
                "terseLabel": "Accounts payable"
              }
            }
          },
          "auth_ref": ["r49", "r556"]
        }
      },
      "report": {
        "R2": {"longName": "1001002 - Statement - CONSOLIDATED STATEMENTS OF OPERATIONS"},
        "R4": {"longName": "1003004 - Statement - CONSOLIDATED BALANCE SHEETS"},
        ...
      }
    }
  },
  "std_ref": {
    "r0": {"Name": "ASC", "Publisher": "FASB", "Topic": "105", ...}
  }
}
```

**Per-element fields:**
- `localname` — element name without namespace prefix
- `nsuri` — namespace URI (identifies taxonomy year and publisher)
- `xbrltype` — data type: `monetaryItemType`, `stringItemType`, `textBlockItemType`, `domainItemType`, `percentItemType`, etc.
- `crdr` — `credit` or `debit` (balance sheet direction)
- `calculation` — parent-child summation relationships by statement role
- `presentation` — which financial statements use this element
- `lang.en-us.role.documentation` — full FASB definitional text
- `lang.en-us.role.label` — display name
- `lang.en-us.role.terseLabel` — abbreviated display name
- `auth_ref` — references into `std_ref` (FASB ASC citations)

### 4.2 XBRL Instance Document (`*_htm.xml`)

The machine-readable equivalent of all financial statement values.

**AAPL 2021 statistics:**

| Metric | Value |
|---|---|
| File size | 1.9 MB |
| Contexts (period × dimension) | 226 |
| Unit definitions | 9 (USD, shares, USD/share, pure + 4 custom) |
| Total tagged facts | 1,189 |
| us-gaap facts | 1,041 |
| dei facts | 63 |
| aapl custom facts | 85 |

**Context structure** (maps fact to reporting period and dimension):
```xml
<context id="i55e5364a9af5491886caee077afe8d44_D20200927-20210925">
  <entity>
    <identifier scheme="http://www.sec.gov/CIK">0000320193</identifier>
  </entity>
  <period>
    <startDate>2020-09-27</startDate>
    <endDate>2021-09-25</endDate>
  </period>
</context>
```

Dimensional contexts add a `<segment>` block specifying e.g.
`us-gaap:StatementGeographicalAxis` = `country:CN` (for China revenue breakout).

**Fact structure:**
```xml
<us-gaap:AccountsPayableCurrent
    contextRef="i55e5364a9af5491886caee077afe8d44_D20200927-20210925"
    unitRef="usd"
    decimals="-6">
  54763000000
</us-gaap:AccountsPayableCurrent>
```

Custom units defined per filing (Apple-specific):
```xml
<unit id="customer"><measure>aapl:Customer</measure></unit>
<unit id="vendor"><measure>aapl:Vendor</measure></unit>
<unit id="subsidiary"><measure>aapl:Subsidiary</measure></unit>
```

### 4.3 FilingSummary.xml

Maps every `R*.htm` sheet to its human-readable name and financial statement category.

```xml
<FilingSummary>
  <Version>3.21.2</Version>
  <ContextCount>226</ContextCount>
  <ElementCount>459</ElementCount>
  <SegmentCount>89</SegmentCount>
  <MyReports>
    <Report instance="aapl-20210925.htm">
      <HtmlFileName>R2.htm</HtmlFileName>
      <LongName>1001002 - Statement - CONSOLIDATED STATEMENTS OF OPERATIONS</LongName>
      <ShortName>CONSOLIDATED STATEMENTS OF OPERATIONS</ShortName>
      <MenuCategory>Statements</MenuCategory>
    </Report>
    <Report>
      <HtmlFileName>R8.htm</HtmlFileName>
      <LongName>2101101 - Disclosure - Summary of Significant Accounting Policies</LongName>
      <MenuCategory>Notes</MenuCategory>
    </Report>
    ...
  </MyReports>
</FilingSummary>
```

**MenuCategory values:** `Cover`, `Statements`, `Notes`, `Policies`, `Tables`, `Details`

### 4.4 R*.htm Files (XBRL Financial Statement Sheets)

Each is a standalone HTML table rendering of one financial statement or
disclosure. All share the same structure:

```html
<html>
<head>
  <link rel="stylesheet" type="text/css" href="include/report.css">
  <script type="text/javascript" src="Show.js">...</script>
</head>
<body>
  <span style="display: none;">v3.25.0.1</span>
  <table class="report" border="0" cellspacing="2">
    <tr>
      <th class="tl" colspan="1" rowspan="2">
        <strong>Earnings per Common Share (Details) - USD ($)<br>
        $ / shares in Units, shares in Millions, $ in Millions</strong>
      </th>
      <th class="th" colspan="8">3 Months Ended</th>
      <th class="th" colspan="3">12 Months Ended</th>
    </tr>
    <tr>
      <th class="th"><div>Dec. 31, 2024</div></th>
      ...
    </tr>
  </table>
</body>
</html>
```

Notable: these reference `include/report.css` and `Show.js` via relative paths
that do not exist on disk — they are only valid when served by EDGAR's viewer.
All styling falls back to inline attributes.

### 4.5 GRAPHIC Documents (UUencoded)

Images are embedded as UUencoded ASCII text, **not** base64:

```
begin 644 all-20241231_g1.jpg
M_]C_x1fw17ai9@  34t *@    @ !w$2  ,    !  $   $:  4    !
...
end
```

Extraction works correctly — the raw UU text is the content. Decoding requires
Python's `uu` module or `base64` after converting from UU format.

---

## Layer 5: Universal Corpus Patterns

Confirmed across AAPL 2021, ADI 2025, ALL 2025 (and by inference, all 600+
filings in the corpus):

| Pattern | Value |
|---|---|
| Container format | EDGAR full-submission text (SGML) |
| Always has SGML header | Yes — `<SEC-HEADER>` present in all |
| Always has iXBRL | Yes — `xmlns:ix=` in main doc |
| Authoring tool | Workiva Wdesk (`<!-- Document created using Wdesk -->`) |
| CSS strategy | Zero `<style>` blocks; all inline `style=` attributes |
| XBRL taxonomy | us-gaap current year + company-custom `{ticker}_` prefix |
| DEI tags | Always present in `<ix:hidden>` block |
| `dei:TradingSymbol` format | Two variants: direct text or `<span>`-wrapped |
| `FISCAL YEAR END` format | `MMDD` (e.g., `0924` = September 24, `1101` = November 1) |
| `CONFORMED PERIOD OF REPORT` format | `YYYYMMDD` |
| `FILED AS OF DATE` format | `YYYYMMDD` |
| Financial reports (R*.htm) | 67–217 per filing, grows over time |
| Standard taxonomy references | 686 FASB ASC citations (AAPL 2021) |

---

## Extraction Method: Robust Document Index

### The Right Approach

Build a document index **once** from the SGML boundaries, then slice any
document by stored character offsets. This is O(1) per document vs. O(N) for
repeated regex scans on a 10–44 MB file.

```python
import re

def build_doc_index(html: str) -> list[dict]:
    """
    Parse SGML <DOCUMENT> boundaries into an index.
    Single pass over the full file; subsequent extractions are O(1).
    """
    index = []
    doc_pattern = re.compile(
        r'<DOCUMENT>\s*'
        r'<TYPE>([^\n]+)\n'
        r'<SEQUENCE>([^\n]+)\n'
        r'<FILENAME>([^\n]+)\n'
        r'(?:<DESCRIPTION>([^\n]*)\n)?'   # optional
        r'<TEXT>',
        re.IGNORECASE
    )
    for m in doc_pattern.finditer(html):
        text_start = m.end()
        text_end_m = re.search(r'</TEXT>', html[text_start:], re.IGNORECASE)
        text_end = text_start + text_end_m.start() if text_end_m else len(html)
        index.append({
            'seq':        m.group(2).strip(),
            'type':       m.group(1).strip(),
            'filename':   m.group(3).strip(),
            'desc':       (m.group(4) or '').strip(),
            'text_start': text_start,
            'text_end':   text_end,
            'size':       text_end - text_start,
        })
    return index


def get_doc(html: str, index: list[dict], filename: str) -> tuple[str | None, dict | None]:
    """
    Extract a named document from the pre-built index.
    Strips <XBRL>, <XML>, <JSON> inner wrapper tags if present.
    Returns (content_str, index_entry) or (None, None) if not found.
    """
    entry = next((d for d in index if d['filename'].lower() == filename.lower()), None)
    if not entry:
        return None, None
    raw = html[entry['text_start']:entry['text_end']].strip()
    # Strip inner wrapper tags (present for XBRL and some XML documents)
    raw = re.sub(r'^<(?:XBRL|XML|JSON)>\s*', '', raw, flags=re.IGNORECASE)
    raw = re.sub(r'\s*</(?:XBRL|XML|JSON)>$', '', raw, flags=re.IGNORECASE)
    return raw.strip(), entry
```

### Usage

```python
html   = open('data/raw/AAPL_10K_2021.html', encoding='utf-8').read()
index  = build_doc_index(html)                         # one pass

# Extract any document by name — no rescan
main_10k,  _  = get_doc(html, index, 'aapl-20210925.htm')    # 8.4 MB iXBRL
meta_links, _ = get_doc(html, index, 'MetaLinks.json')        # 834 KB JSON
filing_sum, _ = get_doc(html, index, 'FilingSummary.xml')     # XBRL report index
r77,        _ = get_doc(html, index, 'R77.htm')               # EPS details table
jpg,        _ = get_doc(html, index, 'aapl-20210925_g1.jpg')  # UUencoded image
```

### Handling Each Document Type

| Type | After extraction | Use |
|---|---|---|
| `10-K` (iXBRL HTML) | Valid HTML with `<html>` tag | Pass to sec-parser or BS4 |
| `XML` (R*.htm) | Valid HTML table | Parse with BS4 for financial data |
| `XML` (instance .xml) | Valid XBRL XML | Parse with `xml.etree.ElementTree` |
| `XML` (FilingSummary.xml) | Valid XML | Parse with ElementTree |
| `JSON` (MetaLinks.json) | Valid JSON string | `json.loads()` |
| `GRAPHIC` (.jpg) | UUencoded ASCII text | `uu` module or manual decode |
| `EX-101.LAB` | XML | ElementTree for label lookup |
| `EX-101.CAL` | XML | ElementTree for calculation tree |
| `ZIP` | Binary (UUencoded or base64) | Decode for XBRL bundle |

---

## What Our Current Parser Extracts vs. What Is Available

| Data | Available | Currently extracted | Location |
|---|---|---|---|
| Company name | ✓ | ✓ | SGML header |
| CIK | ✓ | ✓ | SGML header |
| SIC code + name | ✓ | ✓ | SGML header |
| Ticker | ✓ | ✓ | DEI iXBRL |
| Fiscal year | ✓ | ✓ | SGML header |
| Period of report | ✓ | ✓ | SGML header |
| EIN | ✓ | ✗ | SGML header |
| State of incorporation | ✓ | ✗ | SGML header |
| Fiscal year end (MMDD) | ✓ | ✗ | SGML header |
| Accession number | ✓ | ✗ | SGML header |
| Exchange (Nasdaq/NYSE) | ✓ | ✗ | DEI iXBRL |
| Shares outstanding | ✓ | ✗ | DEI iXBRL |
| Public float | ✓ | ✗ | DEI iXBRL |
| Filer category | ✓ | ✗ | DEI iXBRL |
| FASB element definitions | ✓ | ✗ | MetaLinks.json |
| All financial facts (1,189) | ✓ | ✗ | XBRL instance XML |
| Calculation tree | ✓ | ✗ | EX-101.CAL / MetaLinks |
| Named financial statements | ✓ | ✗ | FilingSummary.xml |
| Company logo / charts | ✓ | ✗ | GRAPHIC documents |

---

## Implications for the Pipeline

1. **Parser metadata is correct but incomplete.** The 6 fields extracted
   (`company_name`, `cik`, `sic_code`, `sic_name`, `ticker`, `fiscal_year`)
   are all correct and sourced from the most reliable locations (SGML header
   for text fields, DEI iXBRL for ticker). No fixes needed.

2. **The 44 MB ALL filing (`PUBLIC DOCUMENT COUNT: 262`) will be
   significantly slower to parse** than AAPL (88 docs). The sec-parser
   receives the full concatenated file including all R*.htm and GRAPHIC
   content as one HTML string. Only `_flatten_html_nesting_bs4()` + the
   sec-parser library receive this; `build_doc_index` is not used.

3. **If financial facts are ever needed** (e.g., revenue, net income for
   normalization), the XBRL instance XML is the correct source — not the
   parsed HTML text. The instance XML is clean, structured, and already
   tagged with GAAP element names, periods, and units.

4. **MetaLinks.json is the authoritative element dictionary.** If we
   need to understand what any XBRL element means — its FASB definition,
   calculation parent, or which financial statement it appears in — that
   is the lookup table.

5. **The `</XBRL>` inner wrapper** is a document-type marker, not part
   of the content. `get_doc()` must strip it. Failure to strip it would
   cause XML parsing to fail on documents that use it.

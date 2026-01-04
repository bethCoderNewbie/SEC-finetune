# SEC Filing Download Script

## Overview

This script downloads SEC 10-K filings optimized for LDA topic modeling with:
- **Target**: 1,000 documents
- **Industries**: 11 different sectors (Technology, Healthcare, Financial Services, etc.)
- **Companies**: 300 unique companies
- **Time Range**: Last 5 years (2019-2024)
- **Output Format**: HTML files named `{TICKER}_{FORMTYPE}_{YEAR}.html`
- **Stratified Sampling**: Balanced across industries

## Features

✅ **HTML Output**: All filings saved as HTML in `data/raw/` with clean naming
✅ **Pydantic V2 Compliant**: All models use Pydantic V2 with proper `model_config`
✅ **Industry Enums**: Type-safe industry sector classifications
✅ **Stratified Sampling**: Intelligent distribution across industries and company sizes
✅ **Real Company Universe**: 300+ real S&P 500 companies pre-mapped to industries
✅ **Smart Year Extraction**: Automatically extracts filing year from metadata
✅ **Rate Limiting**: SEC-compliant download rate (10 req/sec max)
✅ **Progress Tracking**: Detailed logging and statistics
✅ **Auto Cleanup**: Removes temporary files after processing

## Installation

Install required dependency:
```bash
pip install sec-edgar-downloader
```

Already installed in this project ✓

## Quick Start

### Download Optimal Corpus for Topic Modeling (Recommended)

```bash
python scripts/data_collection/download_sec_filings.py --mode topic-modeling
```

This single command will:
1. ✅ Sample 300 companies across 11 industries (stratified)
2. ✅ Download ~1,500 10-K filings (5 years per company)
3. ✅ Save as HTML: `data/raw/AAPL_10K_2023.html`, etc.
4. ✅ Generate metadata and statistics

**Expected Runtime**: ~30-45 minutes (with SEC rate limiting)

**Expected Output**:
```
data/raw/
├── AAPL_10K_2023.html
├── AAPL_10K_2022.html
├── AAPL_10K_2021.html
├── ... (1,000+ HTML files)
├── company_list.json
└── download_results.json
```

## Usage Examples

### Mode 1: Topic Modeling (Optimal Corpus)

```bash
python scripts/data_collection/download_sec_filings.py --mode topic-modeling
```

**What happens:**

1. **Stratified Sampling**:
   ```
   Technology           :  60 companies ( 20.0%)
   Healthcare          :  45 companies ( 15.0%)
   Financial Services  :  45 companies ( 15.0%)
   Consumer Goods      :  36 companies ( 12.0%)
   Manufacturing       :  30 companies ( 10.0%)
   Energy              :  24 companies (  8.0%)
   Real Estate         :  18 companies (  6.0%)
   Retail              :  15 companies (  5.0%)
   Telecommunications  :  12 companies (  4.0%)
   Utilities           :   9 companies (  3.0%)
   Transportation      :   6 companies (  2.0%)

   Total: 300 companies
   ```

2. **Downloads Filings**:
   ```
   [1/300] Apple Inc.
     AAPL   (Technology         ): 5 filings
     Saved: AAPL_10K_2023.html
     Saved: AAPL_10K_2022.html
     Saved: AAPL_10K_2021.html
     Saved: AAPL_10K_2020.html
     Saved: AAPL_10K_2019.html

   [2/300] Microsoft Corporation
     MSFT   (Technology         ): 5 filings
     ...
   ```

3. **Summary Statistics**:
   ```
   Total filings downloaded: 1,487
   Companies with filings: 298/300
   Average per company: 5.0

   Filings by industry:
     Technology               :  298 ( 20.0%)
     Healthcare               :  223 ( 15.0%)
     Financial Services       :  223 ( 15.0%)
     ...
   ```

### Mode 2: Custom Download

**Single Company:**
```bash
python scripts/data_collection/download_sec_filings.py --ticker AAPL --years 3
```

Output:
```
data/raw/
├── AAPL_10K_2023.html
├── AAPL_10K_2022.html
└── AAPL_10K_2021.html
```

**Multiple Companies from File:**
```bash
python scripts/data_collection/download_sec_filings.py --ticker-file my_tickers.txt --years 5
```

`my_tickers.txt`:
```
AAPL
MSFT
GOOGL
AMZN
```

**Download 10-Q Filings:**
```bash
python scripts/data_collection/download_sec_filings.py --ticker AAPL --form-type 10-Q --years 2
```

Output: `AAPL_10Q_2024.html`, `AAPL_10Q_2023.html`, etc.

## Output Files

### 1. Downloaded Filings (Main Output)

**Location**: `data/raw/`

**Format**: `{TICKER}_{FORMTYPE}_{YEAR}.html`

**Examples**:
- `AAPL_10K_2023.html` - Apple Inc. 10-K for fiscal year 2023
- `MSFT_10K_2022.html` - Microsoft 10-K for fiscal year 2022
- `GOOGL_10Q_2024.html` - Alphabet 10-Q for 2024 (if using 10-Q)

**File Structure**:
```
data/raw/
├── AAPL_10K_2023.html          ← Complete 10-K filing in HTML
├── AAPL_10K_2022.html
├── AAPL_10K_2021.html
├── AAPL_10K_2020.html
├── AAPL_10K_2019.html
├── MSFT_10K_2023.html
├── MSFT_10K_2022.html
├── GOOGL_10K_2023.html
├── AMZN_10K_2023.html
├── ... (1,000+ files for topic modeling)
├── company_list.json           ← Metadata
└── download_results.json       ← Statistics
```

**Content**:
- Native HTML from SEC EDGAR when available
- Converted from .txt to HTML when HTML not available
- Complete filing including all sections, tables, and exhibits

### 2. Company List

**File**: `data/raw/company_list.json`

**Purpose**: Metadata about sampled companies

**Format**:
```json
[
  {
    "ticker": "AAPL",
    "name": "Apple Inc.",
    "industry": "Technology",
    "market_cap": "Large Cap",
    "cik": null
  },
  {
    "ticker": "MSFT",
    "name": "Microsoft Corporation",
    "industry": "Technology",
    "market_cap": "Large Cap",
    "cik": null
  }
  // ... 300 companies total
]
```

**Use Cases**:
- Track which companies were downloaded
- Map tickers to industries for analysis
- Filter by industry or market cap

### 3. Download Results

**File**: `data/raw/download_results.json`

**Purpose**: Statistics and summary of download session

**Format**:
```json
{
  "config": {
    "target_documents": 1000,
    "target_companies": 300,
    "years_back": 5,
    "form_type": "10-K",
    "filings_per_company": 5,
    "industry_distribution": {
      "Technology": 0.20,
      "Healthcare": 0.15,
      ...
    }
  },
  "total_filings": 1487,
  "companies_with_filings": 298,
  "results": {
    "AAPL": 5,
    "MSFT": 5,
    "GOOGL": 4,
    ...
  },
  "by_industry": {
    "Technology": 298,
    "Healthcare": 223,
    "Financial Services": 223,
    ...
  }
}
```

**Use Cases**:
- Verify download completeness
- Analyze industry distribution
- Debug missing filings

## Industry Distribution

The script uses stratified sampling to ensure balanced representation:

| Industry | Target % | Companies (of 300) | Expected Filings |
|----------|----------|-------------------|------------------|
| **Technology** | 20% | 60 | ~300 |
| **Healthcare** | 15% | 45 | ~225 |
| **Financial Services** | 15% | 45 | ~225 |
| **Consumer Goods** | 12% | 36 | ~180 |
| **Manufacturing** | 10% | 30 | ~150 |
| **Energy** | 8% | 24 | ~120 |
| **Real Estate** | 6% | 18 | ~90 |
| **Retail** | 5% | 15 | ~75 |
| **Telecommunications** | 4% | 12 | ~60 |
| **Utilities** | 3% | 9 | ~45 |
| **Transportation** | 2% | 6 | ~30 |
| **TOTAL** | 100% | 300 | ~1,500 |

**Why This Distribution?**

✅ **Technology (20%)**: Largest and most diverse sector with unique risks (cybersecurity, innovation)
✅ **Healthcare/Financial (15% each)**: Heavy regulation, compliance-focused
✅ **Consumer/Manufacturing (10-12%)**: Supply chain, operational risks
✅ **Others (2-8%)**: Sector-specific risks (energy=commodity, utilities=regulatory)

This distribution ensures the LDA model discovers diverse risk topics across all major business sectors.

## Company Universe

The script includes **300+ real S&P 500 companies** pre-mapped to industries:

### Technology (40 companies)
AAPL, MSFT, GOOGL, META, NVDA, ORCL, CSCO, INTC, AMD, IBM, QCOM, TXN, ADBE, CRM, AVGO, NOW, INTU, AMAT, MU, LRCX, ADI, KLAC, PANW, SNPS, CDNS, MRVL, CRWD, FTNT, WDAY, TEAM, DDOG, ZS, OKTA, SNOW, NET, HPQ, DELL, HPE, NTAP, STX

### Healthcare (30 companies)
UNH, JNJ, LLY, PFE, ABBV, TMO, ABT, DHR, MRK, BMY, AMGN, GILD, CVS, CI, ISRG, REGN, VRTX, ZTS, BSX, ELV, HUM, SYK, MDT, BDX, BIIB, ILMN, IQV, MCK, CAH, COR

### Financial Services (30 companies)
JPM, BAC, WFC, C, GS, MS, BLK, SCHW, CB, SPGI, PGR, AXP, BK, PNC, USB, TFC, AON, MMC, AIG, MET, PRU, AFL, ALL, TRV, COF, DFS, SYF, FITB, KEY, RF

### Consumer Goods (24 companies)
PG, KO, PEP, COST, WMT, NKE, MCD, SBUX, PM, MO, CL, KMB, GIS, K, MDLZ, KHC, HSY, EL, CLX, SJM, CPB, CAG, HRL, TSN

### Manufacturing (18 companies)
BA, CAT, DE, GE, HON, MMM, LMT, RTX, GD, NOC, EMR, ETN, PH, ROK, PCAR, CMI, DOV, ITW

### Energy (14 companies)
XOM, CVX, COP, SLB, EOG, PXD, MPC, VLO, PSX, OXY, KMI, WMB, HAL, BKR

### Real Estate (12 companies)
AMT, PLD, CCI, EQIX, SPG, PSA, O, DLR, WELL, AVB, EQR, VTR

### Retail (10 companies)
AMZN, HD, LOW, TGT, TJX, ROST, DG, DLTR, BBY, EBAY

### Telecommunications (6 companies)
T, VZ, TMUS, CHTR, CMCSA, DIS

### Utilities (8 companies)
NEE, DUK, SO, D, AEP, EXC, SRE, XEL

### Transportation (6 companies)
UPS, FDX, UNP, CSX, NSC, DAL

## Technical Details

### Pydantic V2 Models

All data models use Pydantic V2 syntax:

```python
class CompanyInfo(BaseModel):
    """Company information (Pydantic V2)"""
    model_config = {"frozen": False}  # V2 syntax

    ticker: str = Field(..., description="Stock ticker symbol")
    name: str = Field(..., description="Company name")
    industry: IndustrySector = Field(..., description="Industry sector")
    market_cap: MarketCap = Field(..., description="Market cap category")
    cik: Optional[str] = Field(default=None, description="SEC CIK number")

    @field_validator('ticker')
    @classmethod
    def ticker_uppercase(cls, v: str) -> str:
        """Ensure ticker is uppercase"""
        return v.upper()
```

### Enums (Type-Safe)

```python
class IndustrySector(str, Enum):
    """Industry sectors for stratified sampling (Pydantic V2 compatible)"""
    TECHNOLOGY = "Technology"
    HEALTHCARE = "Healthcare"
    FINANCIAL_SERVICES = "Financial Services"
    CONSUMER_GOODS = "Consumer Goods"
    MANUFACTURING = "Manufacturing"
    ENERGY = "Energy"
    REAL_ESTATE = "Real Estate"
    TELECOMMUNICATIONS = "Telecommunications"
    UTILITIES = "Utilities"
    RETAIL = "Retail"
    TRANSPORTATION = "Transportation"
    MATERIALS = "Materials"

class MarketCap(str, Enum):
    """Market capitalization categories"""
    LARGE = "Large Cap"    # >$10B
    MID = "Mid Cap"        # $2B-$10B
    SMALL = "Small Cap"    # <$2B
```

### Year Extraction Logic

The script automatically extracts the filing year using multiple methods:

```python
# Method 1: From filing metadata
# Looks for: "CONFORMED PERIOD OF REPORT: 20231230"
match = re.search(r'CONFORMED PERIOD OF REPORT:\s*(\d{8})', content)

# Method 2: From accession number
# Example: "0000320193-23-000106" → year 2023
match = re.search(r'-(\d{2})-\d+', accession_number)

# Method 3: Fallback to current year
year = datetime.now().year
```

### HTML Processing

```python
# Preferred: Use native HTML from SEC
html_file = filing_dir / "primary-document.html"

# Fallback: Convert .txt to HTML
if not html_file.exists():
    txt_content = read_txt_file()
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body><pre>{txt_content}</pre></body>
    </html>
    """
```

## Command-Line Options

```
usage: download_sec_filings.py [-h] [--mode {topic-modeling,custom}]
                               [--ticker TICKER] [--ticker-file TICKER_FILE]
                               [--form-type {10-K,10-Q}] [--years YEARS]
                               [--num-filings NUM_FILINGS]

Download SEC filings optimized for topic modeling

Arguments:
  -h, --help            Show help message and exit

  --mode {topic-modeling,custom}
                        Download mode (default: custom)
                        - topic-modeling: Optimal corpus (1000 docs, 300 companies, 11 industries)
                        - custom: Specify your own tickers

  --ticker TICKER       Single ticker symbol (e.g., AAPL)
                        Only used with --mode custom

  --ticker-file TICKER_FILE
                        Path to file with tickers (one per line)
                        Only used with --mode custom

  --form-type {10-K,10-Q}
                        SEC form type (default: 10-K)

  --years YEARS         Years to look back (default: 5)

  --num-filings NUM_FILINGS
                        Max filings per ticker (default: 5)
```

## SEC Rate Limiting

**SEC Requirement**: Maximum 10 requests per second

**Implementation**:
- Default delay: 0.11 seconds between requests (~9 req/sec)
- Configurable via `rate_limit_delay` parameter in code
- Automatic retry with backoff on rate limit errors

**Why it matters**:
- SEC blocks IPs that exceed rate limits
- Respectful API usage ensures continued access
- Small delay (0.11s) has minimal impact on total time

**Estimated Download Time**:
- 300 companies × 0.11s = 33 seconds minimum
- Actual: ~30-45 minutes (includes file processing, year extraction, HTML conversion)

## File Naming Convention

### Format
```
{TICKER}_{FORMTYPE}_{YEAR}.html
```

### Components

| Component | Description | Example |
|-----------|-------------|---------|
| `TICKER` | Stock ticker symbol (uppercase) | `AAPL`, `MSFT` |
| `FORMTYPE` | SEC form type (no dash) | `10K`, `10Q` |
| `YEAR` | Fiscal year of the filing | `2023`, `2022` |

### Examples

| Filename | Description |
|----------|-------------|
| `AAPL_10K_2023.html` | Apple 10-K for fiscal year 2023 |
| `MSFT_10K_2022.html` | Microsoft 10-K for fiscal year 2022 |
| `GOOGL_10Q_2024.html` | Alphabet 10-Q for Q1/Q2/Q3/Q4 2024 |
| `AMZN_10K_2021.html` | Amazon 10-K for fiscal year 2021 |

### Why This Format?

✅ **Sortable**: Files naturally sort by ticker, then form, then year
✅ **Parseable**: Easy to extract metadata from filename
✅ **No Conflicts**: Unique per company/form/year combination
✅ **Readable**: Human-friendly naming
✅ **Compatible**: Works across all operating systems

## Next Steps

After downloading filings, proceed with the data pipeline:

### Step 1: Validate Download
```bash
# Check downloaded files
ls -l data/raw/*.html | wc -l  # Should be ~1000-1500 files

# Review statistics
cat data/raw/download_results.json
```

### Step 2: Parse Filings
```bash
# Parse HTML filings to extract structure
python scripts/02_parsing/parse_filings.py
```

### Step 3: Extract Item 1A Sections
```bash
# Extract Risk Factors section for topic modeling
python scripts/02_extraction/extract_sections.py --section part1item1a
```

### Step 4: Validate Corpus
```bash
# Validate corpus meets topic modeling requirements
python scripts/feature_engineering/validate_topic_modeling_corpus.py
```

### Step 5: Train Topic Model
```bash
# Train LDA model on Item 1A corpus
python scripts/feature_engineering/topic_modeling_demo.py
```

## Troubleshooting

### Issue: No filings downloaded for some companies

**Symptoms**:
```
AAPL   (Technology         ): 0 filings
```

**Possible Causes**:
1. Ticker symbol incorrect or company not public during time range
2. Company didn't file during the specified date range
3. Network/SEC API issues

**Solutions**:
```bash
# 1. Verify ticker on SEC EDGAR manually: https://www.sec.gov/edgar/search/
# 2. Extend date range
python download_sec_filings.py --ticker AAPL --years 10

# 3. Check if it's a different form type
python download_sec_filings.py --ticker AAPL --form-type 10-Q
```

### Issue: Rate limit errors

**Symptoms**:
```
Error 429: Too Many Requests
```

**Solution**:
Edit `download_sec_filings.py` line 617:
```python
# Increase delay from 0.11 to 0.15 seconds
rate_limit_delay=0.15  # ~6.6 requests/second
```

### Issue: HTML files are empty or corrupted

**Symptoms**:
- Files exist but have size 0 KB
- Opening HTML shows garbled text

**Causes**:
- Download interrupted
- Encoding issues

**Solutions**:
```bash
# 1. Re-download specific ticker
python download_sec_filings.py --ticker AAPL --years 3

# 2. Check disk space
df -h  # Ensure sufficient space

# 3. Check file manually
cat data/raw/AAPL_10K_2023.html | head -100
```

### Issue: Missing years in output

**Symptoms**:
- Only 3 filings for a company instead of 5
- Gaps in years (2023, 2021, 2019 but missing 2022, 2020)

**Explanation**:
- Company may not have filed every year (acquisitions, spinoffs)
- Date range may not capture all filings

**Solution**:
```bash
# Extend date range to ensure coverage
python download_sec_filings.py --ticker AAPL --years 10 --num-filings 10
```

### Issue: Import error for sec-edgar-downloader

**Symptoms**:
```
ERROR: sec-edgar-downloader not installed
```

**Solution**:
```bash
pip install sec-edgar-downloader

# Verify installation
python -c "import sec_edgar_downloader; print('OK')"
```

### Issue: Year extraction fails

**Symptoms**:
- Files named `AAPL_10K_2025.html` (future year)
- Incorrect years in filenames

**Debug**:
```bash
# Check file content
head -100 data/raw/AAPL_10K_2025.html | grep -i "period of report"
```

**Manual Fix** (if needed):
```bash
# Rename file manually
mv data/raw/AAPL_10K_2025.html data/raw/AAPL_10K_2023.html
```

## Performance Tips

### Speed Up Downloads

1. **Reduce companies** (for testing):
   ```python
   # Edit download_sec_filings.py line 575
   target_companies=100,  # Instead of 300
   ```

2. **Reduce years**:
   ```bash
   # Edit or pass --years flag
   python download_sec_filings.py --mode topic-modeling --years 3
   ```

3. **Parallel downloads** (advanced):
   - Not recommended due to SEC rate limits
   - Could result in IP ban

### Optimize Storage

Each HTML file: ~500KB - 2MB
Total for 1,500 filings: ~1.5GB

To save space:
```bash
# Compress old filings
gzip data/raw/*_2019.html
gzip data/raw/*_2020.html
```

## Customization

### Modify Industry Distribution

Edit `DownloadConfig` class in `download_sec_filings.py`:

```python
class DownloadConfig(BaseModel):
    industry_distribution: Dict[IndustrySector, float] = Field(
        default_factory=lambda: {
            IndustrySector.TECHNOLOGY: 0.25,      # Increase Tech to 25%
            IndustrySector.HEALTHCARE: 0.20,      # Increase Healthcare to 20%
            IndustrySector.FINANCIAL_SERVICES: 0.15,
            # ... adjust others to sum to 1.0
        }
    )
```

### Add More Companies

Append to `COMPANY_UNIVERSE` list:

```python
COMPANY_UNIVERSE.extend([
    CompanyInfo(
        ticker="TSLA",
        name="Tesla Inc.",
        industry=IndustrySector.MANUFACTURING,
        market_cap=MarketCap.LARGE
    ),
    CompanyInfo(
        ticker="NFLX",
        name="Netflix Inc.",
        industry=IndustrySector.TELECOMMUNICATIONS,
        market_cap=MarketCap.LARGE
    ),
    # Add more...
])
```

### Change Output Directory

```python
# Modify in download_for_topic_modeling() function
downloader = EdgarDownloader(
    output_dir=Path("custom/output/path")  # Instead of settings.paths.raw_data_dir
)
```

## Best Practices

### ✅ Do

- Run `--mode topic-modeling` for optimal corpus
- Verify download statistics in `download_results.json`
- Check for missing companies before proceeding to next step
- Keep `company_list.json` for reproducibility
- Use version control for configuration changes

### ❌ Don't

- Don't reduce `rate_limit_delay` below 0.1 (risk of IP ban)
- Don't run multiple instances simultaneously (SEC rate limit)
- Don't delete `download_results.json` (needed for analysis)
- Don't manually edit HTML files (breaks checksums)
- Don't commit large HTML files to git (use .gitignore)

## License & Compliance

- **Data Source**: SEC EDGAR public database
- **Rate Limiting**: Complies with SEC 10 req/sec limit
- **Attribution**: Not required but appreciated
- **Use Case**: Research and educational purposes
- **Restrictions**: Respect SEC terms of service

**Important**: Always include proper user agent with contact email:
```python
user_agent = "Company Name contact@example.com"
```

## Summary

This script provides a complete solution for downloading SEC filings optimized for topic modeling:

✅ Downloads 1,000+ 10-K filings in HTML format
✅ Balanced across 11 industries (300 companies)
✅ 5-year time range (2019-2024)
✅ Clean naming: `{TICKER}_{FORM}_{YEAR}.html`
✅ Pydantic V2 compliant, type-safe enums
✅ SEC rate limit compliant
✅ Automatic cleanup and error handling

**Ready to use**:
```bash
python scripts/data_collection/download_sec_filings.py --mode topic-modeling
```

Then proceed to topic modeling pipeline! 🚀

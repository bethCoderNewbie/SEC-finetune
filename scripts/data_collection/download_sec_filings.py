"""
Data Collection: Download SEC Filings for Topic Modeling

This script downloads SEC 10-K filings optimized for LDA topic modeling:
- Target: 1,000 documents
- Industries: 8-12 different sectors
- Time Range: 3-5 years (2019-2023)
- Unique Companies: 200-400
- Stratified sampling across industries and time

Usage:
    # Download optimal corpus for topic modeling
    python scripts/data_collection/download_sec_filings.py --mode topic-modeling

    # Download specific companies
    python scripts/data_collection/download_sec_filings.py --ticker AAPL --years 3

    # Download from ticker file
    python scripts/data_collection/download_sec_filings.py --ticker-file tickers.txt
"""

import argparse
import json
import logging
import random
import time
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import List, Dict, Optional
import sys

from pydantic import BaseModel, Field, field_validator

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ===========================
# Pydantic V2 Models & Enums
# ===========================

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


class CompanyInfo(BaseModel):
    """Company information (Pydantic V2)"""
    model_config = {"frozen": False}

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


class DownloadConfig(BaseModel):
    """Download configuration (Pydantic V2)"""
    model_config = {"frozen": False}

    target_documents: int = Field(1000, description="Target number of documents")
    target_companies: int = Field(300, description="Target number of unique companies")
    years_back: int = Field(5, description="Years to look back")
    form_type: str = Field("10-K", description="SEC form type")
    filings_per_company: int = Field(5, description="Max filings per company")

    # Industry distribution (percentages)
    industry_distribution: Dict[IndustrySector, float] = Field(
        default_factory=lambda: {
            IndustrySector.TECHNOLOGY: 0.20,
            IndustrySector.HEALTHCARE: 0.15,
            IndustrySector.FINANCIAL_SERVICES: 0.15,
            IndustrySector.CONSUMER_GOODS: 0.12,
            IndustrySector.MANUFACTURING: 0.10,
            IndustrySector.ENERGY: 0.08,
            IndustrySector.REAL_ESTATE: 0.06,
            IndustrySector.RETAIL: 0.05,
            IndustrySector.TELECOMMUNICATIONS: 0.04,
            IndustrySector.UTILITIES: 0.03,
            IndustrySector.TRANSPORTATION: 0.02,
        }
    )

    @field_validator('industry_distribution')
    @classmethod
    def validate_distribution_sum(cls, v: Dict[IndustrySector, float]) -> Dict[IndustrySector, float]:
        """Ensure distribution sums to ~1.0"""
        total = sum(v.values())
        if not (0.99 <= total <= 1.01):
            raise ValueError(f"Industry distribution must sum to ~1.0, got {total:.3f}")
        return v


# ===========================
# Company Universe
# ===========================

# Real S&P 500 companies mapped to industries
COMPANY_UNIVERSE: List[CompanyInfo] = [
    # Technology (20%)
    CompanyInfo(ticker="AAPL", name="Apple Inc.", industry=IndustrySector.TECHNOLOGY, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="MSFT", name="Microsoft Corporation", industry=IndustrySector.TECHNOLOGY, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="GOOGL", name="Alphabet Inc.", industry=IndustrySector.TECHNOLOGY, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="META", name="Meta Platforms Inc.", industry=IndustrySector.TECHNOLOGY, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="NVDA", name="NVIDIA Corporation", industry=IndustrySector.TECHNOLOGY, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="ORCL", name="Oracle Corporation", industry=IndustrySector.TECHNOLOGY, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="CSCO", name="Cisco Systems Inc.", industry=IndustrySector.TECHNOLOGY, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="INTC", name="Intel Corporation", industry=IndustrySector.TECHNOLOGY, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="AMD", name="Advanced Micro Devices Inc.", industry=IndustrySector.TECHNOLOGY, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="IBM", name="IBM Corporation", industry=IndustrySector.TECHNOLOGY, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="QCOM", name="Qualcomm Inc.", industry=IndustrySector.TECHNOLOGY, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="TXN", name="Texas Instruments Inc.", industry=IndustrySector.TECHNOLOGY, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="ADBE", name="Adobe Inc.", industry=IndustrySector.TECHNOLOGY, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="CRM", name="Salesforce Inc.", industry=IndustrySector.TECHNOLOGY, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="AVGO", name="Broadcom Inc.", industry=IndustrySector.TECHNOLOGY, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="NOW", name="ServiceNow Inc.", industry=IndustrySector.TECHNOLOGY, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="INTU", name="Intuit Inc.", industry=IndustrySector.TECHNOLOGY, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="AMAT", name="Applied Materials Inc.", industry=IndustrySector.TECHNOLOGY, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="MU", name="Micron Technology Inc.", industry=IndustrySector.TECHNOLOGY, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="LRCX", name="Lam Research Corporation", industry=IndustrySector.TECHNOLOGY, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="ADI", name="Analog Devices Inc.", industry=IndustrySector.TECHNOLOGY, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="KLAC", name="KLA Corporation", industry=IndustrySector.TECHNOLOGY, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="PANW", name="Palo Alto Networks Inc.", industry=IndustrySector.TECHNOLOGY, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="SNPS", name="Synopsys Inc.", industry=IndustrySector.TECHNOLOGY, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="CDNS", name="Cadence Design Systems", industry=IndustrySector.TECHNOLOGY, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="MRVL", name="Marvell Technology Inc.", industry=IndustrySector.TECHNOLOGY, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="CRWD", name="CrowdStrike Holdings Inc.", industry=IndustrySector.TECHNOLOGY, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="FTNT", name="Fortinet Inc.", industry=IndustrySector.TECHNOLOGY, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="WDAY", name="Workday Inc.", industry=IndustrySector.TECHNOLOGY, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="TEAM", name="Atlassian Corporation", industry=IndustrySector.TECHNOLOGY, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="DDOG", name="Datadog Inc.", industry=IndustrySector.TECHNOLOGY, market_cap=MarketCap.MID),
    CompanyInfo(ticker="ZS", name="Zscaler Inc.", industry=IndustrySector.TECHNOLOGY, market_cap=MarketCap.MID),
    CompanyInfo(ticker="OKTA", name="Okta Inc.", industry=IndustrySector.TECHNOLOGY, market_cap=MarketCap.MID),
    CompanyInfo(ticker="SNOW", name="Snowflake Inc.", industry=IndustrySector.TECHNOLOGY, market_cap=MarketCap.MID),
    CompanyInfo(ticker="NET", name="Cloudflare Inc.", industry=IndustrySector.TECHNOLOGY, market_cap=MarketCap.MID),
    CompanyInfo(ticker="HPQ", name="HP Inc.", industry=IndustrySector.TECHNOLOGY, market_cap=MarketCap.MID),
    CompanyInfo(ticker="DELL", name="Dell Technologies Inc.", industry=IndustrySector.TECHNOLOGY, market_cap=MarketCap.MID),
    CompanyInfo(ticker="HPE", name="Hewlett Packard Enterprise", industry=IndustrySector.TECHNOLOGY, market_cap=MarketCap.MID),
    CompanyInfo(ticker="NTAP", name="NetApp Inc.", industry=IndustrySector.TECHNOLOGY, market_cap=MarketCap.MID),
    CompanyInfo(ticker="STX", name="Seagate Technology Holdings", industry=IndustrySector.TECHNOLOGY, market_cap=MarketCap.MID),

    # Healthcare (15%)
    CompanyInfo(ticker="UNH", name="UnitedHealth Group Inc.", industry=IndustrySector.HEALTHCARE, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="JNJ", name="Johnson & Johnson", industry=IndustrySector.HEALTHCARE, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="LLY", name="Eli Lilly and Company", industry=IndustrySector.HEALTHCARE, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="PFE", name="Pfizer Inc.", industry=IndustrySector.HEALTHCARE, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="ABBV", name="AbbVie Inc.", industry=IndustrySector.HEALTHCARE, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="TMO", name="Thermo Fisher Scientific Inc.", industry=IndustrySector.HEALTHCARE, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="ABT", name="Abbott Laboratories", industry=IndustrySector.HEALTHCARE, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="DHR", name="Danaher Corporation", industry=IndustrySector.HEALTHCARE, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="MRK", name="Merck & Co. Inc.", industry=IndustrySector.HEALTHCARE, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="BMY", name="Bristol-Myers Squibb Company", industry=IndustrySector.HEALTHCARE, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="AMGN", name="Amgen Inc.", industry=IndustrySector.HEALTHCARE, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="GILD", name="Gilead Sciences Inc.", industry=IndustrySector.HEALTHCARE, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="CVS", name="CVS Health Corporation", industry=IndustrySector.HEALTHCARE, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="CI", name="Cigna Corporation", industry=IndustrySector.HEALTHCARE, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="ISRG", name="Intuitive Surgical Inc.", industry=IndustrySector.HEALTHCARE, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="REGN", name="Regeneron Pharmaceuticals Inc.", industry=IndustrySector.HEALTHCARE, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="VRTX", name="Vertex Pharmaceuticals Inc.", industry=IndustrySector.HEALTHCARE, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="ZTS", name="Zoetis Inc.", industry=IndustrySector.HEALTHCARE, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="BSX", name="Boston Scientific Corporation", industry=IndustrySector.HEALTHCARE, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="ELV", name="Elevance Health Inc.", industry=IndustrySector.HEALTHCARE, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="HUM", name="Humana Inc.", industry=IndustrySector.HEALTHCARE, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="SYK", name="Stryker Corporation", industry=IndustrySector.HEALTHCARE, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="MDT", name="Medtronic plc", industry=IndustrySector.HEALTHCARE, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="BDX", name="Becton Dickinson and Company", industry=IndustrySector.HEALTHCARE, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="BIIB", name="Biogen Inc.", industry=IndustrySector.HEALTHCARE, market_cap=MarketCap.MID),
    CompanyInfo(ticker="ILMN", name="Illumina Inc.", industry=IndustrySector.HEALTHCARE, market_cap=MarketCap.MID),
    CompanyInfo(ticker="IQV", name="IQVIA Holdings Inc.", industry=IndustrySector.HEALTHCARE, market_cap=MarketCap.MID),
    CompanyInfo(ticker="MCK", name="McKesson Corporation", industry=IndustrySector.HEALTHCARE, market_cap=MarketCap.MID),
    CompanyInfo(ticker="CAH", name="Cardinal Health Inc.", industry=IndustrySector.HEALTHCARE, market_cap=MarketCap.MID),
    CompanyInfo(ticker="COR", name="Cencora Inc.", industry=IndustrySector.HEALTHCARE, market_cap=MarketCap.MID),

    # Financial Services (15%)
    CompanyInfo(ticker="JPM", name="JPMorgan Chase & Co.", industry=IndustrySector.FINANCIAL_SERVICES, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="BAC", name="Bank of America Corporation", industry=IndustrySector.FINANCIAL_SERVICES, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="WFC", name="Wells Fargo & Company", industry=IndustrySector.FINANCIAL_SERVICES, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="C", name="Citigroup Inc.", industry=IndustrySector.FINANCIAL_SERVICES, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="GS", name="The Goldman Sachs Group Inc.", industry=IndustrySector.FINANCIAL_SERVICES, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="MS", name="Morgan Stanley", industry=IndustrySector.FINANCIAL_SERVICES, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="BLK", name="BlackRock Inc.", industry=IndustrySector.FINANCIAL_SERVICES, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="SCHW", name="The Charles Schwab Corporation", industry=IndustrySector.FINANCIAL_SERVICES, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="CB", name="Chubb Limited", industry=IndustrySector.FINANCIAL_SERVICES, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="SPGI", name="S&P Global Inc.", industry=IndustrySector.FINANCIAL_SERVICES, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="PGR", name="The Progressive Corporation", industry=IndustrySector.FINANCIAL_SERVICES, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="AXP", name="American Express Company", industry=IndustrySector.FINANCIAL_SERVICES, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="BK", name="The Bank of New York Mellon Corporation", industry=IndustrySector.FINANCIAL_SERVICES, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="PNC", name="The PNC Financial Services Group Inc.", industry=IndustrySector.FINANCIAL_SERVICES, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="USB", name="U.S. Bancorp", industry=IndustrySector.FINANCIAL_SERVICES, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="TFC", name="Truist Financial Corporation", industry=IndustrySector.FINANCIAL_SERVICES, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="AON", name="Aon plc", industry=IndustrySector.FINANCIAL_SERVICES, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="MMC", name="Marsh & McLennan Companies Inc.", industry=IndustrySector.FINANCIAL_SERVICES, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="AIG", name="American International Group Inc.", industry=IndustrySector.FINANCIAL_SERVICES, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="MET", name="MetLife Inc.", industry=IndustrySector.FINANCIAL_SERVICES, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="PRU", name="Prudential Financial Inc.", industry=IndustrySector.FINANCIAL_SERVICES, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="AFL", name="Aflac Incorporated", industry=IndustrySector.FINANCIAL_SERVICES, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="ALL", name="The Allstate Corporation", industry=IndustrySector.FINANCIAL_SERVICES, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="TRV", name="The Travelers Companies Inc.", industry=IndustrySector.FINANCIAL_SERVICES, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="COF", name="Capital One Financial Corporation", industry=IndustrySector.FINANCIAL_SERVICES, market_cap=MarketCap.MID),
    CompanyInfo(ticker="DFS", name="Discover Financial Services", industry=IndustrySector.FINANCIAL_SERVICES, market_cap=MarketCap.MID),
    CompanyInfo(ticker="SYF", name="Synchrony Financial", industry=IndustrySector.FINANCIAL_SERVICES, market_cap=MarketCap.MID),
    CompanyInfo(ticker="FITB", name="Fifth Third Bancorp", industry=IndustrySector.FINANCIAL_SERVICES, market_cap=MarketCap.MID),
    CompanyInfo(ticker="KEY", name="KeyCorp", industry=IndustrySector.FINANCIAL_SERVICES, market_cap=MarketCap.MID),
    CompanyInfo(ticker="RF", name="Regions Financial Corporation", industry=IndustrySector.FINANCIAL_SERVICES, market_cap=MarketCap.MID),

    # Consumer Goods (12%)
    CompanyInfo(ticker="PG", name="The Procter & Gamble Company", industry=IndustrySector.CONSUMER_GOODS, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="KO", name="The Coca-Cola Company", industry=IndustrySector.CONSUMER_GOODS, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="PEP", name="PepsiCo Inc.", industry=IndustrySector.CONSUMER_GOODS, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="COST", name="Costco Wholesale Corporation", industry=IndustrySector.CONSUMER_GOODS, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="WMT", name="Walmart Inc.", industry=IndustrySector.CONSUMER_GOODS, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="NKE", name="NIKE Inc.", industry=IndustrySector.CONSUMER_GOODS, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="MCD", name="McDonald's Corporation", industry=IndustrySector.CONSUMER_GOODS, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="SBUX", name="Starbucks Corporation", industry=IndustrySector.CONSUMER_GOODS, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="PM", name="Philip Morris International Inc.", industry=IndustrySector.CONSUMER_GOODS, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="MO", name="Altria Group Inc.", industry=IndustrySector.CONSUMER_GOODS, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="CL", name="Colgate-Palmolive Company", industry=IndustrySector.CONSUMER_GOODS, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="KMB", name="Kimberly-Clark Corporation", industry=IndustrySector.CONSUMER_GOODS, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="GIS", name="General Mills Inc.", industry=IndustrySector.CONSUMER_GOODS, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="K", name="Kellogg Company", industry=IndustrySector.CONSUMER_GOODS, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="MDLZ", name="Mondelez International Inc.", industry=IndustrySector.CONSUMER_GOODS, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="KHC", name="The Kraft Heinz Company", industry=IndustrySector.CONSUMER_GOODS, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="HSY", name="The Hershey Company", industry=IndustrySector.CONSUMER_GOODS, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="EL", name="The Estée Lauder Companies Inc.", industry=IndustrySector.CONSUMER_GOODS, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="CLX", name="The Clorox Company", industry=IndustrySector.CONSUMER_GOODS, market_cap=MarketCap.MID),
    CompanyInfo(ticker="SJM", name="The J. M. Smucker Company", industry=IndustrySector.CONSUMER_GOODS, market_cap=MarketCap.MID),
    CompanyInfo(ticker="CPB", name="Campbell Soup Company", industry=IndustrySector.CONSUMER_GOODS, market_cap=MarketCap.MID),
    CompanyInfo(ticker="CAG", name="Conagra Brands Inc.", industry=IndustrySector.CONSUMER_GOODS, market_cap=MarketCap.MID),
    CompanyInfo(ticker="HRL", name="Hormel Foods Corporation", industry=IndustrySector.CONSUMER_GOODS, market_cap=MarketCap.MID),
    CompanyInfo(ticker="TSN", name="Tyson Foods Inc.", industry=IndustrySector.CONSUMER_GOODS, market_cap=MarketCap.MID),

    # Manufacturing (10%)
    CompanyInfo(ticker="BA", name="The Boeing Company", industry=IndustrySector.MANUFACTURING, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="CAT", name="Caterpillar Inc.", industry=IndustrySector.MANUFACTURING, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="DE", name="Deere & Company", industry=IndustrySector.MANUFACTURING, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="GE", name="General Electric Company", industry=IndustrySector.MANUFACTURING, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="HON", name="Honeywell International Inc.", industry=IndustrySector.MANUFACTURING, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="MMM", name="3M Company", industry=IndustrySector.MANUFACTURING, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="LMT", name="Lockheed Martin Corporation", industry=IndustrySector.MANUFACTURING, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="RTX", name="RTX Corporation", industry=IndustrySector.MANUFACTURING, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="GD", name="General Dynamics Corporation", industry=IndustrySector.MANUFACTURING, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="NOC", name="Northrop Grumman Corporation", industry=IndustrySector.MANUFACTURING, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="EMR", name="Emerson Electric Co.", industry=IndustrySector.MANUFACTURING, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="ETN", name="Eaton Corporation plc", industry=IndustrySector.MANUFACTURING, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="PH", name="Parker-Hannifin Corporation", industry=IndustrySector.MANUFACTURING, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="ROK", name="Rockwell Automation Inc.", industry=IndustrySector.MANUFACTURING, market_cap=MarketCap.MID),
    CompanyInfo(ticker="PCAR", name="PACCAR Inc.", industry=IndustrySector.MANUFACTURING, market_cap=MarketCap.MID),
    CompanyInfo(ticker="CMI", name="Cummins Inc.", industry=IndustrySector.MANUFACTURING, market_cap=MarketCap.MID),
    CompanyInfo(ticker="DOV", name="Dover Corporation", industry=IndustrySector.MANUFACTURING, market_cap=MarketCap.MID),
    CompanyInfo(ticker="ITW", name="Illinois Tool Works Inc.", industry=IndustrySector.MANUFACTURING, market_cap=MarketCap.MID),

    # Energy (8%)
    CompanyInfo(ticker="XOM", name="Exxon Mobil Corporation", industry=IndustrySector.ENERGY, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="CVX", name="Chevron Corporation", industry=IndustrySector.ENERGY, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="COP", name="ConocoPhillips", industry=IndustrySector.ENERGY, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="SLB", name="Schlumberger Limited", industry=IndustrySector.ENERGY, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="EOG", name="EOG Resources Inc.", industry=IndustrySector.ENERGY, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="PXD", name="Pioneer Natural Resources Company", industry=IndustrySector.ENERGY, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="MPC", name="Marathon Petroleum Corporation", industry=IndustrySector.ENERGY, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="VLO", name="Valero Energy Corporation", industry=IndustrySector.ENERGY, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="PSX", name="Phillips 66", industry=IndustrySector.ENERGY, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="OXY", name="Occidental Petroleum Corporation", industry=IndustrySector.ENERGY, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="KMI", name="Kinder Morgan Inc.", industry=IndustrySector.ENERGY, market_cap=MarketCap.MID),
    CompanyInfo(ticker="WMB", name="The Williams Companies Inc.", industry=IndustrySector.ENERGY, market_cap=MarketCap.MID),
    CompanyInfo(ticker="HAL", name="Halliburton Company", industry=IndustrySector.ENERGY, market_cap=MarketCap.MID),
    CompanyInfo(ticker="BKR", name="Baker Hughes Company", industry=IndustrySector.ENERGY, market_cap=MarketCap.MID),

    # Real Estate (6%)
    CompanyInfo(ticker="AMT", name="American Tower Corporation", industry=IndustrySector.REAL_ESTATE, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="PLD", name="Prologis Inc.", industry=IndustrySector.REAL_ESTATE, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="CCI", name="Crown Castle Inc.", industry=IndustrySector.REAL_ESTATE, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="EQIX", name="Equinix Inc.", industry=IndustrySector.REAL_ESTATE, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="SPG", name="Simon Property Group Inc.", industry=IndustrySector.REAL_ESTATE, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="PSA", name="Public Storage", industry=IndustrySector.REAL_ESTATE, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="O", name="Realty Income Corporation", industry=IndustrySector.REAL_ESTATE, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="DLR", name="Digital Realty Trust Inc.", industry=IndustrySector.REAL_ESTATE, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="WELL", name="Welltower Inc.", industry=IndustrySector.REAL_ESTATE, market_cap=MarketCap.MID),
    CompanyInfo(ticker="AVB", name="AvalonBay Communities Inc.", industry=IndustrySector.REAL_ESTATE, market_cap=MarketCap.MID),
    CompanyInfo(ticker="EQR", name="Equity Residential", industry=IndustrySector.REAL_ESTATE, market_cap=MarketCap.MID),
    CompanyInfo(ticker="VTR", name="Ventas Inc.", industry=IndustrySector.REAL_ESTATE, market_cap=MarketCap.MID),

    # Retail (5%)
    CompanyInfo(ticker="AMZN", name="Amazon.com Inc.", industry=IndustrySector.RETAIL, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="HD", name="The Home Depot Inc.", industry=IndustrySector.RETAIL, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="LOW", name="Lowe's Companies Inc.", industry=IndustrySector.RETAIL, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="TGT", name="Target Corporation", industry=IndustrySector.RETAIL, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="TJX", name="The TJX Companies Inc.", industry=IndustrySector.RETAIL, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="ROST", name="Ross Stores Inc.", industry=IndustrySector.RETAIL, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="DG", name="Dollar General Corporation", industry=IndustrySector.RETAIL, market_cap=MarketCap.MID),
    CompanyInfo(ticker="DLTR", name="Dollar Tree Inc.", industry=IndustrySector.RETAIL, market_cap=MarketCap.MID),
    CompanyInfo(ticker="BBY", name="Best Buy Co. Inc.", industry=IndustrySector.RETAIL, market_cap=MarketCap.MID),
    CompanyInfo(ticker="EBAY", name="eBay Inc.", industry=IndustrySector.RETAIL, market_cap=MarketCap.MID),

    # Telecommunications (4%)
    CompanyInfo(ticker="T", name="AT&T Inc.", industry=IndustrySector.TELECOMMUNICATIONS, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="VZ", name="Verizon Communications Inc.", industry=IndustrySector.TELECOMMUNICATIONS, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="TMUS", name="T-Mobile US Inc.", industry=IndustrySector.TELECOMMUNICATIONS, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="CHTR", name="Charter Communications Inc.", industry=IndustrySector.TELECOMMUNICATIONS, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="CMCSA", name="Comcast Corporation", industry=IndustrySector.TELECOMMUNICATIONS, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="DIS", name="The Walt Disney Company", industry=IndustrySector.TELECOMMUNICATIONS, market_cap=MarketCap.LARGE),

    # Utilities (3%)
    CompanyInfo(ticker="NEE", name="NextEra Energy Inc.", industry=IndustrySector.UTILITIES, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="DUK", name="Duke Energy Corporation", industry=IndustrySector.UTILITIES, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="SO", name="The Southern Company", industry=IndustrySector.UTILITIES, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="D", name="Dominion Energy Inc.", industry=IndustrySector.UTILITIES, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="AEP", name="American Electric Power Company Inc.", industry=IndustrySector.UTILITIES, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="EXC", name="Exelon Corporation", industry=IndustrySector.UTILITIES, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="SRE", name="Sempra Energy", industry=IndustrySector.UTILITIES, market_cap=MarketCap.MID),
    CompanyInfo(ticker="XEL", name="Xcel Energy Inc.", industry=IndustrySector.UTILITIES, market_cap=MarketCap.MID),

    # Transportation (2%)
    CompanyInfo(ticker="UPS", name="United Parcel Service Inc.", industry=IndustrySector.TRANSPORTATION, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="FDX", name="FedEx Corporation", industry=IndustrySector.TRANSPORTATION, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="UNP", name="Union Pacific Corporation", industry=IndustrySector.TRANSPORTATION, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="CSX", name="CSX Corporation", industry=IndustrySector.TRANSPORTATION, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="NSC", name="Norfolk Southern Corporation", industry=IndustrySector.TRANSPORTATION, market_cap=MarketCap.LARGE),
    CompanyInfo(ticker="DAL", name="Delta Air Lines Inc.", industry=IndustrySector.TRANSPORTATION, market_cap=MarketCap.MID),
]


# ===========================
# Stratified Sampler
# ===========================

class StratifiedSampler:
    """
    Intelligent stratified sampling for building topic modeling corpus
    """

    def __init__(self, config: DownloadConfig):
        self.config = config
        self.company_universe = COMPANY_UNIVERSE.copy()
        random.seed(42)  # Reproducibility

    def sample_companies(self) -> List[CompanyInfo]:
        """
        Sample companies using stratified sampling across industries
        """
        logger.info("=" * 80)
        logger.info("STRATIFIED SAMPLING FOR TOPIC MODELING CORPUS")
        logger.info("=" * 80)

        # Group companies by industry
        by_industry: Dict[IndustrySector, List[CompanyInfo]] = {}
        for company in self.company_universe:
            if company.industry not in by_industry:
                by_industry[company.industry] = []
            by_industry[company.industry].append(company)

        # Calculate target per industry
        sampled = []
        for industry, target_pct in self.config.industry_distribution.items():
            target_count = int(self.config.target_companies * target_pct)
            available = by_industry.get(industry, [])

            if len(available) < target_count:
                logger.warning(
                    f"{industry.value}: Only {len(available)} companies available, "
                    f"target was {target_count}"
                )
                sample_size = len(available)
            else:
                sample_size = target_count

            # Sample
            industry_sample = random.sample(available, sample_size)
            sampled.extend(industry_sample)

            logger.info(
                f"{industry.value:25s}: {len(industry_sample):3d} companies "
                f"({len(industry_sample)/self.config.target_companies*100:5.1f}%)"
            )

        logger.info(f"\nTotal companies sampled: {len(sampled)}")
        logger.info("=" * 80)

        return sampled


# ===========================
# EDGAR Downloader
# ===========================

class EdgarDownloader:
    """
    SEC EDGAR filing downloader using sec-edgar-downloader library

    Downloads filings as HTML files with naming format: {ticker}_{formtype}_{year}.html
    """

    def __init__(self, output_dir: Path, user_agent: str = None):
        """
        Initialize EDGAR downloader

        Args:
            output_dir: Directory to save downloaded filings (final location)
            user_agent: User agent string (required by SEC)
        """
        self.output_dir = output_dir
        self.temp_dir = output_dir / "temp_downloads"  # Temporary download location
        self.user_agent = user_agent or "SEC Filing Analyzer contact@example.com"

        # Try to import sec-edgar-downloader
        try:
            from sec_edgar_downloader import Downloader
            self.downloader = Downloader(
                company_name="SEC Filing Analyzer",
                email_address="contact@example.com",
                download_folder=str(self.temp_dir)
            )
            self.available = True
            logger.info(f"Initialized EDGAR downloader (output: {output_dir})")
        except ImportError:
            self.available = False
            logger.warning(
                "sec-edgar-downloader not installed. "
                "Install with: pip install sec-edgar-downloader"
            )

    def _extract_year_from_filing(self, filing_path: Path) -> Optional[str]:
        """
        Extract filing year from the filing content.

        Args:
            filing_path: Path to the filing file

        Returns:
            Year as string (e.g., "2023") or None
        """
        try:
            with open(filing_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(5000)  # Read first 5000 chars to find date

            # Look for filing date patterns
            # Pattern 1: FILED AS OF DATE: YYYYMMDD
            import re
            match = re.search(r'FILED AS OF DATE:\s*(\d{8})', content)
            if match:
                date_str = match.group(1)
                return date_str[:4]  # Extract year

            # Pattern 2: CONFORMED PERIOD OF REPORT: YYYYMMDD
            match = re.search(r'CONFORMED PERIOD OF REPORT:\s*(\d{8})', content)
            if match:
                date_str = match.group(1)
                return date_str[:4]

            # Pattern 3: Try to extract from filing path (accession number often contains date)
            # Path format: .../0000320193-23-000106/...
            match = re.search(r'-(\d{2})-\d+', filing_path.parent.name)
            if match:
                year_suffix = match.group(1)
                # Convert YY to YYYY
                year = int(year_suffix)
                full_year = 2000 + year if year < 50 else 1900 + year
                return str(full_year)

            return None

        except Exception as e:
            logger.debug(f"Could not extract year from {filing_path}: {e}")
            return None

    def _get_html_version(self, filing_dir: Path) -> Optional[Path]:
        """
        Find the HTML version of the filing.

        Args:
            filing_dir: Directory containing the filing

        Returns:
            Path to HTML file or None
        """
        # Look for common HTML filing names
        html_candidates = [
            filing_dir / "primary-document.html",
            filing_dir / "primary_doc.html",
            filing_dir / "filing.html",
        ]

        for candidate in html_candidates:
            if candidate.exists():
                return candidate

        # Look for any .html file
        html_files = list(filing_dir.glob("*.html"))
        if html_files:
            # Prefer the largest file (usually the main document)
            return max(html_files, key=lambda p: p.stat().st_size)

        # Fallback: look for .htm files
        htm_files = list(filing_dir.glob("*.htm"))
        if htm_files:
            return max(htm_files, key=lambda p: p.stat().st_size)

        return None

    def _convert_txt_to_html(self, txt_path: Path) -> str:
        """
        Convert .txt filing to basic HTML format.

        Args:
            txt_path: Path to .txt filing

        Returns:
            HTML content as string
        """
        try:
            with open(txt_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # Wrap in basic HTML structure
            html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>SEC Filing</title>
</head>
<body>
<pre>{content}</pre>
</body>
</html>"""
            return html_content

        except Exception as e:
            logger.error(f"Error converting {txt_path} to HTML: {e}")
            return ""

    def download_company_filings(
        self,
        company: CompanyInfo,
        form_type: str = "10-K",
        num_filings: int = 5,
        after_date: str = None,
        before_date: str = None
    ) -> int:
        """
        Download filings for a company and save as {ticker}_{formtype}_{year}.html

        Args:
            company: Company info
            form_type: SEC form type (10-K, 10-Q)
            num_filings: Number of filings to download
            after_date: Download filings after this date (YYYYMMDD)
            before_date: Download filings before this date (YYYYMMDD)

        Returns:
            Number of filings downloaded and renamed
        """
        if not self.available:
            logger.error("sec-edgar-downloader not available")
            return 0

        try:
            # Download filings to temp directory
            self.downloader.get(
                form_type,
                company.ticker,
                limit=num_filings,
                after=after_date,
                before=before_date,
                download_details=False  # Don't download supporting documents
            )

            # Find downloaded files
            company_dir = self.temp_dir / "sec-edgar-filings" / company.ticker / form_type
            if not company_dir.exists():
                logger.warning(f"  {company.ticker:6s}: No filings found")
                return 0

            # Process each filing subdirectory
            filing_dirs = [d for d in company_dir.iterdir() if d.is_dir()]
            count = 0

            for filing_dir in filing_dirs:
                try:
                    # Try to find HTML version
                    html_file = self._get_html_version(filing_dir)

                    if html_file:
                        # Use HTML file directly
                        with open(html_file, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                    else:
                        # Fallback: look for .txt file and convert
                        txt_file = filing_dir / "full-submission.txt"
                        if not txt_file.exists():
                            # Try primary-document.txt
                            txt_file = filing_dir / "primary-document.txt"

                        if txt_file.exists():
                            content = self._convert_txt_to_html(txt_file)
                        else:
                            logger.warning(f"  {company.ticker}: No valid filing file in {filing_dir.name}")
                            continue

                    # Extract year
                    year = self._extract_year_from_filing(html_file if html_file else txt_file)
                    if not year:
                        # Fallback: use current year
                        year = datetime.now().year
                        logger.debug(f"  {company.ticker}: Could not extract year, using {year}")

                    # Create output filename: {ticker}_{formtype}_{year}.html
                    form_clean = form_type.replace("-", "")  # 10-K -> 10K
                    output_filename = f"{company.ticker}_{form_clean}_{year}.html"
                    output_path = self.output_dir / output_filename

                    # Save file
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(content)

                    count += 1
                    logger.debug(f"  Saved: {output_filename}")

                except Exception as e:
                    logger.error(f"  {company.ticker}: Error processing {filing_dir.name}: {e}")
                    continue

            # Clean up temp directory for this company
            import shutil
            try:
                shutil.rmtree(company_dir)
            except Exception:
                pass

            logger.info(f"  {company.ticker:6s} ({company.industry.value:20s}): {count} filings")
            return count

        except Exception as e:
            logger.error(f"  {company.ticker:6s}: Error - {e}")
            return 0

    def download_batch(
        self,
        companies: List[CompanyInfo],
        form_type: str = "10-K",
        num_filings_per_company: int = 5,
        years_back: int = 5,
        rate_limit_delay: float = 0.1
    ) -> Dict[str, int]:
        """
        Download filings for multiple companies with rate limiting

        Args:
            companies: List of companies
            form_type: SEC form type
            num_filings_per_company: Max filings per company
            years_back: Years to look back
            rate_limit_delay: Delay between requests (seconds)

        Returns:
            Dict mapping ticker -> number of filings downloaded
        """
        logger.info(f"\nDownloading {form_type} filings for {len(companies)} companies...")
        logger.info(f"Target: {num_filings_per_company} filings per company, last {years_back} years")
        logger.info(f"Output: {self.output_dir} as {{ticker}}_{{form}}_{{year}}.html")
        logger.info("=" * 80)

        # Calculate date range
        today = datetime.now()
        after_date = (today - timedelta(days=years_back * 365)).strftime("%Y-%m-%d")

        results = {}
        total_downloaded = 0

        for i, company in enumerate(companies, 1):
            logger.info(f"[{i}/{len(companies)}] {company.name}")

            count = self.download_company_filings(
                company=company,
                form_type=form_type,
                num_filings=num_filings_per_company,
                after_date=after_date
            )

            results[company.ticker] = count
            total_downloaded += count

            # Rate limiting (SEC requires 10 requests/second max)
            time.sleep(rate_limit_delay)

        # Clean up temp directory
        self._cleanup_temp_dir()

        logger.info("=" * 80)
        logger.info(f"Total filings downloaded: {total_downloaded}")
        logger.info(f"Average per company: {total_downloaded/len(companies):.1f}")

        return results

    def _cleanup_temp_dir(self):
        """Clean up temporary download directory."""
        import shutil
        try:
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
                logger.debug("Cleaned up temporary download directory")
        except Exception as e:
            logger.warning(f"Could not clean up temp directory: {e}")


# ===========================
# Main Download Logic
# ===========================

def download_for_topic_modeling():
    """
    Download optimal corpus for topic modeling:
    - 1,000 documents target
    - 8-12 industries
    - 300 companies
    - 3-5 years
    """
    logger.info("\n" + "=" * 80)
    logger.info("DOWNLOADING SEC FILINGS FOR TOPIC MODELING")
    logger.info("=" * 80)

    # Configuration
    config = DownloadConfig(
        target_documents=1000,
        target_companies=300,
        years_back=5,
        form_type="10-K",
        filings_per_company=5  # To get ~1000 docs from 300 companies
    )

    logger.info(f"\nTarget Configuration:")
    logger.info(f"  Documents: {config.target_documents}")
    logger.info(f"  Companies: {config.target_companies}")
    logger.info(f"  Time range: Last {config.years_back} years")
    logger.info(f"  Form type: {config.form_type}")
    logger.info(f"  Industries: {len(config.industry_distribution)}")

    # Sample companies using stratified sampling
    sampler = StratifiedSampler(config)
    companies = sampler.sample_companies()

    # Save company list
    company_list_path = settings.paths.raw_data_dir / "company_list.json"
    settings.paths.ensure_directories()

    with open(company_list_path, 'w') as f:
        company_data = [c.model_dump() for c in companies]
        json.dump(company_data, f, indent=2, default=str)

    logger.info(f"\nSaved company list to: {company_list_path}")

    # Download filings
    downloader = EdgarDownloader(output_dir=settings.paths.raw_data_dir)

    if not downloader.available:
        logger.error("\n" + "=" * 80)
        logger.error("ERROR: sec-edgar-downloader not installed")
        logger.error("Install with: pip install sec-edgar-downloader")
        logger.error("=" * 80)
        return

    results = downloader.download_batch(
        companies=companies,
        form_type=config.form_type,
        num_filings_per_company=config.filings_per_company,
        years_back=config.years_back,
        rate_limit_delay=0.11  # ~9 requests/second (SEC limit is 10/sec)
    )

    # Summary statistics
    logger.info("\n" + "=" * 80)
    logger.info("DOWNLOAD SUMMARY")
    logger.info("=" * 80)

    total_filings = sum(results.values())
    companies_with_filings = sum(1 for count in results.values() if count > 0)

    logger.info(f"Total filings downloaded: {total_filings}")
    logger.info(f"Companies with filings: {companies_with_filings}/{len(companies)}")
    logger.info(f"Average per company: {total_filings/len(companies):.1f}")

    # Industry breakdown
    logger.info(f"\nFilings by industry:")
    by_industry: Dict[IndustrySector, int] = {}
    for company in companies:
        count = results.get(company.ticker, 0)
        if company.industry not in by_industry:
            by_industry[company.industry] = 0
        by_industry[company.industry] += count

    for industry, count in sorted(by_industry.items(), key=lambda x: x[1], reverse=True):
        pct = count / total_filings * 100 if total_filings > 0 else 0
        logger.info(f"  {industry.value:25s}: {count:4d} ({pct:5.1f}%)")

    # Save results
    results_path = settings.paths.raw_data_dir / "download_results.json"
    with open(results_path, 'w') as f:
        results_data = {
            'config': config.model_dump(),
            'total_filings': total_filings,
            'companies_with_filings': companies_with_filings,
            'results': results,
            'by_industry': {k.value: v for k, v in by_industry.items()}
        }
        json.dump(results_data, f, indent=2, default=str)

    logger.info(f"\nSaved results to: {results_path}")
    logger.info("\n" + "=" * 80)
    logger.info("DOWNLOAD COMPLETE")
    logger.info("=" * 80)


def download_custom(
    tickers: List[str],
    form_type: str = "10-K",
    num_filings: int = 5,
    years_back: int = 3
):
    """
    Download filings for custom list of tickers
    """
    # Create CompanyInfo objects (industry unknown)
    companies = [
        CompanyInfo(
            ticker=ticker,
            name=f"Company {ticker}",
            industry=IndustrySector.TECHNOLOGY,  # Default
            market_cap=MarketCap.LARGE
        )
        for ticker in tickers
    ]

    # Download
    downloader = EdgarDownloader(output_dir=settings.paths.raw_data_dir)
    results = downloader.download_batch(
        companies=companies,
        form_type=form_type,
        num_filings_per_company=num_filings,
        years_back=years_back
    )

    logger.info(f"\nTotal filings downloaded: {sum(results.values())}")


# ===========================
# CLI
# ===========================

def main():
    parser = argparse.ArgumentParser(
        description="Download SEC filings optimized for topic modeling",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download optimal corpus for topic modeling (1000 docs, 300 companies, 8-12 industries)
  python scripts/data_collection/download_sec_filings.py --mode topic-modeling

  # Download specific ticker
  python scripts/data_collection/download_sec_filings.py --ticker AAPL --years 3

  # Download from file
  python scripts/data_collection/download_sec_filings.py --ticker-file tickers.txt --years 5
        """
    )

    parser.add_argument(
        '--mode',
        type=str,
        choices=['topic-modeling', 'custom'],
        default='custom',
        help='Download mode: topic-modeling (optimal corpus) or custom (specify tickers)'
    )

    parser.add_argument(
        '--ticker',
        type=str,
        help='Single ticker symbol (e.g., AAPL)'
    )

    parser.add_argument(
        '--ticker-file',
        type=str,
        help='Path to file containing ticker symbols (one per line)'
    )

    parser.add_argument(
        '--form-type',
        type=str,
        default='10-K',
        choices=['10-K', '10-Q'],
        help='Type of SEC form (default: 10-K)'
    )

    parser.add_argument(
        '--years',
        type=int,
        default=5,
        help='Years to look back (default: 5)'
    )

    parser.add_argument(
        '--num-filings',
        type=int,
        default=5,
        help='Max filings per ticker (default: 5)'
    )

    args = parser.parse_args()

    # Mode: Topic Modeling
    if args.mode == 'topic-modeling':
        download_for_topic_modeling()
        return

    # Mode: Custom
    tickers = []
    if args.ticker:
        tickers = [args.ticker.upper()]
    elif args.ticker_file:
        ticker_file = Path(args.ticker_file)
        if not ticker_file.exists():
            logger.error(f"Ticker file not found: {ticker_file}")
            sys.exit(1)
        with open(ticker_file, 'r') as f:
            tickers = [line.strip().upper() for line in f if line.strip()]
    else:
        parser.error("For custom mode, either --ticker or --ticker-file must be provided")

    download_custom(
        tickers=tickers,
        form_type=args.form_type,
        num_filings=args.num_filings,
        years_back=args.years
    )


if __name__ == "__main__":
    main()

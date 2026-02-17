"""Preprocessing modules for SEC filings

Pipeline Flow:
    1. Sanitize → HTMLSanitizer → cleaned HTML (NEW)
    2. Parse    → SECFilingParser → ParsedFiling
    3. Extract  → SECSectionExtractor → ExtractedSection
    4. Clean    → TextCleaner → cleaned text
    5. Segment  → RiskSegmenter → SegmentedRisks

All metadata (sic_code, sic_name, cik, ticker, company_name) is preserved
throughout the pipeline.

Quick Start:
    >>> from src.preprocessing import process_filing
    >>> result = process_filing("data/raw/AAPL_10K.html")
    >>> print(f"Company: {result.company_name}, SIC: {result.sic_name}")
    >>> print(f"Segments: {len(result)}")
"""

# Data models (canonical location) - TEMPORARILY COMMENTED OUT
# from .models import ParsedFiling, FormType, ExtractedSection, RiskSegment, SegmentedRisks

from .sanitizer import HTMLSanitizer, SanitizerConfig, sanitize_html
from .parser import SECFilingParser, parse_filing_from_path
from .cleaning import TextCleaner, clean_filing_text
from .extractor import (
    SECSectionExtractor,
    ExtractedSection,
    RiskFactorExtractor,
)
from .segmenter import (
    RiskSegmenter,
    RiskSegment,
    SegmentedRisks,
    segment_risk_factors,
)
from .pipeline import (
    SECPreprocessingPipeline,
    PipelineConfig,
    process_filing,
)
from .constants import SectionIdentifier

__all__ = [
    # Sanitizer (NEW)
    'HTMLSanitizer',
    'SanitizerConfig',
    'sanitize_html',
    # Parser
    'SECFilingParser',
    # 'ParsedFiling',  # Commented - import from parser directly
    # 'FormType',  # Commented - import from parser directly
    'parse_filing_from_path',
    # Cleaner
    'TextCleaner',
    'clean_filing_text',
    # Extractor
    'SECSectionExtractor',
    'ExtractedSection',
    'RiskFactorExtractor',
    # Segmenter
    'RiskSegmenter',
    'RiskSegment',
    'SegmentedRisks',
    'segment_risk_factors',
    # Pipeline
    'SECPreprocessingPipeline',
    'PipelineConfig',
    'process_filing',
    # Constants
    'SectionIdentifier',
]

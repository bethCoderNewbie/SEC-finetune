"""Preprocessing modules for SEC filings

Pipeline Flow (ADR-010):
    0. SGML Manifest → extract_sgml_manifest → SGMLManifest (header + byte index)
    1. Pre-seek  → AnchorPreSeeker → ~50-200 KB HTML slice
    2. Parse     → SECFilingParser → ParsedFiling
    3. Extract   → SECSectionExtractor → ExtractedSection
    4. Clean     → TextCleaner → cleaned text
    5. Segment   → RiskSegmenter → SegmentedRisks

All metadata (sic_code, sic_name, cik, ticker, company_name, accession_number,
filed_as_of_date) is preserved throughout the pipeline.

Quick Start:
    >>> from src.preprocessing import process_filing
    >>> result = process_filing("data/raw/AAPL_10K.html")
    >>> print(f"Company: {result.company_name}, SIC: {result.sic_name}")
    >>> print(f"Segments: {len(result)}")
"""

# Data models (canonical location) - TEMPORARILY COMMENTED OUT
# from .models import ParsedFiling, FormType, ExtractedSection, RiskSegment, SegmentedRisks

from .sgml_manifest import extract_sgml_manifest, extract_document
from .models.sgml import SGMLManifest, SGMLHeader, DocumentEntry
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
    # Stage 0: SGML manifest (ADR-010)
    'extract_sgml_manifest',
    'extract_document',
    'SGMLManifest',
    'SGMLHeader',
    'DocumentEntry',
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

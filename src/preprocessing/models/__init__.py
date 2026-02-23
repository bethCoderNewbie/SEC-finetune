"""
Pydantic data models for SEC preprocessing pipeline.

Organized by preprocessing stage:
- parsing: ParsedFiling, FormType
- extraction: ExtractedSection
- segmentation: RiskSegment, SegmentedRisks
- sgml: SGMLManifest, SGMLHeader, DocumentEntry (Stage 0 — ADR-010)
"""
from .parsing import ParsedFiling, FormType
from .extraction import ExtractedSection
from .segmentation import RiskSegment, SegmentedRisks
from .sgml import SGMLManifest, SGMLHeader, DocumentEntry

__all__ = [
    'ParsedFiling',
    'FormType',
    'ExtractedSection',
    'RiskSegment',
    'SegmentedRisks',
    'SGMLManifest',
    'SGMLHeader',
    'DocumentEntry',
]

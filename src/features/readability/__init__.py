"""
Readability and Text Complexity Analysis Module

This package contains components for measuring text readability and complexity
in SEC filings. Text complexity is a known proxy for risk - harder-to-read
filings are associated with higher future volatility and negative outcomes.

Key Components:
- ReadabilityAnalyzer: Main feature extractor
- ReadabilityFeatures: Pydantic model for features
- ReadabilityAnalysisResult: Features + metadata
- FINANCIAL_COMMON_WORDS: Domain exception list

Usage:
    from src.features.readability import ReadabilityAnalyzer

    analyzer = ReadabilityAnalyzer()
    features = analyzer.extract_features(cleaned_text)
    print(f"Gunning Fog: {features.gunning_fog_index}")
    print(f"Obfuscation Score: {features.obfuscation_score}")
"""

from .analyzer import ReadabilityAnalyzer
from .schemas import (
    ReadabilityFeatures,
    ReadabilityAnalysisMetadata,
    ReadabilityAnalysisResult,
)
from .constants import (
    FINANCIAL_COMMON_WORDS,
    READABILITY_MODULE_VERSION,
    STANDARD_READABILITY_INDICES,
    READABILITY_BENCHMARKS,
    SEC_10K_TYPICAL_RANGES,
)

__all__ = [
    # Main classes
    "ReadabilityAnalyzer",
    "ReadabilityFeatures",
    "ReadabilityAnalysisMetadata",
    "ReadabilityAnalysisResult",
    # Constants
    "FINANCIAL_COMMON_WORDS",
    "READABILITY_MODULE_VERSION",
    "STANDARD_READABILITY_INDICES",
    "READABILITY_BENCHMARKS",
    "SEC_10K_TYPICAL_RANGES",
]

__version__ = READABILITY_MODULE_VERSION

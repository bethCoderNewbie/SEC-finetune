"""
Immutable constants for readability and text complexity analysis.

This module contains version-controlled metadata and reference data.
These values should NEVER change at runtime - they define WHAT readability analysis IS.

Constants include:
- Readability indices metadata (versions, citations, descriptions)
- Financial domain exception lists (common 3+ syllable words)
- Complexity thresholds and benchmarks
- Feature categories

For runtime configuration (HOW to use readability), see configs/features/readability.yaml
"""

from typing import Final

# ===========================
# Module Metadata
# ===========================

READABILITY_MODULE_VERSION: Final[str] = "1.0.0"
"""Version of the readability analysis module."""

READABILITY_MODULE_DESCRIPTION: Final[str] = (
    "Text complexity and readability analysis for SEC filings. "
    "Measures obfuscation as a proxy for financial risk."
)
"""Module description."""

# ===========================
# Academic Citations
# ===========================

READABILITY_CITATIONS: Final[dict[str, str]] = {
    "li_2008": (
        "Li, F. (2008). Annual report readability, current earnings, and earnings persistence. "
        "Journal of Accounting and Economics, 45(2-3), 221-247."
    ),
    "loughran_mcdonald_2014": (
        "Loughran, T. and McDonald, B. (2014). Measuring readability in financial disclosures. "
        "Journal of Finance, 69(4), 1643-1671."
    ),
    "flesch_1948": (
        "Flesch, R. (1948). A new readability yardstick. "
        "Journal of Applied Psychology, 32(3), 221."
    ),
    "gunning_1952": (
        "Gunning, R. (1952). The Technique of Clear Writing. "
        "McGraw-Hill."
    ),
}
"""Academic citations for readability research."""

# ===========================
# Readability Indices Metadata
# ===========================

STANDARD_READABILITY_INDICES: Final[tuple[str, ...]] = (
    "flesch_kincaid_grade",
    "gunning_fog_index",
    "flesch_reading_ease",
    "smog_index",
    "automated_readability_index",
    "coleman_liau_index",
)
"""Standard readability indices computed by the analyzer."""

READABILITY_INDEX_DESCRIPTIONS: Final[dict[str, str]] = {
    "flesch_kincaid_grade": (
        "U.S. school grade level based on sentence length and syllables per word. "
        "Formula: 0.39 × (words/sentences) + 11.8 × (syllables/words) - 15.59. "
        "Most widely used in research. Target: 10-12 for investor-friendly documents."
    ),
    "gunning_fog_index": (
        "U.S. grade level based on sentence length and complex words (3+ syllables). "
        "Formula: 0.4 × [(words/sentences) + 100 × (complex_words/words)]. "
        "Better for business/technical writing. Typical 10-K: 14-18."
    ),
    "flesch_reading_ease": (
        "Reading ease score (0-100). Higher = easier to read. "
        "90-100: Very Easy (5th grade), 60-70: Standard (8th-9th grade), "
        "30-50: Difficult (College), 0-30: Very Difficult (College graduate)."
    ),
    "smog_index": (
        "Simple Measure of Gobbledygook. Estimates years of education needed. "
        "Based on polysyllabic words (3+ syllables)."
    ),
    "automated_readability_index": (
        "Automated Readability Index (ARI). Based on characters per word "
        "and words per sentence. Outputs U.S. grade level."
    ),
    "coleman_liau_index": (
        "Coleman-Liau Index. Based on characters rather than syllables. "
        "Outputs U.S. grade level."
    ),
}
"""Descriptions and formulas for each readability index."""

# ===========================
# Financial Domain Exception List
# ===========================
# Common 3+ syllable words in financial documents that should NOT be
# considered "complex" for Gunning Fog purposes.
#
# Rationale: The Gunning Fog 3+ syllable rule was designed for general text.
# In financial documents, many domain-specific terms (e.g., "investment",
# "management") are so common that they should not count as "difficult".
#
# This list was curated from:
# 1. Loughran-McDonald financial word lists
# 2. SEC EDGAR most frequent terms
# 3. Financial reporting standards glossaries
# 4. Manual review of 100+ 10-K filings

FINANCIAL_COMMON_WORDS: Final[frozenset[str]] = frozenset({
    # ===========================
    # Core Business Terms
    # ===========================
    "investment", "investments", "investor", "investors", "investing",
    "management", "manager", "managers", "managing",
    "financial", "financing", "financed",
    "company", "companies", "companion",
    "accounting", "accountant", "accountants",
    "business", "businesses",
    "industry", "industries", "industrial",
    "security", "securities",
    "property", "properties",
    "liability", "liabilities",
    "equity", "equities",
    "revenue", "revenues",
    "operating", "operation", "operations", "operational",
    "organizational", "organization", "organizations",
    "commercial", "commercialize", "commercialization",
    "government", "governmental",
    "development", "developer", "developers", "developing",
    "technology", "technologies", "technological",
    "equipment",
    "acquisition", "acquisitions",
    "subsidiary", "subsidiaries",
    "regulatory", "regulation", "regulations", "regulate", "regulated",
    "strategic", "strategy", "strategies",
    "capital", "capitalize", "capitalization", "capitalized",
    "corporate", "corporation", "corporations",
    "enterprise", "enterprises",
    "customer", "customers",
    "supplier", "suppliers",
    "employee", "employees", "employment",

    # ===========================
    # Financial Metrics & Accounting
    # ===========================
    "amortization", "amortize", "amortized",
    "depreciation", "depreciate", "depreciated",
    "valuation", "valuate", "valuated",
    "inventory", "inventories",
    "receivables", "receivable",
    "payables", "payable",
    "dividends", "dividend",
    "earnings",
    "premium", "premiums",
    "interest", "interests",
    "principal", "principals",
    "material", "materials", "materially",
    "significant", "significantly", "significance",
    "substantial", "substantially",
    "impairment", "impaired",
    "accrual", "accruals", "accrued",
    "estimates", "estimated", "estimating",

    # ===========================
    # SEC/Legal Terms
    # ===========================
    "director", "directors", "directorate",
    "officer", "officers",
    "attorney", "attorneys",
    "agreement", "agreements",
    "amendment", "amendments", "amended",
    "provision", "provisions", "provisional",
    "warranty", "warranties",
    "indemnity", "indemnify", "indemnification",
    "compliance", "compliant",
    "violation", "violations", "violate",
    "litigation", "litigate", "litigated",
    "arbitration", "arbitrate",
    "disclosure", "disclose", "disclosed", "disclosing",
    "registration", "register", "registered",

    # ===========================
    # Time Periods
    # ===========================
    "quarterly", "quarter", "quarters",
    "annually", "annual",
    "fiscal",
    "december", "november", "september", "october",
    "january", "february", "april", "august",

    # ===========================
    # Common Business Verbs
    # ===========================
    "evaluate", "evaluating", "evaluated", "evaluation",
    "determine", "determining", "determined", "determination",
    "consider", "considering", "considered", "consideration",
    "identify", "identifying", "identified", "identification",
    "analyze", "analyzing", "analyzed", "analysis",
    "recognize", "recognizing", "recognized", "recognition",
    "establish", "establishing", "established", "establishment",
    "implement", "implementing", "implemented", "implementation",
    "generate", "generating", "generated", "generation",
    "provide", "providing", "provided",
    "require", "requiring", "required", "requirement", "requirements",
    "represent", "representing", "represented", "representation",
    "indicate", "indicating", "indicated", "indication",

    # ===========================
    # Geographic/Entities
    # ===========================
    "america", "american",
    "united",
    "federal",
    "delaware",
    "california",
    "virginia",
    "international",

    # ===========================
    # General Business
    # ===========================
    "available", "availability",
    "possible", "possibly", "possibility",
    "probable", "probably", "probability",
    "potential", "potentially",
    "continue", "continuing", "continued", "continuation",
    "additional", "additionally",
    "approximate", "approximately", "approximation",
    "estimate", "estimates", "estimated",
    "primarily", "primary",
    "generally", "general",
    "specifically", "specific",
    "particular", "particularly",
    "respective", "respectively",
    "various",
    "similar", "similarly", "similarity",
    "different", "differently", "difference", "differences",
})
"""
Common 3+ syllable words in financial documents that should not be
considered complex for readability calculations.

This set is used to adjust the Gunning Fog Index for the financial domain.
"""

# Count for logging/validation
FINANCIAL_COMMON_WORDS_COUNT: Final[int] = len(FINANCIAL_COMMON_WORDS)


# ===========================
# Complexity Thresholds
# ===========================
# Benchmarks based on empirical research on SEC filings

READABILITY_BENCHMARKS: Final[dict[str, dict[str, float]]] = {
    "flesch_kincaid_grade": {
        "very_easy": 6.0,
        "easy": 8.0,
        "standard": 10.0,
        "difficult": 14.0,
        "very_difficult": 18.0,
    },
    "gunning_fog_index": {
        "very_easy": 8.0,
        "easy": 10.0,
        "standard": 12.0,
        "difficult": 16.0,
        "very_difficult": 20.0,
    },
    "flesch_reading_ease": {
        "very_difficult": 30.0,
        "difficult": 50.0,
        "standard": 60.0,
        "easy": 70.0,
        "very_easy": 90.0,
    },
}
"""Benchmark thresholds for interpreting readability scores."""

# Typical ranges for SEC 10-K filings (based on empirical studies)
SEC_10K_TYPICAL_RANGES: Final[dict[str, tuple[float, float]]] = {
    "flesch_kincaid_grade": (12.0, 16.0),
    "gunning_fog_index": (14.0, 18.0),
    "flesch_reading_ease": (30.0, 50.0),
    "avg_sentence_length": (20.0, 30.0),
    "pct_complex_words": (15.0, 25.0),
}
"""Typical value ranges for 10-K filings."""

# ===========================
# Sentence Complexity Thresholds
# ===========================

LONG_SENTENCE_THRESHOLD: Final[int] = 30
"""Number of words that define a 'long' sentence (potential run-on)."""

SHORT_PARAGRAPH_THRESHOLD: Final[int] = 3
"""Number of sentences that define a 'short' paragraph (easier to scan)."""

# ===========================
# Feature Categories
# ===========================

READABILITY_FEATURE_CATEGORIES: Final[tuple[str, ...]] = (
    "basic_statistics",
    "standard_indices",
    "structural_complexity",
    "complex_words",
    "sentence_variety",
    "aggregate_scores",
)
"""Categories of readability features extracted by the analyzer."""

# ===========================
# Risk Signal Thresholds
# ===========================
# Used for the custom obfuscation score

OBFUSCATION_SCORE_THRESHOLDS: Final[dict[str, float]] = {
    "low_risk": 40.0,          # Score < 40: Clear and readable
    "moderate_risk": 60.0,     # Score 40-60: Typical 10-K complexity
    "high_risk": 75.0,         # Score 60-75: Elevated complexity
    "very_high_risk": 85.0,    # Score > 85: Potential obfuscation
}
"""Thresholds for interpreting the custom obfuscation score (0-100)."""

# ===========================
# Validation Constants
# ===========================

MIN_TEXT_LENGTH_FOR_ANALYSIS: Final[int] = 100
"""Minimum character length for meaningful readability analysis."""

MIN_WORD_COUNT_FOR_ANALYSIS: Final[int] = 30
"""Minimum word count for meaningful readability analysis."""

MIN_SENTENCE_COUNT_FOR_ANALYSIS: Final[int] = 3
"""Minimum sentence count for meaningful readability analysis."""

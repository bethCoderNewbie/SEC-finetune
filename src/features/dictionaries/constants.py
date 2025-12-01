"""
Immutable constants for Loughran-McDonald Master Dictionary.

This module contains version-controlled metadata that defines the dictionary structure.
These values should NEVER change at runtime - they define WHAT the dictionary IS.

Constants include:
- Dictionary metadata (version, citation, source)
- Feature categories (schema definition)
- CSV column mappings (for preprocessing)
- File naming conventions

For runtime configuration (HOW to use the dictionary), see configs/features/sentiment.yaml
"""

from typing import Final

# ===========================
# Dictionary Metadata
# ===========================

LM_DICTIONARY_VERSION: Final[str] = "1993-2024"
"""Version of the Loughran-McDonald Master Dictionary."""

LM_DICTIONARY_CITATION: Final[str] = (
    "Loughran, T. and McDonald, B. (2011). "
    "When is a Liability not a Liability? Textual Analysis, Dictionaries, and 10-Ks. "
    "Journal of Finance, 66(1), 35-65."
)
"""Academic citation for the dictionary."""

LM_SOURCE_URL: Final[str] = "https://sraf.nd.edu/loughranmcdonald-master-dictionary/"
"""Official source URL for the dictionary."""

# ===========================
# Feature Categories (Schema)
# ===========================

LM_FEATURE_CATEGORIES: Final[tuple[str, ...]] = (
    "Negative",
    "Positive",
    "Uncertainty",
    "Litigious",
    "Strong_Modal",
    "Weak_Modal",
    "Constraining",
    "Complexity"
)
"""
All available sentiment categories in the LM dictionary.
These define the complete schema - settings can use a subset.
"""

# ===========================
# CSV Schema Definition
# ===========================

LM_CSV_COLUMNS: Final[dict[str, str]] = {
    "word": "Word",
    "negative": "Negative",
    "positive": "Positive",
    "uncertainty": "Uncertainty",
    "litigious": "Litigious",
    "strong_modal": "Strong_Modal",
    "weak_modal": "Weak_Modal",
    "constraining": "Constraining",
    "complexity": "Complexity"
}
"""Mapping of internal names to CSV column names."""

LM_REQUIRED_COLUMNS: Final[frozenset[str]] = frozenset([
    "Word",
    "Negative",
    "Positive",
    "Uncertainty",
    "Litigious"
])
"""Minimum required columns for a valid LM dictionary CSV."""

# ===========================
# File Naming
# ===========================

LM_SOURCE_CSV_FILENAME: Final[str] = "Loughran-McDonald_MasterDictionary_1993-2024.csv"
"""Original CSV filename from Loughran-McDonald."""

LM_CACHE_FILENAME: Final[str] = "lm_dictionary_cache.pkl"
"""Preprocessed dictionary cache filename (fast loading)."""

# ===========================
# Dictionary Statistics (Reference)
# ===========================

LM_APPROX_WORD_COUNT: Final[int] = 4000
"""Approximate number of sentiment-categorized words in the dictionary (for validation).
Note: The full CSV has ~86,000 words, but only ~4,000 have sentiment category assignments."""

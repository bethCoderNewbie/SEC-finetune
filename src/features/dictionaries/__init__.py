"""
Loughran-McDonald Dictionary Management

This package handles loading, caching, and accessing the Loughran-McDonald
Master Dictionary for financial sentiment analysis.

Key components:
- constants: Immutable metadata (version, categories, file names)
- schemas: Pydantic models for type-safe data structures
- lm_dictionary: Dictionary manager with caching and singleton pattern

Usage:
    from src.features.dictionaries import LMDictionaryManager

    # Get singleton instance (loads dictionary on first access)
    manager = LMDictionaryManager.get_instance()

    # Check if word is negative
    if manager.is_negative("loss"):
        print("'loss' is a negative word")

    # Get all categories for a word
    categories = manager.get_word_categories("uncertain")
"""

from .constants import (
    LM_DICTIONARY_VERSION,
    LM_FEATURE_CATEGORIES,
    LM_CSV_COLUMNS,
    LM_REQUIRED_COLUMNS,
    LM_SOURCE_CSV_FILENAME,
    LM_CACHE_FILENAME,
    LM_APPROX_WORD_COUNT,
    LM_DICTIONARY_CITATION,
    LM_SOURCE_URL,
)

from .schemas import (
    LMDictionaryEntry,
    LMDictionaryMetadata,
    LMDictionary,
)

from .lm_dictionary import LMDictionaryManager

__all__ = [
    # Constants
    "LM_DICTIONARY_VERSION",
    "LM_FEATURE_CATEGORIES",
    "LM_CSV_COLUMNS",
    "LM_REQUIRED_COLUMNS",
    "LM_SOURCE_CSV_FILENAME",
    "LM_CACHE_FILENAME",
    "LM_APPROX_WORD_COUNT",
    "LM_DICTIONARY_CITATION",
    "LM_SOURCE_URL",
    # Schemas
    "LMDictionaryEntry",
    "LMDictionaryMetadata",
    "LMDictionary",
    # Manager
    "LMDictionaryManager",
]

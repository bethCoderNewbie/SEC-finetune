"""
Loughran-McDonald Dictionary Manager

This module manages loading, caching, and accessing the LM dictionary.
Uses singleton pattern to ensure dictionary is loaded only once per session.

The manager handles:
1. Loading preprocessed dictionary from pickle cache (fast)
2. Fallback to CSV loading if cache doesn't exist
3. In-memory caching for maximum performance
4. Convenience methods for word lookup
"""

import pickle
import time
from pathlib import Path
from typing import Optional, Set, Dict
import logging

from .constants import (
    LM_FEATURE_CATEGORIES,
    LM_CACHE_FILENAME,
    LM_DICTIONARY_VERSION,
    LM_APPROX_WORD_COUNT,
)
from .schemas import LMDictionary, LMDictionaryMetadata

logger = logging.getLogger(__name__)


class LMDictionaryManager:
    """
    Singleton manager for Loughran-McDonald dictionary.

    This class ensures the dictionary is loaded only once and provides
    convenient methods for word lookups and category checks.

    Usage:
        manager = LMDictionaryManager.get_instance()
        is_neg = manager.is_negative("loss")
        categories = manager.get_word_categories("uncertain")
    """

    _instance: Optional['LMDictionaryManager'] = None
    _dictionary: Optional[LMDictionary] = None

    def __init__(self, dictionary_path: Optional[Path] = None):
        """
        Initialize dictionary manager.

        Args:
            dictionary_path: Path to dictionary cache file.
                           If None, will be loaded from settings.
        """
        self._dictionary_path = dictionary_path
        self._loaded = False

    @classmethod
    def get_instance(cls, dictionary_path: Optional[Path] = None) -> 'LMDictionaryManager':
        """
        Get singleton instance of dictionary manager.

        Args:
            dictionary_path: Path to dictionary cache. Only used on first call.

        Returns:
            Singleton instance of LMDictionaryManager
        """
        if cls._instance is None:
            cls._instance = cls(dictionary_path)
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """Reset singleton instance (useful for testing)."""
        cls._instance = None
        cls._dictionary = None

    def load_dictionary(self, force_reload: bool = False) -> LMDictionary:
        """
        Load dictionary from cache.

        Args:
            force_reload: If True, reload even if already loaded

        Returns:
            Loaded LMDictionary object

        Raises:
            FileNotFoundError: If dictionary cache doesn't exist
            ValueError: If dictionary validation fails
        """
        if self._dictionary is not None and not force_reload:
            logger.debug("Dictionary already loaded, returning cached version")
            return self._dictionary

        if self._dictionary_path is None:
            # Import here to avoid circular dependency
            from src.config import settings
            self._dictionary_path = settings.paths.lm_dictionary_cache

        if not self._dictionary_path.exists():
            raise FileNotFoundError(
                f"Dictionary cache not found at {self._dictionary_path}. "
                f"Please run preprocessing script: "
                f"python scripts/feature_engineering/utils/preprocess_lm_dict.py"
            )

        logger.info(f"Loading LM dictionary from {self._dictionary_path}")
        start_time = time.time()

        with open(self._dictionary_path, 'rb') as f:
            self._dictionary = pickle.load(f)

        load_time = time.time() - start_time
        logger.info(
            f"Dictionary loaded successfully in {load_time:.3f}s: "
            f"{len(self._dictionary)} words, "
            f"version {self._dictionary.metadata.version}"
        )

        # Validation
        self._validate_dictionary()

        self._loaded = True
        return self._dictionary

    def _validate_dictionary(self):
        """Validate loaded dictionary."""
        if self._dictionary is None:
            raise ValueError("Dictionary not loaded")

        # Check word count is reasonable
        word_count = len(self._dictionary)
        if word_count < LM_APPROX_WORD_COUNT * 0.8:
            logger.warning(
                f"Dictionary has {word_count} words, expected ~{LM_APPROX_WORD_COUNT}. "
                f"Dictionary may be incomplete."
            )

        # Check all expected categories present in metadata
        expected_cats = set(LM_FEATURE_CATEGORIES)
        actual_cats = set(self._dictionary.metadata.categories)
        if expected_cats != actual_cats:
            missing = expected_cats - actual_cats
            extra = actual_cats - expected_cats
            msg = []
            if missing:
                msg.append(f"Missing categories: {missing}")
            if extra:
                msg.append(f"Extra categories: {extra}")
            logger.warning(f"Category mismatch: {', '.join(msg)}")

    @property
    def dictionary(self) -> LMDictionary:
        """
        Get loaded dictionary, loading if necessary.

        Returns:
            LMDictionary object
        """
        if self._dictionary is None:
            self.load_dictionary()
        return self._dictionary

    def get_word_categories(self, word: str, case_sensitive: bool = False) -> Set[str]:
        """
        Get all categories a word belongs to.

        Args:
            word: The word to lookup
            case_sensitive: If False (default), converts to uppercase

        Returns:
            Set of category names (e.g., {"Negative", "Uncertainty"})
        """
        return self.dictionary.get_word_categories(word, case_sensitive)

    def is_in_category(self, word: str, category: str, case_sensitive: bool = False) -> bool:
        """
        Check if word belongs to a specific category.

        Args:
            word: The word to check
            category: Category name (must be in LM_FEATURE_CATEGORIES)
            case_sensitive: If False (default), converts to uppercase

        Returns:
            True if word is in category, False otherwise
        """
        return self.dictionary.is_in_category(word, category, case_sensitive)

    # Convenience methods for common categories
    def is_negative(self, word: str, case_sensitive: bool = False) -> bool:
        """Check if word is negative."""
        return self.is_in_category(word, "Negative", case_sensitive)

    def is_positive(self, word: str, case_sensitive: bool = False) -> bool:
        """Check if word is positive."""
        return self.is_in_category(word, "Positive", case_sensitive)

    def is_uncertain(self, word: str, case_sensitive: bool = False) -> bool:
        """Check if word expresses uncertainty."""
        return self.is_in_category(word, "Uncertainty", case_sensitive)

    def is_litigious(self, word: str, case_sensitive: bool = False) -> bool:
        """Check if word is litigious."""
        return self.is_in_category(word, "Litigious", case_sensitive)

    def is_constraining(self, word: str, case_sensitive: bool = False) -> bool:
        """Check if word is constraining."""
        return self.is_in_category(word, "Constraining", case_sensitive)

    def get_category_words(self, category: str) -> Set[str]:
        """
        Get all words in a specific category.

        Args:
            category: Category name (must be in LM_FEATURE_CATEGORIES)

        Returns:
            Set of words in that category
        """
        return self.dictionary.get_category_words(category)

    def get_metadata(self) -> LMDictionaryMetadata:
        """Get dictionary metadata."""
        return self.dictionary.metadata

    def get_summary(self) -> str:
        """Get human-readable summary of dictionary."""
        return self.dictionary.metadata.get_summary()

    def __len__(self) -> int:
        """Return number of words in dictionary."""
        return len(self.dictionary)

    def __contains__(self, word: str) -> bool:
        """Check if word exists in dictionary (case-insensitive)."""
        return word.upper() in self.dictionary.words

    def __repr__(self) -> str:
        """String representation."""
        if self._dictionary is None:
            return f"<LMDictionaryManager (not loaded)>"
        return f"<LMDictionaryManager ({len(self)} words, v{LM_DICTIONARY_VERSION})>"

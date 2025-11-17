"""
Data structures for Loughran-McDonald dictionary.

This module defines the shape of data using Pydantic models.
These schemas enforce type safety and validation throughout the pipeline.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Dict, Set
from datetime import datetime
from .constants import LM_FEATURE_CATEGORIES, LM_DICTIONARY_VERSION


class LMDictionaryEntry(BaseModel):
    """
    Single word entry in the Loughran-McDonald dictionary.

    Each entry contains the word and binary flags (0 or 1) indicating
    whether the word belongs to each sentiment category.
    """
    word: str = Field(..., description="The word (typically uppercase)")
    negative: int = Field(default=0, ge=0, le=1)
    positive: int = Field(default=0, ge=0, le=1)
    uncertainty: int = Field(default=0, ge=0, le=1)
    litigious: int = Field(default=0, ge=0, le=1)
    strong_modal: int = Field(default=0, ge=0, le=1)
    weak_modal: int = Field(default=0, ge=0, le=1)
    constraining: int = Field(default=0, ge=0, le=1)
    complexity: int = Field(default=0, ge=0, le=1)

    @field_validator('word')
    @classmethod
    def word_must_not_be_empty(cls, v: str) -> str:
        """Ensure word is not empty and normalize to uppercase."""
        if not v.strip():
            raise ValueError('Word cannot be empty')
        return v.strip().upper()

    def get_categories(self) -> Set[str]:
        """Return set of categories this word belongs to."""
        categories = set()
        for category in LM_FEATURE_CATEGORIES:
            attr_name = category.lower()
            if getattr(self, attr_name, 0) == 1:
                categories.add(category)
        return categories


class LMDictionaryMetadata(BaseModel):
    """
    Metadata about the loaded dictionary.

    Tracks dictionary version, loading statistics, and configuration
    for auditability and debugging.
    """
    version: str = Field(default=LM_DICTIONARY_VERSION)
    total_words: int = Field(..., gt=0)
    category_counts: Dict[str, int] = Field(
        ...,
        description="Number of words in each category"
    )
    load_time_seconds: float = Field(..., ge=0)
    source_file: str = Field(..., description="Path to source file")
    loaded_at: datetime = Field(default_factory=datetime.now)
    categories: tuple[str, ...] = Field(default=LM_FEATURE_CATEGORIES)

    @field_validator('category_counts')
    @classmethod
    def validate_category_counts(cls, v: Dict[str, int]) -> Dict[str, int]:
        """Ensure category counts match known categories."""
        unknown = set(v.keys()) - set(LM_FEATURE_CATEGORIES)
        if unknown:
            raise ValueError(f"Unknown categories in counts: {unknown}")
        return v

    def get_summary(self) -> str:
        """Return human-readable summary of dictionary."""
        return (
            f"Loughran-McDonald Dictionary v{self.version}\n"
            f"Total words: {self.total_words:,}\n"
            f"Categories: {', '.join(self.categories)}\n"
            f"Loaded from: {self.source_file}\n"
            f"Load time: {self.load_time_seconds:.3f}s"
        )


class LMDictionary(BaseModel):
    """
    Complete Loughran-McDonald dictionary with metadata.

    This is the main data structure returned by the dictionary manager.
    It combines the word-to-categories mapping with metadata for auditability.
    """
    # Dictionary data: word -> set of categories
    words: Dict[str, Set[str]] = Field(
        ...,
        description="Mapping of words to their sentiment categories"
    )

    # Metadata
    metadata: LMDictionaryMetadata = Field(
        ...,
        description="Dictionary metadata and statistics"
    )

    def get_word_categories(self, word: str, case_sensitive: bool = False) -> Set[str]:
        """
        Get categories for a word.

        Args:
            word: The word to lookup
            case_sensitive: If False (default), converts to uppercase

        Returns:
            Set of category names, empty set if word not found
        """
        lookup_word = word if case_sensitive else word.upper()
        return self.words.get(lookup_word, set())

    def is_in_category(self, word: str, category: str, case_sensitive: bool = False) -> bool:
        """
        Check if a word belongs to a specific category.

        Args:
            word: The word to check
            category: Category name (e.g., "Negative", "Positive")
            case_sensitive: If False (default), converts to uppercase

        Returns:
            True if word is in the category, False otherwise
        """
        if category not in LM_FEATURE_CATEGORIES:
            raise ValueError(f"Invalid category: {category}. Must be one of {LM_FEATURE_CATEGORIES}")

        categories = self.get_word_categories(word, case_sensitive)
        return category in categories

    def get_category_words(self, category: str) -> Set[str]:
        """
        Get all words in a specific category.

        Args:
            category: Category name (e.g., "Negative", "Positive")

        Returns:
            Set of words in that category
        """
        if category not in LM_FEATURE_CATEGORIES:
            raise ValueError(f"Invalid category: {category}. Must be one of {LM_FEATURE_CATEGORIES}")

        return {word for word, cats in self.words.items() if category in cats}

    def __len__(self) -> int:
        """Return number of words in dictionary."""
        return len(self.words)

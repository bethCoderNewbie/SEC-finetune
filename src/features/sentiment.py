"""
Sentiment Analysis Feature Extractor

This module extracts sentiment features from text using the Loughran-McDonald
Master Dictionary for financial sentiment analysis.

The analyzer:
1. Tokenizes text into words
2. Matches words against LM dictionary
3. Computes counts, ratios, and normalized scores for each category
4. Returns structured SentimentFeatures dataclass

Usage:
    from src.features import SentimentAnalyzer

    analyzer = SentimentAnalyzer()
    features = analyzer.extract_features("The company faces uncertainty...")

    print(f"Negative count: {features.negative_count}")
    print(f"Uncertainty ratio: {features.uncertainty_ratio}")
"""

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Set
from collections import Counter
import logging

from src.config import settings
from src.features.dictionaries import LMDictionaryManager
from src.features.dictionaries.constants import LM_FEATURE_CATEGORIES

logger = logging.getLogger(__name__)


@dataclass
class SentimentFeatures:
    """
    Structured sentiment features extracted from text.

    Follows the same pattern as ParsedFiling and ExtractedSection:
    - Dataclass for type safety
    - .save_to_json() and .load_from_json() methods
    - Clear field documentation
    """
    # Metadata
    text_length: int
    word_count: int
    unique_word_count: int

    # Raw counts per category
    negative_count: int = 0
    positive_count: int = 0
    uncertainty_count: int = 0
    litigious_count: int = 0
    strong_modal_count: int = 0
    weak_modal_count: int = 0
    constraining_count: int = 0
    complexity_count: int = 0

    # Ratios (category_count / total_words)
    negative_ratio: float = 0.0
    positive_ratio: float = 0.0
    uncertainty_ratio: float = 0.0
    litigious_ratio: float = 0.0
    strong_modal_ratio: float = 0.0
    weak_modal_ratio: float = 0.0
    constraining_ratio: float = 0.0
    complexity_ratio: float = 0.0

    # Proportions (category_count / total_sentiment_words)
    negative_proportion: float = 0.0
    positive_proportion: float = 0.0
    uncertainty_proportion: float = 0.0
    litigious_proportion: float = 0.0
    strong_modal_proportion: float = 0.0
    weak_modal_proportion: float = 0.0
    constraining_proportion: float = 0.0
    complexity_proportion: float = 0.0

    # Aggregates
    total_sentiment_words: int = 0
    sentiment_word_ratio: float = 0.0  # sentiment_words / total_words

    def save_to_json(self, output_path: Path) -> None:
        """
        Save features to JSON file.

        Args:
            output_path: Path to output JSON file
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(self), f, indent=2)
        logger.info(f"Saved sentiment features to {output_path}")

    @classmethod
    def load_from_json(cls, input_path: Path) -> 'SentimentFeatures':
        """
        Load features from JSON file.

        Args:
            input_path: Path to input JSON file

        Returns:
            SentimentFeatures object
        """
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.info(f"Loaded sentiment features from {input_path}")
        return cls(**data)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)

    def get_category_counts(self) -> Dict[str, int]:
        """Get dictionary of category counts."""
        return {
            "Negative": self.negative_count,
            "Positive": self.positive_count,
            "Uncertainty": self.uncertainty_count,
            "Litigious": self.litigious_count,
            "Strong_Modal": self.strong_modal_count,
            "Weak_Modal": self.weak_modal_count,
            "Constraining": self.constraining_count,
            "Complexity": self.complexity_count,
        }

    def get_category_ratios(self) -> Dict[str, float]:
        """Get dictionary of category ratios."""
        return {
            "Negative": self.negative_ratio,
            "Positive": self.positive_ratio,
            "Uncertainty": self.uncertainty_ratio,
            "Litigious": self.litigious_ratio,
            "Strong_Modal": self.strong_modal_ratio,
            "Weak_Modal": self.weak_modal_ratio,
            "Constraining": self.constraining_ratio,
            "Complexity": self.complexity_ratio,
        }


class SentimentAnalyzer:
    """
    Sentiment feature extractor using Loughran-McDonald dictionary.

    This class:
    1. Loads configuration from settings
    2. Manages dictionary lifecycle
    3. Tokenizes text
    4. Computes sentiment features

    Usage:
        analyzer = SentimentAnalyzer()
        features = analyzer.extract_features(text)
    """

    def __init__(self, config: Optional[object] = None):
        """
        Initialize sentiment analyzer.

        Args:
            config: Optional SentimentConfig object. If None, loads from settings.
        """
        self.config = config or settings.sentiment
        self._dict_manager: Optional[LMDictionaryManager] = None

        # Validate active categories
        invalid = set(self.config.active_categories) - set(LM_FEATURE_CATEGORIES)
        if invalid:
            raise ValueError(
                f"Invalid active categories: {invalid}. "
                f"Must be subset of {LM_FEATURE_CATEGORIES}"
            )

        logger.info(
            f"Initialized SentimentAnalyzer with categories: "
            f"{self.config.active_categories}"
        )

    @property
    def dict_manager(self) -> LMDictionaryManager:
        """Lazy-load dictionary manager."""
        if self._dict_manager is None:
            self._dict_manager = LMDictionaryManager.get_instance()
            self._dict_manager.load_dictionary()
        return self._dict_manager

    def tokenize(self, text: str) -> List[str]:
        """
        Tokenize text into words.

        Args:
            text: Input text

        Returns:
            List of tokens (words)
        """
        # Remove punctuation and split on whitespace
        # Keep alphanumeric and hyphens (for hyphenated words)
        tokens = re.findall(r'\b[a-zA-Z][\w-]*\b', text)

        # Apply case sensitivity setting
        if not self.config.text_processing.case_sensitive:
            tokens = [t.upper() for t in tokens]

        # TODO: Add lemmatization if enabled
        # TODO: Add stopword removal if enabled

        return tokens

    def count_category_words(self, tokens: List[str]) -> Dict[str, int]:
        """
        Count words in each sentiment category.

        Args:
            tokens: List of word tokens

        Returns:
            Dictionary mapping category names to counts
        """
        # Initialize counts
        category_counts = {cat: 0 for cat in LM_FEATURE_CATEGORIES}

        # Count words in each category
        for token in tokens:
            categories = self.dict_manager.get_word_categories(
                token,
                case_sensitive=self.config.text_processing.case_sensitive
            )
            for category in categories:
                if category in self.config.active_categories:
                    category_counts[category] += 1

        return category_counts

    def extract_features(self, text: str) -> SentimentFeatures:
        """
        Extract sentiment features from text.

        Args:
            text: Input text to analyze

        Returns:
            SentimentFeatures dataclass with all computed features
        """
        # Tokenize
        tokens = self.tokenize(text)
        word_count = len(tokens)
        unique_word_count = len(set(tokens))

        # Count category words
        category_counts = self.count_category_words(tokens)

        # Calculate total sentiment words
        total_sentiment_words = sum(category_counts.values())

        # Calculate ratios (category_count / total_words)
        ratios = {
            cat: count / word_count if word_count > 0 else 0.0
            for cat, count in category_counts.items()
        }

        # Calculate proportions (category_count / total_sentiment_words)
        proportions = {
            cat: count / total_sentiment_words if total_sentiment_words > 0 else 0.0
            for cat, count in category_counts.items()
        }

        # Calculate sentiment word ratio
        sentiment_word_ratio = total_sentiment_words / word_count if word_count > 0 else 0.0

        # Build features object
        precision = self.config.output.precision

        return SentimentFeatures(
            # Metadata
            text_length=len(text),
            word_count=word_count,
            unique_word_count=unique_word_count,
            # Counts
            negative_count=category_counts.get("Negative", 0),
            positive_count=category_counts.get("Positive", 0),
            uncertainty_count=category_counts.get("Uncertainty", 0),
            litigious_count=category_counts.get("Litigious", 0),
            strong_modal_count=category_counts.get("Strong_Modal", 0),
            weak_modal_count=category_counts.get("Weak_Modal", 0),
            constraining_count=category_counts.get("Constraining", 0),
            complexity_count=category_counts.get("Complexity", 0),
            # Ratios
            negative_ratio=round(ratios.get("Negative", 0.0), precision),
            positive_ratio=round(ratios.get("Positive", 0.0), precision),
            uncertainty_ratio=round(ratios.get("Uncertainty", 0.0), precision),
            litigious_ratio=round(ratios.get("Litigious", 0.0), precision),
            strong_modal_ratio=round(ratios.get("Strong_Modal", 0.0), precision),
            weak_modal_ratio=round(ratios.get("Weak_Modal", 0.0), precision),
            constraining_ratio=round(ratios.get("Constraining", 0.0), precision),
            complexity_ratio=round(ratios.get("Complexity", 0.0), precision),
            # Proportions
            negative_proportion=round(proportions.get("Negative", 0.0), precision),
            positive_proportion=round(proportions.get("Positive", 0.0), precision),
            uncertainty_proportion=round(proportions.get("Uncertainty", 0.0), precision),
            litigious_proportion=round(proportions.get("Litigious", 0.0), precision),
            strong_modal_proportion=round(proportions.get("Strong_Modal", 0.0), precision),
            weak_modal_proportion=round(proportions.get("Weak_Modal", 0.0), precision),
            constraining_proportion=round(proportions.get("Constraining", 0.0), precision),
            complexity_proportion=round(proportions.get("Complexity", 0.0), precision),
            # Aggregates
            total_sentiment_words=total_sentiment_words,
            sentiment_word_ratio=round(sentiment_word_ratio, precision),
        )

    def extract_features_batch(self, texts: List[str]) -> List[SentimentFeatures]:
        """
        Extract features from multiple texts.

        Args:
            texts: List of text strings

        Returns:
            List of SentimentFeatures objects
        """
        return [self.extract_features(text) for text in texts]

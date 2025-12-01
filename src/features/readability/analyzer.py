"""
Readability Analyzer for SEC Filings

Extracts text complexity and readability features using textstat library
with financial domain adjustments.

Usage:
    from src.features.readability import ReadabilityAnalyzer

    analyzer = ReadabilityAnalyzer()
    features = analyzer.extract_features(cleaned_text)
    print(f"Gunning Fog: {features.gunning_fog_index}")
"""

import re
import logging
from typing import List, Optional, Set

try:
    import textstat
    TEXTSTAT_AVAILABLE = True
except ImportError:
    TEXTSTAT_AVAILABLE = False
    raise ImportError(
        "textstat is required for readability analysis. "
        "Install it with: pip install textstat"
    )

from src.config import settings
from .schemas import (
    ReadabilityFeatures,
    ReadabilityAnalysisMetadata,
    ReadabilityAnalysisResult
)
from .constants import (
    FINANCIAL_COMMON_WORDS,
    LONG_SENTENCE_THRESHOLD,
    MIN_TEXT_LENGTH_FOR_ANALYSIS,
    MIN_WORD_COUNT_FOR_ANALYSIS,
    MIN_SENTENCE_COUNT_FOR_ANALYSIS,
)

logger = logging.getLogger(__name__)


class ReadabilityAnalyzer:
    """
    Readability and text complexity feature extractor.

    This class:
    1. Loads configuration from settings
    2. Uses textstat library for standard metrics
    3. Applies financial domain adjustments for complex words
    4. Computes structural complexity measures
    5. Generates custom obfuscation risk score

    Important: Input text should be pre-cleaned using TextCleaner:
        - HTML tags removed
        - Boilerplate/artifacts removed
        - BUT punctuation preserved (needed for sentence detection)

    Usage:
        analyzer = ReadabilityAnalyzer()
        features = analyzer.extract_features(text)
    """

    def __init__(
        self,
        config: Optional[object] = None,
        financial_word_list: Optional[Set[str]] = None
    ):
        """
        Initialize readability analyzer.

        Args:
            config: Optional ReadabilityConfig object. If None, loads from settings.
            financial_word_list: Optional set of common financial words to exclude
                                from complex word counts. Defaults to FINANCIAL_COMMON_WORDS.
        """
        # Load config (with fallback if not yet implemented)
        try:
            self.config = config or settings.readability
            logger.info("Loaded readability config from settings")
        except AttributeError:
            logger.warning(
                "Readability config not found in settings, using defaults. "
                "Add ReadabilityConfig to src/config.py"
            )
            self.config = None

        # Set financial word exception list
        self.financial_words = financial_word_list or FINANCIAL_COMMON_WORDS

        # Validate textstat availability
        if not TEXTSTAT_AVAILABLE:
            raise ImportError(
                "textstat is required but not installed. "
                "Install it with: pip install textstat"
            )

        logger.info(
            f"Initialized ReadabilityAnalyzer with {len(self.financial_words)} "
            f"financial domain exceptions"
        )

    def extract_features(
        self,
        text: str,
        return_metadata: bool = False
    ) -> ReadabilityFeatures | ReadabilityAnalysisResult:
        """
        Extract readability features from text.

        Args:
            text: Input text to analyze (should be pre-cleaned with TextCleaner)
            return_metadata: If True, return ReadabilityAnalysisResult with metadata.
                           If False (default), return only ReadabilityFeatures.

        Returns:
            ReadabilityFeatures or ReadabilityAnalysisResult
        """
        if not text or len(text.strip()) == 0:
            return self._empty_features()

        # Collect warnings
        warnings = []

        # Validate text length
        if len(text) < MIN_TEXT_LENGTH_FOR_ANALYSIS:
            warnings.append(
                f"Text length ({len(text)}) below minimum ({MIN_TEXT_LENGTH_FOR_ANALYSIS}). "
                f"Results may be unreliable."
            )

        # ===========================
        # Basic Statistics
        # ===========================
        word_count = textstat.lexicon_count(text, removepunct=True)
        sentence_count = textstat.sentence_count(text)
        syllable_count = textstat.syllable_count(text)
        paragraph_count = self._count_paragraphs(text)

        # Additional validation
        if word_count < MIN_WORD_COUNT_FOR_ANALYSIS:
            warnings.append(
                f"Word count ({word_count}) below minimum ({MIN_WORD_COUNT_FOR_ANALYSIS}). "
                f"Results may be unreliable."
            )
        if sentence_count < MIN_SENTENCE_COUNT_FOR_ANALYSIS:
            warnings.append(
                f"Sentence count ({sentence_count}) below minimum ({MIN_SENTENCE_COUNT_FOR_ANALYSIS}). "
                f"Results may be unreliable."
            )

        # ===========================
        # Standard Readability Indices
        # ===========================
        flesch_kincaid_grade = textstat.flesch_kincaid_grade(text)
        gunning_fog_index = textstat.gunning_fog(text)
        flesch_reading_ease = textstat.flesch_reading_ease(text)
        smog_index = textstat.smog_index(text)
        automated_readability_index = textstat.automated_readability_index(text)
        coleman_liau_index = textstat.coleman_liau_index(text)

        # ===========================
        # Structural Complexity
        # ===========================
        avg_sentence_length = word_count / sentence_count if sentence_count > 0 else 0.0
        avg_word_length = textstat.avg_character_per_word(text)
        avg_syllables_per_word = syllable_count / word_count if word_count > 0 else 0.0
        avg_paragraph_length = sentence_count / paragraph_count if paragraph_count > 0 else 0.0

        # ===========================
        # Complex Word Analysis
        # ===========================
        words = self._tokenize_words(text)

        # Standard complex word count (using Dale-Chall list)
        difficult_words = textstat.difficult_words(text)

        # Manual count of 3+ syllable words
        complex_word_count = sum(
            1 for word in words if textstat.syllable_count(word) >= 3
        )

        # Adjusted complex word count (exclude financial domain terms)
        complex_word_count_adjusted, financial_words_excluded = self._count_complex_words_adjusted(words)

        pct_complex_words = (complex_word_count / word_count * 100) if word_count > 0 else 0.0
        pct_complex_words_adjusted = (complex_word_count_adjusted / word_count * 100) if word_count > 0 else 0.0

        # ===========================
        # Sentence Variety
        # ===========================
        sentences = self._split_sentences(text)
        long_sentence_count = sum(1 for s in sentences if len(s.split()) > LONG_SENTENCE_THRESHOLD)
        pct_long_sentences = (long_sentence_count / sentence_count * 100) if sentence_count > 0 else 0.0

        # ===========================
        # Aggregate Scores
        # ===========================
        # Consensus grade: average of multiple grade-level indices
        readability_consensus_grade = textstat.text_standard(text, float_output=True)

        # Custom obfuscation score (0-100 scale)
        obfuscation_score = self._calculate_obfuscation_score(
            flesch_kincaid_grade=flesch_kincaid_grade,
            gunning_fog_index=gunning_fog_index,
            avg_sentence_length=avg_sentence_length,
            pct_complex_words=pct_complex_words_adjusted,
            pct_long_sentences=pct_long_sentences
        )

        # Get precision from config or use default
        precision = 2 if self.config is None else getattr(self.config, 'precision', 2)

        # Build features
        features = ReadabilityFeatures(
            # Basic statistics
            text_length=len(text),
            word_count=word_count,
            sentence_count=sentence_count,
            paragraph_count=paragraph_count,
            syllable_count=syllable_count,
            # Standard indices
            flesch_kincaid_grade=round(flesch_kincaid_grade, precision),
            gunning_fog_index=round(gunning_fog_index, precision),
            flesch_reading_ease=round(flesch_reading_ease, precision),
            smog_index=round(smog_index, precision),
            automated_readability_index=round(automated_readability_index, precision),
            coleman_liau_index=round(coleman_liau_index, precision),
            # Structural complexity
            avg_sentence_length=round(avg_sentence_length, precision),
            avg_word_length=round(avg_word_length, precision),
            avg_syllables_per_word=round(avg_syllables_per_word, precision),
            avg_paragraph_length=round(avg_paragraph_length, precision),
            # Complex words
            complex_word_count=complex_word_count,
            complex_word_count_adjusted=complex_word_count_adjusted,
            pct_complex_words=round(pct_complex_words, precision),
            pct_complex_words_adjusted=round(pct_complex_words_adjusted, precision),
            difficult_words=difficult_words,
            # Sentence variety
            long_sentence_count=long_sentence_count,
            pct_long_sentences=round(pct_long_sentences, precision),
            # Aggregates
            readability_consensus_grade=round(readability_consensus_grade, precision),
            obfuscation_score=round(obfuscation_score, precision),
        )

        # Return features only, or with metadata
        if not return_metadata:
            return features

        # Build metadata
        metadata = ReadabilityAnalysisMetadata(
            text_length=len(text),
            word_count=word_count,
            sentence_count=sentence_count,
            financial_words_excluded=financial_words_excluded,
            warnings=warnings,
            config_used=self._get_config_dict()
        )

        return ReadabilityAnalysisResult(features=features, metadata=metadata)

    def extract_features_batch(
        self,
        texts: List[str],
        return_metadata: bool = False
    ) -> List[ReadabilityFeatures] | List[ReadabilityAnalysisResult]:
        """
        Extract features from multiple texts.

        Args:
            texts: List of text strings
            return_metadata: If True, return results with metadata

        Returns:
            List of ReadabilityFeatures or ReadabilityAnalysisResult objects
        """
        return [self.extract_features(text, return_metadata=return_metadata) for text in texts]

    # ===========================
    # Private Helper Methods
    # ===========================

    def _count_paragraphs(self, text: str) -> int:
        """Count paragraphs (blocks separated by blank lines)."""
        paragraphs = re.split(r'\n\s*\n', text.strip())
        paragraphs = [p for p in paragraphs if p.strip()]
        return len(paragraphs) if paragraphs else 1

    def _tokenize_words(self, text: str) -> List[str]:
        """Tokenize text into words (consistent with sentiment analyzer)."""
        words = re.findall(r'\b[a-zA-Z][\w-]*\b', text)
        return [w.lower() for w in words]

    def _split_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences (simple implementation).
        Note: textstat handles this better internally; this is for custom metrics only.
        """
        sentences = re.split(r'[.!?]+', text)
        return [s.strip() for s in sentences if s.strip()]

    def _count_complex_words_adjusted(self, words: List[str]) -> tuple[int, int]:
        """
        Count complex words (3+ syllables) excluding financial domain terms.

        Returns:
            Tuple of (adjusted_count, num_financial_words_excluded)
        """
        count = 0
        excluded = 0

        for word in words:
            syllables = textstat.syllable_count(word)
            if syllables >= 3:
                # Check if in financial exception list
                if word.lower() in self.financial_words:
                    excluded += 1
                else:
                    count += 1

        return count, excluded

    def _calculate_obfuscation_score(
        self,
        flesch_kincaid_grade: float,
        gunning_fog_index: float,
        avg_sentence_length: float,
        pct_complex_words: float,
        pct_long_sentences: float
    ) -> float:
        """
        Calculate custom obfuscation risk score (0-100).

        Combines multiple readability signals into a single risk metric.
        Higher score = more likely obfuscated/harder to read.

        Args:
            flesch_kincaid_grade: FK grade level
            gunning_fog_index: Fog index
            avg_sentence_length: Average words per sentence
            pct_complex_words: Percentage of complex words (adjusted)
            pct_long_sentences: Percentage of long sentences

        Returns:
            Obfuscation score (0-100)
        """
        # Normalize components to 0-100 scale

        # FK Grade: 0-20 → 0-100 (typical 10-K is 12-16)
        fk_component = min(flesch_kincaid_grade / 20 * 100, 100)

        # Fog Index: 0-20 → 0-100 (typical 10-K is 14-18)
        fog_component = min(gunning_fog_index / 20 * 100, 100)

        # Sentence length: 0-50 words → 0-100 (target is <20)
        sentence_component = min(avg_sentence_length / 50 * 100, 100)

        # Complex words: 0-50% → 0-100
        complex_component = min(pct_complex_words * 2, 100)

        # Long sentences: 0-50% → 0-100
        long_sentence_component = min(pct_long_sentences * 2, 100)

        # Weighted average (emphasize standard indices)
        score = (
            0.30 * fk_component +
            0.30 * fog_component +
            0.15 * sentence_component +
            0.15 * complex_component +
            0.10 * long_sentence_component
        )

        return score

    def _get_config_dict(self) -> dict:
        """Get configuration as dictionary for metadata."""
        if self.config is None:
            return {"source": "defaults (config not loaded)"}

        try:
            return self.config.model_dump()
        except AttributeError:
            return {"source": "config object (not serializable)"}

    def _empty_features(self) -> ReadabilityFeatures:
        """Return zero/empty features for empty text."""
        return ReadabilityFeatures(
            text_length=0,
            word_count=0,
            sentence_count=0,
            paragraph_count=0,
            syllable_count=0,
            flesch_kincaid_grade=0.0,
            gunning_fog_index=0.0,
            flesch_reading_ease=0.0,
            smog_index=0.0,
            automated_readability_index=0.0,
            coleman_liau_index=0.0,
            avg_sentence_length=0.0,
            avg_word_length=0.0,
            avg_syllables_per_word=0.0,
            avg_paragraph_length=0.0,
            complex_word_count=0,
            complex_word_count_adjusted=0,
            pct_complex_words=0.0,
            pct_complex_words_adjusted=0.0,
            difficult_words=0,
            long_sentence_count=0,
            pct_long_sentences=0.0,
            readability_consensus_grade=0.0,
            obfuscation_score=0.0,
        )

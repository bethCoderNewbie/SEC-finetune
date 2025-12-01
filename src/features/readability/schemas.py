"""
Data structures for readability and text complexity analysis.

This module defines Pydantic v2 models for readability features.
These schemas enforce type safety and validation throughout the pipeline.

Following the project's Pydantic v2 enforcement standards:
- Use BaseModel (not dataclass)
- Use @field_validator (not @validator)
- Use model_config = (not class Config:)
- Use .model_dump() (not .dict())
- Use .model_dump_json() (not .json())
"""

from pydantic import BaseModel, Field, field_validator
from typing import Dict, Optional
from datetime import datetime
from pathlib import Path
import json

from .constants import (
    STANDARD_READABILITY_INDICES,
    READABILITY_MODULE_VERSION,
    MIN_TEXT_LENGTH_FOR_ANALYSIS,
    MIN_WORD_COUNT_FOR_ANALYSIS,
    MIN_SENTENCE_COUNT_FOR_ANALYSIS,
)


class ReadabilityFeatures(BaseModel):
    """
    Text complexity and readability metrics extracted from text.

    This is the main data structure returned by the ReadabilityAnalyzer.
    It contains comprehensive readability metrics organized into categories:
    - Basic text statistics
    - Standard readability indices (FK, Fog, etc.)
    - Structural complexity metrics
    - Complex word analysis
    - Sentence variety metrics
    - Aggregate risk scores

    All features are validated and type-safe using Pydantic v2.
    """

    # ===========================
    # Basic Text Statistics
    # ===========================
    text_length: int = Field(..., ge=0, description="Total character count")
    word_count: int = Field(..., ge=0, description="Total word count")
    sentence_count: int = Field(..., ge=0, description="Total sentence count")
    paragraph_count: int = Field(..., ge=0, description="Total paragraph count")
    syllable_count: int = Field(..., ge=0, description="Total syllable count")

    # ===========================
    # Standard Readability Indices
    # ===========================
    flesch_kincaid_grade: float = Field(
        ...,
        description="Flesch-Kincaid Grade Level (U.S. school grade). "
                    "Formula: 0.39 × (words/sentences) + 11.8 × (syllables/words) - 15.59. "
                    "Target for investor-friendly: 10-12. Higher = harder to read."
    )

    gunning_fog_index: float = Field(
        ...,
        description="Gunning Fog Index (U.S. grade level). "
                    "Formula: 0.4 × [(words/sentences) + 100 × (complex_words/words)]. "
                    "Better for business/technical writing. Typical 10-K: 14-18. Higher = harder to read."
    )

    flesch_reading_ease: float = Field(
        ...,
        description="Flesch Reading Ease Score (typically 0-100, but can be negative for very difficult text). "
                    "Higher = easier to read. "
                    "90-100: Very Easy (5th grade), 60-70: Standard (8th-9th grade), "
                    "30-50: Difficult (College), 0-30: Very Difficult (College graduate), "
                    "<0: Extremely difficult."
    )

    smog_index: float = Field(
        ...,
        description="SMOG (Simple Measure of Gobbledygook) Index. "
                    "Estimates years of education needed to understand text."
    )

    automated_readability_index: float = Field(
        ...,
        description="Automated Readability Index (ARI). "
                    "Based on characters per word and words per sentence. Outputs U.S. grade level."
    )

    coleman_liau_index: float = Field(
        ...,
        description="Coleman-Liau Index. Based on characters rather than syllables. "
                    "Outputs U.S. grade level."
    )

    # ===========================
    # Structural Complexity
    # ===========================
    avg_sentence_length: float = Field(
        ...,
        ge=0.0,
        description="Average words per sentence. Shorter sentences = easier to read. "
                    "Target: <20 words/sentence for plain language."
    )

    avg_word_length: float = Field(
        ...,
        ge=0.0,
        description="Average characters per word. Shorter words = easier to read."
    )

    avg_syllables_per_word: float = Field(
        ...,
        ge=0.0,
        description="Average syllables per word. Fewer syllables = easier to read."
    )

    avg_paragraph_length: float = Field(
        ...,
        ge=0.0,
        description="Average sentences per paragraph. Shorter paragraphs = easier to scan."
    )

    # ===========================
    # Complex Word Analysis
    # ===========================
    complex_word_count: int = Field(
        ...,
        ge=0,
        description="Count of words with 3+ syllables (standard definition)"
    )

    complex_word_count_adjusted: int = Field(
        ...,
        ge=0,
        description="Count of complex words excluding common financial terms. "
                    "This is the adjusted count used for domain-specific analysis."
    )

    pct_complex_words: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Percentage of words that are complex (3+ syllables)"
    )

    pct_complex_words_adjusted: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Percentage of complex words (adjusted for financial domain)"
    )

    difficult_words: int = Field(
        ...,
        ge=0,
        description="Count of difficult words (not in Dale-Chall easy word list)"
    )

    # ===========================
    # Sentence Variety
    # ===========================
    long_sentence_count: int = Field(
        ...,
        ge=0,
        description="Count of sentences with >30 words (potential run-ons)"
    )

    pct_long_sentences: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Percentage of sentences that are long (>30 words)"
    )

    # ===========================
    # Aggregate Scores
    # ===========================
    readability_consensus_grade: float = Field(
        ...,
        description="Average of multiple grade-level indices. "
                    "More robust than single metric."
    )

    obfuscation_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Custom risk proxy score (0-100). Higher = more obfuscation/complexity. "
                    "Combines multiple signals: FK grade, Fog index, sentence length variance. "
                    "<40: Clear, 40-60: Typical 10-K, 60-75: Elevated, >75: High risk."
    )

    # ===========================
    # Validators
    # ===========================

    @field_validator('sentence_count')
    @classmethod
    def validate_sentence_count(cls, v: int, values) -> int:
        """Warn if sentence count is too low for meaningful analysis."""
        if v > 0 and v < MIN_SENTENCE_COUNT_FOR_ANALYSIS:
            import logging
            logging.getLogger(__name__).warning(
                f"Sentence count ({v}) is below recommended minimum "
                f"({MIN_SENTENCE_COUNT_FOR_ANALYSIS}) for reliable readability analysis"
            )
        return v

    # ===========================
    # Methods
    # ===========================

    def model_dump_to_json_file(self, output_path: Path) -> None:
        """
        Save features to JSON file.

        Args:
            output_path: Path to output JSON file
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.model_dump(), f, indent=2)

    @classmethod
    def model_load_from_json_file(cls, input_path: Path) -> 'ReadabilityFeatures':
        """
        Load features from JSON file.

        Args:
            input_path: Path to input JSON file

        Returns:
            ReadabilityFeatures object
        """
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls(**data)

    def get_basic_stats(self) -> Dict[str, int]:
        """Get dictionary of basic text statistics."""
        return {
            "text_length": self.text_length,
            "word_count": self.word_count,
            "sentence_count": self.sentence_count,
            "paragraph_count": self.paragraph_count,
            "syllable_count": self.syllable_count,
        }

    def get_standard_indices(self) -> Dict[str, float]:
        """Get dictionary of standard readability indices."""
        return {
            "flesch_kincaid_grade": self.flesch_kincaid_grade,
            "gunning_fog_index": self.gunning_fog_index,
            "flesch_reading_ease": self.flesch_reading_ease,
            "smog_index": self.smog_index,
            "automated_readability_index": self.automated_readability_index,
            "coleman_liau_index": self.coleman_liau_index,
        }

    def get_complexity_metrics(self) -> Dict[str, float]:
        """Get dictionary of structural complexity metrics."""
        return {
            "avg_sentence_length": self.avg_sentence_length,
            "avg_word_length": self.avg_word_length,
            "avg_syllables_per_word": self.avg_syllables_per_word,
            "avg_paragraph_length": self.avg_paragraph_length,
            "pct_complex_words_adjusted": self.pct_complex_words_adjusted,
            "pct_long_sentences": self.pct_long_sentences,
        }

    def get_risk_scores(self) -> Dict[str, float]:
        """Get dictionary of risk-related scores."""
        return {
            "obfuscation_score": self.obfuscation_score,
            "readability_consensus_grade": self.readability_consensus_grade,
            "gunning_fog_index": self.gunning_fog_index,  # Key risk indicator
            "flesch_kincaid_grade": self.flesch_kincaid_grade,  # Key risk indicator
        }

    def interpret_obfuscation_score(self) -> str:
        """
        Get human-readable interpretation of obfuscation score.

        Returns:
            String interpretation (e.g., "Clear", "Typical 10-K", "High Risk")
        """
        from .constants import OBFUSCATION_SCORE_THRESHOLDS

        score = self.obfuscation_score
        if score < OBFUSCATION_SCORE_THRESHOLDS["low_risk"]:
            return "Clear and readable"
        elif score < OBFUSCATION_SCORE_THRESHOLDS["moderate_risk"]:
            return "Typical 10-K complexity"
        elif score < OBFUSCATION_SCORE_THRESHOLDS["high_risk"]:
            return "Elevated complexity"
        elif score < OBFUSCATION_SCORE_THRESHOLDS["very_high_risk"]:
            return "High complexity - potential obfuscation"
        else:
            return "Very high complexity - strong obfuscation signal"

    def get_summary(self) -> str:
        """Return human-readable summary of readability features."""
        return (
            f"Readability Analysis Summary\n"
            f"{'='*50}\n"
            f"Words: {self.word_count:,} | Sentences: {self.sentence_count} | "
            f"Paragraphs: {self.paragraph_count}\n"
            f"\nStandard Indices:\n"
            f"  Flesch-Kincaid Grade: {self.flesch_kincaid_grade:.1f}\n"
            f"  Gunning Fog Index: {self.gunning_fog_index:.1f}\n"
            f"  Flesch Reading Ease: {self.flesch_reading_ease:.1f}/100\n"
            f"\nComplexity:\n"
            f"  Avg Sentence Length: {self.avg_sentence_length:.1f} words\n"
            f"  Complex Words (adj): {self.pct_complex_words_adjusted:.1f}%\n"
            f"  Long Sentences: {self.pct_long_sentences:.1f}%\n"
            f"\nRisk Assessment:\n"
            f"  Consensus Grade: {self.readability_consensus_grade:.1f}\n"
            f"  Obfuscation Score: {self.obfuscation_score:.1f}/100\n"
            f"  Interpretation: {self.interpret_obfuscation_score()}"
        )


class ReadabilityAnalysisMetadata(BaseModel):
    """
    Metadata about a readability analysis run.

    Tracks configuration, execution details, and warnings for auditability.
    """
    version: str = Field(default=READABILITY_MODULE_VERSION)
    analyzed_at: datetime = Field(default_factory=datetime.now)
    text_length: int = Field(..., ge=0)
    word_count: int = Field(..., ge=0)
    sentence_count: int = Field(..., ge=0)
    financial_words_excluded: int = Field(
        ...,
        ge=0,
        description="Number of financial domain words excluded from complex word count"
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Analysis warnings (e.g., text too short)"
    )
    config_used: Dict = Field(
        default_factory=dict,
        description="Configuration settings used for this analysis"
    )

    @field_validator('text_length')
    @classmethod
    def validate_text_length(cls, v: int) -> int:
        """Warn if text is too short for meaningful analysis."""
        if v < MIN_TEXT_LENGTH_FOR_ANALYSIS:
            import logging
            logging.getLogger(__name__).warning(
                f"Text length ({v}) is below recommended minimum "
                f"({MIN_TEXT_LENGTH_FOR_ANALYSIS}) for reliable readability analysis"
            )
        return v

    def get_summary(self) -> str:
        """Return human-readable summary of metadata."""
        warnings_str = "\n    ".join(self.warnings) if self.warnings else "None"
        return (
            f"Analysis Metadata\n"
            f"{'='*50}\n"
            f"Version: {self.version}\n"
            f"Analyzed: {self.analyzed_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Text: {self.word_count:,} words, {self.sentence_count} sentences\n"
            f"Financial words excluded: {self.financial_words_excluded}\n"
            f"Warnings:\n    {warnings_str}"
        )


class ReadabilityAnalysisResult(BaseModel):
    """
    Complete readability analysis result with features and metadata.

    This is the top-level structure that combines:
    - ReadabilityFeatures (the actual metrics)
    - ReadabilityAnalysisMetadata (audit trail)

    Use this for saving complete analysis results to disk.
    """
    features: ReadabilityFeatures = Field(
        ...,
        description="Extracted readability features"
    )
    metadata: ReadabilityAnalysisMetadata = Field(
        ...,
        description="Analysis metadata and configuration"
    )

    def model_dump_to_json_file(self, output_path: Path) -> None:
        """
        Save complete result to JSON file.

        Args:
            output_path: Path to output JSON file
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.model_dump(), f, indent=2)

    @classmethod
    def model_load_from_json_file(cls, input_path: Path) -> 'ReadabilityAnalysisResult':
        """
        Load complete result from JSON file.

        Args:
            input_path: Path to input JSON file

        Returns:
            ReadabilityAnalysisResult object
        """
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls(**data)

    def get_summary(self) -> str:
        """Return human-readable summary of complete result."""
        return (
            f"{self.metadata.get_summary()}\n\n"
            f"{self.features.get_summary()}"
        )

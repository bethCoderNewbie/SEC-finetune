"""
Golden Sentence Tests - Deterministic verification of sentiment analysis.

These tests verify exact output for known input sentences, ensuring
the LM dictionary matching logic is working correctly.

No file dependencies - these tests can run in any environment.
"""

import pytest


class TestGoldenSentence:
    """Deterministic tests using known LM dictionary word matches."""

    def test_golden_sentence_negative_count(
        self,
        golden_sentence: str,
        golden_sentence_expected: dict
    ):
        """
        Verify negative word count matches expected value.

        Expected negative words: catastrophic, losses, litigation
        """
        from src.features.sentiment import SentimentAnalyzer

        analyzer = SentimentAnalyzer()
        features = analyzer.extract_features(golden_sentence)

        assert features.negative_count == golden_sentence_expected['negative_count'], \
            f"Expected {golden_sentence_expected['negative_count']} negative, got {features.negative_count}"

    def test_golden_sentence_positive_count(
        self,
        golden_sentence: str,
        golden_sentence_expected: dict
    ):
        """
        Verify positive word count matches expected value.

        Expected positive words: none
        """
        from src.features.sentiment import SentimentAnalyzer

        analyzer = SentimentAnalyzer()
        features = analyzer.extract_features(golden_sentence)

        assert features.positive_count == golden_sentence_expected['positive_count'], \
            f"Expected {golden_sentence_expected['positive_count']} positive, got {features.positive_count}"

    def test_golden_sentence_uncertainty_count(
        self,
        golden_sentence: str,
        golden_sentence_expected: dict
    ):
        """
        Verify uncertainty word count matches expected value.

        Expected uncertainty words: anticipates
        """
        from src.features.sentiment import SentimentAnalyzer

        analyzer = SentimentAnalyzer()
        features = analyzer.extract_features(golden_sentence)

        assert features.uncertainty_count == golden_sentence_expected['uncertainty_count'], \
            f"Expected {golden_sentence_expected['uncertainty_count']} uncertainty, got {features.uncertainty_count}"

    def test_golden_sentence_litigious_count(
        self,
        golden_sentence: str,
        golden_sentence_expected: dict
    ):
        """
        Verify litigious word count matches expected value.

        Expected litigious words: litigation
        """
        from src.features.sentiment import SentimentAnalyzer

        analyzer = SentimentAnalyzer()
        features = analyzer.extract_features(golden_sentence)

        assert features.litigious_count == golden_sentence_expected['litigious_count'], \
            f"Expected {golden_sentence_expected['litigious_count']} litigious, got {features.litigious_count}"

    def test_golden_sentence_total_sentiment_words(
        self,
        golden_sentence: str,
        golden_sentence_expected: dict
    ):
        """
        Verify total sentiment word count matches expected value.

        Total should be 5: anticipates, litigation, catastrophic, losses
        (litigation counts as both Negative and Litigious but only once in total)
        """
        from src.features.sentiment import SentimentAnalyzer

        analyzer = SentimentAnalyzer()
        features = analyzer.extract_features(golden_sentence)

        assert features.total_sentiment_words == golden_sentence_expected['total_sentiment_words'], \
            f"Expected {golden_sentence_expected['total_sentiment_words']} total, got {features.total_sentiment_words}"

    def test_golden_sentence_all_categories(
        self,
        golden_sentence: str,
        golden_sentence_expected: dict
    ):
        """
        Comprehensive test verifying all expected category counts.

        This is the main deterministic verification test.
        """
        from src.features.sentiment import SentimentAnalyzer

        analyzer = SentimentAnalyzer()
        features = analyzer.extract_features(golden_sentence)

        # Verify all counts match
        assert features.negative_count == golden_sentence_expected['negative_count']
        assert features.positive_count == golden_sentence_expected['positive_count']
        assert features.uncertainty_count == golden_sentence_expected['uncertainty_count']
        assert features.litigious_count == golden_sentence_expected['litigious_count']
        assert features.total_sentiment_words == golden_sentence_expected['total_sentiment_words']


class TestSentimentAnalyzerBasics:
    """Basic functionality tests for SentimentAnalyzer."""

    def test_analyzer_initialization(self):
        """Verify SentimentAnalyzer can be instantiated."""
        from src.features.sentiment import SentimentAnalyzer

        analyzer = SentimentAnalyzer()
        assert analyzer is not None

    def test_empty_text_handling(self):
        """Verify empty text returns zero counts."""
        from src.features.sentiment import SentimentAnalyzer

        analyzer = SentimentAnalyzer()
        features = analyzer.extract_features("")

        assert features.negative_count == 0
        assert features.positive_count == 0
        assert features.total_sentiment_words == 0

    def test_no_sentiment_words_text(self):
        """Verify text with no sentiment words returns zero counts."""
        from src.features.sentiment import SentimentAnalyzer

        analyzer = SentimentAnalyzer()
        # Common words that are not in LM dictionary
        features = analyzer.extract_features("The quick brown fox jumps over the lazy dog.")

        assert features.negative_count == 0
        assert features.positive_count == 0

    def test_case_insensitive_matching(self):
        """Verify LM dictionary matching is case-insensitive."""
        from src.features.sentiment import SentimentAnalyzer

        analyzer = SentimentAnalyzer()

        # Test various case combinations
        features_lower = analyzer.extract_features("losses")
        features_upper = analyzer.extract_features("LOSSES")
        features_mixed = analyzer.extract_features("Losses")

        # All should detect the same negative word
        assert features_lower.negative_count == features_upper.negative_count == features_mixed.negative_count

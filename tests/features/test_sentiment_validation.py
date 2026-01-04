"""
Sentiment Analysis Validation Tests.

These tests validate sentiment analysis functionality using actual
processed 10-K data from AAPL 2021 filing.

Tests use dynamically resolved paths via TestDataConfig fixtures.
Tests gracefully skip if preprocessing data is not available.
"""

from typing import List, Optional

import numpy as np
import pytest


class TestDictionaryEffectiveness:
    """Tests validating LM dictionary effectiveness."""

    def test_lm_vocabulary_hit_rate(
        self,
        aapl_10k_data: Optional[dict],
        aapl_segments: List[dict]
    ):
        """
        Metric: Percentage of tokens found in LM dictionary.
        Target: > 2% (typical 10-K: 3-5%)
        Why: Validates tokenization compatibility with dictionary.
        """
        if aapl_10k_data is None:
            pytest.skip("AAPL 10-K test data not available")

        from src.features.sentiment import SentimentAnalyzer
        from src.features.dictionaries import LMDictionaryManager

        analyzer = SentimentAnalyzer()
        mgr = LMDictionaryManager.get_instance()

        # Combine all segment texts
        all_text = " ".join(seg["text"] for seg in aapl_segments)
        tokens = analyzer.tokenize(all_text)

        lm_hits = sum(1 for t in tokens if mgr.get_word_categories(t))
        hit_rate = lm_hits / len(tokens) * 100

        # Pre-computed from file: avg_sentiment_word_ratio = 10.85%
        # This confirms hit rate is well above 2% threshold
        assert hit_rate > 2.0, f"LM hit rate {hit_rate:.2f}% below 2% threshold"

        # Additional check: should be close to pre-computed value
        expected_ratio = aapl_10k_data["aggregate_sentiment"]["avg_sentiment_word_ratio"] * 100
        assert abs(hit_rate - expected_ratio) < 5.0, \
            f"Hit rate {hit_rate:.2f}% deviates from expected {expected_ratio:.2f}%"

    def test_zero_vector_rate(self, aapl_segments: List[dict]):
        """
        Metric: Percentage of segments returning 0 for all categories.
        Target: < 50%
        Why: High rate indicates broken matching logic.
        """
        if not aapl_segments:
            pytest.skip("AAPL 10-K test data not available")

        # Count segments with zero sentiment words (pre-computed in file)
        zero_count = sum(
            1 for seg in aapl_segments
            if seg["sentiment"]["total_sentiment_words"] == 0
        )

        total_segments = len(aapl_segments)
        zero_rate = zero_count / total_segments * 100

        # From actual data: only segment #2 has 0 sentiment words
        # That's 1/54 = 1.85% - well below 50% threshold
        assert zero_rate < 50.0, f"Zero-vector rate {zero_rate:.1f}% exceeds 50%"

        # Stricter check for this specific file
        assert zero_count <= 5, f"Too many zero-sentiment segments: {zero_count}/{total_segments}"


class TestCategoryPlausibility:
    """Tests validating 10-K sentiment profile."""

    def test_negative_exceeds_positive_for_10k(
        self,
        aapl_10k_data: Optional[dict],
        aapl_segments: List[dict]
    ):
        """
        Metric: Negative word count > Positive word count.
        Context: 10-Ks are legally defensive documents.
        Why: If Positive > Negative, it's either marketing or a bug.
        """
        if aapl_10k_data is None:
            pytest.skip("AAPL 10-K test data not available")

        # Check aggregate sentiment ratios
        agg = aapl_10k_data["aggregate_sentiment"]
        avg_neg = agg["avg_negative_ratio"]
        avg_pos = agg["avg_positive_ratio"]

        # From actual data: 0.0454 vs 0.0054 (8.4x ratio)
        assert avg_neg > avg_pos, \
            f"Failed 10-K profile: Pos({avg_pos:.4f}) >= Neg({avg_neg:.4f})"

        # Check majority of segments follow pattern
        neg_wins = sum(
            1 for seg in aapl_segments
            if seg["sentiment"]["negative_count"] >= seg["sentiment"]["positive_count"]
        )
        total = len(aapl_segments)
        win_rate = neg_wins / total

        # At least 80% of segments should have Neg >= Pos
        assert win_rate >= 0.80, \
            f"Only {win_rate*100:.1f}% segments have Neg >= Pos (need 80%)"

    def test_uncertainty_negative_correlation(self, aapl_segments: List[dict]):
        """
        Metric: Correlation between Uncertainty and Negative words.
        Target: Pearson r > 0.3
        Why: Both are risk indicators and should correlate.
        """
        if not aapl_segments:
            pytest.skip("AAPL 10-K test data not available")

        # Extract category counts from segments
        uncertainty_counts = [seg["sentiment"]["uncertainty_count"] for seg in aapl_segments]
        negative_counts = [seg["sentiment"]["negative_count"] for seg in aapl_segments]

        # Calculate correlation with numpy (no scipy needed)
        correlation = np.corrcoef(uncertainty_counts, negative_counts)[0, 1]

        # Uncertainty should correlate with Negative (both risk indicators)
        assert correlation > 0.3, f"Unc-Neg correlation {correlation:.2f} too low"

    def test_aggregate_sentiment_ratios_valid(self, aapl_10k_data: Optional[dict]):
        """
        Verify aggregate sentiment ratios are within valid ranges.
        """
        if aapl_10k_data is None:
            pytest.skip("AAPL 10-K test data not available")

        agg = aapl_10k_data["aggregate_sentiment"]

        # All ratios should be between 0 and 1
        assert 0 <= agg["avg_negative_ratio"] <= 1
        assert 0 <= agg["avg_positive_ratio"] <= 1
        assert 0 <= agg["avg_uncertainty_ratio"] <= 1
        assert 0 <= agg["avg_sentiment_word_ratio"] <= 1

        # Sentiment word ratio should be sum of individual ratios (approximately)
        # Note: This is approximate due to words belonging to multiple categories
        total_ratio = agg["avg_sentiment_word_ratio"]
        assert total_ratio > 0, "Total sentiment word ratio should be > 0"


class TestSegmentIntegrity:
    """Tests validating segment data integrity."""

    def test_segment_count(self, aapl_segments: List[dict]):
        """Verify expected number of segments."""
        if not aapl_segments:
            pytest.skip("AAPL 10-K test data not available")

        # AAPL 10-K 2021 has 54 risk factor segments
        assert len(aapl_segments) == 54, f"Expected 54 segments, got {len(aapl_segments)}"

    def test_segments_have_required_fields(self, aapl_segments: List[dict]):
        """Verify all segments have required sentiment fields."""
        if not aapl_segments:
            pytest.skip("AAPL 10-K test data not available")

        required_fields = [
            "negative_count",
            "positive_count",
            "uncertainty_count",
            "litigious_count",
            "constraining_count",
            "total_sentiment_words",
        ]

        for i, seg in enumerate(aapl_segments):
            assert "sentiment" in seg, f"Segment {i} missing 'sentiment' field"
            for field in required_fields:
                assert field in seg["sentiment"], \
                    f"Segment {i} missing '{field}' in sentiment"

    def test_segment_text_not_empty(self, aapl_segments: List[dict]):
        """Verify all segments have non-empty text."""
        if not aapl_segments:
            pytest.skip("AAPL 10-K test data not available")

        for i, seg in enumerate(aapl_segments):
            assert "text" in seg, f"Segment {i} missing 'text' field"
            assert len(seg["text"]) > 0, f"Segment {i} has empty text"

    def test_sentiment_counts_non_negative(self, aapl_segments: List[dict]):
        """Verify all sentiment counts are non-negative."""
        if not aapl_segments:
            pytest.skip("AAPL 10-K test data not available")

        count_fields = [
            "negative_count",
            "positive_count",
            "uncertainty_count",
            "litigious_count",
            "constraining_count",
            "total_sentiment_words",
        ]

        for i, seg in enumerate(aapl_segments):
            for field in count_fields:
                count = seg["sentiment"][field]
                assert count >= 0, f"Segment {i} has negative {field}: {count}"

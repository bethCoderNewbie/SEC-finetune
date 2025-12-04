"""
Tests for RiskSegmenter - validating risk factor segmentation quality using real SEC filing data.

Uses actual data from:
- data/processed/*_segmented_risks.json (segmented risk factors)
- data/interim/extracted/*_extracted_risks.json (source text for re-segmentation tests)

Categories:
1. Segmentation Distribution - segment counts, length consistency (Gini)
2. Fallback Logic Validation - method tracking, fallback rates
3. Semantic Quality - filtering, non-risk content rejection
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Any
import pytest

from src.preprocessing.segmenter import RiskSegmenter, segment_risk_factors


# Data directories
DATA_DIR = Path(__file__).parent.parent.parent / "data"
PROCESSED_DIR = DATA_DIR / "processed"
EXTRACTED_DIR = DATA_DIR / "interim" / "extracted"


def get_segmented_files() -> List[Path]:
    """Get all segmented risk files."""
    return list(PROCESSED_DIR.glob("*_segmented_risks.json"))


def get_extracted_files() -> List[Path]:
    """Get all extracted risk files for re-segmentation tests."""
    files = list(EXTRACTED_DIR.glob("*_extracted_risks.json"))
    # Also check v1_ subdirectory
    v1_dir = EXTRACTED_DIR / "v1_"
    if v1_dir.exists():
        files.extend(v1_dir.glob("*_extracted_risks.json"))
    return files


def load_json(filepath: Path) -> Dict[str, Any]:
    """Load JSON file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def calculate_gini(lengths: List[int]) -> float:
    """Calculate Gini coefficient for segment length distribution."""
    n = len(lengths)
    if n == 0:
        return 0.0
    sorted_lengths = sorted(lengths)
    total = sum(sorted_lengths)
    if total == 0:
        return 0.0
    cumsum = sum((i + 1) * length for i, length in enumerate(sorted_lengths))
    return (2 * cumsum) / (n * total) - (n + 1) / n


@pytest.fixture(scope="module")
def segmented_data() -> List[Dict[str, Any]]:
    """Load all segmented risk data."""
    files = get_segmented_files()
    if not files:
        pytest.skip("No segmented data files found")
    return [load_json(f) for f in files[:10]]  # Limit to 10 for speed


@pytest.fixture(scope="module")
def extracted_data() -> List[Dict[str, Any]]:
    """Load extracted risk data for re-segmentation tests."""
    files = get_extracted_files()
    if not files:
        pytest.skip("No extracted data files found")
    return [load_json(f) for f in files[:5]]  # Limit to 5 for speed


@pytest.fixture
def segmenter():
    return RiskSegmenter()


class TestSegmenterDistributionWithRealData:
    """Tests for segmentation distribution metrics using real SEC filing data."""

    def test_segment_count_range(self, segmented_data: List[Dict]):
        """Verify segment count is within expected range (5-100) for 10-K filings."""
        for doc in segmented_data:
            num_segments = doc.get("num_segments", len(doc.get("segments", [])))
            assert num_segments >= 5, (
                f"{doc.get('filing_name')}: Too few segments: {num_segments}"
            )
            assert num_segments <= 100, (
                f"{doc.get('filing_name')}: Too many segments: {num_segments}"
            )

    def test_non_empty_segmentation(self, segmented_data: List[Dict]):
        """Verify all processed files have segments."""
        for doc in segmented_data:
            segments = doc.get("segments", [])
            assert len(segments) > 0, (
                f"{doc.get('filing_name')}: No segments in processed file"
            )

    def test_gini_coefficient_balanced(self, segmented_data: List[Dict]):
        """Verify segment lengths are balanced (Gini < 0.7)."""
        for doc in segmented_data:
            segments = doc.get("segments", [])
            if len(segments) < 2:
                continue

            lengths = [s.get("length", len(s.get("text", ""))) for s in segments]
            gini = calculate_gini(lengths)

            # Real filings may have more variation than ideal, use 0.7 threshold
            assert gini < 0.7, (
                f"{doc.get('filing_name')}: Gini coefficient {gini:.3f} >= 0.7 (too imbalanced)"
            )

    def test_min_max_ratio(self, segmented_data: List[Dict]):
        """Verify no extreme outliers (min/max ratio > 0.01)."""
        for doc in segmented_data:
            segments = doc.get("segments", [])
            if len(segments) < 2:
                continue

            lengths = [s.get("length", len(s.get("text", ""))) for s in segments]
            min_len = min(lengths)
            max_len = max(lengths)

            ratio = min_len / max_len if max_len > 0 else 0
            # Real filings have more variation, use relaxed threshold
            assert ratio > 0.01, (
                f"{doc.get('filing_name')}: Min/max ratio {ratio:.3f} <= 0.01 (extreme outliers)"
            )

    def test_average_segment_length(self, segmented_data: List[Dict]):
        """Verify average segment length is reasonable."""
        for doc in segmented_data:
            segments = doc.get("segments", [])
            if not segments:
                continue

            lengths = [s.get("length", len(s.get("text", ""))) for s in segments]
            avg_length = sum(lengths) / len(lengths)

            # Risk segments typically 200-3000 chars on average
            assert 100 <= avg_length <= 5000, (
                f"{doc.get('filing_name')}: Average segment length {avg_length:.0f} outside expected range"
            )


class TestSegmenterMetadataWithRealData:
    """Tests for segmentation metadata quality using real SEC filing data."""

    def test_segment_has_required_fields(self, segmented_data: List[Dict]):
        """Verify each segment has required fields."""
        required_fields = {"id", "text", "length", "word_count"}
        for doc in segmented_data:
            segments = doc.get("segments", [])
            for i, seg in enumerate(segments):
                missing = required_fields - set(seg.keys())
                assert len(missing) == 0, (
                    f"{doc.get('filing_name')} segment {i}: Missing fields: {missing}"
                )

    def test_segment_length_matches_text(self, segmented_data: List[Dict]):
        """Verify segment length field matches actual text length."""
        for doc in segmented_data:
            segments = doc.get("segments", [])
            for i, seg in enumerate(segments):
                actual_len = len(seg.get("text", ""))
                reported_len = seg.get("length", 0)
                assert actual_len == reported_len, (
                    f"{doc.get('filing_name')} segment {i}: Length mismatch "
                    f"(reported {reported_len}, actual {actual_len})"
                )

    def test_segment_word_count_accurate(self, segmented_data: List[Dict]):
        """Verify segment word count is reasonably accurate."""
        for doc in segmented_data:
            segments = doc.get("segments", [])
            for i, seg in enumerate(segments):
                text = seg.get("text", "")
                actual_words = len(text.split())
                reported_words = seg.get("word_count", 0)
                # Allow small variance due to tokenization differences
                diff = abs(actual_words - reported_words)
                assert diff <= max(3, reported_words * 0.1), (
                    f"{doc.get('filing_name')} segment {i}: Word count mismatch "
                    f"(reported {reported_words}, actual {actual_words})"
                )

    def test_segment_ids_sequential(self, segmented_data: List[Dict]):
        """Verify segment IDs are sequential starting from 1."""
        for doc in segmented_data:
            segments = doc.get("segments", [])
            ids = [s.get("id") for s in segments]
            expected_ids = list(range(1, len(segments) + 1))
            assert ids == expected_ids, (
                f"{doc.get('filing_name')}: Segment IDs not sequential"
            )


class TestSegmenterQualityWithRealData:
    """Tests for semantic quality filtering using real SEC filing data."""

    def test_segments_have_substantive_content(self, segmented_data: List[Dict]):
        """Verify segments contain substantive risk content."""
        risk_keywords = [
            'risk', 'adverse', 'material', 'significant', 'could',
            'may', 'operations', 'business', 'financial', 'impact'
        ]
        for doc in segmented_data:
            segments = doc.get("segments", [])
            # At least 50% of segments should have risk keywords
            segments_with_keywords = 0
            for seg in segments:
                text = seg.get("text", "").lower()
                if any(kw in text for kw in risk_keywords):
                    segments_with_keywords += 1

            ratio = segments_with_keywords / len(segments) if segments else 0
            assert ratio >= 0.5, (
                f"{doc.get('filing_name')}: Only {ratio:.1%} of segments have risk keywords"
            )

    def test_no_empty_segments(self, segmented_data: List[Dict]):
        """Verify no segments have empty or whitespace-only text."""
        for doc in segmented_data:
            segments = doc.get("segments", [])
            for i, seg in enumerate(segments):
                text = seg.get("text", "").strip()
                assert len(text) > 0, (
                    f"{doc.get('filing_name')} segment {i}: Empty segment text"
                )

    def test_min_word_count_enforcement(self, segmented_data: List[Dict]):
        """Verify segments have minimum word count."""
        min_words = 5  # Relaxed threshold for real data
        for doc in segmented_data:
            segments = doc.get("segments", [])
            for i, seg in enumerate(segments):
                word_count = seg.get("word_count", len(seg.get("text", "").split()))
                assert word_count >= min_words, (
                    f"{doc.get('filing_name')} segment {i}: Only {word_count} words (< {min_words})"
                )

    def test_segments_have_sentence_structure(self, segmented_data: List[Dict]):
        """Verify segments have proper sentence structure."""
        for doc in segmented_data:
            segments = doc.get("segments", [])
            segments_with_sentences = 0
            for seg in segments:
                text = seg.get("text", "")
                # Count sentence endings
                sentence_endings = len(re.findall(r'[.!?]', text))
                if sentence_endings >= 1:
                    segments_with_sentences += 1

            ratio = segments_with_sentences / len(segments) if segments else 0
            # At least 80% of segments should have proper sentences
            assert ratio >= 0.8, (
                f"{doc.get('filing_name')}: Only {ratio:.1%} of segments have sentence structure"
            )


class TestSegmenterSentimentWithRealData:
    """Tests for sentiment analysis integration using real SEC filing data."""

    def test_sentiment_fields_present(self, segmented_data: List[Dict]):
        """Verify sentiment fields are present when enabled."""
        for doc in segmented_data:
            if not doc.get("sentiment_analysis_enabled", False):
                continue

            segments = doc.get("segments", [])
            for i, seg in enumerate(segments):
                sentiment = seg.get("sentiment", {})
                expected_fields = {
                    "negative_count", "positive_count", "uncertainty_count",
                    "negative_ratio", "positive_ratio", "uncertainty_ratio"
                }
                present_fields = set(sentiment.keys())
                missing = expected_fields - present_fields
                assert len(missing) == 0, (
                    f"{doc.get('filing_name')} segment {i}: Missing sentiment fields: {missing}"
                )

    def test_sentiment_ratios_valid(self, segmented_data: List[Dict]):
        """Verify sentiment ratios are between 0 and 1."""
        for doc in segmented_data:
            if not doc.get("sentiment_analysis_enabled", False):
                continue

            segments = doc.get("segments", [])
            for i, seg in enumerate(segments):
                sentiment = seg.get("sentiment", {})
                for ratio_field in ["negative_ratio", "positive_ratio", "uncertainty_ratio"]:
                    ratio = sentiment.get(ratio_field, 0)
                    assert 0 <= ratio <= 1, (
                        f"{doc.get('filing_name')} segment {i}: {ratio_field}={ratio} out of range"
                    )

    def test_aggregate_sentiment_consistent(self, segmented_data: List[Dict]):
        """Verify aggregate sentiment matches segment averages."""
        for doc in segmented_data:
            if not doc.get("sentiment_analysis_enabled", False):
                continue

            aggregate = doc.get("aggregate_sentiment", {})
            segments = doc.get("segments", [])
            if not segments:
                continue

            # Calculate actual average negative ratio
            neg_ratios = [s.get("sentiment", {}).get("negative_ratio", 0) for s in segments]
            actual_avg = sum(neg_ratios) / len(neg_ratios)
            reported_avg = aggregate.get("avg_negative_ratio", 0)

            # Allow small floating point variance
            assert abs(actual_avg - reported_avg) < 0.01, (
                f"{doc.get('filing_name')}: Aggregate sentiment mismatch "
                f"(reported {reported_avg:.4f}, calculated {actual_avg:.4f})"
            )


class TestSegmenterReprocessingWithRealData:
    """Tests for re-segmenting extracted data using RiskSegmenter."""

    def test_segmenter_on_extracted_text(self, segmenter, extracted_data: List[Dict]):
        """Test RiskSegmenter produces valid output on real extracted text."""
        for doc in extracted_data[:3]:  # Limit for speed
            text = doc.get("text", "")
            if len(text) < 100:
                continue

            segments = segmenter.segment_risks(text)

            # Should produce segments
            assert len(segments) > 0, (
                f"Segmenter produced no segments for {doc.get('title', 'unknown')}"
            )

            # All segments should be strings
            assert all(isinstance(s, str) for s in segments), "Segments should be strings"

    def test_segmenter_preserves_content(self, segmenter, extracted_data: List[Dict]):
        """Test that segmenter preserves key content."""
        for doc in extracted_data[:3]:
            text = doc.get("text", "")
            if len(text) < 100:
                continue

            segments = segmenter.segment_risks(text)
            combined = " ".join(segments)

            # Should preserve risk-related keywords
            if "risk" in text.lower():
                assert "risk" in combined.lower(), "Lost 'risk' keyword during segmentation"

    def test_empty_input_handling(self, segmenter):
        """Verify empty input returns empty list."""
        assert segmenter.segment_risks("") == []
        assert segmenter.segment_risks("   ") == []

    def test_convenience_function(self):
        """Test the segment_risk_factors convenience function."""
        text = """
        Competition Risk: We face intense competition in our market segment.
        Our competitors have greater resources than we do currently.

        Regulatory Risk: Our operations are subject to extensive regulations.
        Compliance failures could result in significant penalties.
        """
        segments = segment_risk_factors(text)

        assert isinstance(segments, list), "Should return a list"
        assert all(isinstance(s, str) for s in segments), "All segments should be strings"


class TestSegmenterFilingMetadata:
    """Tests for filing-level metadata in segmented files."""

    def test_filing_metadata_present(self, segmented_data: List[Dict]):
        """Verify filing metadata is present."""
        required_fields = {"filing_name", "section_identifier", "num_segments"}
        for doc in segmented_data:
            missing = required_fields - set(doc.keys())
            assert len(missing) == 0, (
                f"Missing filing metadata fields: {missing}"
            )

    def test_num_segments_accurate(self, segmented_data: List[Dict]):
        """Verify num_segments matches actual segment count."""
        for doc in segmented_data:
            reported = doc.get("num_segments", 0)
            actual = len(doc.get("segments", []))
            assert reported == actual, (
                f"{doc.get('filing_name')}: num_segments mismatch "
                f"(reported {reported}, actual {actual})"
            )

    def test_segmentation_settings_present(self, segmented_data: List[Dict]):
        """Verify segmentation settings are recorded."""
        for doc in segmented_data:
            settings = doc.get("segmentation_settings", {})
            assert "min_segment_length" in settings, (
                f"{doc.get('filing_name')}: Missing min_segment_length in settings"
            )

    def test_section_identifier_valid(self, segmented_data: List[Dict]):
        """Verify section identifier is valid."""
        valid_identifiers = {"part1item1a", "item1a", "risk_factors"}
        for doc in segmented_data:
            identifier = doc.get("section_identifier", "").lower()
            # Check if identifier contains expected patterns
            has_valid = any(vid in identifier for vid in valid_identifiers)
            assert has_valid, (
                f"{doc.get('filing_name')}: Unexpected section identifier: {identifier}"
            )


class TestSegmenterCrossFilingConsistency:
    """Tests for consistency across multiple filings."""

    def test_similar_companies_similar_segment_counts(self, segmented_data: List[Dict]):
        """Verify segment counts are within reasonable range across filings."""
        segment_counts = [
            doc.get("num_segments", len(doc.get("segments", [])))
            for doc in segmented_data
        ]
        if len(segment_counts) < 2:
            pytest.skip("Need at least 2 filings for comparison")

        avg_count = sum(segment_counts) / len(segment_counts)
        # Real filings have high variance - use 5x threshold
        # Some companies consolidate risks, others enumerate extensively
        for i, count in enumerate(segment_counts):
            assert count >= avg_count / 5, (
                f"Filing {i} has unusually few segments: {count} (avg: {avg_count:.0f})"
            )
            assert count <= avg_count * 5, (
                f"Filing {i} has unusually many segments: {count} (avg: {avg_count:.0f})"
            )

    def test_tickers_extracted_correctly(self, segmented_data: List[Dict]):
        """Verify ticker symbols are properly extracted."""
        for doc in segmented_data:
            ticker = doc.get("ticker", "")
            filing_name = doc.get("filing_name", "")

            # Ticker should be uppercase letters
            assert ticker.isalpha() and ticker.isupper(), (
                f"Invalid ticker format: {ticker}"
            )
            # Ticker should appear in filing name
            assert ticker in filing_name, (
                f"Ticker {ticker} not found in filing_name {filing_name}"
            )

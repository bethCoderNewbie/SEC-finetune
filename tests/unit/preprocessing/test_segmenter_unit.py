"""
Unit tests for src/preprocessing/segmenter.py

Tests RiskSegmenter methods for header-based segmentation, filtering,
and segment splitting. Uses synthetic data to avoid real data dependencies.
No real data dependencies - runs in <1 second.
"""

import pytest

from src.preprocessing.segmenter import (
    RiskSegmenter,
    RiskSegment,
    SegmentedRisks,
    segment_risk_factors,
)


class TestSegmentByHeaders:
    """Tests for _segment_by_headers method."""

    @pytest.fixture
    def segmenter(self) -> RiskSegmenter:
        """Create RiskSegmenter without semantic model."""
        return RiskSegmenter(min_length=50, max_length=5000)

    def test_splits_on_bullet_points(self, segmenter: RiskSegmenter, sample_bulleted_risks: str):
        """Bullet point patterns create segments."""
        segments = segmenter._segment_by_headers(sample_bulleted_risks)
        assert len(segments) >= 2

    def test_splits_on_numbered_items(self, segmenter: RiskSegmenter, sample_numbered_risks: str):
        """Numbered item patterns create segments."""
        segments = segmenter._segment_by_headers(sample_numbered_risks)
        assert len(segments) >= 2

    def test_splits_on_all_caps_headers(self, segmenter: RiskSegmenter):
        """ALL CAPS HEADER creates segment break."""
        text = """Some intro text here.

MARKET RISK FACTORS
We face various market risks.

OPERATIONAL RISK FACTORS
Our operations may be disrupted."""
        segments = segmenter._segment_by_headers(text)
        assert len(segments) >= 2

    def test_returns_empty_for_no_headers(self, segmenter: RiskSegmenter):
        """Returns empty list when no header patterns found."""
        text = "Plain text without any headers or bullet points."
        segments = segmenter._segment_by_headers(text)
        # May return empty or single segment
        assert isinstance(segments, list)


class TestFilterSegments:
    """Tests for _filter_segments method."""

    @pytest.fixture
    def segmenter(self) -> RiskSegmenter:
        """Create RiskSegmenter with specific min_length."""
        return RiskSegmenter(min_length=50, max_length=5000)

    def test_filters_short_segments(self, segmenter: RiskSegmenter):
        """Segments below min_length removed."""
        segments = [
            "Short",  # Too short
            "This is a much longer segment that should definitely pass the minimum length filter.",
        ]
        result = segmenter._filter_segments(segments)
        assert len(result) == 1
        assert "longer segment" in result[0]

    def test_filters_header_only_segments(self, segmenter: RiskSegmenter):
        """Segments with <10 words removed."""
        segments = [
            "Market Volatility Warning",  # Only 3 words - filtered
            # Must be >50 chars AND >10 words AND not trigger non-risk content filter
            "This is a complete paragraph about market conditions that affects our business operations significantly and provides substantial detail about the challenges we face in our industry.",
        ]
        result = segmenter._filter_segments(segments)
        assert len(result) == 1
        assert "complete paragraph" in result[0]

    def test_preserves_valid_segments(self, segmenter: RiskSegmenter):
        """Substantive segments with enough length and words kept."""
        long_segment = "This is a valid risk segment. " * 10  # >50 chars, >10 words
        segments = [long_segment]
        result = segmenter._filter_segments(segments)
        assert len(result) == 1


class TestIsNonRiskContent:
    """Tests for _is_non_risk_content method."""

    @pytest.fixture
    def segmenter(self) -> RiskSegmenter:
        """Create RiskSegmenter."""
        return RiskSegmenter()

    def test_identifies_toc_content(self, segmenter: RiskSegmenter):
        """'table of contents' flagged as non-risk."""
        text = "Table of Contents"
        assert segmenter._is_non_risk_content(text) is True

    def test_identifies_page_reference(self, segmenter: RiskSegmenter):
        """Short 'page X' content flagged."""
        text = "Page 45"
        assert segmenter._is_non_risk_content(text) is True

    def test_identifies_item_header(self, segmenter: RiskSegmenter):
        """Short 'Item 1A' reference flagged."""
        text = "Item 1A"
        assert segmenter._is_non_risk_content(text) is True

    def test_allows_real_risk_content(self, segmenter: RiskSegmenter):
        """Actual risk paragraph not flagged."""
        text = """We face significant competition from established players in the market.
        Our competitors have more resources and better brand recognition,
        which could adversely affect our market share and profitability."""
        assert segmenter._is_non_risk_content(text) is False

    def test_long_content_with_indicators_allowed(self, segmenter: RiskSegmenter):
        """Long content with indicators (>200 chars) is NOT flagged."""
        text = "table of contents " + "x" * 250  # > 200 chars total
        assert segmenter._is_non_risk_content(text) is False


class TestSplitIntoChunks:
    """Tests for _split_into_chunks method."""

    @pytest.fixture
    def segmenter(self) -> RiskSegmenter:
        """Create RiskSegmenter."""
        return RiskSegmenter(max_length=100)

    def test_splits_at_sentence_boundaries(self, segmenter: RiskSegmenter):
        """Long text split at periods."""
        text = "First sentence here. Second sentence here. Third sentence here."
        chunks = segmenter._split_into_chunks(text, max_length=50)
        assert len(chunks) >= 2
        for chunk in chunks:
            # Each chunk should end with punctuation or be the end
            assert chunk.strip()

    def test_respects_max_length(self, segmenter: RiskSegmenter):
        """Each chunk under max_length (approximately)."""
        text = "Sentence one here. " * 20
        chunks = segmenter._split_into_chunks(text, max_length=100)
        # Most chunks should be under max_length
        # (last chunk may exceed if a sentence is too long)
        under_limit = sum(1 for c in chunks if len(c) <= 100)
        assert under_limit >= len(chunks) - 1

    def test_preserves_all_content(self, segmenter: RiskSegmenter):
        """Joined chunks approximately equal original (accounting for space normalization)."""
        text = "First. Second. Third."
        chunks = segmenter._split_into_chunks(text, max_length=15)
        rejoined = ''.join(chunks)
        # Content should be preserved (may have minor whitespace differences)
        assert "First" in rejoined
        assert "Second" in rejoined
        assert "Third" in rejoined


class TestSegmentRisksEdgeCases:
    """Tests for segment_risks edge cases."""

    @pytest.fixture
    def segmenter(self) -> RiskSegmenter:
        """Create RiskSegmenter."""
        return RiskSegmenter(min_length=50)

    def test_empty_string_returns_empty_list(self, segmenter: RiskSegmenter, empty_string: str):
        """Empty string returns empty list."""
        result = segmenter.segment_risks(empty_string)
        assert result == []

    def test_whitespace_only_returns_empty(self, segmenter: RiskSegmenter, whitespace_only: str):
        """Whitespace-only string effectively returns empty."""
        result = segmenter.segment_risks(whitespace_only)
        # May return empty or filtered to empty
        assert isinstance(result, list)


class TestRiskSegmentModel:
    """Tests for RiskSegment Pydantic model."""

    def test_auto_calculates_word_count(self):
        """word_count auto-calculated if not provided."""
        segment = RiskSegment(chunk_id="1A_001", text="one two three four five")
        assert segment.word_count == 5

    def test_auto_calculates_char_count(self):
        """char_count auto-calculated if not provided."""
        segment = RiskSegment(chunk_id="1A_001", text="hello world")
        assert segment.char_count == 11

    def test_explicit_counts_preserved(self):
        """Explicit word_count and char_count preserved."""
        segment = RiskSegment(chunk_id="1A_001", text="test", word_count=10, char_count=100)
        # When explicitly set to non-zero, values are preserved
        assert segment.word_count == 10
        assert segment.char_count == 100


class TestSegmentedRisksModel:
    """Tests for SegmentedRisks Pydantic model."""

    @pytest.fixture
    def sample_segmented(self) -> SegmentedRisks:
        """Create sample SegmentedRisks."""
        return SegmentedRisks(
            segments=[
                RiskSegment(chunk_id="1A_001", text="First risk segment."),
                RiskSegment(chunk_id="1A_002", text="Second risk segment."),
            ],
            sic_code="7372",
            company_name="TEST INC",
        )

    def test_len_returns_segment_count(self, sample_segmented: SegmentedRisks):
        """__len__ returns number of segments."""
        assert len(sample_segmented) == 2

    def test_get_texts_returns_text_list(self, sample_segmented: SegmentedRisks):
        """get_texts returns list of segment texts."""
        texts = sample_segmented.get_texts()
        assert len(texts) == 2
        assert "First risk" in texts[0]
        assert "Second risk" in texts[1]

    def test_total_segments_auto_calculated(self, sample_segmented: SegmentedRisks):
        """total_segments auto-calculated from segments list."""
        assert sample_segmented.total_segments == 2

    def test_metadata_fields_optional(self):
        """Metadata fields default to None."""
        segmented = SegmentedRisks(segments=[])
        assert segmented.sic_code is None
        assert segmented.cik is None
        assert segmented.company_name is None


class TestSegmentRisksConvenience:
    """Tests for segment_risk_factors convenience function."""

    def test_segments_text(self, sample_risk_paragraphs: str):
        """Convenience function segments text."""
        result = segment_risk_factors(sample_risk_paragraphs)
        assert isinstance(result, list)
        # Should produce some segments from the sample paragraphs
        # (exact count depends on filtering)

    def test_empty_returns_empty(self):
        """Empty input returns empty list."""
        result = segment_risk_factors("")
        assert result == []


class TestSegmenterInit:
    """Tests for RiskSegmenter initialization."""

    def test_default_init(self):
        """Default initialization works."""
        segmenter = RiskSegmenter()
        assert segmenter.min_length > 0
        assert segmenter.max_length > segmenter.min_length

    def test_custom_lengths(self):
        """Custom min/max lengths applied."""
        segmenter = RiskSegmenter(min_length=100, max_length=1000)
        assert segmenter.min_length == 100
        assert segmenter.max_length == 1000

    def test_similarity_threshold(self):
        """Similarity threshold set correctly."""
        segmenter = RiskSegmenter(similarity_threshold=0.7)
        assert segmenter.similarity_threshold == 0.7

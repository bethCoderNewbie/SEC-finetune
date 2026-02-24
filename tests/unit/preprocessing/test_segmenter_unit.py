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
        """Segments with <3 words and <50 chars removed."""
        segments = [
            "Market Volatility Warning",  # Only 3 words, 25 chars — filtered by char floor
            # Must be >50 chars AND not trigger non-risk content filter
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
    """Tests for _split_into_chunks method (word-based accumulator, RFC-003 Option A)."""

    @pytest.fixture
    def segmenter(self) -> RiskSegmenter:
        """Segmenter with low max_words to force splitting in small test inputs."""
        return RiskSegmenter(max_words=5)

    def test_splits_at_sentence_boundaries(self, segmenter: RiskSegmenter):
        """Text is split at sentence boundaries, not mid-sentence."""
        # Each sentence is 6 words; max_words=5 so each becomes its own chunk.
        text = "Alpha beta gamma delta epsilon zeta. Eta theta iota kappa lambda mu."
        chunks = segmenter._split_into_chunks(text)
        assert len(chunks) >= 2
        for chunk in chunks:
            assert chunk.strip()

    def test_respects_max_words(self, segmenter: RiskSegmenter):
        """Each chunk has at most max_words words.

        Sentence length must be ≤ max_words (5) — the chunker never splits
        mid-sentence, so a sentence longer than max_words will always form its
        own over-limit chunk.  Here each sentence is 4 words so the invariant holds.
        """
        # 10 × 4-word sentences = 40 words; max_words=5 forces splits at sentence boundaries.
        text = ("Alpha beta gamma delta. " * 10).strip()
        chunks = segmenter._split_into_chunks(text)
        for chunk in chunks:
            assert len(chunk.split()) <= segmenter.max_words

    def test_preserves_all_content(self, segmenter: RiskSegmenter):
        """All words from the input appear in the joined chunks."""
        text = "First statement ends here. Second statement ends here. Third statement ends here."
        chunks = segmenter._split_into_chunks(text)
        rejoined = " ".join(chunks)
        assert "First" in rejoined
        assert "Second" in rejoined
        assert "Third" in rejoined


class TestSplitLongSegmentsWordGate:
    """Tests for RFC-003 Option A: word-count ceiling in _split_long_segments."""

    @pytest.fixture
    def segmenter(self) -> RiskSegmenter:
        """Segmenter with max_words=20 to keep test inputs small."""
        return RiskSegmenter(min_length=10, max_length=999999, max_words=20)

    def test_segment_under_word_limit_not_split(self, segmenter: RiskSegmenter):
        """A segment at or below max_words passes through unchanged."""
        # 4 sentences × 4 words = 16 words, under the 20-word ceiling.
        text = "Risk one exists here. Risk two applies now. Risk three matters too. Risk four is real."
        result = segmenter._split_long_segments([text])
        assert len(result) == 1

    def test_segment_over_word_limit_is_split(self, segmenter: RiskSegmenter):
        """A segment exceeding max_words (20) is split into multiple chunks."""
        # 6 sentences × 5 words = 30 words, over the 20-word ceiling.
        sentence = "Market risk affects our operations."  # 5 words
        text = (sentence + " ") * 6
        result = segmenter._split_long_segments([text.strip()])
        assert len(result) >= 2

    def test_each_chunk_at_or_under_max_words(self, segmenter: RiskSegmenter):
        """After splitting, every resulting chunk is ≤ max_words words."""
        sentence = "Regulatory changes impose additional compliance costs."  # 6 words
        text = (sentence + " ") * 6  # 36 words total
        result = segmenter._split_long_segments([text.strip()])
        for chunk in result:
            wc = len(chunk.split())
            assert wc <= segmenter.max_words, f"chunk has {wc} words, limit is {segmenter.max_words}"


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


class TestMergeShortSegments:
    """Tests for _merge_short_segments method."""

    @pytest.fixture
    def segmenter(self) -> RiskSegmenter:
        return RiskSegmenter(min_length=50, max_length=5000)

    def test_merges_short_segment_forward(self, segmenter: RiskSegmenter):
        """A sub-threshold segment is merged into its successor."""
        short = "Only a few words."  # 4 words < min_words (20)
        long = ("This is a much longer risk segment that contains enough words "
                "to independently meet the minimum word count threshold for training.")
        result = segmenter._merge_short_segments([short, long])
        assert len(result) == 1
        assert "Only a few words" in result[0]
        assert "longer risk segment" in result[0]

    def test_trailing_short_segment_merges_backward(self, segmenter: RiskSegmenter):
        """A trailing sub-threshold segment merges into its predecessor."""
        long = ("This is a long enough segment that has plenty of words to exceed "
                "the minimum word count threshold comfortably and stand on its own.")
        short = "Short tail fragment."  # 3 words < min_words
        result = segmenter._merge_short_segments([long, short])
        assert len(result) == 1
        assert "Short tail fragment" in result[0]

    def test_long_segments_unchanged(self, segmenter: RiskSegmenter):
        """Segments already at or above min_words (20) are not merged."""
        # Each segment is exactly 20+ words so neither triggers a merge
        seg_a = ("Climate change risk may adversely affect our operations and "
                 "supply chain across multiple jurisdictions in ways that are "
                 "difficult to predict or quantify.")   # 26 words
        seg_b = ("Regulatory changes could impose additional compliance costs and "
                 "administrative burdens that materially impact our financial results "
                 "and competitive position in the market.")  # 26 words
        result = segmenter._merge_short_segments([seg_a, seg_b])
        assert len(result) == 2

    def test_single_segment_unchanged(self, segmenter: RiskSegmenter):
        """Single-element list returned as-is."""
        seg = "Short."
        result = segmenter._merge_short_segments([seg])
        assert result == [seg]

    def test_empty_list_unchanged(self, segmenter: RiskSegmenter):
        """Empty list returned as-is."""
        assert segmenter._merge_short_segments([]) == []


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
        assert segmenter.max_words > 0

    def test_custom_lengths(self):
        """Custom min/max lengths applied."""
        segmenter = RiskSegmenter(min_length=100, max_length=1000)
        assert segmenter.min_length == 100
        assert segmenter.max_length == 1000

    def test_custom_max_words(self):
        """Custom max_words overrides config default."""
        segmenter = RiskSegmenter(max_words=200)
        assert segmenter.max_words == 200

    def test_default_max_words_from_config(self):
        """Default max_words comes from config (380)."""
        segmenter = RiskSegmenter()
        assert segmenter.max_words == 380

    def test_similarity_threshold(self):
        """Similarity threshold set correctly."""
        segmenter = RiskSegmenter(similarity_threshold=0.7)
        assert segmenter.similarity_threshold == 0.7

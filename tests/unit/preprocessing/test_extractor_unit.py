"""
Unit tests for src/preprocessing/extractor.py

Tests SECSectionExtractor helper methods for pattern matching, title normalization,
and element type counting. Uses mocks to avoid sec-parser dependencies where possible.
No real data dependencies - runs in <1 second.
"""

import pytest
from unittest.mock import MagicMock

from src.preprocessing.extractor import SECSectionExtractor, ExtractedSection
from src.preprocessing.constants import SECTION_PATTERNS


class TestMatchesSectionPattern:
    """Tests for _matches_section_pattern method."""

    @pytest.fixture
    def extractor(self) -> SECSectionExtractor:
        """Create SECSectionExtractor instance."""
        return SECSectionExtractor()

    @pytest.mark.parametrize("text,section_id,expected", [
        ("Item 1A. Risk Factors", "part1item1a", True),
        ("ITEM 1A RISK FACTORS", "part1item1a", True),
        ("item 1a. risk", "part1item1a", True),
        ("Item 2. Properties", "part1item1a", False),
        ("Something else", "part1item1a", False),
        ("Item 1B. Unresolved", "part1item1a", False),
    ])
    def test_pattern_matching_item_1a(
        self, extractor: SECSectionExtractor, text: str, section_id: str, expected: bool
    ):
        """Item 1A section patterns match correctly."""
        result = extractor._matches_section_pattern(text, section_id)
        assert result == expected

    @pytest.mark.parametrize("text,section_id,expected", [
        ("Item 7. Management's Discussion", "part2item7", True),
        ("ITEM 7 MD&A", "part2item7", True),
        ("Item 7.", "part2item7", True),
        ("Item 7A. Quantitative", "part2item7", False),  # 7A is different
        ("Item 8. Financial", "part2item7", False),
    ])
    def test_pattern_matching_item_7(
        self, extractor: SECSectionExtractor, text: str, section_id: str, expected: bool
    ):
        """Item 7 (MD&A) section patterns match correctly."""
        result = extractor._matches_section_pattern(text, section_id)
        assert result == expected

    def test_returns_false_for_unknown_section(self, extractor: SECSectionExtractor):
        """Unknown section_id returns False."""
        result = extractor._matches_section_pattern("Any text", "unknown_section")
        assert result is False


class TestNormalizeTitle:
    """Tests for _normalize_title method."""

    @pytest.fixture
    def extractor(self) -> SECSectionExtractor:
        """Create SECSectionExtractor instance."""
        return SECSectionExtractor()

    def test_removes_punctuation(self, extractor: SECSectionExtractor):
        """Punctuation removed from title."""
        result = extractor._normalize_title("Item 1A. Risk Factors")
        assert "." not in result

    def test_lowercases_text(self, extractor: SECSectionExtractor):
        """Title converted to lowercase."""
        result = extractor._normalize_title("ITEM 1A RISK")
        assert result == result.lower()

    def test_collapses_whitespace(self, extractor: SECSectionExtractor):
        """Multiple spaces become single space."""
        result = extractor._normalize_title("Item   1A    Risk")
        assert "   " not in result
        assert "  " not in result

    def test_strips_result(self, extractor: SECSectionExtractor):
        """Result is stripped."""
        result = extractor._normalize_title("  Item 1A  ")
        assert not result.startswith(" ")
        assert not result.endswith(" ")


class TestExtractKeyIdentifier:
    """Tests for _extract_key_identifier method."""

    @pytest.fixture
    def extractor(self) -> SECSectionExtractor:
        """Create SECSectionExtractor instance."""
        return SECSectionExtractor()

    def test_extracts_item_1a(self, extractor: SECSectionExtractor):
        """Extracts 'item 1a' from title."""
        result = extractor._extract_key_identifier("Item 1A. Risk Factors")
        assert result == "item 1a"

    def test_extracts_item_7(self, extractor: SECSectionExtractor):
        """Extracts 'item 7' from title."""
        result = extractor._extract_key_identifier("Item 7. Management's Discussion")
        assert result == "item 7"

    def test_extracts_item_7a(self, extractor: SECSectionExtractor):
        """Extracts 'item 7a' from title."""
        result = extractor._extract_key_identifier("Item 7A. Quantitative Disclosures")
        assert result == "item 7a"

    def test_returns_none_for_no_match(self, extractor: SECSectionExtractor):
        """Returns None when no Item pattern found."""
        result = extractor._extract_key_identifier("Some Other Title")
        assert result is None


class TestCountElementTypes:
    """Tests for _count_element_types method."""

    @pytest.fixture
    def extractor(self) -> SECSectionExtractor:
        """Create SECSectionExtractor instance."""
        return SECSectionExtractor()

    def test_counts_single_type(self, extractor: SECSectionExtractor):
        """Single element type counted correctly."""
        elements = [
            {'type': 'TextElement', 'text': 'a'},
            {'type': 'TextElement', 'text': 'b'},
        ]
        result = extractor._count_element_types(elements)
        assert result == {'TextElement': 2}

    def test_counts_multiple_types(self, extractor: SECSectionExtractor):
        """Multiple element types counted correctly."""
        elements = [
            {'type': 'TextElement', 'text': 'a'},
            {'type': 'TitleElement', 'text': 'b'},
            {'type': 'TextElement', 'text': 'c'},
            {'type': 'TableElement', 'text': 'd'},
        ]
        result = extractor._count_element_types(elements)
        assert result == {'TextElement': 2, 'TitleElement': 1, 'TableElement': 1}

    def test_empty_list_returns_empty_dict(self, extractor: SECSectionExtractor):
        """Empty element list returns empty dict."""
        result = extractor._count_element_types([])
        assert result == {}


class TestGetSectionTitle:
    """Tests for _get_section_title method."""

    @pytest.fixture
    def extractor(self) -> SECSectionExtractor:
        """Create SECSectionExtractor instance."""
        return SECSectionExtractor()

    def test_gets_10k_title(self, extractor: SECSectionExtractor):
        """Gets correct title for 10-K section."""
        result = extractor._get_section_title("part1item1a", "10-K")
        # Should return configured title or section_id
        assert result is not None
        assert len(result) > 0

    def test_gets_10q_title(self, extractor: SECSectionExtractor):
        """Gets correct title for 10-Q section."""
        result = extractor._get_section_title("part2item1a", "10-Q")
        assert result is not None

    def test_returns_section_id_for_unknown(self, extractor: SECSectionExtractor):
        """Returns section_id when title not found."""
        result = extractor._get_section_title("unknown_section", "10-K")
        assert result == "unknown_section"


class TestExtractedSectionModel:
    """Tests for ExtractedSection Pydantic model."""

    @pytest.fixture
    def sample_section(self) -> ExtractedSection:
        """Create sample ExtractedSection."""
        return ExtractedSection(
            text="Sample risk factor text with sufficient length.",
            identifier="part1item1a",
            title="Item 1A. Risk Factors",
            subsections=["Market Risk", "Credit Risk"],
            elements=[
                {'type': 'TextElement', 'text': 'text1'},
                {'type': 'TableElement', 'text': 'table1'},
                {'type': 'TextElement', 'text': 'text2'},
            ],
            metadata={'num_subsections': 2},
        )

    def test_len_returns_text_length(self, sample_section: ExtractedSection):
        """__len__ returns character count of text."""
        assert len(sample_section) == len(sample_section.text)

    def test_get_tables_filters_correctly(self, sample_section: ExtractedSection):
        """get_tables returns only TableElement types."""
        tables = sample_section.get_tables()
        assert len(tables) == 1
        assert all(t['type'] == 'TableElement' for t in tables)

    def test_get_paragraphs_includes_text_types(self, sample_section: ExtractedSection):
        """get_paragraphs includes TextElement and ParagraphElement."""
        paragraphs = sample_section.get_paragraphs()
        assert len(paragraphs) == 2
        assert all(p['type'] in ['TextElement', 'ParagraphElement'] for p in paragraphs)

    def test_optional_metadata_fields(self):
        """Optional metadata fields default to None."""
        section = ExtractedSection(
            text="Text",
            identifier="id",
            title="Title",
            subsections=[],
            elements=[],
            metadata={},
        )
        assert section.sic_code is None
        assert section.cik is None
        assert section.company_name is None

    def test_metadata_fields_preserved(self, sample_filing_metadata: dict):
        """Metadata fields preserved when set."""
        section = ExtractedSection(
            text="Text",
            identifier="id",
            title="Title",
            subsections=[],
            elements=[],
            metadata={},
            sic_code=sample_filing_metadata['sic_code'],
            cik=sample_filing_metadata['cik'],
            company_name=sample_filing_metadata['company_name'],
        )
        assert section.sic_code == "7372"
        assert section.cik == "0000320193"
        assert section.company_name == "APPLE INC"


class TestExtractorInit:
    """Tests for SECSectionExtractor initialization."""

    def test_extractor_initializes(self):
        """Extractor initializes without error."""
        extractor = SECSectionExtractor()
        assert extractor is not None

    def test_has_section_titles(self):
        """Extractor has section title mappings."""
        extractor = SECSectionExtractor()
        assert hasattr(extractor, 'SECTION_TITLES_10K')
        assert hasattr(extractor, 'SECTION_TITLES_10Q')


class TestBulletListDetection:
    """A1: BULLET_LIST_PAT corpus-representative test cases."""

    @pytest.mark.parametrize("text,expected", [
        # Unicode bullets — 94.1% of corpus, no space after bullet
        ("•Supply chain disruption may impact revenue", True),
        ("•Cybersecurity threats including ransomware", True),
        ("• Supply chain risk with space", True),      # space variant
        ("·middle-dot bullet entry", True),
        ("▪square bullet entry", True),
        # Parenthetical — 27.3% of corpus
        ("(1) Risk of increased regulation", True),
        ("(12) Extended parenthetical index", True),
        # Numbered list
        ("1. Competition from new entrants", True),
        ("23. Numbered risk entry", True),
        # Non-bullets — must not match
        ("The company faces macroeconomic risks", False),
        ("Our supply chain depends on third parties", False),
        # Edge cases
        ("", False),
        ("  ", False),
    ])
    def test_bullet_list_pat(self, text, expected):
        from src.preprocessing.constants import BULLET_LIST_PAT
        result = bool(BULLET_LIST_PAT.match(text))
        assert result == expected, f"BULLET_LIST_PAT.match({text!r}) → {result}, expected {expected}"


class TestTitleLevel:
    """A2a: TitleLevel enum values and completeness."""

    @pytest.fixture
    def extractor(self) -> SECSectionExtractor:
        """Create SECSectionExtractor instance."""
        return SECSectionExtractor()

    def test_values_are_ordered(self):
        from src.preprocessing.constants import TitleLevel
        assert TitleLevel.H1.value < TitleLevel.H2.value < TitleLevel.H3.value
        assert TitleLevel.H3.value < TitleLevel.H4.value < TitleLevel.H5.value
        assert TitleLevel.H5.value < TitleLevel.BODY.value

    def test_body_sentinel_value(self):
        from src.preprocessing.constants import TitleLevel
        assert TitleLevel.BODY.value == 99

    def test_names_are_strings(self):
        from src.preprocessing.constants import TitleLevel
        assert TitleLevel.H3.name == "H3"
        assert TitleLevel.BODY.name == "BODY"

    def test_build_level_map_empty(self, extractor):
        """Empty content_nodes → empty map."""
        result = extractor._build_title_level_map([])
        assert result == {}

    def test_build_level_map_single_level(self, extractor):
        """Single unique TitleElement level → maps to H3."""
        # _build_title_level_map uses isinstance(elem, sp.TitleElement).
        # If sec_parser unavailable, returns {}; skip gracefully.
        try:
            import sec_parser as sp
        except ImportError:
            pytest.skip("sec_parser not installed")

        mock_elem = MagicMock(spec=sp.TitleElement)
        mock_elem.level = 2
        mock_node = MagicMock()
        mock_node.semantic_element = mock_elem

        from src.preprocessing.constants import TitleLevel
        result = extractor._build_title_level_map([mock_node])
        assert result == {2: TitleLevel.H3}

    def test_build_level_map_two_levels(self, extractor):
        """Two distinct levels → H3 for smaller, H4 for larger."""
        try:
            import sec_parser as sp
        except ImportError:
            pytest.skip("sec_parser not installed")

        def make_node(lvl):
            m_elem = MagicMock(spec=sp.TitleElement)
            m_elem.level = lvl
            m_node = MagicMock()
            m_node.semantic_element = m_elem
            return m_node

        from src.preprocessing.constants import TitleLevel
        result = extractor._build_title_level_map([make_node(0), make_node(2)])
        assert result[0] == TitleLevel.H3
        assert result[2] == TitleLevel.H4

    def test_build_level_map_capped_at_h5(self, extractor):
        """Four distinct levels: 4th and beyond all map to H5."""
        try:
            import sec_parser as sp
        except ImportError:
            pytest.skip("sec_parser not installed")

        def make_node(lvl):
            m = MagicMock(spec=sp.TitleElement)
            m.level = lvl
            n = MagicMock()
            n.semantic_element = m
            return n

        from src.preprocessing.constants import TitleLevel
        result = extractor._build_title_level_map(
            [make_node(0), make_node(1), make_node(2), make_node(3)]
        )
        assert result[0] == TitleLevel.H3
        assert result[1] == TitleLevel.H4
        assert result[2] == TitleLevel.H5
        assert result[3] == TitleLevel.H5  # capped

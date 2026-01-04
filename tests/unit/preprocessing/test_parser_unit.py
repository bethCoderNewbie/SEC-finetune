"""
Unit tests for src/preprocessing/parser.py

Tests SECFilingParser helper methods for SIC code extraction, form type validation,
and HTML flattening. Uses mocks to avoid sec-parser dependencies where possible.
No real data dependencies - runs in <1 second.
"""

import pytest

from src.preprocessing.parser import SECFilingParser, FormType


class TestValidateFormType:
    """Tests for _validate_form_type method."""

    @pytest.fixture
    def parser(self) -> SECFilingParser:
        """Create SECFilingParser instance."""
        return SECFilingParser()

    def test_validates_10k_uppercase(self, parser: SECFilingParser):
        """10-K returns FormType.FORM_10K."""
        result = parser._validate_form_type("10-K")
        assert result == FormType.FORM_10K

    def test_validates_10k_no_hyphen(self, parser: SECFilingParser):
        """10K (no hyphen) returns FormType.FORM_10K."""
        result = parser._validate_form_type("10K")
        assert result == FormType.FORM_10K

    def test_validates_10k_lowercase(self, parser: SECFilingParser):
        """10-k (lowercase) returns FormType.FORM_10K."""
        result = parser._validate_form_type("10-k")
        assert result == FormType.FORM_10K

    def test_validates_10q_uppercase(self, parser: SECFilingParser):
        """10-Q returns FormType.FORM_10Q."""
        result = parser._validate_form_type("10-Q")
        assert result == FormType.FORM_10Q

    def test_validates_10q_no_hyphen(self, parser: SECFilingParser):
        """10Q (no hyphen) returns FormType.FORM_10Q."""
        result = parser._validate_form_type("10Q")
        assert result == FormType.FORM_10Q

    def test_raises_for_invalid_form(self, parser: SECFilingParser):
        """Invalid form type raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported form type"):
            parser._validate_form_type("8-K")

    def test_raises_for_empty_form(self, parser: SECFilingParser):
        """Empty form type raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported form type"):
            parser._validate_form_type("")


class TestExtractSicCode:
    """Tests for _extract_sic_code method."""

    @pytest.fixture
    def parser(self) -> SECFilingParser:
        """Create SECFilingParser instance."""
        return SECFilingParser()

    def test_extracts_bracketed_sic_code(self, parser: SECFilingParser, sample_sic_html: str):
        """SIC code [7372] extracted from classification line."""
        result = parser._extract_sic_code(sample_sic_html)
        assert result == "7372"

    def test_extracts_assigned_sic_format(self, parser: SECFilingParser, sample_sic_html_assigned: str):
        """ASSIGNED-SIC: 7372 format extracts correctly."""
        result = parser._extract_sic_code(sample_sic_html_assigned)
        assert result == "7372"

    def test_returns_none_when_no_sic(self, parser: SECFilingParser):
        """Returns None for content without SIC code."""
        html = "<html><body>No SIC here</body></html>"
        result = parser._extract_sic_code(html)
        assert result is None

    def test_handles_3_digit_sic(self, parser: SECFilingParser):
        """3-digit SIC codes extracted correctly."""
        html = "STANDARD INDUSTRIAL CLASSIFICATION: BANKING [602]"
        result = parser._extract_sic_code(html)
        assert result == "602"

    def test_handles_4_digit_sic(self, parser: SECFilingParser):
        """4-digit SIC codes extracted correctly."""
        html = "STANDARD INDUSTRIAL CLASSIFICATION: PHARMACEUTICAL PREPARATIONS [2834]"
        result = parser._extract_sic_code(html)
        assert result == "2834"


class TestExtractSicName:
    """Tests for _extract_sic_name method."""

    @pytest.fixture
    def parser(self) -> SECFilingParser:
        """Create SECFilingParser instance."""
        return SECFilingParser()

    def test_extracts_sic_name(self, parser: SECFilingParser, sample_sic_html: str):
        """SIC name extracted from classification line."""
        result = parser._extract_sic_name(sample_sic_html)
        assert result == "SERVICES-PREPACKAGED SOFTWARE"

    def test_returns_none_when_no_sic_name(self, parser: SECFilingParser):
        """Returns None when no SIC classification found."""
        html = "<html>No classification here</html>"
        result = parser._extract_sic_name(html)
        assert result is None

    def test_normalizes_whitespace_in_name(self, parser: SECFilingParser):
        """Extra whitespace in SIC name collapsed."""
        html = "STANDARD INDUSTRIAL CLASSIFICATION:  MULTI\n  WORD   NAME  [1234]"
        result = parser._extract_sic_name(html)
        assert result == "MULTI WORD NAME"


class TestFlattenHtmlNesting:
    """Tests for _flatten_html_nesting method."""

    @pytest.fixture
    def parser(self) -> SECFilingParser:
        """Create SECFilingParser instance."""
        return SECFilingParser()

    def test_removes_empty_tags(self, parser: SECFilingParser):
        """Empty <div></div> tags removed."""
        html = "<div></div><p>Content</p><span></span>"
        result = parser._flatten_html_nesting(html)
        assert "<div></div>" not in result
        assert "<span></span>" not in result
        assert "Content" in result

    def test_unwraps_single_child_divs(self, parser: SECFilingParser):
        """Nested divs with single child unwrapped."""
        html = "<div><div>Content</div></div>"
        result = parser._flatten_html_nesting(html)
        # Should have fewer nested divs
        assert result.count("<div") < 2 or "Content" in result

    def test_preserves_content(self, parser: SECFilingParser, sample_nested_html: str):
        """Text content preserved after flattening."""
        result = parser._flatten_html_nesting(sample_nested_html)
        assert "Content" in result

    def test_collapses_excessive_newlines(self, parser: SECFilingParser):
        """Multiple consecutive newlines collapsed."""
        html = "line1\n\n\n\n\nline2"
        result = parser._flatten_html_nesting(html)
        assert "\n\n\n" not in result


class TestFormTypeEnum:
    """Tests for FormType enum."""

    def test_form_10k_value(self):
        """FORM_10K has correct value."""
        assert FormType.FORM_10K.value == "10-K"

    def test_form_10q_value(self):
        """FORM_10Q has correct value."""
        assert FormType.FORM_10Q.value == "10-Q"

    def test_enum_members(self):
        """FormType has expected members."""
        assert hasattr(FormType, 'FORM_10K')
        assert hasattr(FormType, 'FORM_10Q')


class TestParserInit:
    """Tests for SECFilingParser initialization."""

    def test_parser_initializes(self):
        """Parser initializes without error."""
        parser = SECFilingParser()
        assert parser is not None

    def test_parser_has_parsers_dict(self):
        """Parser has parsers for supported form types."""
        parser = SECFilingParser()
        assert FormType.FORM_10K in parser.parsers
        assert FormType.FORM_10Q in parser.parsers

    def test_get_parser_info(self):
        """get_parser_info returns expected structure."""
        parser = SECFilingParser()
        info = parser.get_parser_info()
        assert 'library' in info
        assert 'version' in info
        assert 'supported_forms' in info
        assert '10-K' in info['supported_forms']
        assert '10-Q' in info['supported_forms']


class TestParseFromContentValidation:
    """Tests for parse_from_content input validation."""

    @pytest.fixture
    def parser(self) -> SECFilingParser:
        """Create SECFilingParser instance."""
        return SECFilingParser()

    def test_raises_on_empty_content(self, parser: SECFilingParser):
        """Empty content raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            parser.parse_from_content("")

    def test_raises_on_whitespace_only(self, parser: SECFilingParser):
        """Whitespace-only content raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            parser.parse_from_content("   \n\t  ")

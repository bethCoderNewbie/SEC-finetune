"""
Unit tests for src/preprocessing/cleaning.py

Tests TextCleaner methods for whitespace normalization, page artifact removal,
punctuation normalization, and HTML tag removal.
No real data dependencies - runs in <1 second.
"""

import pytest

from src.preprocessing.cleaning import TextCleaner, clean_filing_text


class TestNormalizeWhitespace:
    """Tests for _normalize_whitespace method."""

    @pytest.fixture
    def cleaner(self) -> TextCleaner:
        """Create basic TextCleaner."""
        return TextCleaner()

    def test_collapses_multiple_spaces(self, cleaner: TextCleaner):
        """Multiple spaces become single space."""
        result = cleaner._normalize_whitespace("word   word")
        assert result == "word word"

    def test_collapses_multiple_newlines(self, cleaner: TextCleaner):
        """Three+ newlines become double newline."""
        result = cleaner._normalize_whitespace("para1\n\n\n\npara2")
        assert result == "para1\n\npara2"

    def test_replaces_tabs_with_spaces(self, cleaner: TextCleaner):
        """Tabs converted to spaces."""
        result = cleaner._normalize_whitespace("word\tword")
        assert result == "word word"

    def test_strips_line_edges(self, cleaner: TextCleaner):
        """Leading/trailing spaces on lines removed."""
        result = cleaner._normalize_whitespace("  line1  \n  line2  ")
        assert result == "line1\nline2"

    def test_preserves_paragraph_breaks(self, cleaner: TextCleaner):
        """Double newlines (paragraph breaks) preserved."""
        result = cleaner._normalize_whitespace("para1\n\npara2")
        assert "\n\n" in result


class TestRemovePageArtifacts:
    """Tests for _remove_page_artifacts method."""

    @pytest.fixture
    def cleaner(self) -> TextCleaner:
        """Create basic TextCleaner."""
        return TextCleaner()

    def test_removes_standalone_page_numbers(self, cleaner: TextCleaner, sample_page_artifacts_text: str):
        """-12- and 'Page 45' patterns removed."""
        result = cleaner._remove_page_artifacts(sample_page_artifacts_text)
        assert "-12-" not in result
        assert "Page 45" not in result

    def test_removes_toc_dots_pattern(self, cleaner: TextCleaner):
        """'... 45' at end of line removed."""
        text = "Item 1A. Risk Factors... 45"
        result = cleaner._remove_page_artifacts(text)
        assert "... 45" not in result

    def test_preserves_inline_numbers(self, cleaner: TextCleaner):
        """Numbers within sentences preserved."""
        text = "Revenue was $12 million in 2023."
        result = cleaner._remove_page_artifacts(text)
        assert "12" in result
        assert "2023" in result

    def test_removes_various_page_formats(self, cleaner: TextCleaner):
        """Various page number formats removed."""
        text = """Content here
-5-
page 10
PAGE 15
More content"""
        result = cleaner._remove_page_artifacts(text)
        assert "-5-" not in result


class TestRemoveTocArtifacts:
    """Tests for _remove_toc_artifacts method."""

    @pytest.fixture
    def cleaner(self) -> TextCleaner:
        """Create basic TextCleaner."""
        return TextCleaner()

    def test_removes_toc_entries(self, cleaner: TextCleaner, sample_toc_artifacts_text: str):
        """TOC entries with dots removed."""
        result = cleaner._remove_toc_artifacts(sample_toc_artifacts_text)
        assert "..... 25" not in result
        assert "Actual content starts here" in result

    def test_preserves_normal_item_references(self, cleaner: TextCleaner):
        """Normal item references preserved."""
        text = "As discussed in Item 1A, risks are significant."
        result = cleaner._remove_toc_artifacts(text)
        assert "Item 1A" in result

    def test_removes_toc_roman_numerals(self, cleaner: TextCleaner):
        """ToC with Roman numerals removed."""
        text = "Part IV Item 15. Exhibits..... 89\nActual content"
        result = cleaner._remove_toc_artifacts(text)
        assert "Part IV Item 15" not in result
        assert "Actual content" in result

    def test_removes_toc_spaced_dots(self, cleaner: TextCleaner):
        """ToC with spaced dots removed."""
        text = "Item 1A. Risk Factors . . . . . 25\nActual content"
        result = cleaner._remove_toc_artifacts(text)
        assert ". . . . ." not in result
        assert "Actual content" in result

    def test_removes_toc_middle_dot_leaders(self, cleaner: TextCleaner):
        """ToC with middle-dot leaders removed."""
        text = "Item 1A. Risk Factors · · · · · 25\nActual content"
        result = cleaner._remove_toc_artifacts(text)
        assert "· · ·" not in result
        assert "Actual content" in result

    def test_removes_toc_no_period_after_item(self, cleaner: TextCleaner):
        """ToC without period after Item number removed."""
        text = "Item 1A Risk Factors..... 25\nActual content"
        result = cleaner._remove_toc_artifacts(text)
        assert "....." not in result
        assert "Actual content" in result

    def test_removes_toc_alternative_separators(self, cleaner: TextCleaner):
        """ToC with dashes/underscores removed."""
        text = "Item 1A. Risk Factors ━━━━━ 25\nActual content"
        result = cleaner._remove_toc_artifacts(text)
        assert "━━━━━" not in result
        assert "Actual content" in result

    def test_removes_toc_subsection_numbering(self, cleaner: TextCleaner):
        """ToC with subsection numbers removed."""
        text = "Item 1A.1. Sub-risk factors..... 45\nActual content"
        result = cleaner._remove_toc_artifacts(text)
        assert "Item 1A.1" not in result
        assert "Actual content" in result

    def test_removes_toc_leader_only(self, cleaner: TextCleaner):
        """ToC with leader-only (no page number) removed."""
        text = "Item 1A. Risk Factors......\nActual content"
        result = cleaner._remove_toc_artifacts(text)
        assert "......" not in result
        assert "Actual content" in result

    @pytest.mark.parametrize("toc_line", [
        "Part IV Item 15. Exhibits..... 89",
        "Item 1A. Risk Factors . . . . . 25",
        "Item 1A. Risk Factors · · · · · 25",
        "Item 1A Risk Factors..... 25",
        "Item 1A. Risk Factors ━━━━━ 25",
        "Item 1A.1. Sub-risk..... 45",
        "Item 1A. Risk Factors......",
    ])
    def test_removes_diverse_toc_formats(self, cleaner: TextCleaner, toc_line: str):
        """Parametrized test for diverse ToC formats."""
        text = f"{toc_line}\nActual content here"
        result = cleaner._remove_toc_artifacts(text)

        # ToC line should be removed
        assert toc_line not in result
        # Content should remain
        assert "Actual content here" in result


class TestNormalizePunctuation:
    """Tests for _normalize_punctuation method."""

    @pytest.fixture
    def cleaner(self) -> TextCleaner:
        """Create basic TextCleaner."""
        return TextCleaner()

    def test_normalizes_curly_double_quotes(self, cleaner: TextCleaner, sample_curly_quotes_text: str):
        """Curly double quotes (U+201C, U+201D) become straight quotes."""
        result = cleaner._normalize_punctuation(sample_curly_quotes_text)
        assert "\u201c" not in result
        assert "\u201d" not in result
        assert '"' in result

    def test_normalizes_curly_single_quotes(self, cleaner: TextCleaner):
        """Curly single quotes (U+2018, U+2019) become straight apostrophe."""
        text = "company\u2019s \u2018test\u2019"
        result = cleaner._normalize_punctuation(text)
        assert "\u2018" not in result
        assert "\u2019" not in result
        assert "'" in result

    def test_removes_duplicate_punctuation(self, cleaner: TextCleaner):
        """Multiple periods/exclamations collapsed."""
        text = "Wow!!! Amazing..."
        result = cleaner._normalize_punctuation(text)
        assert "!!!" not in result
        assert "..." not in result
        assert "!" in result
        assert "." in result


class TestRemoveHtmlTags:
    """Tests for remove_html_tags method."""

    @pytest.fixture
    def cleaner(self) -> TextCleaner:
        """Create basic TextCleaner."""
        return TextCleaner()

    def test_removes_simple_tags(self, cleaner: TextCleaner):
        """<p>text</p> becomes 'text'."""
        result = cleaner.remove_html_tags("<p>Content here</p>")
        assert "<p>" not in result
        assert "</p>" not in result
        assert "Content here" in result

    def test_removes_script_tags_with_content(self, cleaner: TextCleaner):
        """<script>...</script> fully removed."""
        html = "<p>Before</p><script>alert('test')</script><p>After</p>"
        result = cleaner.remove_html_tags(html)
        assert "<script>" not in result
        assert "alert" not in result
        assert "Before" in result
        assert "After" in result

    def test_removes_style_tags_with_content(self, cleaner: TextCleaner):
        """<style>...</style> fully removed."""
        html = "<style>.class { color: red; }</style><p>Text</p>"
        result = cleaner.remove_html_tags(html)
        assert "<style>" not in result
        assert "color:" not in result
        assert "Text" in result

    def test_decodes_html_entities(self, cleaner: TextCleaner):
        """&amp; becomes &."""
        result = cleaner.remove_html_tags("<p>R&amp;D</p>")
        assert "&" in result
        assert "&amp;" not in result

    def test_removes_html_comments(self, cleaner: TextCleaner):
        """HTML comments removed."""
        html = "Text<!-- comment -->More"
        result = cleaner.remove_html_tags(html)
        assert "<!-- comment -->" not in result
        assert "TextMore" in result


class TestCleanText:
    """Tests for clean_text method."""

    @pytest.fixture
    def cleaner(self) -> TextCleaner:
        """Create basic TextCleaner."""
        return TextCleaner()

    def test_empty_string_returns_empty(self, cleaner: TextCleaner, empty_string: str):
        """Empty input returns empty output."""
        result = cleaner.clean_text(empty_string)
        assert result == ""

    def test_whitespace_only_returns_empty(self, cleaner: TextCleaner, whitespace_only: str):
        """Whitespace-only input returns empty output."""
        result = cleaner.clean_text(whitespace_only)
        assert result == ""

    def test_applies_all_cleaning_steps(self, cleaner: TextCleaner):
        """All cleaning steps applied in order."""
        text = "  word   word  \n\n\n\n  -5-  \n\n  \u201cquote\u201d  "
        result = cleaner.clean_text(text)
        # Whitespace normalized
        assert "   " not in result
        # Page numbers removed
        assert "-5-" not in result
        # Quotes normalized
        assert '"' in result

    def test_strips_final_output(self, cleaner: TextCleaner):
        """Final output is stripped."""
        text = "  content  "
        result = cleaner.clean_text(text)
        assert not result.startswith(" ")
        assert not result.endswith(" ")


class TestCleanFilingTextConvenience:
    """Tests for clean_filing_text convenience function."""

    def test_basic_cleaning(self):
        """Basic cleaning without options."""
        text = "  word   word  "
        result = clean_filing_text(text)
        assert result == "word word"

    def test_remove_html_option(self):
        """remove_html option removes HTML tags."""
        html = "<p>Content</p>"
        result = clean_filing_text(html, remove_html=True)
        assert "<p>" not in result
        assert "Content" in result

    def test_preserves_html_by_default(self):
        """HTML preserved when remove_html=False (default)."""
        html = "<p>Content</p>"
        result = clean_filing_text(html, remove_html=False)
        # Tags still present (though may be slightly modified by whitespace normalization)
        assert "Content" in result


class TestTextCleanerInit:
    """Tests for TextCleaner initialization."""

    def test_default_init(self):
        """Default initialization works."""
        cleaner = TextCleaner()
        assert cleaner.use_lemmatization is False
        assert cleaner.remove_stopwords is False
        assert cleaner.remove_punctuation is False
        assert cleaner.remove_numbers is False

    def test_custom_init(self):
        """Custom initialization options work."""
        cleaner = TextCleaner(
            use_lemmatization=False,  # Keep False to avoid spaCy dependency
            remove_punctuation=True,
            remove_numbers=True,
        )
        assert cleaner.remove_punctuation is True
        assert cleaner.remove_numbers is True

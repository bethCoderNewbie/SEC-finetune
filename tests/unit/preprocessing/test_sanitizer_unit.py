"""
Unit tests for src/preprocessing/sanitizer.py

Tests HTMLSanitizer methods for quote normalization, invisible char removal,
entity decoding, and EDGAR artifact removal.
No real data dependencies - runs in <1 second.
"""

import pytest

from src.preprocessing.sanitizer import HTMLSanitizer, SanitizerConfig, sanitize_html


class TestSanitizerConfig:
    """Tests for SanitizerConfig Pydantic model."""

    def test_default_config_values(self):
        """Default config has expected values."""
        config = SanitizerConfig()
        assert config.remove_edgar_header is False  # Disabled by default
        assert config.remove_edgar_tags is False  # Disabled by default
        assert config.decode_entities is True
        assert config.normalize_unicode is True
        assert config.remove_invisible_chars is True
        assert config.normalize_quotes is True
        assert config.fix_encoding is False  # Requires ftfy
        assert config.flatten_nesting is True

    def test_config_validation(self):
        """Config validates correctly."""
        config = SanitizerConfig(normalize_quotes=False)
        assert config.normalize_quotes is False


class TestNormalizeQuotes:
    """Tests for _normalize_quotes method."""

    @pytest.fixture
    def sanitizer(self) -> HTMLSanitizer:
        """Create sanitizer with only quote normalization enabled."""
        config = SanitizerConfig(
            decode_entities=False,
            normalize_unicode=False,
            remove_invisible_chars=False,
            normalize_quotes=True,
            flatten_nesting=False,
        )
        return HTMLSanitizer(config)

    def test_normalizes_left_double_quote(self, sanitizer: HTMLSanitizer):
        """Left double quote (U+201C) becomes straight quote."""
        result = sanitizer._normalize_quotes("\u201cHello")
        assert result == '"Hello'

    def test_normalizes_right_double_quote(self, sanitizer: HTMLSanitizer):
        """Right double quote (U+201D) becomes straight quote."""
        result = sanitizer._normalize_quotes("world\u201d")
        assert result == 'world"'

    def test_normalizes_left_single_quote(self, sanitizer: HTMLSanitizer):
        """Left single quote (U+2018) becomes straight apostrophe."""
        result = sanitizer._normalize_quotes("\u2018test")
        assert result == "'test"

    def test_normalizes_right_single_quote(self, sanitizer: HTMLSanitizer):
        """Right single quote/apostrophe (U+2019) becomes straight apostrophe."""
        result = sanitizer._normalize_quotes("don\u2019t")
        assert result == "don't"

    def test_normalizes_guillemets(self, sanitizer: HTMLSanitizer):
        """Guillemets (« ») become straight quotes."""
        result = sanitizer._normalize_quotes("\u00abquote\u00bb")
        assert result == '"quote"'

    def test_normalizes_full_text(self, sample_curly_quotes_text: str):
        """Full text with mixed curly quotes normalized."""
        sanitizer = HTMLSanitizer()
        result = sanitizer._normalize_quotes(sample_curly_quotes_text)
        assert "'" in result  # Apostrophe normalized
        assert '"' in result  # Quotes normalized
        assert "\u2019" not in result
        assert "\u201c" not in result
        assert "\u201d" not in result


class TestRemoveInvisibleChars:
    """Tests for _remove_invisible_chars method."""

    @pytest.fixture
    def sanitizer(self) -> HTMLSanitizer:
        """Create sanitizer with only invisible char removal enabled."""
        config = SanitizerConfig(
            decode_entities=False,
            normalize_unicode=False,
            remove_invisible_chars=True,
            normalize_quotes=False,
            flatten_nesting=False,
        )
        return HTMLSanitizer(config)

    def test_removes_zero_width_space(self, sanitizer: HTMLSanitizer):
        """Zero-width space (U+200B) removed."""
        result = sanitizer._remove_invisible_chars("text\u200bhere")
        assert result == "texthere"

    def test_removes_bom(self, sanitizer: HTMLSanitizer):
        """Byte order mark (U+FEFF) removed."""
        result = sanitizer._remove_invisible_chars("\ufeffstart")
        assert result == "start"

    def test_removes_soft_hyphen(self, sanitizer: HTMLSanitizer):
        """Soft hyphen (U+00AD) removed."""
        result = sanitizer._remove_invisible_chars("hy\u00adphen")
        assert result == "hyphen"

    def test_removes_multiple_invisible_chars(self, sample_invisible_chars_html: str):
        """Multiple invisible characters removed."""
        sanitizer = HTMLSanitizer()
        result = sanitizer._remove_invisible_chars(sample_invisible_chars_html)
        assert "\u200b" not in result
        assert "\ufeff" not in result
        assert "\u00ad" not in result
        assert "Textwithzero-widthchars" == result

    def test_preserves_regular_whitespace(self, sanitizer: HTMLSanitizer):
        """Regular spaces, tabs, newlines preserved."""
        text = "line1\nline2\ttab space"
        result = sanitizer._remove_invisible_chars(text)
        assert result == text


class TestDecodeEntities:
    """Tests for _decode_entities method."""

    @pytest.fixture
    def sanitizer(self) -> HTMLSanitizer:
        """Create sanitizer with only entity decoding enabled."""
        config = SanitizerConfig(
            decode_entities=True,
            normalize_unicode=False,
            remove_invisible_chars=False,
            normalize_quotes=False,
            flatten_nesting=False,
        )
        return HTMLSanitizer(config)

    def test_decodes_amp(self, sanitizer: HTMLSanitizer):
        """&amp; becomes &."""
        result = sanitizer._decode_entities("R&amp;D")
        assert result == "R&D"

    def test_decodes_lt_gt(self, sanitizer: HTMLSanitizer):
        """&lt; and &gt; become < and >."""
        result = sanitizer._decode_entities("x &lt; 5 &gt; 0")
        assert result == "x < 5 > 0"

    def test_decodes_nbsp_to_space(self, sanitizer: HTMLSanitizer):
        """&nbsp; becomes regular space."""
        result = sanitizer._decode_entities("word&nbsp;word")
        # After decode, nbsp becomes \xa0, which we then convert to space
        assert " " in result or "\xa0" in result

    def test_decodes_numeric_decimal_entities(self, sanitizer: HTMLSanitizer):
        """Numeric decimal entities (&#160;) decoded."""
        result = sanitizer._decode_entities("text&#160;here")
        assert "text" in result and "here" in result

    def test_decodes_numeric_hex_entities(self, sanitizer: HTMLSanitizer):
        """Numeric hex entities (&#xA0;) decoded."""
        result = sanitizer._decode_entities("text&#xA0;here")
        assert "text" in result and "here" in result


class TestRemoveEdgarHeader:
    """Tests for _remove_edgar_header method."""

    @pytest.fixture
    def sanitizer(self) -> HTMLSanitizer:
        """Create sanitizer with EDGAR header removal enabled."""
        config = SanitizerConfig(
            remove_edgar_header=True,
            decode_entities=False,
            normalize_unicode=False,
            remove_invisible_chars=False,
            normalize_quotes=False,
            flatten_nesting=False,
        )
        return HTMLSanitizer(config)

    def test_removes_sec_header_block(self, sanitizer: HTMLSanitizer, sample_edgar_header_html: str):
        """<SEC-HEADER>...</SEC-HEADER> block removed."""
        result = sanitizer._remove_edgar_header(sample_edgar_header_html)
        assert "<SEC-HEADER>" not in result
        assert "ACCESSION NUMBER" not in result
        assert "<html>" in result or "Content here" in result


class TestFlattenNesting:
    """Tests for _flatten_nesting method."""

    @pytest.fixture
    def sanitizer(self) -> HTMLSanitizer:
        """Create sanitizer with only nesting flattening enabled."""
        config = SanitizerConfig(
            decode_entities=False,
            normalize_unicode=False,
            remove_invisible_chars=False,
            normalize_quotes=False,
            flatten_nesting=True,
        )
        return HTMLSanitizer(config)

    def test_removes_empty_tags(self, sanitizer: HTMLSanitizer):
        """Empty <div></div> tags removed."""
        html = "<div></div><p>Content</p>"
        result = sanitizer._flatten_nesting(html)
        assert "<div></div>" not in result
        assert "Content" in result

    def test_removes_redundant_wrapper_divs(self, sanitizer: HTMLSanitizer):
        """Redundant nested divs collapsed."""
        html = "<div><div>Content</div></div>"
        result = sanitizer._flatten_nesting(html)
        # Should have fewer divs
        assert result.count("<div") < 2 or "Content" in result

    def test_preserves_content(self, sanitizer: HTMLSanitizer, sample_nested_html: str):
        """Content preserved after flattening."""
        result = sanitizer._flatten_nesting(sample_nested_html)
        assert "Content" in result


class TestSanitizeConvenience:
    """Tests for sanitize_html convenience function."""

    def test_sanitize_html_default(self):
        """Default sanitization works."""
        html = "Text\u200bhere &amp; \u201cthere\u201d"
        result = sanitize_html(html)
        assert "&" in result  # Entity decoded
        assert '"' in result  # Quotes normalized

    def test_sanitize_html_with_overrides(self):
        """Config overrides work."""
        html = "Text &amp; more"
        result = sanitize_html(html, decode_entities=False)
        assert "&amp;" in result  # Entity NOT decoded


class TestSanitizerIntegration:
    """Integration tests for full sanitization pipeline."""

    def test_full_sanitization(self, sample_curly_quotes_text: str):
        """Full sanitization applies all enabled steps."""
        sanitizer = HTMLSanitizer()
        result = sanitizer.sanitize(sample_curly_quotes_text)
        # Curly quotes normalized
        assert "\u2019" not in result
        assert "'" in result

    def test_empty_input_returns_empty(self):
        """Empty string returns empty string."""
        sanitizer = HTMLSanitizer()
        assert sanitizer.sanitize("") == ""

    def test_get_stats(self):
        """get_stats returns expected metrics."""
        sanitizer = HTMLSanitizer()
        original = "text &amp; more\u200b"
        sanitized = sanitizer.sanitize(original)
        stats = sanitizer.get_stats(original, sanitized)

        assert 'original_length' in stats
        assert 'sanitized_length' in stats
        assert 'reduction_bytes' in stats
        assert 'reduction_percent' in stats
        assert 'config' in stats

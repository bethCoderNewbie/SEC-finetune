"""
HTML Sanitizer for SEC Filings

Pre-parser sanitization to improve ParsedFiling quality.
Runs BEFORE sec-parser to clean raw HTML and improve extraction accuracy.

Flow: Raw HTML → HTMLSanitizer → sec-parser → ParsedFiling

Sanitization steps:
1. EDGAR artifact removal (<PAGE>, <S>, <C> tags, submission headers)
2. HTML entity decoding (&amp; → &, &nbsp; → space)
3. Unicode normalization (NFKC)
4. Invisible character removal (zero-width spaces, control chars)
5. Smart quote normalization (curly → straight quotes)
6. Encoding fix (mojibake detection and correction)
"""

import re
import unicodedata
from html import unescape
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SanitizerConfig(BaseModel):
    """
    Configuration for HTML sanitization (Pydantic V2 compliant).

    Attributes:
        remove_edgar_header: Remove SEC EDGAR submission header boilerplate
        remove_edgar_tags: Remove EDGAR SGML tags (<PAGE>, <S>, <C>, etc.)
        decode_entities: Decode HTML entities (&amp; → &)
        normalize_unicode: Apply NFKC Unicode normalization
        remove_invisible_chars: Remove zero-width spaces and control characters
        normalize_quotes: Convert curly/smart quotes to straight ASCII quotes
        fix_encoding: Attempt to fix mojibake (encoding errors)
        flatten_nesting: Remove redundant nested tags (div, span, font)
    """
    model_config = ConfigDict(
        validate_assignment=True,
        extra='forbid',
    )

    remove_edgar_header: bool = Field(
        default=False,
        description="Remove SEC EDGAR submission header boilerplate (WARNING: disables metadata extraction)"
    )
    remove_edgar_tags: bool = Field(
        default=False,
        description="Remove EDGAR SGML tags (<PAGE>, <S>, <C>, etc.) - WARNING: breaks sec-parser structure"
    )
    decode_entities: bool = Field(
        default=True,
        description="Decode HTML entities (&amp; → &)"
    )
    normalize_unicode: bool = Field(
        default=True,
        description="Apply NFKC Unicode normalization"
    )
    remove_invisible_chars: bool = Field(
        default=True,
        description="Remove zero-width spaces and control characters"
    )
    normalize_quotes: bool = Field(
        default=True,
        description="Convert curly/smart quotes to straight ASCII quotes"
    )
    fix_encoding: bool = Field(
        default=False,
        description="Attempt to fix mojibake (requires ftfy library)"
    )
    flatten_nesting: bool = Field(
        default=True,
        description="Remove redundant nested tags (div, span, font)"
    )


class HTMLSanitizer:
    """
    Pre-parser HTML sanitizer for SEC filings.

    Cleans raw HTML before sec-parser to improve extraction quality.
    All operations are designed to preserve document structure while
    removing noise that can interfere with parsing.

    Example:
        >>> sanitizer = HTMLSanitizer()
        >>> clean_html = sanitizer.sanitize(raw_html)
        >>> # Now parse with sec-parser
        >>> elements = parser.parse(clean_html)

        >>> # Or with custom config
        >>> config = SanitizerConfig(fix_encoding=True)
        >>> sanitizer = HTMLSanitizer(config)
        >>> clean_html = sanitizer.sanitize(raw_html)
    """

    # EDGAR SGML tags commonly found in SEC filings
    EDGAR_TAGS = [
        'PAGE', 'S', 'C', 'F', 'R',  # Layout tags
        'DOCUMENT', 'TYPE', 'SEQUENCE', 'FILENAME', 'DESCRIPTION',  # Document tags
        'TEXT', 'PDF', 'XML', 'XBRL',  # Content type tags
    ]

    # Invisible Unicode characters to remove
    INVISIBLE_CHARS = [
        '\u200b',  # Zero-width space
        '\u200c',  # Zero-width non-joiner
        '\u200d',  # Zero-width joiner
        '\ufeff',  # Byte order mark (BOM)
        '\u00ad',  # Soft hyphen
        '\u2060',  # Word joiner
        '\u180e',  # Mongolian vowel separator
    ]

    # Control characters (except tab, newline, carriage return)
    CONTROL_CHAR_PATTERN = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')

    def __init__(self, config: Optional[SanitizerConfig] = None):
        """
        Initialize the HTML sanitizer.

        Args:
            config: Sanitization configuration. Uses defaults if not provided.
        """
        self.config = config or SanitizerConfig()
        self._ftfy_available = self._check_ftfy()

    def _check_ftfy(self) -> bool:
        """Check if ftfy library is available for encoding fixes."""
        try:
            import ftfy  # noqa: F401
            return True
        except ImportError:
            return False

    def sanitize(self, html: str) -> str:
        """
        Apply all configured sanitization steps to HTML content.

        Args:
            html: Raw HTML content from SEC filing

        Returns:
            Sanitized HTML ready for parsing

        Note:
            Order of operations matters. Steps are applied in optimal order
            to ensure each step doesn't interfere with subsequent steps.
        """
        if not html:
            return html

        # Step 1: Remove EDGAR submission header (before other processing)
        if self.config.remove_edgar_header:
            html = self._remove_edgar_header(html)

        # Step 2: Remove EDGAR SGML tags
        if self.config.remove_edgar_tags:
            html = self._remove_edgar_tags(html)

        # Step 3: Fix encoding issues (before entity decoding)
        if self.config.fix_encoding and self._ftfy_available:
            html = self._fix_encoding(html)

        # Step 4: Decode HTML entities
        if self.config.decode_entities:
            html = self._decode_entities(html)

        # Step 5: Normalize Unicode
        if self.config.normalize_unicode:
            html = self._normalize_unicode(html)

        # Step 6: Remove invisible characters
        if self.config.remove_invisible_chars:
            html = self._remove_invisible_chars(html)

        # Step 7: Normalize quotes
        if self.config.normalize_quotes:
            html = self._normalize_quotes(html)

        # Step 8: Flatten nested tags (last, as it modifies structure)
        if self.config.flatten_nesting:
            html = self._flatten_nesting(html)

        return html

    def _remove_edgar_header(self, html: str) -> str:
        """
        Remove SEC EDGAR submission header boilerplate.

        The header contains metadata like:
        - ACCESSION NUMBER
        - CONFORMED SUBMISSION TYPE
        - FILED AS OF DATE
        - etc.

        This metadata is useful but can interfere with content parsing
        if not properly isolated.
        """
        # Pattern to match EDGAR header section
        # Headers typically end before <HTML> or first content tag
        patterns = [
            # Match from start to first <html> tag
            r'^.*?(?=<html)',
            # Match SEC-HEADER...SEC-HEADER section
            r'<SEC-HEADER>.*?</SEC-HEADER>',
            # Match IMS-HEADER...IMS-HEADER section
            r'<IMS-HEADER>.*?</IMS-HEADER>',
        ]

        for pattern in patterns:
            html = re.sub(pattern, '', html, flags=re.IGNORECASE | re.DOTALL)

        return html

    def _remove_edgar_tags(self, html: str) -> str:
        """
        Remove EDGAR SGML tags that are not valid HTML.

        These tags are used by EDGAR system but can confuse HTML parsers:
        - <PAGE> - Page break marker
        - <S> - Section marker
        - <C> - Column marker
        - <F> - Footnote marker
        - etc.
        """
        for tag in self.EDGAR_TAGS:
            # Remove opening tags: <TAG> or <TAG attr="value">
            html = re.sub(
                rf'<{tag}[^>]*>',
                '',
                html,
                flags=re.IGNORECASE
            )
            # Remove closing tags: </TAG>
            html = re.sub(
                rf'</{tag}>',
                '',
                html,
                flags=re.IGNORECASE
            )

        return html

    def _fix_encoding(self, html: str) -> str:
        """
        Attempt to fix mojibake (garbled text from encoding issues).

        Uses the ftfy library which can detect and fix common encoding errors
        like UTF-8 decoded as Latin-1.
        """
        try:
            import ftfy
            return ftfy.fix_text(html)
        except ImportError:
            return html

    def _decode_entities(self, html: str) -> str:
        """
        Decode HTML entities to their character equivalents.

        Examples:
        - &amp; → &
        - &lt; → <
        - &gt; → >
        - &nbsp; → (non-breaking space, converted to regular space)
        - &#160; → (space)
        - &mdash; → —

        Note: We preserve < and > for HTML structure, only decode
        entities that appear in text content.
        """
        # First pass: decode standard entities
        html = unescape(html)

        # Handle &nbsp; specifically (convert to regular space)
        html = html.replace('\xa0', ' ')  # Non-breaking space to space

        # Handle any remaining numeric entities
        html = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), html)
        html = re.sub(r'&#x([0-9a-fA-F]+);', lambda m: chr(int(m.group(1), 16)), html)

        return html

    def _normalize_unicode(self, html: str) -> str:
        """
        Apply NFKC Unicode normalization.

        NFKC (Compatibility Decomposition, followed by Canonical Composition):
        - Converts compatibility characters to their canonical equivalents
        - ﬁ → fi (ligature to separate characters)
        - ² → 2 (superscript to regular)
        - Ω → Ω (ohm sign to Greek omega)
        - ™ → TM (trademark to letters)

        This ensures consistent text representation for pattern matching.
        """
        return unicodedata.normalize('NFKC', html)

    def _remove_invisible_chars(self, html: str) -> str:
        """
        Remove invisible Unicode characters that can interfere with parsing.

        These characters are invisible but can break:
        - Word tokenization
        - Pattern matching
        - Text comparison
        """
        # Remove specific invisible characters
        for char in self.INVISIBLE_CHARS:
            html = html.replace(char, '')

        # Remove control characters (except whitespace)
        html = self.CONTROL_CHAR_PATTERN.sub('', html)

        return html

    def _normalize_quotes(self, html: str) -> str:
        """
        Convert curly/smart quotes to straight ASCII quotes.

        Curly quotes can interfere with pattern matching and are
        inconsistently used across SEC filings.

        Conversions:
        - " (U+201C) → " (U+0022) - Left double quote
        - " (U+201D) → " (U+0022) - Right double quote
        - ' (U+2018) → ' (U+0027) - Left single quote
        - ' (U+2019) → ' (U+0027) - Right single quote/apostrophe
        - « (U+00AB) → " - Left guillemet
        - » (U+00BB) → " - Right guillemet
        - ‹ (U+2039) → ' - Single left guillemet
        - › (U+203A) → ' - Single right guillemet
        """
        # Double quotes
        html = html.replace('\u201c', '"')  # Left double quotation mark
        html = html.replace('\u201d', '"')  # Right double quotation mark
        html = html.replace('\u00ab', '"')  # Left-pointing double angle quotation
        html = html.replace('\u00bb', '"')  # Right-pointing double angle quotation
        html = html.replace('\u201e', '"')  # Double low-9 quotation mark

        # Single quotes / apostrophes
        html = html.replace('\u2018', "'")  # Left single quotation mark
        html = html.replace('\u2019', "'")  # Right single quotation mark (apostrophe)
        html = html.replace('\u2039', "'")  # Single left-pointing angle quotation
        html = html.replace('\u203a', "'")  # Single right-pointing angle quotation
        html = html.replace('\u201a', "'")  # Single low-9 quotation mark

        # Prime marks (sometimes used as quotes)
        html = html.replace('\u2032', "'")  # Prime (feet, minutes)
        html = html.replace('\u2033', '"')  # Double prime (inches, seconds)

        return html

    def _flatten_nesting(self, html: str) -> str:
        """
        Remove redundant nested tags to reduce HTML depth.

        SEC filings often have excessive nesting like:
        <div><div><div>content</div></div></div>

        This flattening improves parsing speed and reduces recursion depth.
        """
        # Remove empty tags
        empty_tags = ['div', 'span', 'p', 'font', 'b', 'i', 'u']
        for tag in empty_tags:
            # Remove completely empty tags: <tag></tag> or <tag />
            html = re.sub(
                rf'<{tag}[^>]*>\s*</{tag}>',
                '',
                html,
                flags=re.IGNORECASE
            )

        # Remove redundant wrapper divs (div containing only another div)
        for _ in range(5):  # Limit iterations
            prev_len = len(html)
            html = re.sub(
                r'<div[^>]*>\s*(<div[^>]*>.*?</div>)\s*</div>',
                r'\1',
                html,
                flags=re.IGNORECASE | re.DOTALL
            )
            if len(html) == prev_len:
                break

        # Remove redundant font tags
        for _ in range(3):
            prev_len = len(html)
            html = re.sub(
                r'<font[^>]*>\s*(<font[^>]*>.*?</font>)\s*</font>',
                r'\1',
                html,
                flags=re.IGNORECASE | re.DOTALL
            )
            if len(html) == prev_len:
                break

        # Collapse excessive whitespace
        html = re.sub(r'\n\s*\n\s*\n+', '\n\n', html)

        return html

    def get_stats(self, original: str, sanitized: str) -> dict:
        """
        Get statistics about the sanitization process.

        Args:
            original: Original HTML content
            sanitized: Sanitized HTML content

        Returns:
            Dictionary with sanitization statistics
        """
        return {
            'original_length': len(original),
            'sanitized_length': len(sanitized),
            'reduction_bytes': len(original) - len(sanitized),
            'reduction_percent': (1 - len(sanitized) / len(original)) * 100 if original else 0,
            'config': self.config.model_dump(),
        }


def sanitize_html(html: str, **kwargs) -> str:
    """
    Convenience function to sanitize HTML with optional config overrides.

    Args:
        html: Raw HTML content
        **kwargs: Config overrides passed to SanitizerConfig

    Returns:
        Sanitized HTML

    Example:
        >>> clean = sanitize_html(raw_html, fix_encoding=True)
    """
    config = SanitizerConfig(**kwargs) if kwargs else None
    sanitizer = HTMLSanitizer(config)
    return sanitizer.sanitize(html)


if __name__ == "__main__":
    # Example usage and testing
    print("HTML Sanitizer for SEC Filings")
    print("=" * 50)

    sample_html = """
    <SEC-HEADER>
    ACCESSION NUMBER: 0000320193-21-000105
    CONFORMED SUBMISSION TYPE: 10-K
    </SEC-HEADER>
    <html>
    <body>
    <PAGE>
    <div><div><div>
    <p>The Company's revenue &amp; earnings increased significantly.</p>
    <p>"We're committed to innovation," said the CEO.</p>
    <p>Risk factors include:</p>
    </div></div></div>
    </body>
    </html>
    """

    sanitizer = HTMLSanitizer()
    clean_html = sanitizer.sanitize(sample_html)
    stats = sanitizer.get_stats(sample_html, clean_html)

    print("\nOriginal HTML:")
    print(sample_html[:200] + "...")
    print(f"\nOriginal length: {stats['original_length']}")

    print("\nSanitized HTML:")
    print(clean_html[:200] + "...")
    print(f"\nSanitized length: {stats['sanitized_length']}")
    print(f"Reduction: {stats['reduction_percent']:.1f}%")

    print("\nSanitization steps applied:")
    for key, value in stats['config'].items():
        if value:
            print(f"  ✓ {key}")

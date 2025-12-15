"""
Cleaning module for SEC 10-K filing text
Cleans and normalizes extracted text for further processing using spaCy
"""

import re
from typing import Optional, Set, List
from html import unescape
import string

try:
    import spacy
    from spacy.language import Language
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    print("Warning: spaCy not available. Install with: pip install spacy")
    print("Then download model: python -m spacy download en_core_web_sm")


class TextCleaner:
    """Cleans and normalizes SEC filing text using spaCy"""

    def __init__(self,
                 use_lemmatization: bool = False,
                 remove_stopwords: bool = False,
                 remove_punctuation: bool = False,
                 remove_numbers: bool = False,
                 custom_stopwords: Optional[Set[str]] = None,
                 spacy_model: str = "en_core_web_sm"):
        """
        Initialize TextCleaner with spaCy

        Args:
            use_lemmatization: Whether to apply lemmatization
            remove_stopwords: Whether to remove stop words
            remove_punctuation: Whether to remove punctuation
            remove_numbers: Whether to remove numbers
            custom_stopwords: Custom set of stop words to use (optional)
            spacy_model: spaCy model to use (default: en_core_web_sm)
        """
        self.use_lemmatization = use_lemmatization
        self.remove_stopwords = remove_stopwords
        self.remove_punctuation = remove_punctuation
        self.remove_numbers = remove_numbers

        # Initialize spaCy
        # Note: spaCy is needed for deep_clean, lemmatization, or stopword removal
        self.nlp = None
        self._spacy_model = spacy_model
        if SPACY_AVAILABLE and (use_lemmatization or remove_stopwords):
            self._init_spacy(spacy_model)

        # Set up custom stop words
        if custom_stopwords:
            if self.nlp:
                # Add custom stopwords to spaCy's stopwords
                for word in custom_stopwords:
                    self.nlp.vocab[word].is_stop = True

    def _init_spacy(self, model_name: str):
        """
        Initialize spaCy with optimized pipeline

        Args:
            model_name: Name of spaCy model to load
        """
        try:
            # Load model with only necessary components for efficiency
            # Disable parser and NER if we only need lemmatization/stopwords
            self.nlp = spacy.load(
                model_name,
                disable=["parser", "ner"]  # Disable unused components for speed
            )

            # Increase max_length for long SEC filings (default is 1,000,000)
            self.nlp.max_length = 2000000  # 2M characters

        except OSError:
            print(f"spaCy model '{model_name}' not found.")
            print(f"Download it with: python -m spacy download {model_name}")
            self.nlp = None

    def clean_text(self, text: str, deep_clean: bool = False) -> str:
        """
        Clean and normalize filing text

        Args:
            text: Raw text to clean
            deep_clean: If True, apply advanced NLP preprocessing (lemmatization, stopwords, etc.)

        Returns:
            str: Cleaned text
        """
        if not text:
            return ""

        # Remove excessive whitespace
        text = self._normalize_whitespace(text)

        # Remove page numbers and headers/footers
        text = self._remove_page_artifacts(text)

        # Remove table of contents artifacts
        text = self._remove_toc_artifacts(text)

        # Normalize punctuation
        text = self._normalize_punctuation(text)

        # Apply deep cleaning with spaCy if requested
        if deep_clean:
            # Lazy-initialize spaCy if not already done
            if self.nlp is None and SPACY_AVAILABLE:
                self._init_spacy(self._spacy_model)
            if self.nlp:
                text = self._apply_nlp_cleaning(text)

        # Final whitespace cleanup
        text = self._normalize_whitespace(text)

        return text.strip()

    def _normalize_whitespace(self, text: str) -> str:
        """
        Normalize whitespace (multiple spaces, tabs, newlines)

        Args:
            text: Input text

        Returns:
            str: Text with normalized whitespace
        """
        # Replace tabs with spaces
        text = text.replace('\t', ' ')

        # Replace multiple spaces with single space
        text = re.sub(r' +', ' ', text)

        # Replace multiple newlines with double newline (paragraph break)
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)

        # Remove spaces at the beginning/end of lines
        text = '\n'.join(line.strip() for line in text.split('\n'))

        return text

    def _remove_page_artifacts(self, text: str) -> str:
        """
        Remove page numbers, headers, and footers

        Args:
            text: Input text

        Returns:
            str: Text without page artifacts
        """
        # Remove standalone page numbers (e.g., "Page 12", "12", "-12-")
        text = re.sub(r'^[\s\-]*\d+[\s\-]*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'^[\s\-]*Page\s+\d+[\s\-]*$', '', text, flags=re.MULTILINE | re.IGNORECASE)

        # Remove table of contents page references (e.g., "... 45")
        text = re.sub(r'\s*\.{3,}\s*\d+\s*$', '', text, flags=re.MULTILINE)

        return text

    def _remove_toc_artifacts(self, text: str) -> str:
        """
        Remove table of contents artifacts

        Args:
            text: Input text

        Returns:
            str: Text without TOC artifacts
        """
        # Remove lines that look like TOC entries (Item X..... Page Y)
        text = re.sub(
            r'^(Item|ITEM)\s+\d+[A-Z]?\..*\.{3,}.*\d+\s*$',
            '',
            text,
            flags=re.MULTILINE | re.IGNORECASE
        )

        return text

    def _normalize_punctuation(self, text: str) -> str:
        """
        Normalize punctuation

        Args:
            text: Input text

        Returns:
            str: Text with normalized punctuation
        """
        # Normalize curly/smart quotes to straight ASCII quotes
        # Double quotes: " (U+201C) and " (U+201D) → " (U+0022)
        text = text.replace('\u201c', '"').replace('\u201d', '"')
        # Single quotes/apostrophes: ' (U+2018) and ' (U+2019) → ' (U+0027)
        text = text.replace('\u2018', "'").replace('\u2019', "'")

        # Remove excessive punctuation
        text = re.sub(r'([.!?])\1+', r'\1', text)

        return text

    def _apply_nlp_cleaning(self, text: str) -> str:
        """
        Apply advanced NLP cleaning using spaCy

        Args:
            text: Input text

        Returns:
            str: Cleaned text with lemmatization, stopword removal, etc.
        """
        if not self.nlp:
            return text

        # Process text with spaCy
        doc = self.nlp(text)

        # Build cleaned tokens
        cleaned_tokens = []

        for token in doc:
            # Skip if it's a stop word and we're removing them
            if self.remove_stopwords and token.is_stop:
                continue

            # Skip punctuation if configured
            if self.remove_punctuation and token.is_punct:
                continue

            # Skip spaces
            if token.is_space:
                continue

            # Skip numbers if configured
            if self.remove_numbers and (token.like_num or token.is_digit):
                continue

            # Use lemma if lemmatization is enabled, otherwise use original text
            if self.use_lemmatization:
                # Get lemma and convert to lowercase
                token_text = token.lemma_.lower()
            else:
                token_text = token.text

            cleaned_tokens.append(token_text)

        # Join tokens back into text
        # Preserve some sentence structure
        return ' '.join(cleaned_tokens)

    def process_with_spacy(self, text: str, return_tokens: bool = False):
        """
        Process text with spaCy and optionally return tokens

        Args:
            text: Input text
            return_tokens: If True, return list of cleaned tokens instead of string

        Returns:
            str or List[str]: Cleaned text or list of tokens
        """
        if not self.nlp:
            raise RuntimeError("spaCy not initialized. Set use_lemmatization=True or remove_stopwords=True")

        doc = self.nlp(text)
        cleaned_tokens = []

        for token in doc:
            if self.remove_stopwords and token.is_stop:
                continue
            if self.remove_punctuation and token.is_punct:
                continue
            if token.is_space:
                continue
            if self.remove_numbers and (token.like_num or token.is_digit):
                continue

            token_text = token.lemma_.lower() if self.use_lemmatization else token.text
            cleaned_tokens.append(token_text)

        if return_tokens:
            return cleaned_tokens
        return ' '.join(cleaned_tokens)

    def remove_html_tags(self, text: str) -> str:
        """
        Remove HTML tags and entities comprehensively

        Args:
            text: Input text potentially containing HTML

        Returns:
            str: Text without HTML tags
        """
        # Remove HTML comments
        text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)

        # Remove script and style elements
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)

        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)

        # Decode HTML entities
        text = unescape(text)

        # Remove common HTML entities that unescape might miss
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'&[a-zA-Z]+;', '', text)
        text = re.sub(r'&#\d+;', '', text)

        return text

    def clean_html_text(self, text: str) -> str:
        """
        Clean text that may contain HTML

        Args:
            text: Input text potentially containing HTML

        Returns:
            str: Cleaned text
        """
        text = self.remove_html_tags(text)
        return self.clean_text(text)


def clean_filing_text(text: str,
                      remove_html: bool = False,
                      deep_clean: bool = False,
                      use_lemmatization: bool = False,
                      remove_stopwords: bool = False,
                      remove_punctuation: bool = False,
                      remove_numbers: bool = False) -> str:
    """
    Convenience function to clean filing text

    Args:
        text: Raw text to clean
        remove_html: Whether to remove HTML tags
        deep_clean: Apply advanced NLP preprocessing
        use_lemmatization: Apply lemmatization (requires spaCy)
        remove_stopwords: Remove stop words (requires spaCy)
        remove_punctuation: Remove punctuation
        remove_numbers: Remove numbers

    Returns:
        str: Cleaned text
    """
    cleaner = TextCleaner(
        use_lemmatization=use_lemmatization,
        remove_stopwords=remove_stopwords,
        remove_punctuation=remove_punctuation,
        remove_numbers=remove_numbers
    )

    if remove_html:
        text = cleaner.remove_html_tags(text)

    return cleaner.clean_text(text, deep_clean=deep_clean)


if __name__ == "__main__":
    print("Cleaning module loaded successfully")
    print()

    # Example usage
    sample_html = """
    <html>
        <head><title>10-K Filing</title></head>
        <body>
            <h1>Management's Discussion &amp; Analysis</h1>
            <p>The company's revenue increased by 15% in 2023.
            We are committed to driving innovation and growth.</p>
            <table>
                <tr><td>Item 1</td><td>..... 5</td></tr>
            </table>
            Page 12
        </body>
    </html>
    """

    print("=" * 60)
    print("EXAMPLE 1: Basic HTML Removal")
    print("=" * 60)
    cleaner_basic = TextCleaner()
    cleaned = cleaner_basic.clean_html_text(sample_html)
    print(cleaned)
    print()

    print("=" * 60)
    print("EXAMPLE 2: Deep Clean with Lemmatization")
    print("=" * 60)
    if SPACY_AVAILABLE:
        cleaner_advanced = TextCleaner(
            use_lemmatization=True,
            remove_stopwords=False
        )
        if cleaner_advanced.nlp:
            text = cleaner_advanced.remove_html_tags(sample_html)
            cleaned_advanced = cleaner_advanced.clean_text(text, deep_clean=True)
            print(cleaned_advanced)
        else:
            print("spaCy model not available - skipping")
    else:
        print("spaCy not installed - skipping")
    print()

    print("=" * 60)
    print("EXAMPLE 3: Full Preprocessing (Stopwords + Lemmatization)")
    print("=" * 60)
    if SPACY_AVAILABLE:
        cleaner_full = TextCleaner(
            use_lemmatization=True,
            remove_stopwords=True,
            remove_punctuation=True,
            remove_numbers=True
        )
        if cleaner_full.nlp:
            text = cleaner_full.remove_html_tags(sample_html)
            cleaned_full = cleaner_full.clean_text(text, deep_clean=True)
            print(cleaned_full)
        else:
            print("spaCy model not available - skipping")
    else:
        print("spaCy not installed - skipping")
    print()

    print("=" * 60)
    print("EXAMPLE 4: Using Convenience Function")
    print("=" * 60)
    cleaned_convenience = clean_filing_text(
        sample_html,
        remove_html=True,
        deep_clean=True,
        use_lemmatization=True,
        remove_stopwords=True
    )
    print(cleaned_convenience)

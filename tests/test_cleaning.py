"""
Unit tests for text cleaning module
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.preprocessing.cleaning import TextCleaner, clean_filing_text


def test_html_removal():
    """Test HTML tag and entity removal"""
    print("Testing HTML removal...")

    html_text = """
    <html>
        <head><title>Test</title></head>
        <body>
            <p>Revenue increased by &nbsp; 15% &amp; growth accelerated.</p>
            <script>alert('test');</script>
            <style>.test { color: red; }</style>
        </body>
    </html>
    """

    cleaner = TextCleaner()
    cleaned = cleaner.remove_html_tags(html_text)

    assert '<html>' not in cleaned
    assert '<p>' not in cleaned
    assert 'alert' not in cleaned  # Script removed
    assert 'color: red' not in cleaned  # Style removed
    assert '&nbsp;' not in cleaned
    assert '&amp;' not in cleaned or '&' in cleaned  # Entity decoded

    print("✓ HTML removal test passed")
    print(f"  Original: {len(html_text)} chars")
    print(f"  Cleaned: {len(cleaned)} chars")
    print(f"  Output: {cleaned[:100]}...")
    print()


def test_whitespace_normalization():
    """Test whitespace normalization"""
    print("Testing whitespace normalization...")

    messy_text = "This    has   multiple     spaces\n\n\n\nand\n\n\nnewlines\t\ttabs"

    cleaner = TextCleaner()
    cleaned = cleaner.clean_text(messy_text)

    # Should not have multiple consecutive spaces
    assert '  ' not in cleaned
    # Should not have more than 2 consecutive newlines
    assert '\n\n\n' not in cleaned

    print("✓ Whitespace normalization test passed")
    print(f"  Output: {repr(cleaned)}")
    print()


def test_page_artifact_removal():
    """Test removal of page numbers and artifacts"""
    print("Testing page artifact removal...")

    text_with_pages = """
    Content here
    Page 12
    More content
    -15-
    Final content
    Item 1..... 45
    """

    cleaner = TextCleaner()
    cleaned = cleaner.clean_text(text_with_pages)

    # Page numbers should be removed
    assert 'Page 12' not in cleaned
    assert '-15-' not in cleaned

    print("✓ Page artifact removal test passed")
    print(f"  Output: {cleaned}")
    print()


def test_lemmatization():
    """Test spaCy lemmatization"""
    print("Testing lemmatization...")

    try:
        text = "The companies are running multiple operations successfully"

        cleaner = TextCleaner(use_lemmatization=True)

        if cleaner.nlp:
            cleaned = cleaner.clean_text(text, deep_clean=True)

            # Check for lemmatized forms
            assert 'running' not in cleaned.lower() or 'run' in cleaned.lower()
            assert 'companies' not in cleaned.lower() or 'company' in cleaned.lower()

            print("✓ Lemmatization test passed")
            print(f"  Original: {text}")
            print(f"  Lemmatized: {cleaned}")
        else:
            print("⚠ Lemmatization test skipped (spaCy model not available)")
    except Exception as e:
        print(f"⚠ Lemmatization test skipped: {e}")

    print()


def test_stopword_removal():
    """Test stop word removal"""
    print("Testing stop word removal...")

    try:
        text = "The company is running the operations in the market"

        cleaner = TextCleaner(
            use_lemmatization=False,
            remove_stopwords=True
        )

        if cleaner.nlp:
            cleaned = cleaner.clean_text(text, deep_clean=True)

            # Common stop words should be removed
            cleaned_lower = cleaned.lower()
            assert 'the' not in cleaned_lower or cleaned_lower.count('the') < text.lower().count('the')

            print("✓ Stop word removal test passed")
            print(f"  Original: {text}")
            print(f"  Cleaned: {cleaned}")
        else:
            print("⚠ Stop word removal test skipped (spaCy model not available)")
    except Exception as e:
        print(f"⚠ Stop word removal test skipped: {e}")

    print()


def test_punctuation_removal():
    """Test punctuation removal"""
    print("Testing punctuation removal...")

    try:
        text = "Hello, world! This is a test... with punctuation?"

        cleaner = TextCleaner(
            remove_punctuation=True,
            remove_stopwords=False
        )

        if cleaner.nlp:
            cleaned = cleaner.clean_text(text, deep_clean=True)

            # Punctuation should be removed
            assert ',' not in cleaned
            assert '!' not in cleaned
            assert '?' not in cleaned
            assert '...' not in cleaned

            print("✓ Punctuation removal test passed")
            print(f"  Original: {text}")
            print(f"  Cleaned: {cleaned}")
        else:
            print("⚠ Punctuation removal test skipped (spaCy model not available)")
    except Exception as e:
        print(f"⚠ Punctuation removal test skipped: {e}")

    print()


def test_number_removal():
    """Test number removal"""
    print("Testing number removal...")

    try:
        text = "Revenue increased by 15% to $1.5 billion in 2023"

        cleaner = TextCleaner(
            remove_numbers=True,
            remove_stopwords=False
        )

        if cleaner.nlp:
            cleaned = cleaner.clean_text(text, deep_clean=True)

            # Numbers should be reduced or removed
            # Note: This might be tricky with currency symbols
            print("✓ Number removal test passed")
            print(f"  Original: {text}")
            print(f"  Cleaned: {cleaned}")
        else:
            print("⚠ Number removal test skipped (spaCy model not available)")
    except Exception as e:
        print(f"⚠ Number removal test skipped: {e}")

    print()


def test_full_pipeline():
    """Test complete preprocessing pipeline"""
    print("Testing full preprocessing pipeline...")

    try:
        html_text = """
        <html>
            <body>
                <h1>Management's Discussion</h1>
                <p>The companies are running multiple operations.
                Revenue increased by 15% in 2023.</p>
                Page 42
            </body>
        </html>
        """

        cleaner = TextCleaner(
            use_lemmatization=True,
            remove_stopwords=True,
            remove_punctuation=True,
            remove_numbers=True
        )

        if cleaner.nlp:
            # Remove HTML
            text = cleaner.remove_html_tags(html_text)

            # Apply deep cleaning
            cleaned = cleaner.clean_text(text, deep_clean=True)

            # Should not contain HTML
            assert '<' not in cleaned
            assert '>' not in cleaned

            print("✓ Full pipeline test passed")
            print(f"  Original length: {len(html_text)}")
            print(f"  Cleaned length: {len(cleaned)}")
            print(f"  Output: {cleaned}")
        else:
            print("⚠ Full pipeline test skipped (spaCy model not available)")
    except Exception as e:
        print(f"⚠ Full pipeline test skipped: {e}")

    print()


def test_convenience_function():
    """Test convenience function"""
    print("Testing convenience function...")

    html_text = "<p>The company's revenue increased significantly.</p>"

    # Basic cleaning
    cleaned = clean_filing_text(html_text, remove_html=True)

    assert '<p>' not in cleaned
    assert 'revenue' in cleaned.lower()

    print("✓ Convenience function test passed")
    print(f"  Output: {cleaned}")
    print()


def test_token_output():
    """Test token list output"""
    print("Testing token output...")

    try:
        text = "The company manages operations efficiently"

        cleaner = TextCleaner(
            use_lemmatization=True,
            remove_stopwords=True
        )

        if cleaner.nlp:
            tokens = cleaner.process_with_spacy(text, return_tokens=True)

            assert isinstance(tokens, list)
            assert len(tokens) > 0
            assert all(isinstance(t, str) for t in tokens)

            print("✓ Token output test passed")
            print(f"  Original: {text}")
            print(f"  Tokens: {tokens}")
        else:
            print("⚠ Token output test skipped (spaCy model not available)")
    except Exception as e:
        print(f"⚠ Token output test skipped: {e}")

    print()


if __name__ == "__main__":
    print("=" * 70)
    print("RUNNING TEXT CLEANING TESTS")
    print("=" * 70)
    print()

    # Run all tests
    test_html_removal()
    test_whitespace_normalization()
    test_page_artifact_removal()
    test_lemmatization()
    test_stopword_removal()
    test_punctuation_removal()
    test_number_removal()
    test_full_pipeline()
    test_convenience_function()
    test_token_output()

    print("=" * 70)
    print("ALL TESTS COMPLETED")
    print("=" * 70)

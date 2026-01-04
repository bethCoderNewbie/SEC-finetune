"""
Lightweight fixtures for unit tests - NO real data dependencies.
All fixtures use mock/synthetic data that runs in <1 second.
"""

import pytest


# =============================================================================
# HTML/Text Fixtures
# =============================================================================

@pytest.fixture
def sample_sic_html() -> str:
    """HTML with SIC code in bracket format."""
    return """STANDARD INDUSTRIAL CLASSIFICATION: SERVICES-PREPACKAGED SOFTWARE [7372]"""


@pytest.fixture
def sample_sic_html_assigned() -> str:
    """HTML with ASSIGNED-SIC format."""
    return """ASSIGNED-SIC: 7372"""


@pytest.fixture
def sample_curly_quotes_text() -> str:
    """Text with curly quotes for normalization testing."""
    return "The company\u2019s revenue increased \u201csignificantly\u201d."


@pytest.fixture
def sample_page_artifacts_text() -> str:
    """Text with page numbers and artifacts."""
    return """Some content here
-12-
More content
Page 45
Final content"""


@pytest.fixture
def sample_toc_artifacts_text() -> str:
    """Text with diverse table of contents artifacts."""
    return """Item 1A. Risk Factors..... 25
Part IV Item 15. Exhibits..... 89
Item 7. Management's Discussion . . . . . 45
Item 1A Risk Factors · · · · · 25
Actual content starts here."""


@pytest.fixture
def sample_invisible_chars_html() -> str:
    """HTML with invisible Unicode characters."""
    return "Text\u200bwith\ufeffzero-width\u00adchars"


@pytest.fixture
def sample_nested_html() -> str:
    """Deeply nested HTML for flattening tests."""
    return "<div><div><div><p>Content</p></div></div></div>"


@pytest.fixture
def sample_edgar_header_html() -> str:
    """HTML with SEC EDGAR header."""
    return """<SEC-HEADER>
ACCESSION NUMBER: 0000320193-21-000105
CONFORMED SUBMISSION TYPE: 10-K
</SEC-HEADER>
<html>
<body>Content here</body>
</html>"""


@pytest.fixture
def sample_html_with_entities() -> str:
    """HTML with various entities to decode."""
    return """<p>Revenue &amp; expenses</p>
<p>Price &lt; $100 &gt; 0</p>
<p>Space&nbsp;here</p>
<p>Numeric&#160;entity</p>"""


# =============================================================================
# Risk Segmentation Fixtures
# =============================================================================

@pytest.fixture
def sample_risk_paragraphs() -> str:
    """Multiple paragraphs for segmentation testing."""
    return """Competition Risk: We face intense competition from established players
in the market. Our competitors have more resources and brand recognition
than we do, which could adversely affect our market share.

Regulatory Risk: We are subject to various federal, state, and local
regulations that may change at any time. Compliance with new regulations
could require significant investment and operational changes.

Cybersecurity Risk: Security breaches could compromise our systems and
expose sensitive customer data. Such incidents could result in legal
liability, reputational damage, and loss of customer trust."""


@pytest.fixture
def sample_bulleted_risks() -> str:
    """Risk text with bullet points."""
    return """The following risks could affect our business:

• Market volatility may impact our investment portfolio and financial results.

• Regulatory changes could increase compliance costs significantly.

• Supply chain disruptions may delay product deliveries."""


@pytest.fixture
def sample_numbered_risks() -> str:
    """Risk text with numbered items."""
    return """Key risks include:

1. Economic downturns could reduce consumer spending on our products.

2. Technology changes may render our products obsolete.

3. Talent retention challenges could impact our competitive position."""


# =============================================================================
# Metadata Fixtures
# =============================================================================

@pytest.fixture
def sample_filing_metadata() -> dict:
    """Sample metadata dictionary."""
    return {
        'sic_code': '7372',
        'sic_name': 'SERVICES-PREPACKAGED SOFTWARE',
        'cik': '0000320193',
        'company_name': 'APPLE INC',
        'ticker': 'AAPL',
    }


# =============================================================================
# Empty/Edge Case Fixtures
# =============================================================================

@pytest.fixture
def empty_string() -> str:
    """Empty string for edge case testing."""
    return ""


@pytest.fixture
def whitespace_only() -> str:
    """Whitespace-only string for edge case testing."""
    return "   \n\t\n   "


@pytest.fixture
def single_word() -> str:
    """Single word for edge case testing."""
    return "Risk"

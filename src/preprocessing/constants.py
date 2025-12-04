"""
Constants for SEC Filing Preprocessing

This module contains all constants used by the preprocessing modules,
including section identifiers, regex patterns for section matching,
and element type definitions.
"""

import re
from enum import Enum
from typing import Dict, List


# ===========================
# Page Header Pattern
# ===========================

# Pattern for filtering page headers (e.g., "Apple Inc. | 2021 Form 10-K | 6")
PAGE_HEADER_PATTERN = re.compile(
    r'.+\|\s*\d{4}\s+Form\s+\d+-[KQ]\s*\|\s*\d+',
    re.IGNORECASE
)


# ===========================
# Section Identifiers
# ===========================

class SectionIdentifier(Enum):
    """
    Standard section identifiers for SEC filings

    These identifiers follow the sec-parser convention for
    identifying specific items within 10-K and 10-Q filings.

    Usage:
        >>> from src.preprocessing.constants import SectionIdentifier
        >>> section = SectionIdentifier.ITEM_1A_RISK_FACTORS
        >>> print(section.value)  # "part1item1a"
    """

    # 10-K Sections
    ITEM_1_BUSINESS = "part1item1"
    ITEM_1A_RISK_FACTORS = "part1item1a"
    ITEM_1B_UNRESOLVED_STAFF = "part1item1b"
    ITEM_1C_CYBERSECURITY = "part1item1c"
    ITEM_2_PROPERTIES = "part1item2"
    ITEM_3_LEGAL_PROCEEDINGS = "part1item3"
    ITEM_4_MINE_SAFETY = "part1item4"
    ITEM_5_MARKET = "part2item5"
    ITEM_6_RESERVED = "part2item6"
    ITEM_7_MDNA = "part2item7"
    ITEM_7A_MARKET_RISK = "part2item7a"
    ITEM_8_FINANCIAL_STATEMENTS = "part2item8"
    ITEM_9_CHANGES = "part2item9"
    ITEM_9A_CONTROLS = "part2item9a"
    ITEM_9B_OTHER = "part2item9b"

    # 10-Q Sections
    ITEM_1_FINANCIAL_STATEMENTS_10Q = "part1item1"
    ITEM_2_MDNA_10Q = "part1item2"
    ITEM_3_MARKET_RISK_10Q = "part1item3"
    ITEM_4_CONTROLS_10Q = "part1item4"
    ITEM_1_LEGAL_10Q = "part2item1"
    ITEM_1A_RISK_FACTORS_10Q = "part2item1a"
    ITEM_2_UNREGISTERED_10Q = "part2item2"
    ITEM_5_OTHER_10Q = "part2item5"
    ITEM_6_EXHIBITS_10Q = "part2item6"


# ===========================
# Section Matching Patterns
# ===========================

SECTION_PATTERNS: Dict[str, List[str]] = {
    # Regex patterns for flexible section matching.
    # Used when the identifier attribute is not set by sec-parser.
    # Multiple patterns are provided per section to handle variations
    # in how sections are titled across different filings.

    "part1item1": [
        r'(?i)^item\s*1\s*\.?\s*business',
        r'(?i)^item\s*1\s*$',
        r'(?i)^item\s*1\s*[^a-z0-9]',  # Item 1 followed by non-alphanumeric
    ],
    "part1item1a": [
        r'(?i)item\s*1\s*a\.?\s*risk\s*factors?',
        r'(?i)item\s*1a\.?\s*risk',
        r'(?i)^item\s*1\s*a\s*\.?',  # Item 1A with optional period
    ],
    "part1item1b": [
        r'(?i)item\s*1\s*b\.?\s*unresolved',
        r'(?i)item\s*1b\.?',
    ],
    "part1item1c": [
        r'(?i)item\s*1\s*c\.?\s*cybersecurity',
        r'(?i)item\s*1c\.?',
    ],
    "part2item7": [
        r'(?i)item\s*7\.?\s*management',
        r'(?i)item\s*7\.?\s*md\s*&?\s*a',
        r'(?i)^item\s*7\s*\.?$',
    ],
    "part2item7a": [
        r'(?i)item\s*7\s*a\.?\s*market\s*risk',
        r'(?i)item\s*7a\.?',
    ],
    "part2item8": [
        r'(?i)item\s*8\.?\s*financial\s*statements',
        r'(?i)^item\s*8\s*\.?$',
    ],
    "part2item9": [
        r'(?i)item\s*9\.?\s*changes',
        r'(?i)^item\s*9\s*\.?$',
    ],
    "part2item9a": [
        r'(?i)item\s*9\s*a\.?\s*controls',
        r'(?i)item\s*9a\.?',
    ],
}


# ===========================
# Element Type Constants
# ===========================

# Semantic element types from sec-parser
TEXT_ELEMENT_TYPES = frozenset([
    'TextElement',
    'ParagraphElement',
])

TITLE_ELEMENT_TYPES = frozenset([
    'TitleElement',
    'TopSectionTitle',
])

TABLE_ELEMENT_TYPES = frozenset([
    'TableElement',
])

ALL_CONTENT_TYPES = TEXT_ELEMENT_TYPES | TITLE_ELEMENT_TYPES | TABLE_ELEMENT_TYPES


# ===========================
# Extraction Defaults
# ===========================
# NOTE: Runtime-configurable values have been moved to src/config/:
#   - MIN_PARAGRAPH_LENGTH → settings.preprocessing.min_segment_length
#   - DEFAULT_EXTRACTION_SECTIONS → settings.extraction.default_sections

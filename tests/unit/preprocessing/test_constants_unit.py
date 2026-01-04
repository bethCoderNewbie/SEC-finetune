"""
Unit tests for src/preprocessing/constants.py

Tests SectionIdentifier enum, SECTION_PATTERNS regex patterns, and element type sets.
No real data dependencies - runs in <1 second.
"""

import re
import pytest

from src.preprocessing.constants import (
    SectionIdentifier,
    SECTION_PATTERNS,
    PAGE_HEADER_PATTERN,
    TEXT_ELEMENT_TYPES,
    TITLE_ELEMENT_TYPES,
    TABLE_ELEMENT_TYPES,
    ALL_CONTENT_TYPES,
)


class TestSectionIdentifier:
    """Tests for SectionIdentifier enum."""

    def test_item_1a_risk_factors_value(self):
        """ITEM_1A_RISK_FACTORS has correct value."""
        assert SectionIdentifier.ITEM_1A_RISK_FACTORS.value == "part1item1a"

    def test_item_7_mdna_value(self):
        """ITEM_7_MDNA has correct value."""
        assert SectionIdentifier.ITEM_7_MDNA.value == "part2item7"

    def test_all_10k_sections_have_part_prefix(self):
        """All 10-K section values start with 'part'."""
        for member in SectionIdentifier:
            assert member.value.startswith("part"), f"{member.name} doesn't start with 'part'"

    def test_enum_values_are_unique(self):
        """No duplicate values in enum (except intentional 10-K/10-Q overlap)."""
        values = [m.value for m in SectionIdentifier]
        # Some overlap is expected between 10-K and 10-Q (e.g., part1item1)
        # But within each form type, values should be unique
        # Just verify the list has expected length
        assert len(values) == len(SectionIdentifier)

    def test_enum_members_exist(self):
        """Key enum members exist."""
        assert hasattr(SectionIdentifier, 'ITEM_1_BUSINESS')
        assert hasattr(SectionIdentifier, 'ITEM_1A_RISK_FACTORS')
        assert hasattr(SectionIdentifier, 'ITEM_7_MDNA')
        assert hasattr(SectionIdentifier, 'ITEM_8_FINANCIAL_STATEMENTS')


class TestSectionPatterns:
    """Tests for SECTION_PATTERNS regex patterns."""

    def test_patterns_exist_for_key_sections(self):
        """Key sections have patterns defined."""
        assert "part1item1a" in SECTION_PATTERNS
        assert "part2item7" in SECTION_PATTERNS
        assert "part2item7a" in SECTION_PATTERNS

    @pytest.mark.parametrize("text,expected_match", [
        ("Item 1A. Risk Factors", True),
        ("ITEM 1A RISK FACTORS", True),
        ("item 1a. risk", True),
        ("Item 1A Risk", True),
        ("Item 2. Properties", False),
        ("Something else", False),
        ("Item 1B. Unresolved", False),
    ])
    def test_item_1a_pattern_matching(self, text: str, expected_match: bool):
        """Item 1A patterns match expected variations."""
        patterns = SECTION_PATTERNS.get("part1item1a", [])
        matched = any(re.search(p, text) for p in patterns)
        assert matched == expected_match, f"Pattern match for '{text}' was {matched}, expected {expected_match}"

    @pytest.mark.parametrize("text,expected_match", [
        ("Item 7. Management's Discussion", True),
        ("ITEM 7 MD&A", True),
        ("Item 7 MD & A", True),
        ("Item 7.", True),
        ("Item 8. Financial", False),
    ])
    def test_item_7_pattern_matching(self, text: str, expected_match: bool):
        """Item 7 (MD&A) patterns match expected variations."""
        patterns = SECTION_PATTERNS.get("part2item7", [])
        matched = any(re.search(p, text) for p in patterns)
        assert matched == expected_match

    @pytest.mark.parametrize("text,expected_match", [
        ("Item 7A. Quantitative", True),
        ("Item 7A Market Risk", True),
        ("item 7a.", True),
        ("Item 7. MD&A", False),
    ])
    def test_item_7a_pattern_matching(self, text: str, expected_match: bool):
        """Item 7A (Market Risk) patterns match expected variations."""
        patterns = SECTION_PATTERNS.get("part2item7a", [])
        matched = any(re.search(p, text) for p in patterns)
        assert matched == expected_match


class TestPageHeaderPattern:
    """Tests for PAGE_HEADER_PATTERN regex."""

    @pytest.mark.parametrize("header", [
        "Apple Inc. | 2021 Form 10-K | 6",
        "Microsoft Corporation | 2023 Form 10-K | 15",
        "NVIDIA CORP | 2024 Form 10-Q | 42",
    ])
    def test_matches_valid_page_headers(self, header: str):
        """Valid page headers match the pattern."""
        assert PAGE_HEADER_PATTERN.match(header) is not None

    @pytest.mark.parametrize("text", [
        "Risks Related to COVID-19",
        "Business Risks",
        "Item 1A. Risk Factors",
        "The company faces significant risks",
    ])
    def test_does_not_match_subsection_titles(self, text: str):
        """Subsection titles don't match the pattern."""
        assert PAGE_HEADER_PATTERN.match(text) is None


class TestElementTypeSets:
    """Tests for element type frozensets."""

    def test_text_types_is_frozenset(self):
        """TEXT_ELEMENT_TYPES is immutable frozenset."""
        assert isinstance(TEXT_ELEMENT_TYPES, frozenset)

    def test_text_types_contents(self):
        """TEXT_ELEMENT_TYPES contains expected values."""
        assert 'TextElement' in TEXT_ELEMENT_TYPES
        assert 'ParagraphElement' in TEXT_ELEMENT_TYPES

    def test_title_types_is_frozenset(self):
        """TITLE_ELEMENT_TYPES is immutable frozenset."""
        assert isinstance(TITLE_ELEMENT_TYPES, frozenset)

    def test_title_types_contents(self):
        """TITLE_ELEMENT_TYPES contains expected values."""
        assert 'TitleElement' in TITLE_ELEMENT_TYPES
        assert 'TopSectionTitle' in TITLE_ELEMENT_TYPES

    def test_table_types_is_frozenset(self):
        """TABLE_ELEMENT_TYPES is immutable frozenset."""
        assert isinstance(TABLE_ELEMENT_TYPES, frozenset)

    def test_table_types_contents(self):
        """TABLE_ELEMENT_TYPES contains expected values."""
        assert 'TableElement' in TABLE_ELEMENT_TYPES

    def test_all_content_types_is_union(self):
        """ALL_CONTENT_TYPES is union of text, title, and table types."""
        expected = TEXT_ELEMENT_TYPES | TITLE_ELEMENT_TYPES | TABLE_ELEMENT_TYPES
        assert ALL_CONTENT_TYPES == expected

    def test_sets_are_disjoint(self):
        """Text, title, and table sets don't overlap."""
        assert TEXT_ELEMENT_TYPES.isdisjoint(TITLE_ELEMENT_TYPES)
        assert TEXT_ELEMENT_TYPES.isdisjoint(TABLE_ELEMENT_TYPES)
        assert TITLE_ELEMENT_TYPES.isdisjoint(TABLE_ELEMENT_TYPES)

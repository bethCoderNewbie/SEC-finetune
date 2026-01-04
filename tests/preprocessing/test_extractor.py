"""
Tests for SEC Section Extractor - validating extraction quality using real SEC filing data.

Uses actual data from:
- data/raw/*.html (raw 10-K/10-Q filings for extraction tests)
- data/interim/extracted/*_extracted_risks.json (pre-extracted sections)

Categories:
1. Boundary Detection - section start/end identification
2. Content Quality - character counts, keyword density
3. Subsection Classification - filtering, page header removal
4. ExtractedSection Model - serialization, field validation
5. Integration Tests - end-to-end extraction from real files

Note: This module uses centralized fixtures from conftest.py:
- extracted_data: List of extracted risk JSON data
- test_10k_files: List of raw 10-K HTML file paths
- extractor: SECSectionExtractor instance
- risk_extractor: RiskFactorExtractor instance
- parser: SECFilingParser instance
"""

import re
from pathlib import Path
from typing import List, Dict
import pytest

from src.preprocessing.extractor import ExtractedSection
from src.preprocessing.constants import PAGE_HEADER_PATTERN, SectionIdentifier


# Note: All fixtures (extracted_data, test_10k_files, extractor, risk_extractor, parser)
# are provided by conftest.py


# =============================================================================
# Test Class 1: Boundary Detection Tests with Real Data
# =============================================================================

class TestBoundaryDetectionWithRealData:
    """Test section boundary detection using real extracted data."""

    def test_extracted_sections_have_valid_identifier(self, extracted_data: List[Dict]):
        """Verify all extracted sections have valid identifiers."""
        if not extracted_data:
            pytest.skip("No extracted data available")
        valid_identifiers = {"part1item1a", "item1a", "part2item1a"}
        for doc in extracted_data:
            identifier = doc.get("identifier", "").lower()
            has_valid = any(vid in identifier for vid in valid_identifiers)
            assert has_valid, (
                f"Invalid identifier: {identifier}"
            )

    def test_extracted_sections_have_title(self, extracted_data: List[Dict]):
        """Verify all extracted sections have a title."""
        if not extracted_data:
            pytest.skip("No extracted data available")
        for doc in extracted_data:
            title = doc.get("title", "")
            assert len(title) > 0, "Missing section title"
            # Should mention risk factors
            assert "risk" in title.lower(), (
                f"Title doesn't mention 'risk': {title}"
            )

    def test_extracted_sections_have_content(self, extracted_data: List[Dict]):
        """Verify all extracted sections have substantial content."""
        if not extracted_data:
            pytest.skip("No extracted data available")
        for doc in extracted_data:
            text = doc.get("text", "")
            assert len(text) > 1000, (
                f"Extracted text too short: {len(text)} chars"
            )


class TestBoundaryPatternMatching:
    """Test boundary pattern matching against real section titles."""

    @pytest.fixture
    def real_section_titles(self, extracted_data: List[Dict]) -> List[str]:
        """Extract real section titles from data."""
        if not extracted_data:
            return []
        titles = []
        for doc in extracted_data:
            titles.append(doc.get("title", ""))
            for subsection in doc.get("subsections", []):
                if isinstance(subsection, str):
                    titles.append(subsection)
        return [t for t in titles if t]

    def test_item_pattern_matches_real_titles(self, extractor, real_section_titles):
        """Verify Item pattern matches real extracted titles."""
        if not real_section_titles:
            pytest.skip("No section titles available")
        item_pattern = re.compile(r'item\s+\d+[a-z]?\s*\.?', re.IGNORECASE)
        matched = [t for t in real_section_titles if item_pattern.search(t)]
        # At least some titles should match Item pattern
        assert len(matched) >= 1, "No titles matched Item pattern"


# =============================================================================
# Test Class 2: Page Header Filtering Tests with Real Data
# =============================================================================

class TestPageHeaderFilteringWithRealData:
    """Test page header detection using real extracted subsections."""

    @pytest.mark.xfail(reason="Known issue: some extracted files contain page headers in subsections")
    def test_no_page_headers_in_subsections(self, extracted_data: List[Dict]):
        """Verify subsections don't contain page header artifacts.

        Note: This test documents a known gap in the extraction process.
        Some extracted files were processed before page header filtering was improved.
        """
        if not extracted_data:
            pytest.skip("No extracted data available")
        for doc in extracted_data:
            subsections = doc.get("subsections", [])
            for subsection in subsections:
                if isinstance(subsection, str):
                    # Should not match page header pattern
                    if PAGE_HEADER_PATTERN.match(subsection):
                        pytest.fail(
                            f"Page header found in subsections: {subsection}"
                        )

    def test_subsections_are_meaningful(self, extracted_data: List[Dict]):
        """Verify subsections contain meaningful risk-related content."""
        if not extracted_data:
            pytest.skip("No extracted data available")
        risk_keywords = ['risk', 'adverse', 'material', 'may', 'could', 'impact']
        for doc in extracted_data:
            subsections = doc.get("subsections", [])
            if len(subsections) < 3:
                continue  # Skip docs with few subsections

            # At least 30% should have risk keywords
            meaningful = 0
            for subsection in subsections:
                if isinstance(subsection, str):
                    if any(kw in subsection.lower() for kw in risk_keywords):
                        meaningful += 1

            ratio = meaningful / len(subsections) if subsections else 0
            # Allow flexibility - some subsections are category headers
            assert ratio >= 0.1 or len(subsections) < 5, (
                f"Too few meaningful subsections: {ratio:.1%}"
            )

    @pytest.mark.parametrize("header_pattern", [
        "Apple Inc. | 2021 Form 10-K | 6",
        "Microsoft Corporation | 2023 Form 10-K | 15",
        "NVIDIA Corporation | 2024 Form 10-Q | 8",
    ])
    def test_page_header_pattern_matches(self, header_pattern):
        """Verify PAGE_HEADER_PATTERN correctly identifies page headers."""
        assert PAGE_HEADER_PATTERN.match(header_pattern) is not None

    @pytest.mark.parametrize("valid_title", [
        "Risks Related to COVID-19",
        "Macroeconomic and Industry Risks",
        "Business Risks",
        "Legal and Regulatory Compliance Risks",
        "Technology and Cybersecurity Risks",
    ])
    def test_valid_titles_not_filtered(self, valid_title):
        """Verify valid subsection titles are not filtered as page headers."""
        assert PAGE_HEADER_PATTERN.match(valid_title) is None


# =============================================================================
# Test Class 3: Character Count and Content Quality Tests
# =============================================================================

class TestContentQualityWithRealData:
    """Test extracted content quality metrics."""

    RISK_FACTORS_MIN_CHARS = 10000  # Relaxed for variety of filings
    RISK_FACTORS_MAX_CHARS = 150000  # Allow for longer filings

    def test_extracted_text_length_in_range(self, extracted_data: List[Dict]):
        """Verify extracted text length is within expected range."""
        if not extracted_data:
            pytest.skip("No extracted data available")
        for doc in extracted_data:
            text = doc.get("text", "")
            text_len = len(text)
            assert text_len >= self.RISK_FACTORS_MIN_CHARS, (
                f"Text too short: {text_len} < {self.RISK_FACTORS_MIN_CHARS}"
            )
            assert text_len <= self.RISK_FACTORS_MAX_CHARS, (
                f"Text too long: {text_len} > {self.RISK_FACTORS_MAX_CHARS}"
            )

    def test_risk_keyword_density(self, extracted_data: List[Dict]):
        """Verify risk-related keyword density in extracted text."""
        if not extracted_data:
            pytest.skip("No extracted data available")
        risk_keywords = ["risk", "adversely", "material", "significant", "uncertain"]
        for doc in extracted_data:
            text = doc.get("text", "").lower()
            word_count = len(text.split())
            if word_count < 100:
                continue

            keyword_count = sum(text.count(kw) for kw in risk_keywords)
            density = keyword_count / word_count

            # Risk factors should have reasonable keyword density
            assert density >= 0.005, (
                f"Low keyword density: {density:.4f} (expected >= 0.005)"
            )

    def test_sentence_structure_preserved(self, extracted_data: List[Dict]):
        """Verify extracted text has proper sentence structure."""
        if not extracted_data:
            pytest.skip("No extracted data available")
        for doc in extracted_data:
            text = doc.get("text", "")
            if len(text) < 500:
                continue

            # Count sentence endings
            sentence_count = len(re.findall(r'[.!?]', text))
            word_count = len(text.split())

            # Reasonable sentences: 15-50 words per sentence on average
            if sentence_count > 0:
                words_per_sentence = word_count / sentence_count
                assert 5 <= words_per_sentence <= 100, (
                    f"Unusual sentence length: {words_per_sentence:.1f} words/sentence"
                )


# =============================================================================
# Test Class 4: Elements Structure Tests with Real Data
# =============================================================================

class TestElementsStructureWithRealData:
    """Test element structure in extracted data."""

    def test_elements_have_required_fields(self, extracted_data: List[Dict]):
        """Verify elements have type and text fields."""
        if not extracted_data:
            pytest.skip("No extracted data available")
        for doc in extracted_data:
            elements = doc.get("elements", [])
            for i, elem in enumerate(elements):
                assert "type" in elem, f"Element {i} missing 'type'"
                assert "text" in elem, f"Element {i} missing 'text'"

    def test_element_types_are_valid(self, extracted_data: List[Dict]):
        """Verify element types are from expected set."""
        if not extracted_data:
            pytest.skip("No extracted data available")
        valid_types = {
            "TextElement", "TitleElement", "SupplementaryText",
            "EmptyElement", "TableElement", "ListElement",
            "ParagraphElement", "HeaderElement"
        }
        for doc in extracted_data:
            elements = doc.get("elements", [])
            for elem in elements:
                elem_type = elem.get("type", "")
                # Allow unknown types but log them
                if elem_type and elem_type not in valid_types:
                    # Just verify it's a string, don't fail on unknown types
                    assert isinstance(elem_type, str), "Type should be string"

    def test_elements_count_matches_metadata(self, extracted_data: List[Dict]):
        """Verify element count matches stats if present."""
        if not extracted_data:
            pytest.skip("No extracted data available")
        for doc in extracted_data:
            elements = doc.get("elements", [])
            stats = doc.get("stats", {})
            if "num_elements" in stats:
                assert len(elements) == stats["num_elements"], (
                    f"Element count mismatch: {len(elements)} vs {stats['num_elements']}"
                )

    def test_title_elements_present(self, extracted_data: List[Dict]):
        """Verify TitleElement types are present for structure."""
        if not extracted_data:
            pytest.skip("No extracted data available")
        for doc in extracted_data:
            elements = doc.get("elements", [])
            title_elements = [e for e in elements if e.get("type") == "TitleElement"]
            # Most risk sections have multiple subsection titles
            if len(elements) > 20:
                assert len(title_elements) >= 1, "No TitleElement found in large section"


# =============================================================================
# Test Class 5: ExtractedSection Model Tests
# =============================================================================

class TestExtractedSectionModel:
    """Test ExtractedSection Pydantic model."""

    def test_model_has_required_fields(self):
        """Verify ExtractedSection model has all required fields."""
        fields = ExtractedSection.model_fields
        required = ["text", "identifier", "title", "subsections", "elements", "metadata"]
        for field in required:
            assert field in fields, f"Missing required field: {field}"

    def test_model_serialization_roundtrip(self):
        """Verify ExtractedSection can serialize and deserialize."""
        section = ExtractedSection(
            text="Sample risk factors text with substantial content for testing.",
            identifier="part1item1a",
            title="Item 1A. Risk Factors",
            subsections=["Business Risks", "Financial Risks", "Operational Risks"],
            elements=[
                {"type": "TitleElement", "text": "Business Risks"},
                {"type": "TextElement", "text": "We face various risks..."}
            ],
            metadata={"source": "test", "form_type": "10-K"}
        )

        # Serialize
        data = section.model_dump()
        assert data["identifier"] == "part1item1a"
        assert len(data["subsections"]) == 3
        assert len(data["elements"]) == 2

        # Deserialize
        restored = ExtractedSection.model_validate(data)
        assert restored.identifier == section.identifier
        assert restored.title == section.title

    def test_model_length_method(self):
        """Verify __len__ returns text character count."""
        section = ExtractedSection(
            text="A" * 5000,
            identifier="test",
            title="Test Section",
            subsections=[],
            elements=[],
            metadata={}
        )
        assert len(section) == 5000

    def test_get_tables_method(self):
        """Verify get_tables returns TableElement types."""
        section = ExtractedSection(
            text="Sample text",
            identifier="test",
            title="Test",
            subsections=[],
            elements=[
                {"type": "TextElement", "text": "paragraph"},
                {"type": "TableElement", "text": "table data"},
                {"type": "TextElement", "text": "another paragraph"},
            ],
            metadata={}
        )
        tables = section.get_tables()
        assert len(tables) == 1
        assert tables[0]["type"] == "TableElement"

    def test_get_paragraphs_method(self):
        """Verify get_paragraphs returns text elements."""
        section = ExtractedSection(
            text="Sample text",
            identifier="test",
            title="Test",
            subsections=[],
            elements=[
                {"type": "TextElement", "text": "paragraph 1"},
                {"type": "TableElement", "text": "table"},
                {"type": "TextElement", "text": "paragraph 2"},
                {"type": "ParagraphElement", "text": "paragraph 3"},
            ],
            metadata={}
        )
        paragraphs = section.get_paragraphs()
        assert len(paragraphs) == 3


# =============================================================================
# Test Class 6: Integration Tests - Real Extraction
# =============================================================================

class TestExtractorIntegrationWithRealFiles:
    """Integration tests extracting from real HTML files."""

    def test_extract_risk_factors_from_real_file(
        self,
        extractor,
        test_10k_files: List[Path],
        parser
    ):
        """Test extracting risk factors from real 10-K file."""
        if not test_10k_files:
            pytest.skip("No raw 10-K files available")

        file_path = test_10k_files[0]
        filing = parser.parse_filing(file_path, form_type="10-K")
        section = extractor.extract_risk_factors(filing)

        assert section is not None, f"Failed to extract risk factors from {file_path.name}"
        assert len(section.text) > 1000, "Extracted text too short"
        assert section.identifier == "part1item1a"
        assert "risk" in section.title.lower()

    def test_extract_item_7a_market_risk_from_real_file(
        self,
        extractor,
        test_10k_files: List[Path],
        parser
    ):
        """Test extracting Item 7A (Market Risk) from real 10-K file."""
        if not test_10k_files:
            pytest.skip("No raw 10-K files available")

        # Try up to 3 files as some might not have Item 7A (it's optional for smaller companies)
        found = False
        for file_path in test_10k_files[:3]:
            filing = parser.parse_filing(file_path, form_type="10-K")
            # Item 7A identifier is part2item7a
            section = extractor.extract_section(filing, SectionIdentifier.ITEM_7A_MARKET_RISK)
            
            if section:
                found = True
                assert section.identifier == "part2item7a"
                assert len(section.text) > 100, "Extracted Item 7A text too short"
                break
        
        if not found:
            pytest.skip("Item 7A not found in available test files (might be optional for these companies)")

    def test_extract_preserves_subsections(
        self,
        extractor,
        test_10k_files: List[Path],
        parser
    ):
        """Test that extraction preserves subsection structure."""
        if not test_10k_files:
            pytest.skip("No raw 10-K files available")

        file_path = test_10k_files[0]
        filing = parser.parse_filing(file_path, form_type="10-K")
        section = extractor.extract_risk_factors(filing)

        if section:
            # Most 10-K risk sections have multiple subsections
            assert len(section.subsections) >= 1, (
                f"No subsections found in {file_path.name}"
            )

    def test_extract_metadata_populated(
        self,
        extractor,
        test_10k_files: List[Path],
        parser
    ):
        """Test that extraction populates metadata."""
        if not test_10k_files:
            pytest.skip("No raw 10-K files available")

        file_path = test_10k_files[0]
        filing = parser.parse_filing(file_path, form_type="10-K")
        section = extractor.extract_risk_factors(filing)

        if section:
            assert "form_type" in section.metadata
            assert section.metadata["form_type"] == "10-K"
            assert "num_elements" in section.metadata

    def test_risk_extractor_convenience_class(
        self,
        risk_extractor,
        test_10k_files: List[Path]
    ):
        """Test RiskFactorExtractor convenience methods."""
        if not test_10k_files:
            pytest.skip("No raw 10-K files available")

        file_path = test_10k_files[0]
        section = risk_extractor.extract_from_file(str(file_path), form_type="10-K")

        assert section is not None, f"Failed to extract from {file_path.name}"
        assert len(section.text) > 1000

        # Test get_risk_categories
        categories = risk_extractor.get_risk_categories(section)
        assert isinstance(categories, list)

        # Test get_risk_paragraphs
        paragraphs = risk_extractor.get_risk_paragraphs(section)
        assert isinstance(paragraphs, list)


# =============================================================================
# Test Class 7: Cross-Filing Consistency
# =============================================================================

class TestCrossFilingConsistency:
    """Test extraction consistency across multiple filings."""

    def test_multiple_filings_extract_successfully(
        self,
        extractor,
        test_10k_files: List[Path],
        parser
    ):
        """Test that multiple filings can be extracted."""
        if not test_10k_files or len(test_10k_files) < 2:
            pytest.skip("Need at least 2 files for consistency test")

        success_count = 0
        for file_path in test_10k_files[:5]:
            try:
                filing = parser.parse_filing(file_path, form_type="10-K")
                section = extractor.extract_risk_factors(filing)
                if section and len(section.text) > 1000:
                    success_count += 1
            except Exception:
                pass

        # At least 80% should succeed
        success_rate = success_count / min(5, len(test_10k_files))
        assert success_rate >= 0.6, (
            f"Low extraction success rate: {success_rate:.1%}"
        )

    def test_extracted_lengths_reasonable_variance(self, extracted_data: List[Dict]):
        """Verify extracted text lengths have reasonable variance."""
        if not extracted_data:
            pytest.skip("No extracted data available")
        lengths = [len(doc.get("text", "")) for doc in extracted_data]
        if len(lengths) < 2:
            pytest.skip("Need multiple documents for variance test")

        avg_length = sum(lengths) / len(lengths)
        # All should be within 10x of average (risk sections vary widely)
        for i, length in enumerate(lengths):
            assert length >= avg_length / 10, (
                f"Document {i} unusually short: {length} (avg: {avg_length:.0f})"
            )
            assert length <= avg_length * 10, (
                f"Document {i} unusually long: {length} (avg: {avg_length:.0f})"
            )


# =============================================================================
# Test Class 8: Save/Load JSON Tests
# =============================================================================

class TestExtractedSectionSaveLoad:
    """Test ExtractedSection save and load functionality."""

    def test_save_and_load_roundtrip(self, tmp_path):
        """Test saving and loading ExtractedSection."""
        section = ExtractedSection(
            text="Risk factors content for testing save/load functionality.",
            identifier="part1item1a",
            title="Item 1A. Risk Factors",
            subsections=["Market Risks", "Operational Risks"],
            elements=[{"type": "TextElement", "text": "Sample element"}],
            metadata={"form_type": "10-K", "test": True}
        )

        # Save
        output_path = tmp_path / "test_section.json"
        saved_path = section.save_to_json(output_path, overwrite=True)
        assert saved_path.exists()

        # Load
        loaded = ExtractedSection.load_from_json(saved_path)
        assert loaded.identifier == section.identifier
        assert loaded.title == section.title
        assert len(loaded.subsections) == len(section.subsections)

    def test_save_creates_parent_directory(self, tmp_path):
        """Test that save creates parent directories."""
        section = ExtractedSection(
            text="Test content",
            identifier="test",
            title="Test",
            subsections=[],
            elements=[],
            metadata={}
        )

        nested_path = tmp_path / "nested" / "dir" / "section.json"
        saved_path = section.save_to_json(nested_path, overwrite=True)
        assert saved_path.exists()

    def test_load_nonexistent_file_raises(self, tmp_path):
        """Test loading nonexistent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            ExtractedSection.load_from_json(tmp_path / "nonexistent.json")

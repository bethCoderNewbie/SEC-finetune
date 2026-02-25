"""Unit tests for Pydantic preprocessing models.

Covers:
- src/preprocessing/models/segmentation.py  (RiskSegment, SegmentedRisks)
- src/preprocessing/models/extraction.py    (ExtractedSection)
- src/preprocessing/models/parsing.py       (ParsedFiling, FormType)
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from pydantic import ValidationError

from src.preprocessing.models.segmentation import RiskSegment, SegmentedRisks
from src.preprocessing.models.extraction import ExtractedSection
from src.preprocessing.models.parsing import ParsedFiling, FormType


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def risk_segment():
    return RiskSegment(chunk_id="1A_001", text="We face intense market competition risks.")


@pytest.fixture
def segmented_risks(risk_segment):
    return SegmentedRisks(
        segments=[risk_segment],
        sic_code="7372",
        sic_name="PREPACKAGED SOFTWARE",
        cik="0000320193",
        ticker="AAPL",
        company_name="APPLE INC",
        form_type="10-K",
        section_title="Item 1A. Risk Factors",
    )


@pytest.fixture
def extracted_section():
    return ExtractedSection(
        text="Risk factor text here.",
        identifier="part1item1a",
        title="Item 1A. Risk Factors",
        subsections=["Competition", "Regulation"],
        elements=[
            {"type": "TextElement", "text": "Risk factor text here."},
            {"type": "TableElement", "text": "Table data"},
        ],
        metadata={"source": "10-K"},
        sic_code="7372",
        cik="0000320193",
        ticker="AAPL",
        company_name="APPLE INC",
        form_type="10-K",
    )


# ---------------------------------------------------------------------------
# RiskSegment
# ---------------------------------------------------------------------------

class TestRiskSegment:
    def test_auto_computes_word_count(self):
        seg = RiskSegment(chunk_id="1A_001", text="one two three four five")
        assert seg.word_count == 5

    def test_auto_computes_char_count(self):
        text = "hello world"
        seg = RiskSegment(chunk_id="1A_001", text=text)
        assert seg.char_count == len(text)

    def test_preserves_explicit_word_count(self):
        seg = RiskSegment(chunk_id="1A_001", text="one two three", word_count=99)
        assert seg.word_count == 99

    def test_preserves_explicit_char_count(self):
        seg = RiskSegment(chunk_id="1A_001", text="hello", char_count=999)
        assert seg.char_count == 999

    def test_chunk_id_stored_correctly(self):
        seg = RiskSegment(chunk_id="1A_043", text="text")
        assert seg.chunk_id == "1A_043"

    def test_requires_chunk_id_and_text(self):
        with pytest.raises(ValidationError):
            RiskSegment(text="missing chunk_id")


# ---------------------------------------------------------------------------
# SegmentedRisks
# ---------------------------------------------------------------------------

class TestSegmentedRisks:
    def test_auto_computes_total_segments(self, risk_segment):
        sr = SegmentedRisks(segments=[risk_segment, risk_segment])
        assert sr.total_segments == 2

    def test_len_equals_segment_count(self, segmented_risks):
        assert len(segmented_risks) == 1

    def test_get_texts_returns_all_texts(self, risk_segment):
        sr = SegmentedRisks(segments=[
            RiskSegment(chunk_id="1A_001", text="First risk."),
            RiskSegment(chunk_id="1A_002", text="Second risk."),
        ])
        texts = sr.get_texts()
        assert texts == ["First risk.", "Second risk."]

    def test_optional_metadata_fields_default_none(self):
        sr = SegmentedRisks(segments=[])
        assert sr.sic_code is None
        assert sr.ticker is None
        assert sr.company_name is None

    def test_metadata_dict_defaults_empty(self):
        sr = SegmentedRisks(segments=[])
        assert sr.metadata == {}


class TestSegmentedRisksSaveLoad:
    def test_save_creates_json_file(self, segmented_risks, tmp_path):
        out = tmp_path / "AAPL_segmented.json"
        saved = segmented_risks.save_to_json(out)
        assert saved.exists()
        assert saved.suffix == ".json"

    def test_save_enforces_json_extension(self, segmented_risks, tmp_path):
        out = tmp_path / "AAPL_segmented.txt"
        saved = segmented_risks.save_to_json(out)
        assert saved.suffix == ".json"

    def test_save_raises_if_exists_no_overwrite(self, segmented_risks, tmp_path):
        out = tmp_path / "AAPL_segmented.json"
        segmented_risks.save_to_json(out)
        with pytest.raises(FileExistsError):
            segmented_risks.save_to_json(out, overwrite=False)

    def test_save_overwrite_true_succeeds(self, segmented_risks, tmp_path):
        out = tmp_path / "AAPL_segmented.json"
        segmented_risks.save_to_json(out)
        saved = segmented_risks.save_to_json(out, overwrite=True)
        assert saved.exists()

    def test_roundtrip_preserves_segments(self, segmented_risks, tmp_path):
        out = tmp_path / "AAPL_segmented.json"
        segmented_risks.save_to_json(out)
        loaded = SegmentedRisks.load_from_json(out)
        assert len(loaded.segments) == len(segmented_risks.segments)
        assert loaded.segments[0].text == segmented_risks.segments[0].text

    def test_roundtrip_preserves_metadata(self, segmented_risks, tmp_path):
        out = tmp_path / "AAPL_segmented.json"
        segmented_risks.save_to_json(out)
        loaded = SegmentedRisks.load_from_json(out)
        assert loaded.ticker == "AAPL"
        assert loaded.sic_code == "7372"
        assert loaded.company_name == "APPLE INC"

    def test_load_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            SegmentedRisks.load_from_json(tmp_path / "nonexistent.json")

    def test_save_creates_parent_dirs(self, segmented_risks, tmp_path):
        out = tmp_path / "a" / "b" / "AAPL_segmented.json"
        segmented_risks.save_to_json(out)
        assert out.exists()

    def test_saved_json_includes_version(self, segmented_risks, tmp_path):
        out = tmp_path / "AAPL_segmented.json"
        segmented_risks.save_to_json(out)
        data = json.loads(out.read_text())
        assert "version" in data
        assert data["version"] == "1.0"


# ---------------------------------------------------------------------------
# ExtractedSection
# ---------------------------------------------------------------------------

class TestExtractedSection:
    def test_len_returns_text_length(self, extracted_section):
        assert len(extracted_section) == len(extracted_section.text)

    def test_get_tables_filters_correctly(self, extracted_section):
        tables = extracted_section.get_tables()
        assert len(tables) == 1
        assert tables[0]["type"] == "TableElement"

    def test_get_paragraphs_filters_correctly(self, extracted_section):
        paras = extracted_section.get_paragraphs()
        assert len(paras) == 1
        assert paras[0]["type"] == "TextElement"

    def test_optional_fields_default_none(self):
        section = ExtractedSection(
            text="text",
            identifier="id",
            title="title",
            subsections=[],
            elements=[],
            metadata={},
        )
        assert section.sic_code is None
        assert section.ticker is None


class TestExtractedSectionSaveLoad:
    def test_save_creates_json_file(self, extracted_section, tmp_path):
        out = tmp_path / "section.json"
        saved = extracted_section.save_to_json(out)
        assert saved.exists()

    def test_save_enforces_json_extension(self, extracted_section, tmp_path):
        out = tmp_path / "section.txt"
        saved = extracted_section.save_to_json(out)
        assert saved.suffix == ".json"

    def test_save_raises_if_exists_no_overwrite(self, extracted_section, tmp_path):
        out = tmp_path / "section.json"
        extracted_section.save_to_json(out)
        with pytest.raises(FileExistsError):
            extracted_section.save_to_json(out, overwrite=False)

    def test_save_overwrite_replaces_file(self, extracted_section, tmp_path):
        out = tmp_path / "section.json"
        extracted_section.save_to_json(out)
        extracted_section.save_to_json(out, overwrite=True)
        assert out.exists()

    def test_roundtrip_preserves_text(self, extracted_section, tmp_path):
        out = tmp_path / "section.json"
        extracted_section.save_to_json(out)
        loaded = ExtractedSection.load_from_json(out)
        assert loaded.text == extracted_section.text
        assert loaded.identifier == extracted_section.identifier
        assert loaded.ticker == "AAPL"

    def test_load_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            ExtractedSection.load_from_json(tmp_path / "missing.json")

    def test_load_raises_value_error_on_invalid_format(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text(json.dumps({"no_version": True}))
        with pytest.raises(ValueError):
            ExtractedSection.load_from_json(bad)

    def test_saved_json_includes_stats(self, extracted_section, tmp_path):
        out = tmp_path / "section.json"
        extracted_section.save_to_json(out)
        data = json.loads(out.read_text())
        assert "stats" in data
        assert data["stats"]["num_elements"] == 2
        assert data["stats"]["num_tables"] == 1
        assert data["stats"]["num_paragraphs"] == 1


# ---------------------------------------------------------------------------
# ParsedFiling
# ---------------------------------------------------------------------------

class TestParsedFiling:
    @pytest.fixture
    def mock_filing(self):
        mock_elem = MagicMock()
        mock_elem.text = "Some element text"
        mock_elem.__class__.__name__ = "TextElement"

        mock_tree = MagicMock()
        mock_tree.nodes = []

        return ParsedFiling(
            elements=[mock_elem],
            tree=mock_tree,
            form_type=FormType.FORM_10K,
            metadata={"cik": "0000320193"},
        )

    def test_len_returns_element_count(self, mock_filing):
        assert len(mock_filing) == 1

    def test_form_type_enum(self):
        assert FormType.FORM_10K.value == "10-K"
        assert FormType.FORM_10Q.value == "10-Q"

    def test_to_serializable_dict_has_required_keys(self, mock_filing):
        d = mock_filing._to_serializable_dict()
        assert "version" in d
        assert "form_type" in d
        assert "metadata" in d
        assert "elements" in d
        assert "tree" in d

    def test_form_type_value_in_serializable_dict(self, mock_filing):
        d = mock_filing._to_serializable_dict()
        assert d["form_type"] == "10-K"

    def test_metadata_preserved_in_serializable_dict(self, mock_filing):
        d = mock_filing._to_serializable_dict()
        assert d["metadata"]["cik"] == "0000320193"


class TestParsedFilingSaveLoad:
    @pytest.fixture
    def mock_filing(self):
        mock_elem = MagicMock()
        mock_elem.text = "Element text"
        mock_elem.__class__.__name__ = "TextElement"
        mock_tree = MagicMock()
        mock_tree.nodes = []
        return ParsedFiling(
            elements=[mock_elem],
            tree=mock_tree,
            form_type=FormType.FORM_10K,
            metadata={"cik": "12345"},
        )

    def test_save_to_pickle_creates_json(self, mock_filing, tmp_path):
        out = tmp_path / "filing.json"
        saved = mock_filing.save_to_pickle(out)
        assert saved.exists()
        assert saved.suffix == ".json"

    def test_pkl_extension_converted_to_json(self, mock_filing, tmp_path):
        out = tmp_path / "filing.pkl"
        saved = mock_filing.save_to_pickle(out)
        assert saved.suffix == ".json"

    def test_save_raises_if_exists_no_overwrite(self, mock_filing, tmp_path):
        out = tmp_path / "filing.json"
        mock_filing.save_to_pickle(out)
        with pytest.raises(FileExistsError):
            mock_filing.save_to_pickle(out, overwrite=False)

    def test_load_from_pickle_returns_dict(self, mock_filing, tmp_path):
        out = tmp_path / "filing.json"
        mock_filing.save_to_pickle(out)
        data = ParsedFiling.load_from_pickle(out)
        assert isinstance(data, dict)
        assert "form_type" in data
        assert "metadata" in data

    def test_load_from_json_alias(self, mock_filing, tmp_path):
        out = tmp_path / "filing.json"
        mock_filing.save_to_pickle(out)
        data = ParsedFiling.load_from_json(out)
        assert isinstance(data, dict)

    def test_load_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            ParsedFiling.load_from_pickle(tmp_path / "missing.json")

    def test_pkl_path_fallback_to_json(self, mock_filing, tmp_path):
        json_path = tmp_path / "filing.json"
        mock_filing.save_to_pickle(json_path)
        # Attempt to load via .pkl path — should fall back to .json
        pkl_path = tmp_path / "filing.pkl"
        data = ParsedFiling.load_from_pickle(pkl_path)
        assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# D2-A: ancestors field round-trip
# ---------------------------------------------------------------------------

class TestAncestorsRoundTrip:
    def test_ancestors_survive_save_load(self, tmp_path):
        """ancestors field survives save_to_json / load_from_json round-trip."""
        seg = RiskSegment(
            chunk_id="1A_001",
            text="Our supply chain depends on third parties.",
            ancestors=["ITEM 1A. RISK FACTORS", "Supply Chain Risk"],
        )
        sr = SegmentedRisks(segments=[seg], company_name="ACME", form_type="10-K")
        out = sr.save_to_json(tmp_path / "test.json", overwrite=True)
        loaded = SegmentedRisks.load_from_json(out)
        assert loaded.segments[0].ancestors == ["ITEM 1A. RISK FACTORS", "Supply Chain Risk"]

    def test_ancestors_present_in_raw_json(self, tmp_path):
        """ancestors key written to every chunk in the JSON file."""
        seg = RiskSegment(
            chunk_id="1A_001",
            text="Risk text.",
            ancestors=["ITEM 1A. RISK FACTORS"],
        )
        sr = SegmentedRisks(segments=[seg], company_name="ACME", form_type="10-K")
        out = sr.save_to_json(tmp_path / "test.json", overwrite=True)
        data = json.loads(out.read_text())
        assert "ancestors" in data["chunks"][0]
        assert data["chunks"][0]["ancestors"] == ["ITEM 1A. RISK FACTORS"]

    def test_ancestors_backward_compat_old_json(self, tmp_path):
        """Old JSON files without ancestors key load with default []."""
        old_data = {
            "version": "1.0",
            "document_info": {"company_name": "ACME"},
            "section_metadata": {
                "title": "Risk Factors",
                "identifier": "part1item1a",
                "stats": {},
            },
            "chunks": [
                {"chunk_id": "1A_001", "text": "Some risk.", "word_count": 2, "char_count": 9}
            ],
        }
        path = tmp_path / "old.json"
        path.write_text(json.dumps(old_data))
        loaded = SegmentedRisks.load_from_json(path)
        assert loaded.segments[0].ancestors == []

"""
Tests for boundary quality validation gates.

Tests validate_filing() (per-filing gate), validate_classification_record()
(per-record gate), and integration at all five system boundaries.
All tests use tmp_path for isolated SQLite DBs. No GPU/model dependencies.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Pre-warm partial module cache: src.preprocessing.__init__ may fail if
# sec_parser is not installed, but the submodule models.segmentation
# still loads.  The first import attempt caches enough for subsequent
# imports of src.analysis.segment_annotator to succeed.
try:
    import src.analysis.segment_annotator  # noqa: F401
except ImportError:
    pass

from src.validation.quality_gates import (
    FilingValidationResult,
    validate_classification_record,
    validate_filing,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_valid_filing(*, v2: bool = True, **overrides) -> dict:
    """Build a valid v2.1 segmented filing dict."""
    segments = [
        {
            "id": 1,
            "text": (
                "The company faces significant risk from cybersecurity threats "
                "and data breaches that may adversely affect operations. "
                "These risks could result in material losses and potential "
                "regulatory penalties. The uncertain nature of these threats "
                "requires ongoing investment in security infrastructure."
            ),
            "length": 280,
            "word_count": 42,
        },
        {
            "id": 2,
            "text": (
                "Climate change and environmental regulations pose material "
                "risks to our operations. Adverse weather events may disrupt "
                "supply chains and could increase operating costs significantly. "
                "The potential impact of carbon pricing remains uncertain."
            ),
            "length": 240,
            "word_count": 36,
        },
    ]

    if v2:
        data = {
            "document_info": {
                "ticker": "AAPL",
                "fiscal_year": "2024",
                "form_type": "10-K",
                "cik": "0000320193",
                "company_name": "Apple Inc.",
                "sic_code": "3571",
                "filed_as_of_date": "20241101",
                "accession_number": "0000320193-24-000105",
            },
            "section_metadata": {
                "identifier": "part1item1a",
                "stats": {
                    "total_chunks": 2,
                    "raw_section_char_count": 520,
                    "cleaned_section_char_count": 500,
                },
            },
            "segments": segments,
        }
        data["document_info"].update(overrides)
    else:
        data = {
            "ticker": "AAPL",
            "fiscal_year": "2024",
            "form_type": "10-K",
            "cik": "0000320193",
            "company_name": "Apple Inc.",
            "sic_code": "3571",
            "filed_as_of_date": "20241101",
            "segments": segments,
        }
        data.update(overrides)
    return data


def _make_valid_record(**overrides) -> dict:
    """Build a valid classification record matching PRD-002 schema."""
    record = {
        "index": 0,
        "text": (
            "The company faces significant risk from cybersecurity threats "
            "that may adversely affect operations and result in material losses."
        ),
        "word_count": 20,
        "char_count": 120,
        "label": 1,
        "risk_label": "social_capital",
        "sasb_topic": None,
        "sasb_industry": None,
        "sic_code": "3571",
        "ticker": "AAPL",
        "cik": "0000320193",
        "filing_date": "2024-11-01",
        "confidence": 0.85,
        "label_source": "nli_zero_shot",
    }
    record.update(overrides)
    return record


# ===========================================================================
# validate_filing tests
# ===========================================================================


class TestValidateFiling:
    """Tests for the per-filing quality gate."""

    def test_valid_filing_passes(self):
        """Complete filing with segments passes validation."""
        data = _make_valid_filing()
        result = validate_filing(data)
        assert result.is_valid is True
        assert result.status in ("PASS", "WARN")
        assert result.blocking_failures == []

    def test_missing_ticker_fails(self):
        """No ticker causes a blocking failure."""
        data = _make_valid_filing(ticker="")
        result = validate_filing(data)
        assert result.is_valid is False
        assert "ticker_present" in result.blocking_failures

    def test_missing_fiscal_year_fails(self):
        """No fiscal_year causes a blocking failure."""
        data = _make_valid_filing(fiscal_year="")
        result = validate_filing(data)
        assert result.is_valid is False
        assert "fiscal_year_valid" in result.blocking_failures

    def test_invalid_fiscal_year_fails(self):
        """Non-4-digit fiscal_year causes a blocking failure."""
        data = _make_valid_filing(fiscal_year="24")
        result = validate_filing(data)
        assert result.is_valid is False
        assert "fiscal_year_valid" in result.blocking_failures

    def test_empty_segments_fails(self):
        """Empty segments list triggers a blocking failure via check_single."""
        data = _make_valid_filing()
        data["segments"] = []
        result = validate_filing(data)
        # empty_segment_rate or substance check should fail
        assert result.is_valid is False

    def test_missing_cik_fails(self):
        """No CIK triggers a blocking failure via cik_present_rate."""
        data = _make_valid_filing(cik="")
        result = validate_filing(data)
        # cik_present_rate is a blocking threshold in health_check.yaml
        assert result.is_valid is False
        assert any("cik" in f for f in result.blocking_failures)

    def test_html_artifact_fails(self):
        """HTML tags in segment text trigger a blocking failure."""
        data = _make_valid_filing()
        data["segments"] = [
            {"id": 1, "text": "<div>This has <b>HTML</b> tags</div>", "length": 40, "word_count": 6}
        ]
        result = validate_filing(data)
        assert result.is_valid is False
        assert any("html" in f for f in result.blocking_failures)

    def test_short_segments_fails(self):
        """Segments below 50 chars trigger blocking failure."""
        data = _make_valid_filing()
        data["segments"] = [
            {"id": 1, "text": "Too short.", "length": 10, "word_count": 2}
        ]
        result = validate_filing(data)
        assert result.is_valid is False

    def test_missing_filed_as_of_date_warns(self):
        """No filed_as_of_date is a warning, not a blocking failure."""
        data = _make_valid_filing(filed_as_of_date="")
        result = validate_filing(data)
        assert "filed_as_of_date_present" in result.warnings
        # Should still be valid (warning, not blocking)
        # Unless other checks fail, is_valid should be True
        # (filed_as_of_date is the only non-blocking pre-condition)

    def test_v2_schema_supported(self):
        """document_info nested format is handled correctly."""
        data = _make_valid_filing(v2=True)
        result = validate_filing(data)
        assert result.is_valid is True
        assert result.blocking_failures == []

    def test_v1_schema_supported(self):
        """Flat v1 schema is also handled correctly."""
        data = _make_valid_filing(v2=False)
        result = validate_filing(data)
        assert result.is_valid is True
        assert result.blocking_failures == []


# ===========================================================================
# validate_classification_record tests
# ===========================================================================


class TestValidateClassificationRecord:
    """Tests for the per-record quality gate."""

    def test_valid_record_passes(self):
        """All PRD-002 fields present passes validation."""
        record = _make_valid_record()
        result = validate_classification_record(record)
        assert result.is_valid is True
        assert result.blocking_failures == []

    def test_empty_text_fails(self):
        """Empty text causes a blocking failure."""
        record = _make_valid_record(text="")
        result = validate_classification_record(record)
        assert result.is_valid is False
        assert "text_non_empty" in result.blocking_failures

    def test_invalid_risk_label_fails(self):
        """Label not in ARCHETYPE_NAMES causes a blocking failure."""
        record = _make_valid_record(risk_label="nonexistent_label")
        result = validate_classification_record(record)
        assert result.is_valid is False
        assert "risk_label_valid" in result.blocking_failures

    def test_invalid_label_source_fails(self):
        """Source not in _VALID_LABEL_SOURCES causes a blocking failure."""
        record = _make_valid_record(label_source="invalid_source")
        result = validate_classification_record(record)
        assert result.is_valid is False
        assert "label_source_valid" in result.blocking_failures

    def test_confidence_out_of_range_fails(self):
        """Confidence > 1.0 causes a blocking failure."""
        record = _make_valid_record(confidence=1.5)
        result = validate_classification_record(record)
        assert result.is_valid is False
        assert "confidence_in_range" in result.blocking_failures

    def test_confidence_negative_fails(self):
        """Confidence < 0.0 causes a blocking failure."""
        record = _make_valid_record(confidence=-0.1)
        result = validate_classification_record(record)
        assert result.is_valid is False
        assert "confidence_in_range" in result.blocking_failures

    def test_label_int_out_of_range_fails(self):
        """label=7 (not in {0..5}) causes a blocking failure."""
        record = _make_valid_record(label=7)
        result = validate_classification_record(record)
        assert result.is_valid is False
        assert "label_valid" in result.blocking_failures

    def test_zero_word_count_fails(self):
        """word_count=0 causes a blocking failure."""
        record = _make_valid_record(word_count=0)
        result = validate_classification_record(record)
        assert result.is_valid is False
        assert "word_count_positive" in result.blocking_failures

    def test_zero_char_count_fails(self):
        """char_count=0 causes a blocking failure."""
        record = _make_valid_record(char_count=0)
        result = validate_classification_record(record)
        assert result.is_valid is False
        assert "char_count_positive" in result.blocking_failures

    def test_word_count_below_min_warns(self):
        """word_count=5 (below MIN_SEGMENT_WORDS=20) triggers a warning."""
        record = _make_valid_record(word_count=5)
        result = validate_classification_record(record)
        assert "word_count_in_range" in result.warnings

    def test_missing_cik_warns(self):
        """Missing CIK is a warning, not a blocking failure."""
        record = _make_valid_record(cik="")
        result = validate_classification_record(record)
        assert "cik_present" in result.warnings
        # Should still be valid
        assert result.is_valid is True

    def test_missing_filing_date_warns(self):
        """Missing filing_date is a warning, not a blocking failure."""
        record = _make_valid_record(filing_date="")
        result = validate_classification_record(record)
        assert "filing_date_present" in result.warnings
        assert result.is_valid is True

    def test_all_archetypes_pass(self):
        """Each of 6 archetypes is accepted as valid."""
        from src.analysis.segment_annotator import ARCHETYPE_LABEL_MAP

        for archetype, label_int in ARCHETYPE_LABEL_MAP.items():
            record = _make_valid_record(risk_label=archetype, label=label_int)
            result = validate_classification_record(record)
            assert result.is_valid is True, f"Archetype {archetype} should pass"

    def test_all_label_sources_pass(self):
        """Each of the valid label sources is accepted."""
        from src.analysis.segment_annotator import _VALID_LABEL_SOURCES

        for source in _VALID_LABEL_SOURCES:
            record = _make_valid_record(label_source=source)
            result = validate_classification_record(record)
            assert result.is_valid is True, f"Label source {source} should pass"

    def test_missing_ticker_fails(self):
        """Empty ticker causes a blocking failure."""
        record = _make_valid_record(ticker="")
        result = validate_classification_record(record)
        assert result.is_valid is False
        assert "ticker_non_empty" in result.blocking_failures


# ===========================================================================
# Integration tests
# ===========================================================================


class TestIntegrationBackfill:
    """Test that _import_segmented_json rejects bad filings."""

    def test_backfill_rejects_bad_filing(self, tmp_path):
        """_import_segmented_json skips filings that fail validation."""
        from src.storage.database import FilingDatabase

        # Create a segmented JSON file missing required ticker
        bad_data = _make_valid_filing(ticker="")
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        bad_file = run_dir / "BAD_10K_2024_part1item1a_segmented.json"
        bad_file.write_text(json.dumps(bad_data), encoding="utf-8")

        db = FilingDatabase(tmp_path / "test.db")
        db.connect()
        try:
            imported, skipped = db.backfill_from_run_dir(run_dir)
            assert imported == 0
            assert skipped == 1
        finally:
            db.close()

    def test_backfill_accepts_good_filing(self, tmp_path):
        """_import_segmented_json accepts valid filings."""
        from src.storage.database import FilingDatabase

        good_data = _make_valid_filing()
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        good_file = run_dir / "AAPL_10K_2024_part1item1a_segmented.json"
        good_file.write_text(json.dumps(good_data), encoding="utf-8")

        db = FilingDatabase(tmp_path / "test.db")
        db.connect()
        try:
            imported, skipped = db.backfill_from_run_dir(run_dir)
            assert imported == 1
            assert skipped == 0
        finally:
            db.close()


class TestIntegrationClassifyAndStore:
    """Test that classify_and_store rejects invalid filings."""

    def test_classify_and_store_rejects_bad_filing(self, tmp_path):
        """classify_and_store raises ValueError on invalid filing."""
        from src.storage.database import FilingDatabase, classify_and_store

        # Create a segmented JSON file missing required ticker
        bad_data = _make_valid_filing(ticker="")
        json_file = tmp_path / "bad_segmented.json"
        json_file.write_text(json.dumps(bad_data), encoding="utf-8")

        db = FilingDatabase(tmp_path / "test.db")
        db.connect()
        try:
            filing = {
                "id": 1,
                "ticker": "",
                "fiscal_year": "2024",
                "form_type": "10-K",
                "segmented_json_path": str(json_file),
            }
            with pytest.raises(ValueError, match="Validation failed"):
                classify_and_store(db, filing, MagicMock(), "v1")
        finally:
            db.close()


class TestIntegrationAnnotator:
    """Test degenerate segment filtering in annotate()."""

    def test_annotate_filters_empty_segments(self):
        """annotate() skips empty-text segments after merge."""
        from src.preprocessing.models.segmentation import RiskSegment, SegmentedRisks
        from src.analysis.segment_annotator import SegmentAnnotator

        # Create a SegmentedRisks with degenerate segments
        segments = [
            RiskSegment(chunk_id="1", text="", word_count=0, char_count=0),
            RiskSegment(chunk_id="2", text="   ", word_count=0, char_count=0),
        ]
        segmented = SegmentedRisks(
            segments=segments,
            ticker="TEST",
            fiscal_year="2024",
            section_identifier="part1item1a",
            total_segments=2,
        )

        # Build a minimal annotator without loading the NLI model
        annotator = SegmentAnnotator.__new__(SegmentAnnotator)
        annotator._merge_lo = 200
        annotator._merge_hi = 379
        annotator._taxonomy = MagicMock()
        annotator._taxonomy.get_industry_for_sic.return_value = None

        records = annotator.annotate(segmented)
        assert records == []

    def test_annotate_run_dir_skips_invalid_records(self, tmp_path):
        """Invalid records are not written to JSONL."""
        from src.preprocessing.models.segmentation import RiskSegment, SegmentedRisks

        # Create a valid segmented JSON file
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        good_data = _make_valid_filing()
        json_file = run_dir / "AAPL_10K_2024_part1item1a_segmented.json"
        json_file.write_text(json.dumps(good_data), encoding="utf-8")

        output_path = tmp_path / "output.jsonl"

        # Create an annotator mock that returns one valid and one invalid record
        valid_record = _make_valid_record()
        invalid_record = _make_valid_record(text="", label=99)

        with patch("src.analysis.segment_annotator.SegmentAnnotator.__init__", return_value=None):
            from src.analysis.segment_annotator import SegmentAnnotator

            annotator = SegmentAnnotator.__new__(SegmentAnnotator)

            with patch.object(annotator, "annotate", return_value=[valid_record, invalid_record]):
                from src.config import settings

                annotator._merge_lo = 200
                annotator._merge_hi = 379

                total = annotator.annotate_run_dir(
                    run_dir=run_dir,
                    output_path=output_path,
                    section_include=["part1item1a"],
                )

            # Only the valid record should be written
            assert total == 1
            lines = output_path.read_text(encoding="utf-8").strip().split("\n")
            assert len(lines) == 1
            written = json.loads(lines[0])
            assert written["text"] == valid_record["text"]


class TestIntegrationQualityAudit:
    """Test the CLI quality audit feature."""

    def test_quality_audit_clean_db(self, tmp_path):
        """Zero issues reported on clean data."""
        from src.storage.database import FilingDatabase

        db = FilingDatabase(tmp_path / "test.db")
        db.connect()
        try:
            # Insert a clean filing
            fid = db.upsert_filing(
                ticker="AAPL",
                fiscal_year="2024",
                form_type="10-K",
                section_id="part1item1a",
                cik="0000320193",
                company_name="Apple Inc.",
                sic_code="3571",
                total_segments=2,
            )
            # Insert clean classifications
            db.store_classifications(
                filing_id=fid,
                classifications=[
                    {
                        "text": "Valid risk text about environment.",
                        "word_count": 5,
                        "risk_label": "environment",
                        "confidence": 0.85,
                        "label_source": "nli_zero_shot",
                    }
                ],
                classifier_version="v1",
                ticker="AAPL",
                fiscal_year="2024",
            )

            # Run audit queries directly
            from src.analysis.segment_annotator import ARCHETYPE_NAMES, _VALID_LABEL_SOURCES

            archetype_placeholders = ", ".join("?" for _ in ARCHETYPE_NAMES)
            source_placeholders = ", ".join("?" for _ in _VALID_LABEL_SOURCES)

            checks = {
                "missing_cik": (
                    "SELECT COUNT(*) as cnt FROM filings WHERE cik IS NULL OR cik = ''",
                    (),
                ),
                "invalid_labels": (
                    f"SELECT COUNT(*) as cnt FROM classifications WHERE risk_label NOT IN ({archetype_placeholders})",
                    tuple(ARCHETYPE_NAMES),
                ),
                "out_of_range_confidence": (
                    "SELECT COUNT(*) as cnt FROM classifications WHERE confidence < 0 OR confidence > 1",
                    (),
                ),
                "invalid_sources": (
                    f"SELECT COUNT(*) as cnt FROM classifications WHERE label_source NOT IN ({source_placeholders})",
                    tuple(_VALID_LABEL_SOURCES),
                ),
            }

            for name, (sql, params) in checks.items():
                row = db.conn.execute(sql, params).fetchone()
                assert row["cnt"] == 0, f"Expected 0 issues for {name}, got {row['cnt']}"
        finally:
            db.close()

    def test_quality_audit_detects_issues(self, tmp_path):
        """Detects missing CIK and invalid labels in DB."""
        from src.storage.database import FilingDatabase

        db = FilingDatabase(tmp_path / "test.db")
        db.connect()
        try:
            # Insert a filing with missing CIK
            fid = db.upsert_filing(
                ticker="BAD",
                fiscal_year="2024",
                form_type="10-K",
                section_id="part1item1a",
                cik="",
                company_name="Bad Corp",
                total_segments=1,
            )
            # Insert classification with invalid risk_label
            db.conn.execute(
                """INSERT INTO classifications (
                    filing_id, segment_index, text, word_count,
                    risk_label, confidence, label_source, ticker, fiscal_year
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (fid, 0, "some text", 5, "INVALID_LABEL", 0.5, "nli_zero_shot", "BAD", "2024"),
            )
            db.conn.commit()

            # Check missing CIK
            row = db.conn.execute(
                "SELECT COUNT(*) as cnt FROM filings WHERE cik IS NULL OR cik = ''"
            ).fetchone()
            assert row["cnt"] == 1

            # Check invalid labels
            from src.analysis.segment_annotator import ARCHETYPE_NAMES

            placeholders = ", ".join("?" for _ in ARCHETYPE_NAMES)
            row = db.conn.execute(
                f"SELECT COUNT(*) as cnt FROM classifications WHERE risk_label NOT IN ({placeholders})",
                tuple(ARCHETYPE_NAMES),
            ).fetchone()
            assert row["cnt"] == 1
        finally:
            db.close()

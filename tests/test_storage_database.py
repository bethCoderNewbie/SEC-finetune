"""
Unit tests for src.storage.database — FilingDatabase, singleton, and helpers.

All tests use tmp_path (pytest fixture) for an isolated SQLite DB.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.storage.database import (
    FilingDatabase,
    classify_and_store,
    close_database,
    compute_classifier_version,
    get_database,
    _CURRENT_SCHEMA_VERSION,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db(tmp_path: Path) -> FilingDatabase:
    """Create a fresh in-memory-like FilingDatabase for each test."""
    database = FilingDatabase(tmp_path / "test.db")
    database.connect()
    yield database
    database.close()


def _insert_filing(
    db: FilingDatabase,
    ticker: str = "AAPL",
    fiscal_year: str = "2024",
    form_type: str = "10-K",
    section_id: str = "part1item1a",
    **kwargs,
) -> int:
    """Helper to insert a filing and return its id."""
    return db.upsert_filing(
        ticker=ticker,
        fiscal_year=fiscal_year,
        form_type=form_type,
        section_id=section_id,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Test 1: upsert and get filing
# ---------------------------------------------------------------------------


def test_upsert_and_get_filing(db: FilingDatabase) -> None:
    fid = _insert_filing(
        db,
        ticker="AAPL",
        fiscal_year="2024",
        company_name="Apple Inc.",
        sic_code="3571",
        accession_number="0000320193-24-000081",
    )
    assert fid > 0

    row = db.get_filing("AAPL", "2024", "10-K", "part1item1a")
    assert row is not None
    assert row["ticker"] == "AAPL"
    assert row["company_name"] == "Apple Inc."
    assert row["sic_code"] == "3571"
    assert row["accession_number"] == "0000320193-24-000081"


# ---------------------------------------------------------------------------
# Test 2: upsert conflict updates
# ---------------------------------------------------------------------------


def test_upsert_conflict_updates(db: FilingDatabase) -> None:
    fid1 = _insert_filing(db, company_name="Apple Inc.")
    fid2 = _insert_filing(db, company_name="Apple Inc. (Updated)")
    assert fid1 == fid2  # same filing id on conflict

    row = db.get_filing("AAPL", "2024", "10-K", "part1item1a")
    assert row["company_name"] == "Apple Inc. (Updated)"


# ---------------------------------------------------------------------------
# Test 3: get_segmented_json_paths
# ---------------------------------------------------------------------------


def test_get_segmented_json_paths(db: FilingDatabase) -> None:
    _insert_filing(db, section_id="part1item1a", segmented_json_path="/data/aapl_1a.json")
    _insert_filing(db, section_id="part2item7", segmented_json_path="/data/aapl_7.json")
    _insert_filing(db, ticker="MSFT", section_id="part1item1a", segmented_json_path="/data/msft_1a.json")

    paths = db.get_segmented_json_paths("AAPL", "2024")
    assert len(paths) == 2
    assert "/data/aapl_1a.json" in paths
    assert "/data/aapl_7.json" in paths


# ---------------------------------------------------------------------------
# Test 4: find_tickers_for_sic
# ---------------------------------------------------------------------------


def test_find_tickers_for_sic(db: FilingDatabase) -> None:
    _insert_filing(db, ticker="AAPL", sic_code="3571")
    _insert_filing(db, ticker="DELL", section_id="part1item1a", sic_code="3571")
    _insert_filing(db, ticker="MSFT", section_id="part1item1a", sic_code="7372")

    result = db.find_tickers_for_sic("3571")
    assert result == ["AAPL", "DELL"]

    result = db.find_tickers_for_sic("7372")
    assert result == ["MSFT"]


# ---------------------------------------------------------------------------
# Test 5: store and get classifications
# ---------------------------------------------------------------------------


def test_store_and_get_classifications(db: FilingDatabase) -> None:
    fid = _insert_filing(db)

    classifications = [
        {"text": "Risk segment 1", "word_count": 5, "risk_label": "environment",
         "confidence": 0.85, "label_source": "nli_zero_shot"},
        {"text": "Risk segment 2", "word_count": 4, "risk_label": "governance",
         "confidence": 0.72, "label_source": "heuristic"},
    ]

    count = db.store_classifications(fid, classifications, "v1", "AAPL", "2024")
    assert count == 2

    rows = db.get_classifications("AAPL", "2024")
    assert len(rows) == 2
    assert rows[0]["risk_label"] == "environment"
    assert rows[1]["risk_label"] == "governance"
    assert rows[0]["segment_index"] == 0
    assert rows[1]["segment_index"] == 1


# ---------------------------------------------------------------------------
# Test 6: store classifications atomic (no duplicates on re-store)
# ---------------------------------------------------------------------------


def test_store_classifications_atomic(db: FilingDatabase) -> None:
    fid = _insert_filing(db)

    first_batch = [
        {"text": "Old text", "risk_label": "environment", "confidence": 0.9,
         "label_source": "nli_zero_shot"},
    ]
    db.store_classifications(fid, first_batch, "v1", "AAPL", "2024")

    second_batch = [
        {"text": "New text A", "risk_label": "governance", "confidence": 0.8,
         "label_source": "heuristic"},
        {"text": "New text B", "risk_label": "other", "confidence": 0.6,
         "label_source": "heuristic"},
    ]
    db.store_classifications(fid, second_batch, "v2", "AAPL", "2024")

    rows = db.get_classifications("AAPL", "2024")
    assert len(rows) == 2  # old row deleted, only new batch remains
    assert rows[0]["text"] == "New text A"
    assert rows[1]["text"] == "New text B"


# ---------------------------------------------------------------------------
# Test 7: has_classifications version check
# ---------------------------------------------------------------------------


def test_has_classifications_version_check(db: FilingDatabase) -> None:
    fid = _insert_filing(db)

    classifications = [
        {"text": "text", "risk_label": "other", "confidence": 0.5, "label_source": "heuristic"},
    ]
    db.store_classifications(fid, classifications, "v1", "AAPL", "2024")

    assert db.has_classifications("AAPL", "2024", classifier_version="v1") is True
    assert db.has_classifications("AAPL", "2024", classifier_version="v2") is False


# ---------------------------------------------------------------------------
# Test 8: store and get risk score
# ---------------------------------------------------------------------------


def test_store_and_get_risk_score(db: FilingDatabase) -> None:
    fid = _insert_filing(db)

    db.store_risk_score(
        filing_id=fid,
        ticker="AAPL",
        fiscal_year="2024",
        form_type="10-K",
        score=72,
        dominant_archetype="governance",
        label_distribution={"governance": 5, "environment": 3},
    )

    row = db.get_risk_score("AAPL", "2024")
    assert row is not None
    assert row["score"] == 72
    assert row["dominant_archetype"] == "governance"
    assert row["label_distribution"] == {"governance": 5, "environment": 3}


# ---------------------------------------------------------------------------
# Test 9: backfill_from_run_dir
# ---------------------------------------------------------------------------


def _make_segmented_json(path: Path, ticker: str, fiscal_year: str, section_id: str = "part1item1a") -> None:
    """Create a minimal valid segmented JSON file."""
    data = {
        "document_info": {
            "ticker": ticker,
            "fiscal_year": fiscal_year,
            "form_type": "10-K",
            "cik": "0001234",
            "company_name": f"{ticker} Corp",
        },
        "section_metadata": {
            "identifier": section_id,
            "stats": {"total_chunks": 2},
        },
        "chunks": [
            {"text": "Segment one", "word_count": 2},
            {"text": "Segment two", "word_count": 2},
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_backfill_from_run_dir(db: FilingDatabase, tmp_path: Path) -> None:
    run_dir = tmp_path / "20260101_120000_preprocessing_abc1234"
    run_dir.mkdir()

    _make_segmented_json(run_dir / "AAPL_10K_2024_part1item1a_segmented.json", "AAPL", "2024")
    _make_segmented_json(run_dir / "MSFT_10K_2024_part1item1a_segmented.json", "MSFT", "2024")

    imported, skipped = db.backfill_from_run_dir(run_dir)
    assert imported == 2
    assert skipped == 0

    paths = db.get_segmented_json_paths("AAPL", "2024")
    assert len(paths) == 1


# ---------------------------------------------------------------------------
# Test 10: backfill returns skip count
# ---------------------------------------------------------------------------


def test_backfill_returns_skip_count(db: FilingDatabase, tmp_path: Path) -> None:
    run_dir = tmp_path / "20260101_120000_preprocessing_abc1234"
    run_dir.mkdir()

    _make_segmented_json(run_dir / "AAPL_10K_2024_part1item1a_segmented.json", "AAPL", "2024")

    # File with missing ticker → will be skipped
    bad_data = {"document_info": {"fiscal_year": "2024", "form_type": "10-K"}, "chunks": []}
    (run_dir / "BAD_10K_2024_part1item1a_segmented.json").write_text(
        json.dumps(bad_data), encoding="utf-8"
    )

    imported, skipped = db.backfill_from_run_dir(run_dir)
    assert imported == 1
    assert skipped == 1


# ---------------------------------------------------------------------------
# Test 11: search_tickers
# ---------------------------------------------------------------------------


def test_search_tickers(db: FilingDatabase) -> None:
    _insert_filing(db, ticker="AAPL", company_name="Apple Inc.")
    _insert_filing(db, ticker="MSFT", section_id="part1item1a", company_name="Microsoft Corp")

    results = db.search_tickers("AAPL")
    assert len(results) == 1
    assert results[0]["ticker"] == "AAPL"

    results = db.search_tickers("Corp")
    assert len(results) == 1
    assert results[0]["ticker"] == "MSFT"


# ---------------------------------------------------------------------------
# Test 12: get_statistics
# ---------------------------------------------------------------------------


def test_get_statistics(db: FilingDatabase) -> None:
    _insert_filing(db, ticker="AAPL")
    _insert_filing(db, ticker="MSFT", section_id="part1item1a")
    _insert_filing(db, ticker="AAPL", section_id="part2item7")

    stats = db.get_statistics()
    assert stats["total_filings"] == 3
    assert stats["unique_tickers"] == 2
    assert stats["unclassified_filings"] == 3
    assert stats["classified_filings"] == 0
    assert stats["fiscal_year_range"] == ("2024", "2024")
    assert "10-K" in stats["by_form_type"]


# ---------------------------------------------------------------------------
# Test 13: get_unclassified_filings
# ---------------------------------------------------------------------------


def test_get_unclassified_filings(db: FilingDatabase) -> None:
    fid1 = _insert_filing(db, ticker="AAPL")
    fid2 = _insert_filing(db, ticker="MSFT", section_id="part1item1a")

    # Classify AAPL only
    db.store_classifications(
        fid1,
        [{"text": "x", "risk_label": "other", "confidence": 0.5, "label_source": "heuristic"}],
        "v1",
        "AAPL",
        "2024",
    )

    unclassified = db.get_unclassified_filings(classifier_version="v1")
    assert len(unclassified) == 1
    assert unclassified[0]["ticker"] == "MSFT"


# ---------------------------------------------------------------------------
# Test 14: compute_classifier_version
# ---------------------------------------------------------------------------


def test_compute_classifier_version() -> None:
    v1 = compute_classifier_version("model_a", 0.5, 0.3, 200, 379)
    v2 = compute_classifier_version("model_a", 0.5, 0.3, 200, 379)
    assert v1 == v2  # deterministic

    v3 = compute_classifier_version("model_b", 0.5, 0.3, 200, 379)
    assert v1 != v3  # changes on config change

    assert len(v1) == 12  # short hash


# ---------------------------------------------------------------------------
# Test 15: get_database singleton
# ---------------------------------------------------------------------------


def test_get_database_singleton(tmp_path: Path) -> None:
    db_path = tmp_path / "singleton.db"

    try:
        a = get_database(db_path)
        b = get_database(db_path)
        assert a is b  # same instance
    finally:
        close_database()

    # After close, a new call should return a new instance
    try:
        c = get_database(db_path)
        assert c is not a
    finally:
        close_database()


# ---------------------------------------------------------------------------
# Test 16: schema_version table
# ---------------------------------------------------------------------------


def test_schema_version(db: FilingDatabase) -> None:
    row = db.conn.execute("SELECT MAX(version) as v FROM schema_version").fetchone()
    assert row["v"] == _CURRENT_SCHEMA_VERSION

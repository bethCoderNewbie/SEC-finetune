"""
FilingDatabase — SQLite-backed storage for filing metadata, classifications, and risk scores.

Design rationale (ADR-017):
  - SQLite (not PostgreSQL): single-developer project, embedded, zero-config, WAL mode
    supports concurrent reads from Streamlit while background jobs write.
  - Supplements JSON: stamped run directories (ADR-007) remain the authoritative source.
    If deleted, backfill_from_run_dir() reconstructs the DB from JSON files.
  - Cache invalidation: SEC filings are immutable (amendments get new accession numbers).
    Classifications invalidate when classifier_version changes.

Critical query patterns:
  - Lookup by ticker+year:   <1ms via idx_filings_ticker_year
  - Compare two companies:   <2ms via idx_classifications_ticker
  - Sector cohort by SIC:    <10ms via idx_filings_sic
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS filings (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker              TEXT NOT NULL,
    cik                 TEXT,
    company_name        TEXT,
    form_type           TEXT NOT NULL,
    fiscal_year         TEXT NOT NULL,
    fiscal_quarter      TEXT,
    accession_number    TEXT,
    filed_as_of_date    TEXT,
    sic_code            TEXT,
    sic_name            TEXT,
    section_id          TEXT NOT NULL,
    raw_file_path       TEXT,
    segmented_json_path TEXT,
    run_dir             TEXT,
    total_segments      INTEGER,
    raw_char_count      INTEGER,
    cleaned_char_count  INTEGER,
    text_coverage_ratio REAL,
    pipeline_version    TEXT,
    classifier_version  TEXT,
    processed_at        TEXT,
    classified_at       TEXT,
    no_material_change  BOOLEAN DEFAULT FALSE,
    UNIQUE(ticker, fiscal_year, form_type, section_id)
);

CREATE TABLE IF NOT EXISTS classifications (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    filing_id       INTEGER NOT NULL REFERENCES filings(id) ON DELETE CASCADE,
    segment_index   INTEGER NOT NULL,
    chunk_id        TEXT,
    text            TEXT NOT NULL,
    word_count      INTEGER,
    char_count      INTEGER,
    segment_hash    TEXT,
    risk_label      TEXT NOT NULL,
    sasb_topic      TEXT,
    sasb_industry   TEXT,
    confidence      REAL NOT NULL,
    label_source    TEXT NOT NULL,
    parent_subsection TEXT,
    ticker          TEXT NOT NULL,
    fiscal_year     TEXT NOT NULL,
    UNIQUE(filing_id, segment_index)
);

CREATE TABLE IF NOT EXISTS risk_scores (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    filing_id           INTEGER NOT NULL REFERENCES filings(id) ON DELETE CASCADE,
    ticker              TEXT NOT NULL,
    fiscal_year         TEXT NOT NULL,
    form_type           TEXT NOT NULL,
    score               INTEGER NOT NULL,
    dominant_archetype  TEXT,
    label_distribution  TEXT,
    computed_at         TEXT NOT NULL,
    UNIQUE(filing_id)
);

CREATE INDEX IF NOT EXISTS idx_filings_ticker_year ON filings(ticker, fiscal_year);
CREATE INDEX IF NOT EXISTS idx_filings_sic ON filings(sic_code, fiscal_year);
CREATE INDEX IF NOT EXISTS idx_filings_form_type ON filings(form_type, fiscal_year);
CREATE INDEX IF NOT EXISTS idx_classifications_filing ON classifications(filing_id);
CREATE INDEX IF NOT EXISTS idx_classifications_ticker ON classifications(ticker, fiscal_year);
CREATE INDEX IF NOT EXISTS idx_classifications_label ON classifications(risk_label, ticker);
CREATE INDEX IF NOT EXISTS idx_risk_scores_ticker ON risk_scores(ticker, fiscal_year);
CREATE INDEX IF NOT EXISTS idx_filings_accession ON filings(accession_number);

CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER NOT NULL,
    applied_at  TEXT NOT NULL
);
"""

# ---------------------------------------------------------------------------
# Schema migrations — keyed by target version, value is SQL to apply.
# Each migration runs inside the same transaction as the version bump.
# ---------------------------------------------------------------------------

_MIGRATIONS: Dict[int, str] = {
    # Version 1 = initial schema (everything above). No migration SQL needed.
    2: """
ALTER TABLE classifications ADD COLUMN char_count INTEGER;
ALTER TABLE classifications ADD COLUMN segment_hash TEXT;
ALTER TABLE filings ADD COLUMN text_coverage_ratio REAL;
UPDATE classifications SET char_count = LENGTH(text);
CREATE INDEX IF NOT EXISTS idx_classifications_hash ON classifications(segment_hash);
""",
}

_CURRENT_SCHEMA_VERSION = 2


def compute_classifier_version(
    model_name: str,
    confidence_threshold: float,
    gate_threshold: float,
    merge_lo: int,
    merge_hi: int,
) -> str:
    """Compute a short hash representing the classifier configuration.

    When this changes, cached classifications are invalidated.
    """
    version_inputs = f"{model_name}:{confidence_threshold}:{gate_threshold}:{merge_lo}:{merge_hi}"
    return hashlib.sha256(version_inputs.encode()).hexdigest()[:12]


class FilingDatabase:
    """SQLite-backed filing database.

    Usage:
        db = FilingDatabase(Path("data/sec_filings.db"))
        db.backfill_from_run_dir(Path("data/processed/20260220_..."))
        rows = db.get_classifications("AAPL", "2024")
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Open (or reopen) the SQLite connection with WAL mode."""
        if self._conn is not None:
            return
        self._conn = sqlite3.connect(str(self._db_path), timeout=30)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA_SQL)
        self._conn.commit()
        self._ensure_schema_version()
        logger.debug("FilingDatabase connected: %s", self._db_path)

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "FilingDatabase":
        self.connect()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def _ensure_schema_version(self) -> None:
        """Check current schema version and apply any pending migrations.

        For fresh databases (version 0), the CREATE TABLE statements in
        ``_SCHEMA_SQL`` already include all columns up to the current version,
        so we skip migration SQL and just stamp the version.  Migrations only
        run when upgrading an existing database from a prior version.
        """
        assert self._conn is not None
        row = self._conn.execute(
            "SELECT MAX(version) as v FROM schema_version"
        ).fetchone()
        current = row["v"] if row["v"] is not None else 0

        if current >= _CURRENT_SCHEMA_VERSION:
            return

        if current == 0:
            # Fresh database: schema already has all columns from _SCHEMA_SQL.
            # Just record the current version and create any indexes that depend
            # on v2+ columns (kept out of _SCHEMA_SQL to avoid errors on v1 DBs).
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_classifications_hash "
                "ON classifications(segment_hash)"
            )
            now = datetime.now(tz=timezone.utc).isoformat()
            self._conn.execute(
                "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                (_CURRENT_SCHEMA_VERSION, now),
            )
            logger.info("Fresh database — stamped schema version %d", _CURRENT_SCHEMA_VERSION)
            self._conn.commit()
            return

        for target_ver in range(current + 1, _CURRENT_SCHEMA_VERSION + 1):
            migration_sql = _MIGRATIONS.get(target_ver)
            if migration_sql:
                self._conn.executescript(migration_sql)
            now = datetime.now(tz=timezone.utc).isoformat()
            self._conn.execute(
                "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                (target_ver, now),
            )
            logger.info("Applied schema migration to version %d", target_ver)

        self._conn.commit()

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self.connect()
        return self._conn  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Filing CRUD
    # ------------------------------------------------------------------

    def upsert_filing(
        self,
        ticker: str,
        fiscal_year: str,
        form_type: str,
        section_id: str,
        *,
        cik: Optional[str] = None,
        company_name: Optional[str] = None,
        fiscal_quarter: Optional[str] = None,
        accession_number: Optional[str] = None,
        filed_as_of_date: Optional[str] = None,
        sic_code: Optional[str] = None,
        sic_name: Optional[str] = None,
        raw_file_path: Optional[str] = None,
        segmented_json_path: Optional[str] = None,
        run_dir: Optional[str] = None,
        total_segments: Optional[int] = None,
        raw_char_count: Optional[int] = None,
        cleaned_char_count: Optional[int] = None,
        text_coverage_ratio: Optional[float] = None,
        pipeline_version: Optional[str] = None,
        no_material_change: bool = False,
    ) -> int:
        """Insert or update a filing record. Returns the filing id."""
        now = datetime.now(tz=timezone.utc).isoformat()
        cursor = self.conn.execute(
            """
            INSERT INTO filings (
                ticker, cik, company_name, form_type, fiscal_year, fiscal_quarter,
                accession_number, filed_as_of_date, sic_code, sic_name, section_id,
                raw_file_path, segmented_json_path, run_dir, total_segments,
                raw_char_count, cleaned_char_count, text_coverage_ratio,
                pipeline_version, processed_at, no_material_change
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker, fiscal_year, form_type, section_id) DO UPDATE SET
                cik=excluded.cik,
                company_name=excluded.company_name,
                fiscal_quarter=excluded.fiscal_quarter,
                accession_number=excluded.accession_number,
                filed_as_of_date=excluded.filed_as_of_date,
                sic_code=excluded.sic_code,
                sic_name=excluded.sic_name,
                raw_file_path=excluded.raw_file_path,
                segmented_json_path=excluded.segmented_json_path,
                run_dir=excluded.run_dir,
                total_segments=excluded.total_segments,
                raw_char_count=excluded.raw_char_count,
                cleaned_char_count=excluded.cleaned_char_count,
                text_coverage_ratio=excluded.text_coverage_ratio,
                pipeline_version=excluded.pipeline_version,
                processed_at=excluded.processed_at,
                no_material_change=excluded.no_material_change
            """,
            (
                ticker.upper(), cik, company_name, form_type, fiscal_year,
                fiscal_quarter, accession_number, filed_as_of_date,
                sic_code, sic_name, section_id, raw_file_path,
                segmented_json_path, run_dir, total_segments,
                raw_char_count, cleaned_char_count, text_coverage_ratio,
                pipeline_version, now, no_material_change,
            ),
        )
        self.conn.commit()
        # Retrieve the id (lastrowid is 0 on UPDATE, so query it)
        row = self.conn.execute(
            "SELECT id FROM filings WHERE ticker=? AND fiscal_year=? AND form_type=? AND section_id=?",
            (ticker.upper(), fiscal_year, form_type, section_id),
        ).fetchone()
        return row["id"]

    def get_filing(
        self,
        ticker: str,
        fiscal_year: str,
        form_type: str = "10-K",
        section_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Look up a single filing record."""
        if section_id:
            row = self.conn.execute(
                "SELECT * FROM filings WHERE ticker=? AND fiscal_year=? AND form_type=? AND section_id=?",
                (ticker.upper(), fiscal_year, form_type, section_id),
            ).fetchone()
        else:
            row = self.conn.execute(
                "SELECT * FROM filings WHERE ticker=? AND fiscal_year=? AND form_type=? LIMIT 1",
                (ticker.upper(), fiscal_year, form_type),
            ).fetchone()
        return dict(row) if row else None

    def get_filing_sections(
        self,
        ticker: str,
        fiscal_year: str,
        form_type: str = "10-K",
    ) -> List[Dict[str, Any]]:
        """Return all section records for a ticker+year+form_type."""
        rows = self.conn.execute(
            "SELECT * FROM filings WHERE ticker=? AND fiscal_year=? AND form_type=? ORDER BY section_id",
            (ticker.upper(), fiscal_year, form_type),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_segmented_json_paths(
        self,
        ticker: str,
        fiscal_year: Optional[str] = None,
        form_type: str = "10-K",
    ) -> List[str]:
        """Return segmented_json_path values for a ticker (and optional year)."""
        if fiscal_year:
            rows = self.conn.execute(
                """SELECT segmented_json_path FROM filings
                   WHERE ticker=? AND fiscal_year=? AND form_type=?
                   AND segmented_json_path IS NOT NULL
                   ORDER BY section_id""",
                (ticker.upper(), fiscal_year, form_type),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """SELECT segmented_json_path FROM filings
                   WHERE ticker=? AND form_type=?
                   AND segmented_json_path IS NOT NULL
                   ORDER BY fiscal_year DESC, section_id""",
                (ticker.upper(), form_type),
            ).fetchall()
        return [r["segmented_json_path"] for r in rows]

    def find_tickers_for_sic(
        self,
        sic_code: str,
        fiscal_year: Optional[str] = None,
    ) -> List[str]:
        """Return distinct tickers matching a SIC code (and optional year)."""
        if fiscal_year:
            rows = self.conn.execute(
                "SELECT DISTINCT ticker FROM filings WHERE sic_code=? AND fiscal_year=? ORDER BY ticker",
                (sic_code, fiscal_year),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT DISTINCT ticker FROM filings WHERE sic_code=? ORDER BY ticker",
                (sic_code,),
            ).fetchall()
        return [r["ticker"] for r in rows]

    def list_filings(
        self,
        form_type: Optional[str] = None,
        classified_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """List all filings, optionally filtered."""
        clauses = []
        params: List[Any] = []
        if form_type:
            clauses.append("form_type=?")
            params.append(form_type)
        if classified_only:
            clauses.append("classified_at IS NOT NULL")
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        rows = self.conn.execute(
            f"SELECT * FROM filings{where} ORDER BY ticker, fiscal_year", params
        ).fetchall()
        return [dict(r) for r in rows]

    def get_unclassified_filings(
        self,
        classifier_version: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return filings needing (re-)classification.

        A filing needs classification when:
          - classifier_version IS NULL (never classified), OR
          - classifier_version != current version (config changed)
        """
        if classifier_version:
            rows = self.conn.execute(
                """SELECT * FROM filings
                   WHERE classifier_version IS NULL
                      OR classifier_version != ?
                   ORDER BY ticker, fiscal_year""",
                (classifier_version,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM filings WHERE classifier_version IS NULL ORDER BY ticker, fiscal_year",
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Classification CRUD
    # ------------------------------------------------------------------

    def store_classifications(
        self,
        filing_id: int,
        classifications: List[Dict[str, Any]],
        classifier_version: str,
        ticker: str,
        fiscal_year: str,
    ) -> int:
        """Store classification results for a filing atomically. Returns count stored."""
        now = datetime.now(tz=timezone.utc).isoformat()
        with self.conn:  # implicit BEGIN / COMMIT / ROLLBACK
            self.conn.execute("DELETE FROM classifications WHERE filing_id=?", (filing_id,))

            for i, cls in enumerate(classifications):
                text = cls.get("text", "")
                self.conn.execute(
                    """INSERT INTO classifications (
                        filing_id, segment_index, chunk_id, text, word_count,
                        char_count, segment_hash,
                        risk_label, sasb_topic, sasb_industry, confidence,
                        label_source, parent_subsection, ticker, fiscal_year
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        filing_id, i,
                        cls.get("chunk_id") or cls.get("segment_id", str(i)),
                        text,
                        cls.get("word_count", 0),
                        cls.get("char_count") or len(text),
                        cls.get("segment_hash"),
                        cls.get("risk_label", "other"),
                        cls.get("sasb_topic"),
                        cls.get("sasb_industry"),
                        cls.get("confidence", 0.0),
                        cls.get("label_source", "heuristic"),
                        cls.get("parent_subsection"),
                        ticker.upper(),
                        fiscal_year,
                    ),
                )

            self.conn.execute(
                "UPDATE filings SET classifier_version=?, classified_at=? WHERE id=?",
                (classifier_version, now, filing_id),
            )
        return len(classifications)

    def get_classifications(
        self,
        ticker: str,
        fiscal_year: str,
        form_type: str = "10-K",
    ) -> List[Dict[str, Any]]:
        """Get all cached classifications for a ticker+year.

        Joins across all section filings for the given ticker+year+form_type.
        """
        rows = self.conn.execute(
            """SELECT c.* FROM classifications c
               JOIN filings f ON c.filing_id = f.id
               WHERE f.ticker=? AND f.fiscal_year=? AND f.form_type=?
               ORDER BY c.filing_id, c.segment_index""",
            (ticker.upper(), fiscal_year, form_type),
        ).fetchall()
        return [dict(r) for r in rows]

    def has_classifications(
        self,
        ticker: str,
        fiscal_year: str,
        classifier_version: Optional[str] = None,
        form_type: str = "10-K",
    ) -> bool:
        """Check if valid cached classifications exist."""
        if classifier_version:
            row = self.conn.execute(
                """SELECT COUNT(*) as cnt FROM classifications c
                   JOIN filings f ON c.filing_id = f.id
                   WHERE f.ticker=? AND f.fiscal_year=? AND f.form_type=?
                     AND f.classifier_version=?""",
                (ticker.upper(), fiscal_year, form_type, classifier_version),
            ).fetchone()
        else:
            row = self.conn.execute(
                """SELECT COUNT(*) as cnt FROM classifications c
                   JOIN filings f ON c.filing_id = f.id
                   WHERE f.ticker=? AND f.fiscal_year=? AND f.form_type=?
                     AND f.classified_at IS NOT NULL""",
                (ticker.upper(), fiscal_year, form_type),
            ).fetchone()
        return row["cnt"] > 0

    # ------------------------------------------------------------------
    # Risk scores
    # ------------------------------------------------------------------

    def store_risk_score(
        self,
        filing_id: int,
        ticker: str,
        fiscal_year: str,
        form_type: str,
        score: int,
        dominant_archetype: Optional[str] = None,
        label_distribution: Optional[Dict[str, int]] = None,
    ) -> None:
        """Store or update a risk score for a filing."""
        now = datetime.now(tz=timezone.utc).isoformat()
        dist_json = json.dumps(label_distribution) if label_distribution else None
        self.conn.execute(
            """INSERT INTO risk_scores (
                filing_id, ticker, fiscal_year, form_type,
                score, dominant_archetype, label_distribution, computed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(filing_id) DO UPDATE SET
                score=excluded.score,
                dominant_archetype=excluded.dominant_archetype,
                label_distribution=excluded.label_distribution,
                computed_at=excluded.computed_at
            """,
            (filing_id, ticker.upper(), fiscal_year, form_type,
             score, dominant_archetype, dist_json, now),
        )
        self.conn.commit()

    def get_risk_score(
        self,
        ticker: str,
        fiscal_year: str,
        form_type: str = "10-K",
    ) -> Optional[Dict[str, Any]]:
        """Get the cached risk score for a ticker+year."""
        row = self.conn.execute(
            "SELECT * FROM risk_scores WHERE ticker=? AND fiscal_year=? AND form_type=?",
            (ticker.upper(), fiscal_year, form_type),
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        if result.get("label_distribution"):
            result["label_distribution"] = json.loads(result["label_distribution"])
        return result

    # ------------------------------------------------------------------
    # Backfill from JSON run directories
    # ------------------------------------------------------------------

    def backfill_from_run_dir(self, run_dir: Path) -> Tuple[int, int]:
        """Import all *_segmented.json files from a run directory into the DB.

        This is the reconstruction path: if the DB is deleted, this rebuilds
        it from the authoritative stamped run directories (ADR-007).

        Returns:
            (imported, skipped) — count of records upserted and files skipped.
        """
        run_dir = Path(run_dir)
        if not run_dir.is_dir():
            raise FileNotFoundError(f"Run directory not found: {run_dir}")

        # Extract pipeline_version from directory name (git SHA)
        pipeline_version = _extract_pipeline_version(run_dir.name)

        count = 0
        skipped = 0
        for json_path in sorted(run_dir.rglob("*_segmented.json")):
            try:
                result = self._import_segmented_json(json_path, run_dir, pipeline_version)
                if result == 0:
                    skipped += 1
                else:
                    count += result
            except Exception as exc:
                logger.warning("Failed to import %s: %s", json_path, exc)
                skipped += 1
                continue

        logger.info(
            "backfill_from_run_dir: imported %d filing records (%d skipped) from %s",
            count, skipped, run_dir,
        )
        return count, skipped

    def _import_segmented_json(
        self,
        json_path: Path,
        run_dir: Path,
        pipeline_version: Optional[str],
    ) -> int:
        """Import a single segmented JSON file into the filings table."""
        with open(json_path, encoding="utf-8") as fh:
            data = json.load(fh)

        # Validate filing quality before import
        from src.validation.quality_gates import validate_filing

        validation = validate_filing(data)
        if not validation.is_valid:
            logger.warning(
                "Skipping %s: %s", json_path.name, validation.blocking_failures
            )
            return 0

        # Extract document_info (handles both schema versions)
        if "document_info" in data:
            di = data["document_info"]
            sm = data.get("section_metadata", {})
            stats = sm.get("stats", {})
            chunks = data.get("chunks") or data.get("segments", [])
        else:
            di = data
            sm = {}
            stats = {}
            chunks = data.get("segments", [])

        ticker = di.get("ticker")
        fiscal_year = di.get("fiscal_year")
        form_type = di.get("form_type", "10-K")

        section_id = sm.get("identifier") or _infer_section_id(json_path.name)
        if not section_id:
            section_id = "unknown"

        # Extract text_coverage_ratio from stats
        text_coverage = stats.get("text_coverage")
        coverage_ratio = None
        if isinstance(text_coverage, dict):
            coverage_ratio = text_coverage.get("coverage_ratio")

        self.upsert_filing(
            ticker=ticker,
            fiscal_year=fiscal_year,
            form_type=form_type,
            section_id=section_id,
            cik=di.get("cik"),
            company_name=di.get("company_name"),
            accession_number=di.get("accession_number"),
            filed_as_of_date=di.get("filed_as_of_date"),
            sic_code=di.get("sic_code"),
            sic_name=di.get("sic_name"),
            segmented_json_path=str(json_path),
            run_dir=str(run_dir),
            total_segments=stats.get("total_chunks") or len(chunks),
            raw_char_count=stats.get("raw_section_char_count"),
            cleaned_char_count=stats.get("cleaned_section_char_count"),
            text_coverage_ratio=coverage_ratio,
            pipeline_version=pipeline_version,
            no_material_change=sm.get("no_material_change", False),
        )
        return 1

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_statistics(self) -> Dict[str, Any]:
        """Return summary statistics about the database contents."""
        stats: Dict[str, Any] = {}

        row = self.conn.execute("SELECT COUNT(*) as cnt FROM filings").fetchone()
        stats["total_filings"] = row["cnt"]

        row = self.conn.execute(
            "SELECT COUNT(DISTINCT ticker) as cnt FROM filings"
        ).fetchone()
        stats["unique_tickers"] = row["cnt"]

        row = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM filings WHERE classified_at IS NOT NULL"
        ).fetchone()
        stats["classified_filings"] = row["cnt"]

        row = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM filings WHERE classified_at IS NULL"
        ).fetchone()
        stats["unclassified_filings"] = row["cnt"]

        row = self.conn.execute("SELECT COUNT(*) as cnt FROM classifications").fetchone()
        stats["total_classifications"] = row["cnt"]

        row = self.conn.execute("SELECT COUNT(*) as cnt FROM risk_scores").fetchone()
        stats["total_risk_scores"] = row["cnt"]

        # Breakdown by form_type
        rows = self.conn.execute(
            "SELECT form_type, COUNT(*) as cnt FROM filings GROUP BY form_type"
        ).fetchall()
        stats["by_form_type"] = {r["form_type"]: r["cnt"] for r in rows}

        # Fiscal year range
        row = self.conn.execute(
            "SELECT MIN(fiscal_year) as min_yr, MAX(fiscal_year) as max_yr FROM filings"
        ).fetchone()
        stats["fiscal_year_range"] = (row["min_yr"], row["max_yr"]) if row["min_yr"] else None

        return stats

    def search_tickers(self, query: str) -> List[Dict[str, str]]:
        """Search for tickers or company names matching a query string."""
        rows = self.conn.execute(
            """SELECT DISTINCT ticker, company_name FROM filings
               WHERE ticker LIKE ? OR company_name LIKE ?
               ORDER BY ticker LIMIT 50""",
            (f"%{query.upper()}%", f"%{query}%"),
        ).fetchall()
        return [{"ticker": r["ticker"], "company_name": r["company_name"]} for r in rows]


# ---------------------------------------------------------------------------
# Connection singleton
# ---------------------------------------------------------------------------

_DB_INSTANCE: Optional[FilingDatabase] = None


def get_database(db_path: Optional[Path] = None) -> FilingDatabase:
    """Return a shared FilingDatabase instance (singleton).

    If *db_path* is None, the default path from AnalysisConfig is used.
    If the singleton exists but points to a different path, it is replaced.
    """
    global _DB_INSTANCE

    if db_path is None:
        from src.config.analysis import AnalysisConfig
        db_path = AnalysisConfig().db_path

    if _DB_INSTANCE is not None and _DB_INSTANCE._db_path == Path(db_path):
        return _DB_INSTANCE

    # Close existing if path changed
    if _DB_INSTANCE is not None:
        _DB_INSTANCE.close()

    _DB_INSTANCE = FilingDatabase(db_path)
    _DB_INSTANCE.connect()
    return _DB_INSTANCE


def close_database() -> None:
    """Close and discard the singleton database instance."""
    global _DB_INSTANCE
    if _DB_INSTANCE is not None:
        _DB_INSTANCE.close()
        _DB_INSTANCE = None


def classify_and_store(
    db: FilingDatabase,
    filing: Dict[str, Any],
    annotator: Any,
    classifier_version: str,
) -> int:
    """Classify a single filing and store results. Returns segment count.

    Encapsulates: load JSON → annotate → store_classifications → score_risk → store_risk_score.
    Raises on error (caller decides how to handle).
    """
    from src.preprocessing.models.segmentation import SegmentedRisks
    from src.analysis.models.analysis import ClassificationResult
    from src.analysis.skills.scorer import score_risk

    json_path = filing.get("segmented_json_path")
    if not json_path or not Path(json_path).exists():
        raise FileNotFoundError(f"Missing JSON at {json_path}")

    # Validate filing quality before classification
    from src.validation.quality_gates import validate_filing

    filing_data = json.loads(Path(json_path).read_text(encoding="utf-8"))
    validation = validate_filing(filing_data)
    if not validation.is_valid:
        raise ValueError(f"Validation failed: {validation.blocking_failures}")

    segmented = SegmentedRisks.load_from_json(json_path)
    records = annotator.annotate(segmented)

    db.store_classifications(
        filing_id=filing["id"],
        classifications=records,
        classifier_version=classifier_version,
        ticker=filing["ticker"],
        fiscal_year=filing["fiscal_year"],
    )

    # Compute and store risk score
    cls_results = [
        ClassificationResult(
            segment_id=str(rec.get("index", i)),
            text=rec.get("text", ""),
            risk_label=rec.get("risk_label", "other"),
            sasb_topic=rec.get("sasb_topic"),
            sasb_industry=rec.get("sasb_industry"),
            confidence=float(rec.get("confidence", 0.0)),
            label_source=rec.get("label_source", "heuristic"),
            word_count=int(rec.get("word_count", 0)),
        )
        for i, rec in enumerate(records)
    ]

    if cls_results:
        risk = score_risk(cls_results)
        db.store_risk_score(
            filing_id=filing["id"],
            ticker=filing["ticker"],
            fiscal_year=filing["fiscal_year"],
            form_type=filing["form_type"],
            score=risk.score,
            dominant_archetype=risk.dominant_archetype,
            label_distribution=risk.label_distribution,
        )

    return len(records)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _extract_pipeline_version(dir_name: str) -> Optional[str]:
    """Extract the git SHA from a stamped run directory name.

    Format: YYYYMMDD_HHMMSS_preprocessing_<sha>
    """
    parts = dir_name.split("_")
    if len(parts) >= 4:
        return parts[-1]
    return None


def _infer_section_id(filename: str) -> Optional[str]:
    """Infer section_id from a segmented JSON filename.

    Examples:
        AAPL_10K_2024_part1item1a_segmented.json → part1item1a
        AAPL_10K_2024_part2item7_segmented.json  → part2item7
    """
    # Remove _segmented.json suffix
    stem = filename.replace("_segmented.json", "").replace("_segmented_risks.json", "")
    # Section identifiers follow patterns like part1item1a, part2item7
    import re
    match = re.search(r"(part\d+item\d+[a-z]?)", stem, re.IGNORECASE)
    if match:
        return match.group(1).lower()
    return None

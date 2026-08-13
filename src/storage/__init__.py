"""Storage layer — SQLite-backed filing database for pre-computed results (ADR-017).

Provides O(1) filing lookup, cached classifications, and pre-computed risk scores.
The database supplements (does not replace) stamped run directories (ADR-007).
"""

from src.storage.database import FilingDatabase

__all__ = ["FilingDatabase"]

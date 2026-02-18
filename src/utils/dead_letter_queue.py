"""Unified Dead Letter Queue for tracking failed batch-processing files.

Replaces duplicated ``_write_dead_letter_queue()`` implementations in:
- ``src/utils/parallel.py``
- ``scripts/data_preprocessing/run_preprocessing_pipeline.py``

The DLQ is a JSON file (default ``logs/failed_files.json``) that accumulates
records of files that timed out or raised exceptions during batch processing.
The retry script (``scripts/utils/retry_failed_files.py``) reads this file to
drive re-processing with increased resources.

Usage:
    from src.utils.dead_letter_queue import DeadLetterQueue

    dlq = DeadLetterQueue()

    # After a batch run
    if failed_items:
        dlq.add_failures(failed_items, script_name="pipeline.py")

    # Inspect
    failures = dlq.load()
    print(f"{len(failures)} files pending retry")

    # After a successful retry run
    dlq.remove_successes(["/path/to/file.html"])
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, List, Dict, Union

logger = logging.getLogger(__name__)


class DeadLetterQueue:
    """
    Persistent JSON-backed store for files that failed batch processing.

    Thread/process safety: reads and writes the JSON file atomically via
    a read-modify-write cycle. Suitable for use from the main process only
    (the ``ParallelProcessor`` calls it after the executor shuts down).

    Args:
        log_path: Path to the DLQ JSON file. Created on first write if it
            does not exist. Default: ``logs/failed_files.json``.

    Record schema:
        {
            "file": "/abs/path/to/filing.html",
            "timestamp": "2026-02-17T12:34:56.789012",
            "reason": "timeout_or_exception",
            "script": "pipeline.py",
            "attempt_count": 1
        }
    """

    def __init__(self, log_path: Union[str, Path] = Path("logs/failed_files.json")):
        self.log_path = Path(log_path)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def add_failures(
        self,
        failed_items: List[Any],
        script_name: str = "",
        reason: str = "timeout_or_exception",
    ) -> None:
        """
        Append *failed_items* to the DLQ.

        Accepts heterogeneous item types (Path, str, tuple) — extracts the
        file path from the first element when the item is a tuple (the
        format used by ``ParallelProcessor``'s worker args).

        Args:
            failed_items: Items that failed — may be ``Path``, ``str``, or
                ``tuple`` whose first element is the file path.
            script_name: Human-readable name of the calling script.
            reason: Short failure reason (``"timeout"``, ``"exception"``, …).
        """
        if not failed_items:
            return

        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        existing = self.load()

        timestamp = datetime.now().isoformat()
        for item in failed_items:
            file_path = self._extract_path(item)
            existing.append({
                "file": file_path,
                "timestamp": timestamp,
                "reason": reason,
                "script": script_name,
                "attempt_count": 1,
            })

        self._save(existing)
        logger.info(
            "DeadLetterQueue: wrote %d failure(s) to %s",
            len(failed_items), self.log_path,
        )

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def load(self) -> List[Dict[str, Any]]:
        """
        Load all failure records from the DLQ file.

        Returns:
            List of failure record dicts. Empty list if file does not exist
            or is corrupt.
        """
        if not self.log_path.exists():
            return []
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            logger.warning("Could not read DLQ %s, treating as empty", self.log_path)
            return []

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def remove_successes(self, successful_files: List[str]) -> int:
        """
        Remove entries for files that were successfully retried.

        Also increments ``attempt_count`` on remaining failures so the retry
        script can respect ``--max-attempts``.

        Args:
            successful_files: List of file-path strings that succeeded.

        Returns:
            Number of records removed.
        """
        failures = self.load()
        success_set = set(successful_files)

        remaining = [f for f in failures if f["file"] not in success_set]
        removed = len(failures) - len(remaining)

        for record in remaining:
            record["attempt_count"] = record.get("attempt_count", 1) + 1
            record["last_retry"] = datetime.now().isoformat()

        self._save(remaining)
        logger.info(
            "DeadLetterQueue: removed %d success(es), %d still pending",
            removed, len(remaining),
        )
        return removed

    def clear(self) -> None:
        """Delete all records from the DLQ."""
        self._save([])
        logger.info("DeadLetterQueue: cleared %s", self.log_path)

    def __len__(self) -> int:
        return len(self.load())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _save(self, records: List[Dict[str, Any]]) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)

    @staticmethod
    def _extract_path(item: Any) -> str:
        """Normalise a worker-args item to a file-path string."""
        if isinstance(item, Path):
            return str(item)
        if isinstance(item, str):
            return item
        if isinstance(item, tuple) and len(item) > 0:
            return str(item[0])
        return str(item)

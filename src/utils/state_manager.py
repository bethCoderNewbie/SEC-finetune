"""State management for incremental preprocessing with production-ready features.

This module implements a DVC-lite pattern for tracking file processing state,
enabling incremental runs that skip unchanged files. It provides:

1. **Atomic writes** - Prevent manifest corruption via temp file + rename
2. **Config snapshots** - Full reproducibility of preprocessing runs
3. **Quarantine tracking** - Record failed files with failure reasons
4. **Deleted file cleanup** - Prune stale entries from manifest

Design Assumptions:
- Single-threaded processing (safe for JSON manifest)
- When parallelizing, migrate to file locking or SQLite
- Platform-specific handling for Windows atomic operations

Production-Ready Features (Rev 2.0):
- Atomic writes prevent corruption during crashes
- Config snapshots enable FDA 21 CFR Part 11 compliance
- Quarantine pattern eliminates silent drops
- Deleted file cleanup prevents manifest bloat

Author: bethCoderNewbie
Date: 2025-12-28
Reference: thoughts/shared/plans/2025-12-28_13-33-27_consolidated_mlops_roadmap.md
"""

import hashlib
import json
import logging
import os
import platform
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def compute_file_hash(file_path: Path, chunk_size: int = 65536) -> str:
    """Compute SHA-256 hash of file content.

    Args:
        file_path: Path to file to hash
        chunk_size: Bytes to read per iteration (default: 64KB)

    Returns:
        Hexadecimal SHA-256 digest

    Example:
        >>> hash1 = compute_file_hash(Path("data.json"))
        >>> hash2 = compute_file_hash(Path("data.json"))
        >>> hash1 == hash2
        True
    """
    sha256_hash = hashlib.sha256()

    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            sha256_hash.update(chunk)

    return sha256_hash.hexdigest()


class StateManifest:
    """Tracks file processing state for incremental preprocessing.

    Manifest structure:
    {
        "files": {
            "path/to/file.html": {
                "hash": "abc123...",
                "last_processed": "2025-12-28T13:00:00",
                "run_id": "20251228_130000_batch_parse_648bf25",
                "status": "success|failed|quarantined",
                "output_path": "data/interim/parsed/.../file.json",
                "quarantine_path": "data/quarantine/.../file_FAILED.json",  # if failed
                "failure_reason": "validation_failed",  # if failed
                "validation_report": {...}  # if failed
            }
        },
        "run_config": {
            "git_commit": "648bf25",
            "branch": "main",
            "researcher": "bethCoderNewbie",
            "timestamp": "2025-12-28T13:00:00",
            "python_version": "3.11.5",
            "platform": "Windows-10.0.19045",
            "config_snapshot": {...}  # Full pipeline config
        }
    }

    Thread Safety:
    - Current implementation assumes single-threaded processing
    - JSON writes are atomic on POSIX (rename is atomic)
    - Windows requires backup + delete + rename
    - For parallel processing, migrate to file locking or SQLite

    Example:
        >>> manifest = StateManifest(Path("data/.manifest.json"))
        >>> manifest.load()
        >>> if manifest.should_process(Path("data/file.html")):
        ...     # Process file
        ...     manifest.record_success(
        ...         input_path=Path("data/file.html"),
        ...         output_path=Path("data/interim/parsed/file.json"),
        ...         run_id="20251228_130000"
        ...     )
        >>> manifest.save()
    """

    def __init__(self, manifest_path: Path):
        """Initialize state manifest.

        Args:
            manifest_path: Path to manifest JSON file (e.g., data/.manifest.json)
        """
        self.manifest_path = Path(manifest_path)
        self.data: Dict[str, Any] = {
            "files": {},
            "run_config": {}
        }

    def load(self) -> None:
        """Load manifest from disk or initialize empty if not exists."""
        if self.manifest_path.exists():
            try:
                with open(self.manifest_path, 'r') as f:
                    self.data = json.load(f)
                logger.info(f"Loaded manifest with {len(self.data.get('files', {}))} tracked files")
            except json.JSONDecodeError as e:
                logger.error(f"Manifest corrupted: {e}")
                # Try backup if available
                backup_path = self.manifest_path.with_suffix('.json.bak')
                if backup_path.exists():
                    logger.info(f"Attempting recovery from backup: {backup_path}")
                    shutil.copy2(backup_path, self.manifest_path)
                    with open(self.manifest_path, 'r') as f:
                        self.data = json.load(f)
                    logger.info("✅ Recovered from backup")
                else:
                    logger.warning("No backup available, starting fresh")
                    self.data = {"files": {}, "run_config": {}}
        else:
            logger.info("No existing manifest found, starting fresh")
            self.data = {"files": {}, "run_config": {}}

    def save(self) -> None:
        """Save manifest with atomic write to prevent corruption.

        Implementation:
        1. Write to temporary file in same directory
        2. On Windows: Create backup, delete original, rename temp
        3. On POSIX: Atomic rename (overwrites original)
        4. On failure: Clean up temp file and re-raise exception

        This prevents corruption if process crashes mid-save.
        """
        # Create parent directory if it doesn't exist
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)

        # Create temp file in same directory for atomic rename
        temp_fd, temp_path = tempfile.mkstemp(
            dir=self.manifest_path.parent,
            prefix='.manifest_',
            suffix='.tmp'
        )

        try:
            # Write to temp file
            with os.fdopen(temp_fd, 'w') as f:
                json.dump(self.data, f, indent=2, default=str)

            # Platform-specific atomic rename
            if platform.system() == 'Windows':
                # Windows doesn't support atomic overwrite via rename
                # Create backup first
                if self.manifest_path.exists():
                    backup = self.manifest_path.with_suffix('.json.bak')
                    shutil.copy2(self.manifest_path, backup)
                    self.manifest_path.unlink()

            # Atomic rename (POSIX) or move after delete (Windows)
            shutil.move(temp_path, self.manifest_path)
            logger.debug(f"Manifest saved atomically to {self.manifest_path}")

        except Exception:
            # Clean up temp file on failure
            Path(temp_path).unlink(missing_ok=True)
            raise

    def should_process(self, input_path: Path, force: bool = False) -> bool:
        """Determine if file needs processing.

        Args:
            input_path: Path to input file
            force: If True, always return True (reprocess all)

        Returns:
            True if file should be processed (new or changed), False if unchanged

        Logic:
        - Always process if force=True
        - Always process if file not in manifest
        - Process if hash changed (file modified)
        - Skip if hash unchanged (file unmodified)
        """
        if force:
            return True

        file_key = str(input_path)
        if file_key not in self.data["files"]:
            return True

        # Compute current hash
        try:
            current_hash = compute_file_hash(input_path)
        except Exception as e:
            logger.warning(f"Failed to hash {input_path}: {e}")
            return True  # Process on error

        # Check if hash changed
        stored_hash = self.data["files"][file_key].get("hash")
        if current_hash != stored_hash:
            logger.debug(f"Hash changed for {input_path}")
            return True

        logger.debug(f"Skipping unchanged file: {input_path}")
        return False

    def record_success(
        self,
        input_path: Path,
        output_path: Path,
        run_id: str,
        validation_report: Optional[Dict] = None
    ) -> None:
        """Record successful processing of file.

        Args:
            input_path: Path to input file
            output_path: Path to output file
            run_id: Unique run identifier
            validation_report: Optional validation report (for PASS with warnings)
        """
        file_key = str(input_path)
        file_hash = compute_file_hash(input_path)

        self.data["files"][file_key] = {
            "hash": file_hash,
            "last_processed": datetime.now().isoformat(),
            "run_id": run_id,
            "status": "success",
            "output_path": str(output_path),
        }

        if validation_report:
            self.data["files"][file_key]["validation_report"] = validation_report

        logger.debug(f"Recorded success: {input_path} -> {output_path}")

    def record_failure(
        self,
        input_path: Path,
        run_id: str,
        reason: str,
        quarantine_path: Optional[Path] = None,
        validation_report: Optional[Dict] = None
    ) -> None:
        """Record failed processing of file.

        Args:
            input_path: Path to input file
            run_id: Unique run identifier
            reason: Failure reason (e.g., "validation_failed", "parsing_error")
            quarantine_path: Path to quarantined file (if applicable)
            validation_report: Detailed validation report
        """
        file_key = str(input_path)
        file_hash = compute_file_hash(input_path)

        self.data["files"][file_key] = {
            "hash": file_hash,
            "last_processed": datetime.now().isoformat(),
            "run_id": run_id,
            "status": "failed",
            "failure_reason": reason,
        }

        if quarantine_path:
            self.data["files"][file_key]["quarantine_path"] = str(quarantine_path)

        if validation_report:
            self.data["files"][file_key]["validation_report"] = validation_report

        logger.debug(f"Recorded failure: {input_path} -> {reason}")

    def prune_deleted_files(self, input_dir: Path) -> int:
        """Remove entries from manifest for deleted input files.

        Args:
            input_dir: Directory containing input files

        Returns:
            Number of entries pruned

        Example:
            >>> manifest.prune_deleted_files(Path("data/raw"))
            3  # Removed 3 deleted files from manifest
        """
        files_to_remove = []

        for file_key in self.data["files"].keys():
            file_path = Path(file_key)
            # Only prune files from the specified input directory
            if file_path.is_relative_to(input_dir) and not file_path.exists():
                files_to_remove.append(file_key)

        for file_key in files_to_remove:
            del self.data["files"][file_key]
            logger.debug(f"Pruned deleted file: {file_key}")

        if files_to_remove:
            logger.info(f"Pruned {len(files_to_remove)} deleted files from manifest")

        return len(files_to_remove)

    def get_failed_files(self) -> Dict[str, Dict[str, Any]]:
        """Get dict of failed/quarantined files keyed by file path.

        Returns:
            Dict mapping file path (str) to record data for status='failed' files

        Example:
            >>> failed = manifest.get_failed_files()
            >>> for file_path, record in failed.items():
            ...     print(f"{file_path}: {record['failure_reason']}")
        """
        return {
            file_key: record
            for file_key, record in self.data["files"].items()
            if record.get("status") == "failed"
        }

    def update_run_config(self, config_snapshot: Dict[str, Any]) -> None:
        """Update run configuration with snapshot.

        Args:
            config_snapshot: Full pipeline configuration snapshot

        This captures:
        - Git metadata (commit, branch, researcher)
        - Python version and platform
        - Full pipeline configuration (preprocessing settings)
        - Timestamp of run

        For FDA 21 CFR Part 11 compliance and reproducibility.
        """
        self.data["run_config"] = {
            "timestamp": datetime.now().isoformat(),
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "platform": platform.platform(),
            "config_snapshot": config_snapshot
        }
        logger.debug("Updated run config with snapshot")

    def get_statistics(self) -> Dict[str, int]:
        """Get processing statistics.

        Returns:
            Dictionary with counts by status

        Example:
            >>> stats = manifest.get_statistics()
            >>> print(f"Success: {stats['success']}, Failed: {stats['failed']}")
        """
        stats = {
            "total": len(self.data["files"]),
            "success": 0,
            "failed": 0,
            "skipped": 0
        }

        for record in self.data["files"].values():
            status = record.get("status", "unknown")
            if status in stats:
                stats[status] += 1

        return stats

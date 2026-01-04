"""Checkpoint management for batch processing with crash recovery."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


class CheckpointManager:
    """
    Manages checkpoint save/load for crash recovery in batch processing.

    Maintains exact checkpoint format compatibility with existing batch scripts:
    {
        "processed_files": [...],
        "results": [...],
        "metrics": {...},
        "timestamp": "2025-12-27T14:30:00.123456"
    }

    Usage:
        checkpoint = CheckpointManager(run_dir / "_validation_checkpoint.json")

        # Save checkpoint periodically
        checkpoint.save(processed_files, results, metrics)

        # Resume from checkpoint
        if resume and checkpoint.exists():
            processed_set, results, metrics = checkpoint.load()

        # Cleanup after success
        checkpoint.cleanup()
    """

    def __init__(self, checkpoint_path: Path):
        """
        Initialize checkpoint manager.

        Args:
            checkpoint_path: Path to checkpoint file (e.g., run_dir / "_checkpoint.json")
        """
        self.checkpoint_path = checkpoint_path

    def save(
        self,
        processed_files: List[str],
        results: List[Dict],
        metrics: Dict[str, Any]
    ) -> None:
        """
        Save checkpoint for crash recovery.

        Preserves exact format from existing scripts for compatibility.

        Args:
            processed_files: List of filenames already processed
            results: List of validation results
            metrics: Current metrics dict
        """
        checkpoint_data = {
            "processed_files": processed_files,
            "results": results,
            "metrics": metrics,
            "timestamp": datetime.now().isoformat()
        }

        with open(self.checkpoint_path, 'w', encoding='utf-8') as f:
            json.dump(checkpoint_data, f, indent=2, default=str)

    def load(self) -> Tuple[Set[str], List[Dict], Dict]:
        """
        Load checkpoint data for resume.

        Returns:
            Tuple of (processed_files_set, results_list, metrics_dict)
            - processed_files_set: Set of filenames for fast lookup
            - results_list: List of validation results
            - metrics_dict: Metrics dictionary

        Note: Returns empty values if checkpoint doesn't exist
        """
        if not self.checkpoint_path.exists():
            return set(), [], {}

        with open(self.checkpoint_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return (
                set(data.get('processed_files', [])),
                data.get('results', []),
                data.get('metrics', {})
            )

    def cleanup(self) -> None:
        """Remove checkpoint file after successful completion."""
        if self.checkpoint_path.exists():
            self.checkpoint_path.unlink()

    def exists(self) -> bool:
        """Check if checkpoint file exists."""
        return self.checkpoint_path.exists()

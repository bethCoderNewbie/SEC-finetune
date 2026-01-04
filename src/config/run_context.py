"""Run context and versioning management."""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from src.config import settings


def _get_current_git_sha() -> Optional[str]:
    """Get the current git SHA (short form)."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL
        ).decode().strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


class RunContext(BaseSettings):
    """
    Manages versioning and output paths for data processing runs.
    Ensures all artifacts from a run are saved together.

    Pydantic V2 compliant model with computed properties.

    Usage:
        # Basic usage
        run = RunContext(name="auto_label_bart")
        run.create()
        output_path = run.output_dir  # e.g., data/processed/labeled/20231201_143022_auto_label_bart/
        run.save_config({"model": "bart-large-mnli"})

        # With Git SHA for strict versioning
        run = RunContext(name="experiment", git_sha="ea45dd2")
        run.create()
        output_path = run.output_dir  # e.g., data/processed/labeled/20231201_143022_experiment_ea45dd2/

        # Save metrics
        run.save_metrics({"accuracy": 0.87, "f1_score": 0.84})
    """
    model_config = SettingsConfigDict(
        arbitrary_types_allowed=True,
        validate_default=True
    )

    name: str = Field(..., description="Name identifier for this run")
    base_dir: Optional[Path] = Field(
        default=None,
        description="Base directory for run outputs. Defaults to labeled_data_dir"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp for this run"
    )
    git_sha: Optional[str] = Field(
        default=None,
        description="Git SHA to include in output path for data-code linkage"
    )
    auto_git_sha: bool = Field(
        default=False,
        description="Automatically capture current git SHA if git_sha not provided"
    )
    capture_config: bool = Field(
        default=True,
        description="Capture full config snapshot for reproducibility (FDA 21 CFR Part 11 compliance)"
    )
    config_snapshot: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Full configuration snapshot for this run"
    )

    def model_post_init(self, __context) -> None:
        """Set default base_dir and optionally capture git SHA."""
        if self.base_dir is None:
            # Import here to avoid circular dependency
            from src.config import settings
            object.__setattr__(self, 'base_dir', settings.paths.labeled_data_dir)

        # Auto-capture git SHA if requested
        if self.auto_git_sha and self.git_sha is None:
            sha = _get_current_git_sha()
            if sha:
                object.__setattr__(self, 'git_sha', sha)

        # Capture config snapshot if requested
        if self.capture_config and self.config_snapshot is None:
            snapshot = self._capture_config_snapshot()
            object.__setattr__(self, 'config_snapshot', snapshot)

    def _capture_config_snapshot(self) -> Dict[str, Any]:
        """Capture full configuration snapshot for reproducibility.

        Captures:
        - Git metadata (commit, branch, researcher)
        - Python version and platform
        - Full pipeline configuration
        - Timestamp

        For FDA 21 CFR Part 11 compliance and reproducibility.
        """
        import platform
        import sys
        from src.config import settings

        # Get git branch
        git_branch = None
        try:
            git_branch = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                stderr=subprocess.DEVNULL
            ).decode().strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        # Get researcher/user (from git config)
        researcher = None
        try:
            researcher = subprocess.check_output(
                ["git", "config", "user.name"],
                stderr=subprocess.DEVNULL
            ).decode().strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        snapshot = {
            "git_commit": self.git_sha or _get_current_git_sha(),
            "git_branch": git_branch,
            "researcher": researcher,
            "timestamp": self.timestamp.isoformat(),
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "platform": platform.platform(),
            "config": settings.model_dump() if hasattr(settings, 'model_dump') else {}
        }

        return snapshot

    @property
    def run_id(self) -> str:
        """Generate run ID from timestamp using naming config format."""
        from src.config import settings
        return self.timestamp.strftime(settings.naming.timestamp_format)

    @property
    def output_dir(self) -> Path:
        """
        Construct unique output directory path using naming config patterns.

        If git_sha is provided, includes it in the path for data-code linkage:
        - Without git_sha: {base_dir}/{run_id}_{name}/
        - With git_sha: {base_dir}/{run_id}_{name}_{git_sha}/
        """
        from src.config import settings
        folder_name = settings.naming.format_folder(
            run_id=self.run_id,
            name=self.name,
            git_sha=self.git_sha
        )
        return self.base_dir / folder_name

    def create(self) -> "RunContext":
        """Create the run directory."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        return self

    def save_config(self, config: Dict) -> Path:
        """
        Save the configuration used for this run.

        Returns:
            Path to the saved config file
        """
        self.create()
        config_path = self.output_dir / "run_config.yaml"
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False)
        return config_path

    def save_metrics(self, metrics: Dict[str, Any]) -> Path:
        """
        Save metrics from this run to a JSON file.

        Args:
            metrics: Dictionary of metric names to values
                     (e.g., {"accuracy": 0.87, "f1_score": 0.84})

        Returns:
            Path to the saved metrics file

        Example:
            run.save_metrics({
                "accuracy": 0.87,
                "f1_score": 0.84,
                "precision": 0.85,
                "recall": 0.83,
                "loss": 0.23
            })
        """
        self.create()
        metrics_path = self.output_dir / "metrics.json"

        # Add metadata to metrics
        metrics_with_metadata = {
            "run_id": self.run_id,
            "name": self.name,
            "git_sha": self.git_sha,
            "timestamp": self.timestamp.isoformat(),
            "metrics": metrics
        }

        with open(metrics_path, 'w', encoding='utf-8') as f:
            json.dump(metrics_with_metadata, f, indent=2, default=str)
        return metrics_path

    def load_metrics(self) -> Optional[Dict[str, Any]]:
        """
        Load metrics from this run.

        Returns:
            Dictionary with metrics and metadata, or None if not found
        """
        metrics_path = self.output_dir / "metrics.json"
        if not metrics_path.exists():
            return None

        with open(metrics_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def get_artifact_path(self, artifact_name: str) -> Path:
        """
        Get path for an artifact within this run's directory.

        Args:
            artifact_name: Name of the artifact (e.g., "model.pt", "predictions.json")

        Returns:
            Full path to the artifact
        """
        return self.output_dir / artifact_name

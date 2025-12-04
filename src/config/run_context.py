"""Run context and versioning management."""

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from src.config import settings


class RunContext(BaseSettings):
    """
    Manages versioning and output paths for data processing runs.
    Ensures all artifacts from a run are saved together.

    Pydantic V2 compliant model with computed properties.

    Usage:
        run = RunContext(name="auto_label_bart")
        run.create()
        output_path = run.output_dir  # e.g., data/processed/labeled/20231201_143022_auto_label_bart/
        run.save_config({"model": "bart-large-mnli"})
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

    def model_post_init(self, __context) -> None:
        """Set default base_dir after settings are available."""
        if self.base_dir is None:
            # Import here to avoid circular dependency
            from src.config import settings
            object.__setattr__(self, 'base_dir', settings.paths.labeled_data_dir)

    @property
    def run_id(self) -> str:
        """Generate run ID from timestamp."""
        return self.timestamp.strftime("%Y%m%d_%H%M%S")

    @property
    def output_dir(self) -> Path:
        """Construct unique output directory path."""
        return self.base_dir / f"{self.run_id}_{self.name}"

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
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        return config_path

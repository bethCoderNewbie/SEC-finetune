"""Centralized naming convention configuration."""

from typing import Dict
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class NamingConfig(BaseSettings):
    """
    Configuration for file and folder naming patterns.

    Patterns support these placeholders:
    - {run_id}: Timestamp in YYYYMMDD_HHMMSS format
    - {name}: User-provided run name
    - {git_sha}: Git commit SHA (optional)
    - {stem}: Original input file stem
    - {output_type}: Processing stage identifier

    Usage:
        from src.config import settings

        # Format a folder name
        folder = settings.naming.format_folder("20251212_200149", "batch_parse", "ea45dd2")
        # -> "20251212_200149_batch_parse_ea45dd2"

        # Format a filename
        filename = settings.naming.format_filename("AAPL_10K", "20251212_200149", "parsed")
        # -> "AAPL_10K_20251212_200149_parsed.json"
    """
    model_config = SettingsConfigDict(
        env_prefix="NAMING_",
        extra="ignore"
    )

    timestamp_format: str = Field(
        default="%Y%m%d_%H%M%S",
        description="strftime format for run_id timestamps"
    )

    folder_pattern: str = Field(
        default="{run_id}_{name}_{git_sha}",
        description="Pattern for run folder names (with git SHA)"
    )

    folder_pattern_no_sha: str = Field(
        default="{run_id}_{name}",
        description="Pattern for run folder names (without git SHA)"
    )

    file_pattern: str = Field(
        default="{stem}_{run_id}_{output_type}.json",
        description="Pattern for output file names"
    )

    output_types: Dict[str, str] = Field(
        default={
            "parsed": "parsed",
            "extracted": "extracted_risks",
            "cleaned": "cleaned_risks",
            "segmented": "segmented_risks",
            "labeled": "labeled"
        },
        description="Mapping of stage names to output type suffixes"
    )

    def format_folder(self, run_id: str, name: str, git_sha: str = None) -> str:
        """
        Generate folder name from pattern.

        Args:
            run_id: Timestamp identifier (e.g., "20251212_200149")
            name: User-provided run name
            git_sha: Optional git commit SHA

        Returns:
            Formatted folder name
        """
        if git_sha:
            return self.folder_pattern.format(
                run_id=run_id, name=name, git_sha=git_sha
            )
        return self.folder_pattern_no_sha.format(run_id=run_id, name=name)

    def format_filename(self, stem: str, run_id: str, output_type: str) -> str:
        """
        Generate filename from pattern.

        Args:
            stem: Original input file stem (e.g., "AAPL_10K")
            run_id: Timestamp identifier (e.g., "20251212_200149")
            output_type: Processing stage key (e.g., "parsed", "extracted")

        Returns:
            Formatted filename with extension
        """
        type_suffix = self.output_types.get(output_type, output_type)
        return self.file_pattern.format(
            stem=stem, run_id=run_id, output_type=type_suffix
        )

    def get_output_type(self, stage: str) -> str:
        """
        Get the output type suffix for a processing stage.

        Args:
            stage: Processing stage key

        Returns:
            Output type suffix string
        """
        return self.output_types.get(stage, stage)

"""
Model Registry Manager for versioned model artifact management.

Handles creating, saving, loading, and listing model registry entries.
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.models.registry.schemas import (
    ModelRegistryEntry,
    ModelMetrics,
    TrainingConfig,
    DatasetInfo,
)


class ModelRegistryManager:
    """
    Manager for model registry operations.

    Handles:
    - Creating model version directories
    - Saving/loading model metadata
    - Listing registered models
    - Promoting models between stages

    Directory structure:
        models/registry/
        └── {model_name}/
            └── {version}/
                ├── metadata.json
                ├── model.pt (or other artifacts)
                └── ...

    Example:
        >>> manager = ModelRegistryManager()
        >>> entry = manager.register_model(
        ...     model_name="risk_classifier",
        ...     version="1.0.0",
        ...     metrics={"accuracy": 0.87}
        ... )
        >>> print(entry.full_name)
        risk_classifier/1.0.0
    """

    METADATA_FILENAME = "metadata.json"

    def __init__(self, registry_dir: Optional[Path] = None):
        """
        Initialize the ModelRegistryManager.

        Args:
            registry_dir: Path to registry directory.
                         Defaults to models/registry/ in project root.
        """
        if registry_dir is None:
            from src.config import settings
            self.registry_dir = settings.paths.model_registry_dir
        else:
            self.registry_dir = Path(registry_dir)

        # Ensure registry directory exists
        self.registry_dir.mkdir(parents=True, exist_ok=True)

    def _get_model_dir(self, model_name: str, version: str) -> Path:
        """Get path to model version directory."""
        return self.registry_dir / model_name / version

    def _get_git_info(self) -> Dict[str, Optional[str]]:
        """Get current git SHA and branch."""
        git_sha = None
        branch = None

        try:
            git_sha = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                stderr=subprocess.DEVNULL
            ).decode().strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        try:
            branch = subprocess.check_output(
                ["git", "branch", "--show-current"],
                stderr=subprocess.DEVNULL
            ).decode().strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        return {"git_sha": git_sha, "branch": branch}

    def register_model(
        self,
        model_name: str,
        version: str,
        description: Optional[str] = None,
        model_type: Optional[str] = None,
        base_model: Optional[str] = None,
        metrics: Optional[Dict[str, Any]] = None,
        training_config: Optional[Dict[str, Any]] = None,
        dataset_info: Optional[Dict[str, Any]] = None,
        artifact_paths: Optional[Dict[str, str]] = None,
        tags: Optional[List[str]] = None,
        status: str = "development",
        notes: Optional[str] = None,
        overwrite: bool = False,
    ) -> ModelRegistryEntry:
        """
        Register a new model version.

        Args:
            model_name: Name of the model
            version: Semantic version (X.Y.Z)
            description: Human-readable description
            model_type: Type of model (transformer, bert, etc.)
            base_model: Base model used for fine-tuning
            metrics: Performance metrics dict
            training_config: Training configuration dict
            dataset_info: Dataset information dict
            artifact_paths: Dict of artifact name to relative path
            tags: List of tags
            status: Model status (development, staging, production, archived)
            notes: Additional notes
            overwrite: Whether to overwrite existing entry

        Returns:
            ModelRegistryEntry with populated metadata

        Raises:
            FileExistsError: If version exists and overwrite=False
        """
        model_dir = self._get_model_dir(model_name, version)
        metadata_path = model_dir / self.METADATA_FILENAME

        if metadata_path.exists() and not overwrite:
            raise FileExistsError(
                f"Model {model_name}/{version} already exists. "
                f"Set overwrite=True to replace."
            )

        # Create directory
        model_dir.mkdir(parents=True, exist_ok=True)

        # Get git info
        git_info = self._get_git_info()

        # Build entry
        entry = ModelRegistryEntry(
            model_name=model_name,
            version=version,
            git_sha=git_info["git_sha"],
            branch=git_info["branch"],
            description=description,
            model_type=model_type,
            base_model=base_model,
            metrics=ModelMetrics(**(metrics or {})),
            training_config=TrainingConfig(**(training_config or {})),
            dataset_info=DatasetInfo(**(dataset_info or {})),
            artifact_paths=artifact_paths or {},
            tags=tags or [],
            status=status,
            notes=notes,
        )

        # Save metadata
        self._save_metadata(entry, metadata_path)

        return entry

    def _save_metadata(self, entry: ModelRegistryEntry, path: Path) -> None:
        """Save model metadata to JSON file."""
        data = entry.model_dump(mode="json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    def load_model(self, model_name: str, version: str) -> ModelRegistryEntry:
        """
        Load model metadata from registry.

        Args:
            model_name: Name of the model
            version: Version to load

        Returns:
            ModelRegistryEntry

        Raises:
            FileNotFoundError: If model/version not found
        """
        model_dir = self._get_model_dir(model_name, version)
        metadata_path = model_dir / self.METADATA_FILENAME

        if not metadata_path.exists():
            raise FileNotFoundError(
                f"Model {model_name}/{version} not found at {metadata_path}"
            )

        with open(metadata_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return ModelRegistryEntry.model_validate(data)

    def list_models(self) -> List[str]:
        """
        List all registered model names.

        Returns:
            List of model names
        """
        if not self.registry_dir.exists():
            return []

        return [
            d.name for d in self.registry_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ]

    def list_versions(self, model_name: str) -> List[str]:
        """
        List all versions of a model.

        Args:
            model_name: Name of the model

        Returns:
            List of version strings, sorted by semantic version
        """
        model_dir = self.registry_dir / model_name

        if not model_dir.exists():
            return []

        versions = [
            d.name for d in model_dir.iterdir()
            if d.is_dir() and (d / self.METADATA_FILENAME).exists()
        ]

        # Sort by semantic version
        def version_key(v: str) -> tuple:
            try:
                return tuple(int(x) for x in v.split("."))
            except ValueError:
                return (0, 0, 0)

        return sorted(versions, key=version_key)

    def get_latest_version(self, model_name: str) -> Optional[str]:
        """
        Get the latest version of a model.

        Args:
            model_name: Name of the model

        Returns:
            Latest version string, or None if no versions exist
        """
        versions = self.list_versions(model_name)
        return versions[-1] if versions else None

    def promote_model(
        self,
        model_name: str,
        version: str,
        new_status: str,
    ) -> ModelRegistryEntry:
        """
        Promote a model to a new status.

        Args:
            model_name: Name of the model
            version: Version to promote
            new_status: New status (staging, production, archived)

        Returns:
            Updated ModelRegistryEntry
        """
        entry = self.load_model(model_name, version)
        old_status = entry.status
        entry.status = new_status
        entry.updated_at = datetime.now()

        if entry.notes:
            entry.notes += f"\nPromoted from {old_status} to {new_status}"
        else:
            entry.notes = f"Promoted from {old_status} to {new_status}"

        # Save updated metadata
        metadata_path = self._get_model_dir(model_name, version) / self.METADATA_FILENAME
        self._save_metadata(entry, metadata_path)

        return entry

    def get_model_dir(self, model_name: str, version: str) -> Path:
        """
        Get the directory path for a model version.

        Args:
            model_name: Name of the model
            version: Version string

        Returns:
            Path to model version directory
        """
        return self._get_model_dir(model_name, version)

    def delete_model(
        self,
        model_name: str,
        version: str,
        confirm: bool = False
    ) -> bool:
        """
        Delete a model version from the registry.

        Args:
            model_name: Name of the model
            version: Version to delete
            confirm: Must be True to actually delete

        Returns:
            True if deleted, False otherwise
        """
        if not confirm:
            print(f"Set confirm=True to delete {model_name}/{version}")
            return False

        model_dir = self._get_model_dir(model_name, version)

        if not model_dir.exists():
            return False

        import shutil
        shutil.rmtree(model_dir)
        return True

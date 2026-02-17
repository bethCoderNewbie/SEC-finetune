"""
Pydantic schemas for Model Registry entries.

Defines validated structures for model metadata, metrics, and artifacts.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ModelMetrics(BaseModel):
    """
    Model performance metrics.

    Attributes:
        accuracy: Classification accuracy (0-1)
        f1_score: F1 score (0-1)
        precision: Precision score (0-1)
        recall: Recall score (0-1)
        loss: Training/validation loss
        custom: Additional custom metrics
    """
    model_config = ConfigDict(extra="allow")

    accuracy: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    f1_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    precision: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    recall: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    loss: Optional[float] = Field(default=None, ge=0.0)
    custom: Dict[str, Any] = Field(default_factory=dict)


class TrainingConfig(BaseModel):
    """
    Training configuration snapshot.

    Attributes:
        learning_rate: Learning rate used
        batch_size: Batch size used
        epochs: Number of epochs trained
        seed: Random seed for reproducibility
        optimizer: Optimizer name (e.g., "AdamW")
        scheduler: LR scheduler name
        early_stopping: Whether early stopping was used
        additional: Additional configuration parameters
    """
    model_config = ConfigDict(extra="allow")

    learning_rate: Optional[float] = None
    batch_size: Optional[int] = None
    epochs: Optional[int] = None
    seed: Optional[int] = Field(default=42)
    optimizer: Optional[str] = None
    scheduler: Optional[str] = None
    early_stopping: bool = False
    additional: Dict[str, Any] = Field(default_factory=dict)


class DatasetInfo(BaseModel):
    """
    Dataset information used for training.

    Attributes:
        name: Dataset name or identifier
        version: Dataset version (git SHA or tag)
        train_samples: Number of training samples
        val_samples: Number of validation samples
        test_samples: Number of test samples
        path: Path to dataset
    """
    name: Optional[str] = None
    version: Optional[str] = None
    train_samples: Optional[int] = None
    val_samples: Optional[int] = None
    test_samples: Optional[int] = None
    path: Optional[str] = None


class ModelRegistryEntry(BaseModel):
    """
    Complete model registry entry with metadata.

    Attributes:
        model_name: Name of the model (e.g., "risk_classifier")
        version: Semantic version string (e.g., "1.0.0")
        git_sha: Git commit SHA at training time
        branch: Git branch at training time
        created_at: Timestamp when model was registered
        updated_at: Timestamp of last update
        description: Human-readable description
        model_type: Type of model (e.g., "transformer", "bert", "lstm")
        base_model: Base model used (e.g., "ProsusAI/finbert")
        metrics: Performance metrics
        training_config: Training configuration
        dataset_info: Dataset information
        artifact_paths: Relative paths to model artifacts
        tags: List of tags for categorization
        status: Model status (e.g., "development", "staging", "production")
        promoted_from: Previous version this was promoted from
        notes: Additional notes
    """
    model_config = ConfigDict(
        validate_assignment=True,
        extra="forbid",
    )

    # Required fields
    model_name: str = Field(..., min_length=1, description="Model identifier")
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$", description="Semantic version")

    # Git tracking
    git_sha: Optional[str] = Field(default=None, description="Git commit SHA")
    branch: Optional[str] = Field(default=None, description="Git branch")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # Descriptive fields
    description: Optional[str] = None
    model_type: Optional[str] = None
    base_model: Optional[str] = None

    # Performance and configuration
    metrics: ModelMetrics = Field(default_factory=ModelMetrics)
    training_config: TrainingConfig = Field(default_factory=TrainingConfig)
    dataset_info: DatasetInfo = Field(default_factory=DatasetInfo)

    # Artifacts
    artifact_paths: Dict[str, str] = Field(
        default_factory=dict,
        description="Relative paths to artifacts (e.g., {'model': 'model.pt'})"
    )

    # Categorization
    tags: List[str] = Field(default_factory=list)
    status: str = Field(default="development", pattern=r"^(development|staging|production|archived)$")
    promoted_from: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        """Ensure version follows semantic versioning."""
        parts = v.split(".")
        if len(parts) != 3:
            raise ValueError("Version must be in format X.Y.Z")
        return v

    @property
    def full_name(self) -> str:
        """Return full model identifier."""
        return f"{self.model_name}/{self.version}"

    def get_artifact_path(self, artifact_name: str, base_dir: Path) -> Optional[Path]:
        """
        Get absolute path to an artifact.

        Args:
            artifact_name: Name of the artifact (e.g., "model")
            base_dir: Base directory where model is stored

        Returns:
            Absolute path to artifact, or None if not found
        """
        relative_path = self.artifact_paths.get(artifact_name)
        if relative_path:
            return base_dir / relative_path
        return None

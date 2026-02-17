"""
Model Registry package for versioned model artifact management.

Provides Pydantic-validated schemas and a manager class for:
- Creating model version directories
- Saving/loading model metadata
- Tracking model artifacts and metrics

Usage:
    from src.models.registry import ModelRegistryManager, ModelRegistryEntry

    # Register a new model
    manager = ModelRegistryManager()
    entry = manager.register_model(
        model_name="risk_classifier",
        version="1.0.0",
        metrics={"accuracy": 0.87, "f1_score": 0.84},
        artifact_paths={"model": "model.pt", "tokenizer": "tokenizer/"}
    )

    # Load existing model metadata
    entry = manager.load_model("risk_classifier", "1.0.0")
"""

from src.models.registry.schemas import ModelRegistryEntry, ModelMetrics
from src.models.registry.manager import ModelRegistryManager

__all__ = [
    "ModelRegistryEntry",
    "ModelMetrics",
    "ModelRegistryManager",
]

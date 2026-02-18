"""Unit tests for model registry schemas and manager.

Covers:
- src/models/registry/schemas.py  (ModelMetrics, TrainingConfig, DatasetInfo,
                                    ModelRegistryEntry)
- src/models/registry/manager.py  (ModelRegistryManager)
"""

import json
import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import patch

from pydantic import ValidationError

from src.models.registry.schemas import (
    ModelMetrics,
    TrainingConfig,
    DatasetInfo,
    ModelRegistryEntry,
)
from src.models.registry.manager import ModelRegistryManager


# ---------------------------------------------------------------------------
# ModelMetrics
# ---------------------------------------------------------------------------

class TestModelMetrics:
    def test_all_optional_defaults_none(self):
        m = ModelMetrics()
        assert m.accuracy is None
        assert m.f1_score is None
        assert m.precision is None
        assert m.recall is None
        assert m.loss is None

    def test_valid_values_accepted(self):
        m = ModelMetrics(accuracy=0.95, f1_score=0.90, precision=0.88, recall=0.92, loss=0.1)
        assert m.accuracy == 0.95

    def test_boundary_zero_accepted(self):
        m = ModelMetrics(accuracy=0.0, f1_score=0.0)
        assert m.accuracy == 0.0

    def test_boundary_one_accepted(self):
        m = ModelMetrics(accuracy=1.0, f1_score=1.0)
        assert m.accuracy == 1.0

    def test_accuracy_above_one_raises(self):
        with pytest.raises(ValidationError):
            ModelMetrics(accuracy=1.01)

    def test_accuracy_below_zero_raises(self):
        with pytest.raises(ValidationError):
            ModelMetrics(accuracy=-0.01)

    def test_negative_loss_raises(self):
        with pytest.raises(ValidationError):
            ModelMetrics(loss=-1.0)

    def test_custom_dict_defaults_empty(self):
        m = ModelMetrics()
        assert m.custom == {}

    def test_extra_fields_allowed(self):
        m = ModelMetrics(extra_metric=0.5)
        assert m.extra_metric == 0.5


# ---------------------------------------------------------------------------
# TrainingConfig
# ---------------------------------------------------------------------------

class TestTrainingConfig:
    def test_all_optional_fields(self):
        tc = TrainingConfig()
        assert tc.learning_rate is None
        assert tc.batch_size is None
        assert tc.epochs is None
        assert tc.optimizer is None

    def test_seed_defaults_to_42(self):
        tc = TrainingConfig()
        assert tc.seed == 42

    def test_early_stopping_defaults_false(self):
        tc = TrainingConfig()
        assert tc.early_stopping is False

    def test_stores_values(self):
        tc = TrainingConfig(
            learning_rate=2e-5,
            batch_size=32,
            epochs=3,
            optimizer="AdamW",
        )
        assert tc.learning_rate == 2e-5
        assert tc.batch_size == 32


# ---------------------------------------------------------------------------
# DatasetInfo
# ---------------------------------------------------------------------------

class TestDatasetInfo:
    def test_all_optional(self):
        di = DatasetInfo()
        assert di.name is None
        assert di.version is None
        assert di.train_samples is None

    def test_stores_values(self):
        di = DatasetInfo(name="sec-10k", version="abc123", train_samples=5000)
        assert di.name == "sec-10k"
        assert di.train_samples == 5000


# ---------------------------------------------------------------------------
# ModelRegistryEntry
# ---------------------------------------------------------------------------

class TestModelRegistryEntry:
    @pytest.fixture
    def entry(self):
        return ModelRegistryEntry(model_name="risk_classifier", version="1.0.0")

    def test_valid_entry_created(self, entry):
        assert entry.model_name == "risk_classifier"
        assert entry.version == "1.0.0"

    def test_full_name_property(self, entry):
        assert entry.full_name == "risk_classifier/1.0.0"

    def test_status_defaults_development(self, entry):
        assert entry.status == "development"

    def test_valid_statuses_accepted(self):
        for status in ("development", "staging", "production", "archived"):
            e = ModelRegistryEntry(model_name="m", version="1.0.0", status=status)
            assert e.status == status

    def test_invalid_status_raises(self):
        with pytest.raises(ValidationError):
            ModelRegistryEntry(model_name="m", version="1.0.0", status="unknown")

    def test_invalid_version_pattern_raises(self):
        with pytest.raises(ValidationError):
            ModelRegistryEntry(model_name="m", version="v1.0")

    def test_invalid_version_missing_parts_raises(self):
        with pytest.raises(ValidationError):
            ModelRegistryEntry(model_name="m", version="1.0")

    def test_version_with_four_parts_raises(self):
        with pytest.raises(ValidationError):
            ModelRegistryEntry(model_name="m", version="1.0.0.0")

    def test_empty_model_name_raises(self):
        with pytest.raises(ValidationError):
            ModelRegistryEntry(model_name="", version="1.0.0")

    def test_tags_defaults_empty_list(self, entry):
        assert entry.tags == []

    def test_artifact_paths_defaults_empty_dict(self, entry):
        assert entry.artifact_paths == {}

    def test_get_artifact_path_found(self, entry, tmp_path):
        entry.artifact_paths["model"] = "model.pt"
        result = entry.get_artifact_path("model", tmp_path)
        assert result == tmp_path / "model.pt"

    def test_get_artifact_path_not_found_returns_none(self, entry, tmp_path):
        result = entry.get_artifact_path("nonexistent", tmp_path)
        assert result is None

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            ModelRegistryEntry(model_name="m", version="1.0.0", unknown_field="x")

    def test_created_at_auto_populated(self, entry):
        assert isinstance(entry.created_at, datetime)


# ---------------------------------------------------------------------------
# ModelRegistryManager
# ---------------------------------------------------------------------------

@pytest.fixture
def manager(tmp_path) -> ModelRegistryManager:
    return ModelRegistryManager(registry_dir=tmp_path / "registry")


class TestRegisterModel:
    def test_creates_metadata_file(self, manager):
        manager.register_model("risk_classifier", "1.0.0")
        meta = manager.registry_dir / "risk_classifier" / "1.0.0" / "metadata.json"
        assert meta.exists()

    def test_metadata_json_is_valid(self, manager):
        manager.register_model("risk_classifier", "1.0.0")
        meta = manager.registry_dir / "risk_classifier" / "1.0.0" / "metadata.json"
        data = json.loads(meta.read_text())
        assert data["model_name"] == "risk_classifier"
        assert data["version"] == "1.0.0"

    def test_returns_model_registry_entry(self, manager):
        entry = manager.register_model("risk_classifier", "1.0.0")
        assert isinstance(entry, ModelRegistryEntry)
        assert entry.model_name == "risk_classifier"

    def test_raises_if_already_exists(self, manager):
        manager.register_model("risk_classifier", "1.0.0")
        with pytest.raises(FileExistsError):
            manager.register_model("risk_classifier", "1.0.0", overwrite=False)

    def test_overwrite_true_succeeds(self, manager):
        manager.register_model("risk_classifier", "1.0.0")
        entry = manager.register_model("risk_classifier", "1.0.0", overwrite=True)
        assert entry.version == "1.0.0"

    def test_stores_metrics(self, manager):
        manager.register_model(
            "risk_classifier", "1.0.0",
            metrics={"accuracy": 0.87, "f1_score": 0.85},
        )
        entry = manager.load_model("risk_classifier", "1.0.0")
        assert entry.metrics.accuracy == 0.87

    def test_stores_tags(self, manager):
        manager.register_model("m", "1.0.0", tags=["sec", "finbert"])
        entry = manager.load_model("m", "1.0.0")
        assert "sec" in entry.tags

    def test_stores_description(self, manager):
        manager.register_model("m", "1.0.0", description="My model")
        entry = manager.load_model("m", "1.0.0")
        assert entry.description == "My model"

    def test_populates_git_info(self, manager):
        with patch.object(manager, "_get_git_info", return_value={"git_sha": "abc123", "branch": "main"}):
            entry = manager.register_model("m", "1.0.0")
        assert entry.git_sha == "abc123"
        assert entry.branch == "main"


class TestLoadModel:
    def test_loads_registered_model(self, manager):
        manager.register_model("risk_classifier", "1.0.0", description="Test")
        entry = manager.load_model("risk_classifier", "1.0.0")
        assert entry.model_name == "risk_classifier"
        assert entry.description == "Test"

    def test_raises_if_not_found(self, manager):
        with pytest.raises(FileNotFoundError):
            manager.load_model("nonexistent", "1.0.0")


class TestListModels:
    def test_empty_registry_returns_empty(self, manager):
        assert manager.list_models() == []

    def test_returns_registered_model_names(self, manager):
        manager.register_model("model_a", "1.0.0")
        manager.register_model("model_b", "1.0.0")
        names = manager.list_models()
        assert "model_a" in names
        assert "model_b" in names

    def test_does_not_include_dot_dirs(self, manager):
        (manager.registry_dir / ".hidden").mkdir(parents=True)
        names = manager.list_models()
        assert ".hidden" not in names


class TestListVersions:
    def test_returns_empty_for_unknown_model(self, manager):
        assert manager.list_versions("nonexistent") == []

    def test_returns_sorted_versions(self, manager):
        for v in ("1.2.0", "1.0.0", "2.0.0", "1.10.0"):
            manager.register_model("m", v)
        versions = manager.list_versions("m")
        assert versions == ["1.0.0", "1.2.0", "1.10.0", "2.0.0"]

    def test_only_includes_dirs_with_metadata(self, manager):
        manager.register_model("m", "1.0.0")
        # Create a dir without metadata
        (manager.registry_dir / "m" / "bad_dir").mkdir()
        versions = manager.list_versions("m")
        assert versions == ["1.0.0"]


class TestGetLatestVersion:
    def test_returns_none_for_unknown_model(self, manager):
        assert manager.get_latest_version("nonexistent") is None

    def test_returns_latest_semantic_version(self, manager):
        for v in ("1.0.0", "2.0.0", "1.5.0"):
            manager.register_model("m", v)
        assert manager.get_latest_version("m") == "2.0.0"


class TestPromoteModel:
    def test_updates_status(self, manager):
        manager.register_model("m", "1.0.0", status="development")
        entry = manager.promote_model("m", "1.0.0", "staging")
        assert entry.status == "staging"

    def test_appends_promotion_note(self, manager):
        manager.register_model("m", "1.0.0")
        entry = manager.promote_model("m", "1.0.0", "production")
        assert "Promoted from" in entry.notes

    def test_persists_status_change(self, manager):
        manager.register_model("m", "1.0.0")
        manager.promote_model("m", "1.0.0", "staging")
        loaded = manager.load_model("m", "1.0.0")
        assert loaded.status == "staging"

    def test_invalid_status_raises(self, manager):
        manager.register_model("m", "1.0.0")
        with pytest.raises(ValidationError):
            manager.promote_model("m", "1.0.0", "invalid_status")


class TestDeleteModel:
    def test_confirm_false_is_noop(self, manager):
        manager.register_model("m", "1.0.0")
        result = manager.delete_model("m", "1.0.0", confirm=False)
        assert result is False
        assert manager.load_model("m", "1.0.0") is not None

    def test_confirm_true_deletes(self, manager):
        manager.register_model("m", "1.0.0")
        result = manager.delete_model("m", "1.0.0", confirm=True)
        assert result is True
        with pytest.raises(FileNotFoundError):
            manager.load_model("m", "1.0.0")

    def test_nonexistent_returns_false(self, manager):
        result = manager.delete_model("nonexistent", "1.0.0", confirm=True)
        assert result is False

"""Project path configuration."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PathsConfig(BaseSettings):
    """
    Project path configuration.
    All paths are computed from project_root.
    """
    model_config = SettingsConfigDict(
        env_prefix='PATHS_',
        case_sensitive=False
    )

    # Project root directory (computed)
    project_root: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent)

    @property
    def data_dir(self) -> Path:
        return self.project_root / "data"

    @property
    def raw_data_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def interim_data_dir(self) -> Path:
        return self.data_dir / "interim"

    @property
    def parsed_data_dir(self) -> Path:
        """Parsed SEC filings (JSON format)"""
        return self.interim_data_dir / "parsed"

    @property
    def extracted_data_dir(self) -> Path:
        """Extracted sections (JSON format)"""
        return self.interim_data_dir / "extracted"

    @property
    def processed_data_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def labeled_data_dir(self) -> Path:
        return self.processed_data_dir / "labeled"

    @property
    def features_data_dir(self) -> Path:
        """Directory for computed features"""
        return self.processed_data_dir / "features"

    @property
    def models_dir(self) -> Path:
        return self.project_root / "models"

    @property
    def experiments_dir(self) -> Path:
        """Directory for training experiments"""
        return self.models_dir / "experiments"

    @property
    def model_registry_dir(self) -> Path:
        """Directory for production-ready models"""
        return self.models_dir / "registry"

    @property
    def src_dir(self) -> Path:
        return self.project_root / "src"

    @property
    def analysis_dir(self) -> Path:
        return self.src_dir / "analysis"

    @property
    def taxonomies_dir(self) -> Path:
        return self.analysis_dir / "taxonomies"

    @property
    def logs_dir(self) -> Path:
        return self.project_root / "logs"

    @property
    def extraction_logs_dir(self) -> Path:
        return self.logs_dir / "extractions"

    @property
    def risk_taxonomy_path(self) -> Path:
        return self.taxonomies_dir / "risk_taxonomy.yaml"

    @property
    def golden_dataset_path(self) -> Path:
        return self.project_root / "tests" / "fixtures" / "golden_extractions.json"

    @property
    def dictionary_dir(self) -> Path:
        """Directory containing dictionary resources"""
        return self.data_dir / "dictionary"

    @property
    def lm_dictionary_csv(self) -> Path:
        """Path to LM dictionary source CSV."""
        # Inline constant to avoid circular import with features module
        return self.dictionary_dir / "Loughran-McDonald_MasterDictionary_1993-2024.csv"

    @property
    def lm_dictionary_cache(self) -> Path:
        """Path to preprocessed LM dictionary cache."""
        # Inline constant to avoid circular import with features module
        return self.dictionary_dir / "lm_dictionary_cache.pkl"

    def ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        directories = [
            self.raw_data_dir,
            self.interim_data_dir,
            self.parsed_data_dir,
            self.extracted_data_dir,
            self.processed_data_dir,
            self.labeled_data_dir,
            self.features_data_dir,
            self.models_dir,
            self.experiments_dir,
            self.model_registry_dir,
            self.logs_dir,
            self.extraction_logs_dir,
            self.dictionary_dir,
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

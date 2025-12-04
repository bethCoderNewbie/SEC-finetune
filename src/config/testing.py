"""Testing and reproducibility configuration."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.config._loader import load_yaml_section


def _get_testing_config() -> dict:
    return load_yaml_section("config.yaml").get("testing", {})


def _get_reproducibility_config() -> dict:
    return load_yaml_section("config.yaml").get("reproducibility", {})


class TestingConfig(BaseSettings):
    """Testing and validation configuration settings."""
    model_config = SettingsConfigDict(
        env_prefix='TESTING_',
        case_sensitive=False
    )

    enable_golden_validation: bool = Field(
        default_factory=lambda: _get_testing_config().get('enable_golden_validation', False)
    )


class ReproducibilityConfig(BaseSettings):
    """Reproducibility configuration settings."""
    model_config = SettingsConfigDict(
        env_prefix='REPRODUCIBILITY_',
        case_sensitive=False
    )

    random_seed: int = Field(
        default_factory=lambda: _get_reproducibility_config().get('random_seed', 42)
    )

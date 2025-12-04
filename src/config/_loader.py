"""
Cached YAML configuration loader.

Usage:
    from src.config._loader import load_yaml_section

    # Load entire file
    config = load_yaml_section("config.yaml")

    # Load specific section
    sentiment = load_yaml_section("features/sentiment.yaml", "sentiment")
"""

from functools import lru_cache
from pathlib import Path
from typing import Any
import yaml


def _get_configs_dir() -> Path:
    """Get the configs directory path."""
    return Path(__file__).parent.parent.parent / "configs"


@lru_cache(maxsize=16)
def load_yaml_section(config_file: str, section: str | None = None) -> dict[str, Any]:
    """
    Load and cache YAML configuration.

    Args:
        config_file: Path relative to configs/ directory
            (e.g., "config.yaml" or "features/sentiment.yaml")
        section: Optional top-level key to extract (e.g., "sentiment")

    Returns:
        Configuration dictionary (empty dict if file not found)

    Note:
        Results are cached. Use clear_config_cache() to reload.
    """
    config_path = _get_configs_dir() / config_file

    if not config_path.exists():
        return {}

    with open(config_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}

    return data.get(section, {}) if section else data


def clear_config_cache() -> None:
    """Clear all cached configurations. Useful for testing."""
    load_yaml_section.cache_clear()

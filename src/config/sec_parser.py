"""SEC Parser configuration."""

from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.config._loader import load_yaml_section


def _get_config() -> dict:
    return load_yaml_section("config.yaml").get("sec_parser", {})


class SecParserConfig(BaseSettings):
    """SEC Parser configuration settings."""
    model_config = SettingsConfigDict(
        env_prefix='SEC_PARSER_',
        case_sensitive=False
    )

    supported_form_types: List[str] = Field(
        default_factory=lambda: _get_config().get('supported_form_types', ["10-K", "10-Q"])
    )
    default_form_type: str = Field(
        default_factory=lambda: _get_config().get('default_form_type', "10-K")
    )
    input_file_extensions: List[str] = Field(
        default_factory=lambda: _get_config().get('input_file_extensions', ["html"])
    )
    parse_tables: bool = Field(
        default_factory=lambda: _get_config().get('parse_tables', True)
    )
    parse_images: bool = Field(
        default_factory=lambda: _get_config().get('parse_images', False)
    )
    version: str = Field(
        default_factory=lambda: _get_config().get('version', "0.54.0")
    )

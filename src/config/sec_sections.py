"""SEC section identifiers configuration."""

from typing import Dict

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.config._loader import load_yaml_section


def _get_config() -> dict:
    return load_yaml_section("config.yaml").get("sec_sections", {})


class SecSectionsConfig(BaseSettings):
    """SEC section identifiers for different form types."""
    model_config = SettingsConfigDict(
        env_prefix='SEC_SECTIONS_',
        case_sensitive=False
    )

    sections_10k: Dict[str, str] = Field(
        default_factory=lambda: _get_config().get('10-K', {
            "part1item1": "Item 1. Business",
            "part1item1a": "Item 1A. Risk Factors",
            "part1item1b": "Item 1B. Unresolved Staff Comments",
            "part1item1c": "Item 1C. Cybersecurity",
            "part2item7": "Item 7. Management's Discussion and Analysis",
            "part2item7a": "Item 7A. Quantitative and Qualitative Disclosures About Market Risk",
            "part2item8": "Item 8. Financial Statements and Supplementary Data",
        })
    )
    sections_10q: Dict[str, str] = Field(
        default_factory=lambda: _get_config().get('10-Q', {
            "part1item1": "Item 1. Financial Statements",
            "part1item2": "Item 2. Management's Discussion and Analysis",
            "part2item1a": "Item 1A. Risk Factors",
        })
    )

    @property
    def SEC_10K_SECTIONS(self) -> Dict[str, str]:
        """Legacy property name for backward compatibility."""
        return self.sections_10k

    @property
    def SEC_10Q_SECTIONS(self) -> Dict[str, str]:
        """Legacy property name for backward compatibility."""
        return self.sections_10q

"""Annotation pipeline configuration (SegmentAnnotator / US-032)."""

from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.config._loader import load_yaml_section


def _get_config() -> dict:
    return load_yaml_section("features/annotation.yaml", "annotation")


class AnnotationConfig(BaseSettings):
    """
    SegmentAnnotator configuration.

    Loads from configs/features/annotation.yaml.
    All fields are overridable via environment variables (prefix: SEC_ANNOTATION__).

    Examples:
        SEC_ANNOTATION__CONFIDENCE_THRESHOLD=0.75
        SEC_ANNOTATION__DEVICE=0
        SEC_ANNOTATION__MODEL_NAME=cross-encoder/nli-deberta-v3-small
    """

    model_config = SettingsConfigDict(
        env_prefix="SEC_ANNOTATION__",
        env_nested_delimiter="__",
        case_sensitive=False,
    )

    model_name: str = Field(
        default_factory=lambda: _get_config().get("model_name", "facebook/bart-large-mnli")
    )
    confidence_threshold: float = Field(
        default_factory=lambda: _get_config().get("confidence_threshold", 0.70)
    )
    binary_gate_threshold: float = Field(
        default_factory=lambda: _get_config().get("binary_gate_threshold", 0.50)
    )
    merge_lo: int = Field(
        default_factory=lambda: _get_config().get("merge_lo", 200)
    )
    merge_hi: int = Field(
        default_factory=lambda: _get_config().get("merge_hi", 379)
    )
    device: int = Field(
        default_factory=lambda: _get_config().get("device", -1)
    )
    section_include: List[str] = Field(
        default_factory=lambda: _get_config().get(
            "section_include", ["part1item1a", "part2item7a", "part1item1c"]
        )
    )

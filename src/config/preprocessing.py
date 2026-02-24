"""Text preprocessing configuration."""

from pydantic import BaseModel, ConfigDict, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.config._loader import load_yaml_section


def _get_config() -> dict:
    return load_yaml_section("config.yaml").get("preprocessing", {})


def _get_sanitizer_config() -> dict:
    return _get_config().get("sanitizer", {})


class SanitizerConfig(BaseModel):
    """
    HTML Sanitizer configuration for pre-parser cleaning.

    These settings control how raw HTML is cleaned before sec-parser processing.
    Proper sanitization improves ParsedFiling quality and extraction accuracy.
    """
    model_config = ConfigDict(
        validate_assignment=True,
        extra='forbid',
    )

    enabled: bool = Field(
        default_factory=lambda: _get_sanitizer_config().get('enabled', True),
        description="Enable pre-parser HTML sanitization"
    )
    remove_edgar_header: bool = Field(
        default_factory=lambda: _get_sanitizer_config().get('remove_edgar_header', False),
        description="Remove SEC EDGAR submission header boilerplate (WARNING: disables metadata extraction)"
    )
    remove_edgar_tags: bool = Field(
        default_factory=lambda: _get_sanitizer_config().get('remove_edgar_tags', False),
        description="Remove EDGAR SGML tags (<PAGE>, <S>, <C>, etc.) - WARNING: breaks sec-parser structure"
    )
    decode_entities: bool = Field(
        default_factory=lambda: _get_sanitizer_config().get('decode_entities', True),
        description="Decode HTML entities (&amp; → &)"
    )
    normalize_unicode: bool = Field(
        default_factory=lambda: _get_sanitizer_config().get('normalize_unicode', True),
        description="Apply NFKC Unicode normalization"
    )
    remove_invisible_chars: bool = Field(
        default_factory=lambda: _get_sanitizer_config().get('remove_invisible_chars', True),
        description="Remove zero-width spaces and control characters"
    )
    normalize_quotes: bool = Field(
        default_factory=lambda: _get_sanitizer_config().get('normalize_quotes', True),
        description="Convert curly/smart quotes to straight ASCII quotes"
    )
    fix_encoding: bool = Field(
        default_factory=lambda: _get_sanitizer_config().get('fix_encoding', False),
        description="Attempt to fix mojibake (requires ftfy library)"
    )
    flatten_nesting: bool = Field(
        default_factory=lambda: _get_sanitizer_config().get('flatten_nesting', True),
        description="Remove redundant nested tags (div, span, font)"
    )


class PreprocessingConfig(BaseSettings):
    """Text preprocessing configuration settings."""
    model_config = SettingsConfigDict(
        env_prefix='PREPROCESSING_',
        case_sensitive=False
    )

    min_segment_length: int = Field(
        default_factory=lambda: _get_config().get('min_segment_length', 50)
    )
    max_segment_length: int = Field(
        default_factory=lambda: _get_config().get('max_segment_length', 2000)
    )
    min_segment_words: int = Field(
        default_factory=lambda: _get_config().get('min_segment_words', 20)
    )
    remove_html_tags: bool = Field(
        default_factory=lambda: _get_config().get('remove_html_tags', True)
    )
    normalize_whitespace: bool = Field(
        default_factory=lambda: _get_config().get('normalize_whitespace', True)
    )
    remove_page_numbers: bool = Field(
        default_factory=lambda: _get_config().get('remove_page_numbers', True)
    )
    sanitizer: SanitizerConfig = Field(
        default_factory=SanitizerConfig,
        description="HTML sanitization settings for pre-parser cleaning"
    )

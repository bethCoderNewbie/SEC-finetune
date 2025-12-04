"""
Legacy exports with deprecation warnings.

These constants are deprecated. Use settings.* instead:

    # Old (deprecated)
    from src.config import DATA_DIR

    # New (preferred)
    from src.config import settings
    data_dir = settings.paths.data_dir

Note: Deprecation warnings are emitted immediately to help migration.
Set PYTHONWARNINGS=ignore::DeprecationWarning to suppress if needed.
"""

import warnings
from typing import Any


def _get_settings():
    """Lazy import to avoid circular dependency."""
    from src.config import settings
    return settings


def _deprecated(name: str, new_path: str) -> Any:
    """Emit deprecation warning and return the value."""
    warnings.warn(
        f"'{name}' is deprecated. Use 'settings.{new_path}' instead. "
        f"Example: from src.config import settings; settings.{new_path}",
        DeprecationWarning,
        stacklevel=4
    )
    # Navigate the settings object
    settings = _get_settings()
    obj = settings
    for part in new_path.split('.'):
        obj = getattr(obj, part)
    return obj


# Mapping of legacy names to new paths
_LEGACY_MAPPINGS = {
    # Paths
    'PROJECT_ROOT': 'paths.project_root',
    'DATA_DIR': 'paths.data_dir',
    'RAW_DATA_DIR': 'paths.raw_data_dir',
    'INTERIM_DATA_DIR': 'paths.interim_data_dir',
    'PARSED_DATA_DIR': 'paths.parsed_data_dir',
    'EXTRACTED_DATA_DIR': 'paths.extracted_data_dir',
    'PROCESSED_DATA_DIR': 'paths.processed_data_dir',
    'LABELED_DATA_DIR': 'paths.labeled_data_dir',
    'MODELS_DIR': 'paths.models_dir',
    'SRC_DIR': 'paths.src_dir',
    'ANALYSIS_DIR': 'paths.analysis_dir',
    'TAXONOMIES_DIR': 'paths.taxonomies_dir',
    'LOGS_DIR': 'paths.logs_dir',
    'EXTRACTION_LOGS_DIR': 'paths.extraction_logs_dir',
    'RISK_TAXONOMY_PATH': 'paths.risk_taxonomy_path',
    'GOLDEN_DATASET_PATH': 'paths.golden_dataset_path',
    'MODEL_REGISTRY_DIR': 'paths.model_registry_dir',
    'EXPERIMENTS_DIR': 'paths.experiments_dir',
    # SEC Parser
    'SUPPORTED_FORM_TYPES': 'sec_parser.supported_form_types',
    'DEFAULT_FORM_TYPE': 'sec_parser.default_form_type',
    'INPUT_FILE_EXTENSIONS': 'sec_parser.input_file_extensions',
    'PARSE_TABLES': 'sec_parser.parse_tables',
    'PARSE_IMAGES': 'sec_parser.parse_images',
    'SEC_PARSER_VERSION': 'sec_parser.version',
    # Models
    'DEFAULT_MODEL': 'models.default_model',
    'ZERO_SHOT_MODEL': 'models.zero_shot_model',
    # Preprocessing
    'MIN_SEGMENT_LENGTH': 'preprocessing.min_segment_length',
    'MAX_SEGMENT_LENGTH': 'preprocessing.max_segment_length',
    'REMOVE_HTML_TAGS': 'preprocessing.remove_html_tags',
    'NORMALIZE_WHITESPACE': 'preprocessing.normalize_whitespace',
    'REMOVE_PAGE_NUMBERS': 'preprocessing.remove_page_numbers',
    # Extraction
    'MIN_EXTRACTION_CONFIDENCE': 'extraction.min_confidence',
    'ENABLE_AUDIT_LOGGING': 'extraction.enable_audit_logging',
    'EXTRACTION_OUTPUT_FORMAT': 'extraction.output_format',
    'DEFAULT_SECTIONS_TO_EXTRACT': 'extraction.default_sections',
    # SEC Sections
    'SEC_10K_SECTIONS': 'sec_sections.sections_10k',
    'SEC_10Q_SECTIONS': 'sec_sections.sections_10q',
    # Testing
    'ENABLE_GOLDEN_VALIDATION': 'testing.enable_golden_validation',
    # Reproducibility
    'RANDOM_SEED': 'reproducibility.random_seed',
}


def __getattr__(name: str) -> Any:
    """Handle deprecated attribute access."""
    if name in _LEGACY_MAPPINGS:
        return _deprecated(name, _LEGACY_MAPPINGS[name])

    raise AttributeError(f"module 'src.config.legacy' has no attribute '{name}'")


def __dir__():
    """List available legacy names."""
    return list(_LEGACY_MAPPINGS.keys())


__all__ = list(_LEGACY_MAPPINGS.keys())

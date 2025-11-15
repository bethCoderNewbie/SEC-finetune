"""
Global configuration for SEC Filing Analyzer
Provides paths and settings for the application
"""

from pathlib import Path
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent

# Data directories
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
INTERIM_DATA_DIR = DATA_DIR / "interim"
PARSED_DATA_DIR = INTERIM_DATA_DIR / "parsed"  # Parsed SEC filings (JSON format)
EXTRACTED_DATA_DIR = INTERIM_DATA_DIR / "extracted"  # Extracted sections (JSON format)
PROCESSED_DATA_DIR = DATA_DIR / "processed"

# Model directories
MODELS_DIR = PROJECT_ROOT / "models"

# Source directories
SRC_DIR = PROJECT_ROOT / "src"
ANALYSIS_DIR = SRC_DIR / "analysis"
TAXONOMIES_DIR = ANALYSIS_DIR / "taxonomies"

# Logs directory
LOGS_DIR = PROJECT_ROOT / "logs"
EXTRACTION_LOGS_DIR = LOGS_DIR / "extractions"

# Risk taxonomy path
RISK_TAXONOMY_PATH = TAXONOMIES_DIR / "risk_taxonomy.yaml"

# ===========================
# SEC Parser Configuration
# ===========================

# Supported form types
SUPPORTED_FORM_TYPES = ["10-K", "10-Q"]

# Default form type
DEFAULT_FORM_TYPE = "10-K"

# Input file types
# Options: ["html"], ["txt"], or ["html", "txt"] for both
# Note: sec-parser requires HTML format for semantic parsing
# Using .txt files will require a different parsing approach
INPUT_FILE_EXTENSIONS = ["html"]  # Change to ["txt"] or ["html", "txt"] as needed

# Parsing configuration
PARSE_TABLES = True  # Whether to parse tables
PARSE_IMAGES = False  # Whether to extract images

# ===========================
# Model Configuration
# ===========================

# Model for financial text analysis
DEFAULT_MODEL = "ProsusAI/finbert"  # FinBERT for financial text
ZERO_SHOT_MODEL = "facebook/bart-large-mnli"  # Zero-shot classification model

# ===========================
# Preprocessing Configuration
# ===========================

# Segmentation settings
MIN_SEGMENT_LENGTH = 50  # Minimum characters for a valid risk segment
MAX_SEGMENT_LENGTH = 2000  # Maximum characters for a risk segment

# Text cleaning settings
REMOVE_HTML_TAGS = True
NORMALIZE_WHITESPACE = True
REMOVE_PAGE_NUMBERS = True

# ===========================
# Extraction Configuration
# ===========================

# Minimum confidence for extraction acceptance
MIN_EXTRACTION_CONFIDENCE = 0.7

# Enable audit logging
ENABLE_AUDIT_LOGGING = os.getenv("ENABLE_AUDIT_LOGGING", "true").lower() == "true"

# Output format for extracted sections
# Options: "json", "parquet", "both"
EXTRACTION_OUTPUT_FORMAT = os.getenv("EXTRACTION_OUTPUT_FORMAT", "json")

# SEC Section Identifiers (10-K)
SEC_10K_SECTIONS = {
    "part1item1": "Item 1. Business",
    "part1item1a": "Item 1A. Risk Factors",
    "part1item1b": "Item 1B. Unresolved Staff Comments",
    "part1item1c": "Item 1C. Cybersecurity",
    "part2item7": "Item 7. Management's Discussion and Analysis",
    "part2item7a": "Item 7A. Quantitative and Qualitative Disclosures About Market Risk",
    "part2item8": "Item 8. Financial Statements and Supplementary Data",
}

# SEC Section Identifiers (10-Q)
SEC_10Q_SECTIONS = {
    "part1item1": "Item 1. Financial Statements",
    "part1item2": "Item 2. Management's Discussion and Analysis",
    "part2item1a": "Item 1A. Risk Factors",
}

# Default sections to extract (can be overridden per job)
DEFAULT_SECTIONS_TO_EXTRACT = ["part1item1a"]  # Risk Factors by default

# ===========================
# Testing & Validation
# ===========================

# Golden dataset path for validation
GOLDEN_DATASET_PATH = PROJECT_ROOT / "tests" / "fixtures" / "golden_extractions.json"

# Enable golden dataset validation
ENABLE_GOLDEN_VALIDATION = os.getenv("ENABLE_GOLDEN_VALIDATION", "false").lower() == "true"

# ===========================
# Reproducibility
# ===========================

# Random seed for reproducibility
RANDOM_SEED = 42

# Version tracking
SEC_PARSER_VERSION = os.getenv("SEC_PARSER_VERSION", "0.54.0")

# Ensure directories exist
def ensure_directories():
    """Create necessary directories if they don't exist"""
    directories = [
        RAW_DATA_DIR,
        INTERIM_DATA_DIR,
        PARSED_DATA_DIR,
        EXTRACTED_DATA_DIR,
        PROCESSED_DATA_DIR,
        MODELS_DIR,
        LOGS_DIR,
        EXTRACTION_LOGS_DIR,
    ]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

if __name__ == "__main__":
    ensure_directories()
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Data directory: {DATA_DIR}")
    print(f"Risk taxonomy: {RISK_TAXONOMY_PATH}")

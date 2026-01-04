"""
Preprocess Loughran-McDonald Dictionary

This script converts the LM Master Dictionary CSV file to an optimized pickle format.

Benefits of preprocessing:
1. Faster loading (pickle is 10-20x faster than CSV parsing)
2. Smaller file size (compressed binary format)
3. Pre-computed data structures (sets for O(1) lookups)
4. Validated data (ensures all required columns present)

Usage:
    python scripts/feature_engineering/utils/preprocess_lm_dict.py

Output:
    data/dictionary/lm_dictionary_cache.pkl
"""

import sys
import time
from pathlib import Path
import pandas as pd
import pickle
import logging

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.config import settings
from src.features.dictionaries.constants import (
    LM_FEATURE_CATEGORIES,
    LM_CSV_COLUMNS,
    LM_REQUIRED_COLUMNS,
    LM_APPROX_WORD_COUNT,
    LM_DICTIONARY_VERSION
)
from src.features.dictionaries.schemas import LMDictionary, LMDictionaryMetadata

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_csv_dictionary(csv_path: Path) -> pd.DataFrame:
    """
    Load LM dictionary from CSV file.

    Args:
        csv_path: Path to CSV file

    Returns:
        DataFrame with dictionary data

    Raises:
        FileNotFoundError: If CSV doesn't exist
        ValueError: If required columns missing
    """
    if not csv_path.exists():
        raise FileNotFoundError(
            f"LM dictionary CSV not found at {csv_path}. "
            f"Please download it from https://sraf.nd.edu/loughranmcdonald-master-dictionary/"
        )

    logger.info(f"Loading dictionary from {csv_path}")
    df = pd.read_csv(csv_path, encoding='latin1')  # LM dict uses latin1 encoding

    # Validate required columns
    missing = LM_REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    logger.info(f"Loaded {len(df)} words from CSV")
    return df


def build_word_category_mapping(df: pd.DataFrame) -> dict:
    """
    Build efficient word -> categories mapping.

    Args:
        df: DataFrame with dictionary data

    Returns:
        Dictionary mapping words to sets of categories
    """
    logger.info("Building word-to-categories mapping...")
    word_categories = {}

    for _, row in df.iterrows():
        word = str(row['Word']).strip().upper()
        categories = set()

        # Check each category
        for category in LM_FEATURE_CATEGORIES:
            col_name = LM_CSV_COLUMNS.get(category.lower(), category)
            if col_name in df.columns and row.get(col_name, 0) != 0:
                categories.add(category)

        if categories:  # Only include words with at least one category
            word_categories[word] = categories

    logger.info(f"Mapped {len(word_categories)} words to categories")
    return word_categories


def compute_category_counts(word_categories: dict) -> dict:
    """
    Compute number of words in each category.

    Args:
        word_categories: Mapping of words to category sets

    Returns:
        Dictionary of category counts
    """
    category_counts = {cat: 0 for cat in LM_FEATURE_CATEGORIES}

    for categories in word_categories.values():
        for category in categories:
            category_counts[category] += 1

    return category_counts


def preprocess_dictionary(csv_path: Path, output_path: Path) -> None:
    """
    Convert CSV dictionary to optimized pickle format.

    Args:
        csv_path: Path to input CSV file
        output_path: Path to output pickle file
    """
    start_time = time.time()

    # Load CSV
    df = load_csv_dictionary(csv_path)

    # Build word-to-categories mapping
    word_categories = build_word_category_mapping(df)

    # Compute statistics
    category_counts = compute_category_counts(word_categories)

    # Create metadata
    load_time = time.time() - start_time
    metadata = LMDictionaryMetadata(
        version=LM_DICTIONARY_VERSION,
        total_words=len(word_categories),
        category_counts=category_counts,
        load_time_seconds=load_time,
        source_file=str(csv_path),
        categories=LM_FEATURE_CATEGORIES
    )

    # Create dictionary object
    dictionary = LMDictionary(
        words=word_categories,
        metadata=metadata
    )

    # Save to pickle
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'wb') as f:
        pickle.dump(dictionary, f, protocol=pickle.HIGHEST_PROTOCOL)

    file_size_mb = output_path.stat().st_size / (1024 * 1024)

    logger.info(f"\n{'='*60}")
    logger.info("Dictionary preprocessing completed successfully!")
    logger.info(f"{'='*60}")
    logger.info(f"Total words: {len(word_categories):,}")
    logger.info(f"Processing time: {load_time:.2f}s")
    logger.info(f"Output file: {output_path}")
    logger.info(f"Output size: {file_size_mb:.2f} MB")
    logger.info(f"\nCategory counts:")
    for category in LM_FEATURE_CATEGORIES:
        count = category_counts.get(category, 0)
        logger.info(f"  {category:15s}: {count:5,} words")
    logger.info(f"{'='*60}\n")


def verify_cache(cache_path: Path) -> bool:
    """
    Verify that cached dictionary loads correctly.

    Args:
        cache_path: Path to cached pickle file

    Returns:
        True if verification successful, False otherwise
    """
    try:
        logger.info(f"Verifying cached dictionary at {cache_path}")
        start_time = time.time()

        with open(cache_path, 'rb') as f:
            dictionary = pickle.load(f)

        load_time = time.time() - start_time

        # Validate structure
        assert isinstance(dictionary, LMDictionary), "Invalid dictionary type"
        assert len(dictionary.words) > 0, "Dictionary is empty"
        assert dictionary.metadata.total_words == len(dictionary.words), "Word count mismatch"

        # Check word count is reasonable
        if len(dictionary.words) < LM_APPROX_WORD_COUNT * 0.8:
            logger.warning(
                f"Dictionary has {len(dictionary.words)} words, "
                f"expected ~{LM_APPROX_WORD_COUNT}"
            )

        logger.info(f"✓ Verification successful! Load time: {load_time:.3f}s")
        logger.info(f"✓ Dictionary contains {len(dictionary.words):,} words")
        return True

    except Exception as e:
        logger.error(f"✗ Verification failed: {e}")
        return False


def main():
    """Main preprocessing pipeline."""
    logger.info("Starting LM Dictionary preprocessing...")

    # Get paths from settings
    csv_path = settings.paths.lm_dictionary_csv
    cache_path = settings.paths.lm_dictionary_cache

    logger.info(f"Input CSV: {csv_path}")
    logger.info(f"Output cache: {cache_path}")

    # Check if CSV exists
    if not csv_path.exists():
        logger.error(
            f"\n{'='*60}\n"
            f"ERROR: LM Dictionary CSV not found!\n"
            f"{'='*60}\n"
            f"Expected location: {csv_path}\n\n"
            f"Please download the dictionary from:\n"
            f"https://sraf.nd.edu/loughranmcdonald-master-dictionary/\n\n"
            f"Save it as: {csv_path.name}\n"
            f"In directory: {csv_path.parent}\n"
            f"{'='*60}\n"
        )
        sys.exit(1)

    # Preprocess dictionary
    try:
        preprocess_dictionary(csv_path, cache_path)
    except Exception as e:
        logger.error(f"Preprocessing failed: {e}", exc_info=True)
        sys.exit(1)

    # Verify cache
    if not verify_cache(cache_path):
        logger.error("Cache verification failed!")
        sys.exit(1)

    logger.info("\n✓ Preprocessing completed successfully!")
    logger.info(f"✓ Cache saved to: {cache_path}")
    logger.info(f"\nYou can now delete the CSV file to save space:")
    logger.info(f"  rm \"{csv_path}\"")


if __name__ == "__main__":
    main()

"""
Feature Engineering: Extract Features from Risk Factors

Purpose: Generate features for ML models from extracted risk text
Stage: 4 - Feature Engineering
Input: data/interim/ - Extracted and cleaned risk factors
Output: data/processed/ - Feature matrices, embeddings

Usage:
    python scripts/feature_engineering/extract_features.py
    python scripts/feature_engineering/extract_features.py --embedding-model sentence-transformers
"""

import argparse
from pathlib import Path
import sys
from typing import List, Dict
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import settings, ensure_directories, RunContext

# Directory shortcuts from settings (avoids deprecated legacy constants)
EXTRACTED_DATA_DIR = settings.paths.extracted_data_dir
PROCESSED_DATA_DIR = settings.paths.processed_data_dir
from src.preprocessing.cleaning import TextCleaner
from src.features import SentimentAnalyzer, ReadabilityAnalyzer


def extract_text_features(texts: List[str]) -> Dict[str, List]:
    """
    Extract text features including sentiment and readability.

    This function:
    1. Cleans text using TextCleaner (removes HTML, boilerplate, normalizes whitespace)
    2. Extracts sentiment features using LM dictionary
    3. Extracts readability/complexity features
    4. Returns structured feature dictionaries

    Args:
        texts: List of risk factor texts (raw or pre-extracted)

    Returns:
        Dictionary with sentiment_features and readability_features lists
    """
    print(f"Extracting features from {len(texts)} texts...")

    # Initialize analyzers
    print("  - Initializing TextCleaner...")
    cleaner = TextCleaner(
        use_lemmatization=False,      # Don't lemmatize (changes word meaning for readability)
        remove_stopwords=False,        # Keep stopwords (affect readability metrics)
        remove_punctuation=False,      # CRITICAL: Keep punctuation for sentence detection
        remove_numbers=False           # Keep numbers (part of document)
    )

    print("  - Initializing SentimentAnalyzer...")
    sentiment_analyzer = SentimentAnalyzer()

    print("  - Initializing ReadabilityAnalyzer...")
    readability_analyzer = ReadabilityAnalyzer()

    # Extract features for each text
    sentiment_features = []
    readability_features = []

    for i, text in enumerate(texts):
        if (i + 1) % 10 == 0 or i == 0:
            print(f"  - Processing text {i+1}/{len(texts)}...")

        # Step 1: Clean text (remove HTML, boilerplate, normalize whitespace)
        cleaned_text = cleaner.clean_html_text(text)

        # Step 2: Extract sentiment features
        sentiment_feat = sentiment_analyzer.extract_features(cleaned_text)
        sentiment_features.append(sentiment_feat.to_dict())

        # Step 3: Extract readability features
        readability_feat = readability_analyzer.extract_features(cleaned_text)
        readability_features.append(readability_feat.model_dump())

    print(f"  ✓ Extracted {len(sentiment_features)} sentiment feature sets")
    print(f"  ✓ Extracted {len(readability_features)} readability feature sets")

    # TODO: Add TF-IDF vectors, NER features, POS distributions

    return {
        'sentiment_features': sentiment_features,
        'readability_features': readability_features
    }


def generate_embeddings(texts: List[str], model_name: str = "sentence-transformers") -> np.ndarray:
    """
    Generate embeddings for risk factors

    Args:
        texts: List of risk factor texts
        model_name: Name of embedding model to use

    Returns:
        Embedding matrix (n_samples, embedding_dim)
    """
    # TODO: Implement embedding generation
    # Options:
    # - Sentence-BERT (sentence-transformers)
    # - OpenAI embeddings
    # - Custom fine-tuned model
    #
    # Example with sentence-transformers:
    # from sentence_transformers import SentenceTransformer
    # model = SentenceTransformer('all-MiniLM-L6-v2')
    # embeddings = model.encode(texts)

    print(f"[TODO] Generate embeddings using {model_name}")
    return np.array([])


def extract_metadata_features(metadata_list: List[Dict]) -> np.ndarray:
    """
    Extract features from filing metadata

    Args:
        metadata_list: List of metadata dictionaries

    Returns:
        Feature matrix (n_samples, n_features)
    """
    # TODO: Implement metadata feature extraction
    # - Company size (market cap, revenue)
    # - Industry sector
    # - Filing year/quarter
    # - YoY changes in risk factors
    # - Company age

    print("[TODO] Implement metadata feature extraction")
    return np.array([])


def save_features(features: Dict, output_dir: Path):
    """
    Save extracted features in JSON format.

    Args:
        features: Dictionary of feature lists/arrays
        output_dir: Directory to save features
    """
    import json

    output_dir.mkdir(parents=True, exist_ok=True)

    # Save sentiment features
    if 'sentiment_features' in features and features['sentiment_features']:
        sentiment_path = output_dir / 'sentiment_features.json'
        with open(sentiment_path, 'w', encoding='utf-8') as f:
            json.dump(features['sentiment_features'], f, indent=2)
        print(f"  ✓ Saved sentiment features to {sentiment_path}")

    # Save readability features
    if 'readability_features' in features and features['readability_features']:
        readability_path = output_dir / 'readability_features.json'
        with open(readability_path, 'w', encoding='utf-8') as f:
            json.dump(features['readability_features'], f, indent=2)
        print(f"  ✓ Saved readability features to {readability_path}")

    # Save embeddings (if present)
    if 'embeddings' in features and len(features['embeddings']) > 0:
        embeddings_path = output_dir / 'embeddings.npz'
        np.savez_compressed(embeddings_path, embeddings=features['embeddings'])
        print(f"  ✓ Saved embeddings to {embeddings_path}")

    # Save metadata features (if present)
    if 'metadata_features' in features and len(features['metadata_features']) > 0:
        metadata_path = output_dir / 'metadata_features.npz'
        np.savez_compressed(metadata_path, metadata=features['metadata_features'])
        print(f"  ✓ Saved metadata features to {metadata_path}")

    print(f"\n✓ All features saved to {output_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="Extract features from risk factors"
    )
    parser.add_argument(
        '--input-dir',
        type=str,
        default=str(EXTRACTED_DATA_DIR),
        help='Directory containing extracted risk factors'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default=str(PROCESSED_DATA_DIR),
        help='Output directory for features'
    )
    parser.add_argument(
        '--embedding-model',
        type=str,
        default='sentence-transformers',
        choices=['sentence-transformers', 'openai', 'custom'],
        help='Embedding model to use'
    )
    parser.add_argument(
        '--include-metadata',
        action='store_true',
        help='Include metadata features'
    )

    args = parser.parse_args()

    ensure_directories()

    print("Feature Engineering Pipeline")
    print("=" * 80)

    # TODO: Load risk factor data
    texts = []
    metadata = []

    # Extract text features
    print("\n1. Extracting text features...")
    text_features = extract_text_features(texts)

    # Generate embeddings
    print("\n2. Generating embeddings...")
    embeddings = generate_embeddings(texts, args.embedding_model)

    # Extract metadata features
    if args.include_metadata:
        print("\n3. Extracting metadata features...")
        metadata_features = extract_metadata_features(metadata)

    # Save features
    print("\n4. Saving features...")
    features = {
        'text_features': text_features,
        'embeddings': embeddings
    }
    if args.include_metadata:
        features['metadata_features'] = metadata_features

    save_features(features, Path(args.output_dir))

    print("\n" + "=" * 80)
    print("Feature extraction complete!")


if __name__ == "__main__":
    main()

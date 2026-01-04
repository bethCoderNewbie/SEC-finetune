"""
Topic Modeling Feature Extraction Demo

This script demonstrates how to:
1. Train an LDA model on a corpus of Item 1A risk sections
2. Extract topic modeling features from new documents
3. Use these features for downstream classification

Usage:
    python scripts/feature_engineering/topic_modeling_demo.py
"""

import json
import logging
from pathlib import Path
from typing import List, Dict

from src.config import settings
from src.features.topic_modeling import LDATrainer, TopicModelingAnalyzer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_item1a_corpus(extracted_data_dir: Path) -> List[Dict]:
    """
    Load Item 1A sections from extracted data.

    Args:
        extracted_data_dir: Path to extracted data directory

    Returns:
        List of documents with metadata
    """
    documents = []

    # Find all JSON files with extracted Item 1A sections
    for json_file in extracted_data_dir.glob("*_extracted.json"):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

                # Extract Item 1A section if available
                if 'sections' in data and 'part1item1a' in data['sections']:
                    item1a = data['sections']['part1item1a']
                    documents.append({
                        'text': item1a.get('text', ''),
                        'company': data.get('company', 'unknown'),
                        'filing_date': data.get('filing_date', 'unknown'),
                        'form_type': data.get('form_type', '10-K'),
                    })
        except Exception as e:
            logger.warning(f"Failed to load {json_file}: {e}")

    logger.info(f"Loaded {len(documents)} Item 1A sections")
    return documents


def train_lda_model(
    documents: List[str],
    num_topics: int = 15,
    save_path: Path | None = None
) -> LDATrainer:
    """
    Train LDA model on corpus.

    Args:
        documents: List of text documents
        num_topics: Number of topics to discover
        save_path: Path to save trained model

    Returns:
        Trained LDATrainer instance
    """
    logger.info(f"Training LDA model with {num_topics} topics...")

    # Initialize trainer
    trainer = LDATrainer(
        num_topics=num_topics,
        passes=10,
        iterations=100,
        random_state=42,
    )

    # Train model
    model_info = trainer.train(
        documents=documents,
        save_path=save_path,
        compute_coherence=True,
    )

    # Print model quality metrics
    logger.info(f"Model trained successfully!")
    logger.info(f"  Perplexity: {model_info.perplexity:.4f}")
    logger.info(f"  Coherence: {model_info.coherence_score:.4f}")
    logger.info(f"  Vocabulary size: {model_info.vocabulary_size}")

    # Print discovered topics
    trainer.print_topics(num_words=10)

    return trainer


def extract_features_from_corpus(
    analyzer: TopicModelingAnalyzer,
    documents: List[Dict]
) -> List[Dict]:
    """
    Extract topic modeling features from corpus.

    Args:
        analyzer: Trained TopicModelingAnalyzer
        documents: List of documents with metadata

    Returns:
        List of feature dictionaries
    """
    logger.info("Extracting topic modeling features...")

    results = []
    for doc in documents:
        # Extract features
        features = analyzer.extract_features(doc['text'])

        # Convert to feature vector
        feature_vector = features.to_feature_vector(analyzer.num_topics)

        # Build result
        result = {
            'company': doc.get('company'),
            'filing_date': doc.get('filing_date'),
            'dominant_topic_id': features.dominant_topic_id,
            'dominant_topic_probability': features.dominant_topic_probability,
            'topic_entropy': features.topic_entropy,
            'num_significant_topics': features.num_significant_topics,
            'topic_probabilities': features.topic_probabilities,
            'topic_vector': feature_vector,
        }

        results.append(result)

    logger.info(f"Extracted features from {len(results)} documents")
    return results


def save_features(features: List[Dict], output_path: Path) -> None:
    """Save extracted features to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(features, f, indent=2)

    logger.info(f"Saved features to {output_path}")


def main():
    """Main execution flow."""
    logger.info("=" * 80)
    logger.info("Topic Modeling Feature Extraction Demo")
    logger.info("=" * 80)

    # Step 1: Load corpus
    logger.info("\nStep 1: Loading Item 1A corpus...")
    extracted_dir = settings.paths.extracted_data_dir
    corpus_docs = load_item1a_corpus(extracted_dir)

    if len(corpus_docs) == 0:
        logger.error(
            "No Item 1A sections found in extracted data. "
            "Please run section extraction first."
        )
        return

    # Extract just the text for training
    corpus_texts = [doc['text'] for doc in corpus_docs]

    # Step 2: Train LDA model
    logger.info("\nStep 2: Training LDA model...")
    model_path = settings.paths.models_dir / "lda_item1a"
    trainer = train_lda_model(
        documents=corpus_texts,
        num_topics=15,
        save_path=model_path
    )

    # Step 3: Load trained model and create analyzer
    logger.info("\nStep 3: Creating topic modeling analyzer...")
    analyzer = TopicModelingAnalyzer(trainer=trainer)

    # Step 4: Extract features from corpus
    logger.info("\nStep 4: Extracting features...")
    features = extract_features_from_corpus(analyzer, corpus_docs)

    # Step 5: Save features
    logger.info("\nStep 5: Saving features...")
    output_path = settings.paths.features_data_dir / "topic_modeling_features.json"
    save_features(features, output_path)

    # Print example
    logger.info("\nExample feature output:")
    logger.info("=" * 80)
    if features:
        example = features[0]
        logger.info(f"Company: {example['company']}")
        logger.info(f"Filing Date: {example['filing_date']}")
        logger.info(f"Dominant Topic: {example['dominant_topic_id']}")
        logger.info(f"Dominant Prob: {example['dominant_topic_probability']:.4f}")
        logger.info(f"Topic Entropy: {example['topic_entropy']:.4f}")
        logger.info(f"Significant Topics: {example['num_significant_topics']}")
        logger.info(f"\nTopic Probabilities:")
        for topic_id, prob in sorted(
            example['topic_probabilities'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]:
            logger.info(f"  Topic {topic_id}: {prob:.4f}")

    logger.info("\n" + "=" * 80)
    logger.info("Demo complete!")
    logger.info("=" * 80)
    logger.info(f"\nTrained model saved to: {model_path}")
    logger.info(f"Features saved to: {output_path}")
    logger.info("\nNext steps:")
    logger.info("1. Inspect topic descriptions in model output")
    logger.info("2. Assign human-readable labels to topics")
    logger.info("3. Use topic features as inputs to your classifier")


if __name__ == "__main__":
    main()

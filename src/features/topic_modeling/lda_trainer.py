"""
LDA Model Training Utilities

This module provides utilities for training and managing LDA topic models
on SEC filing risk sections (Item 1A).

Usage:
    from src.features.topic_modeling.lda_trainer import LDATrainer

    # Train a new model
    trainer = LDATrainer(num_topics=15)
    model_info = trainer.train(documents, save_path="models/lda_item1a")

    # Load existing model
    trainer = LDATrainer.load("models/lda_item1a")
"""

import logging
import pickle
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any

try:
    import gensim
    from gensim import corpora
    from gensim.models import LdaModel, CoherenceModel
    from gensim.parsing.preprocessing import preprocess_string, strip_tags, strip_punctuation, \
        strip_multiple_whitespaces, strip_numeric, remove_stopwords, strip_short
    GENSIM_AVAILABLE = True
except ImportError:
    GENSIM_AVAILABLE = False

try:
    import nltk
    from nltk.corpus import stopwords
    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False

from .constants import (
    DEFAULT_NUM_TOPICS,
    DEFAULT_PASSES,
    DEFAULT_ITERATIONS,
    DEFAULT_RANDOM_STATE,
    DEFAULT_ALPHA,
    DEFAULT_ETA,
    NO_BELOW,
    NO_ABOVE,
    KEEP_N,
    FINANCIAL_STOPWORDS,
    LDA_MODEL_FILENAME,
    DICTIONARY_FILENAME,
    TOPIC_LABELS_FILENAME,
    RECOMMENDED_MIN_CORPUS_SIZE,
)
from .schemas import LDAModelInfo

logger = logging.getLogger(__name__)


class LDATrainer:
    """
    LDA Topic Model Trainer for SEC Risk Factors.

    This class handles:
    1. Text preprocessing and tokenization
    2. Building vocabulary (gensim Dictionary)
    3. Creating document-term matrix (bag-of-words corpus)
    4. Training LDA model
    5. Evaluating model quality (perplexity, coherence)
    6. Saving/loading trained models

    Usage:
        # Train new model
        trainer = LDATrainer(num_topics=15)
        model_info = trainer.train(documents, save_path="models/lda")

        # Load existing model
        trainer = LDATrainer.load("models/lda")
        features = trainer.extract_features(new_document)
    """

    def __init__(
        self,
        num_topics: int = DEFAULT_NUM_TOPICS,
        passes: int = DEFAULT_PASSES,
        iterations: int = DEFAULT_ITERATIONS,
        random_state: int = DEFAULT_RANDOM_STATE,
        alpha: str | float = DEFAULT_ALPHA,
        eta: str | float = DEFAULT_ETA,
        custom_stopwords: Optional[List[str]] = None,
    ):
        """
        Initialize LDA trainer.

        Args:
            num_topics: Number of topics to discover
            passes: Number of training passes through corpus
            iterations: Number of iterations during training
            random_state: Random seed for reproducibility
            alpha: Document-topic density ('auto' or float)
            eta: Topic-word density ('auto' or float)
            custom_stopwords: Additional stopwords beyond defaults
        """
        # Validate dependencies
        if not GENSIM_AVAILABLE:
            raise ImportError(
                "gensim is required for topic modeling. "
                "Install it with: pip install gensim"
            )

        if not NLTK_AVAILABLE:
            logger.warning(
                "nltk not available. Install with: pip install nltk"
            )

        # Model parameters
        self.num_topics = num_topics
        self.passes = passes
        self.iterations = iterations
        self.random_state = random_state
        self.alpha = alpha
        self.eta = eta

        # Stopwords
        self.stopwords = self._load_stopwords(custom_stopwords)

        # Model components (initialized during training or loading)
        self.dictionary: Optional[corpora.Dictionary] = None
        self.lda_model: Optional[LdaModel] = None
        self.topic_labels: Optional[Dict[int, str]] = None
        self.model_info: Optional[LDAModelInfo] = None

        logger.info(
            f"Initialized LDATrainer with {num_topics} topics, "
            f"{passes} passes, {iterations} iterations"
        )

    def train(
        self,
        documents: List[str],
        save_path: Optional[Path | str] = None,
        compute_coherence: bool = True,
    ) -> LDAModelInfo:
        """
        Train LDA model on corpus of documents.

        Args:
            documents: List of text documents (e.g., Item 1A sections)
            save_path: Optional path to save trained model
            compute_coherence: Whether to compute coherence score (slower)

        Returns:
            LDAModelInfo with training metadata

        Raises:
            ValueError: If corpus is too small
        """
        if len(documents) < RECOMMENDED_MIN_CORPUS_SIZE:
            logger.warning(
                f"Corpus size ({len(documents)}) is below recommended minimum "
                f"({RECOMMENDED_MIN_CORPUS_SIZE}). Results may be unreliable."
            )

        logger.info(f"Training LDA model on {len(documents)} documents...")

        # Step 1: Preprocess documents
        logger.info("Preprocessing documents...")
        processed_docs = [self._preprocess_text(doc) for doc in documents]
        processed_docs = [doc for doc in processed_docs if len(doc) > 0]

        if len(processed_docs) == 0:
            raise ValueError("No valid documents after preprocessing")

        # Step 2: Build vocabulary
        logger.info("Building vocabulary...")
        self.dictionary = corpora.Dictionary(processed_docs)

        # Filter extremes
        self.dictionary.filter_extremes(
            no_below=NO_BELOW,
            no_above=NO_ABOVE,
            keep_n=KEEP_N
        )

        logger.info(
            f"Vocabulary size: {len(self.dictionary)} "
            f"(after filtering)"
        )

        # Step 3: Create bag-of-words corpus
        logger.info("Creating bag-of-words corpus...")
        corpus = [self.dictionary.doc2bow(doc) for doc in processed_docs]

        # Step 4: Train LDA model
        logger.info(f"Training LDA with {self.num_topics} topics...")
        self.lda_model = LdaModel(
            corpus=corpus,
            id2word=self.dictionary,
            num_topics=self.num_topics,
            random_state=self.random_state,
            passes=self.passes,
            iterations=self.iterations,
            alpha=self.alpha,
            eta=self.eta,
            per_word_topics=True,
        )

        logger.info("LDA training complete!")

        # Step 5: Evaluate model
        perplexity = self.lda_model.log_perplexity(corpus)
        logger.info(f"Model perplexity: {perplexity:.4f}")

        coherence_score = None
        if compute_coherence:
            logger.info("Computing coherence score...")
            coherence_model = CoherenceModel(
                model=self.lda_model,
                texts=processed_docs,
                dictionary=self.dictionary,
                coherence='c_v'
            )
            coherence_score = coherence_model.get_coherence()
            logger.info(f"Coherence score: {coherence_score:.4f}")

        # Step 6: Extract top words for each topic
        topic_top_words = {}
        for topic_id in range(self.num_topics):
            top_words = self.lda_model.show_topic(topic_id, topn=20)
            topic_top_words[topic_id] = top_words

        # Step 7: Create model info
        self.model_info = LDAModelInfo(
            num_topics=self.num_topics,
            num_documents=len(documents),
            vocabulary_size=len(self.dictionary),
            passes=self.passes,
            iterations=self.iterations,
            alpha=self.alpha,
            eta=self.eta,
            perplexity=perplexity,
            coherence_score=coherence_score,
            topic_top_words=topic_top_words,
            topic_labels=self.topic_labels,
        )

        # Step 8: Save model if path provided
        if save_path:
            self.save(save_path)

        return self.model_info

    def save(self, save_path: Path | str) -> None:
        """
        Save trained model to disk.

        Args:
            save_path: Directory to save model files
        """
        if self.lda_model is None or self.dictionary is None:
            raise ValueError("No trained model to save. Train a model first.")

        save_path = Path(save_path)
        save_path.mkdir(parents=True, exist_ok=True)

        # Save LDA model
        model_path = save_path / LDA_MODEL_FILENAME
        with open(model_path, 'wb') as f:
            pickle.dump(self.lda_model, f)
        logger.info(f"Saved LDA model to {model_path}")

        # Save dictionary
        dict_path = save_path / DICTIONARY_FILENAME
        with open(dict_path, 'wb') as f:
            pickle.dump(self.dictionary, f)
        logger.info(f"Saved dictionary to {dict_path}")

        # Save topic labels if available
        if self.topic_labels:
            import json
            labels_path = save_path / TOPIC_LABELS_FILENAME
            with open(labels_path, 'w') as f:
                json.dump(self.topic_labels, f, indent=2)
            logger.info(f"Saved topic labels to {labels_path}")

        # Save model info
        if self.model_info:
            info_path = save_path / "model_info.json"
            with open(info_path, 'w') as f:
                import json
                json.dump(self.model_info.model_dump(), f, indent=2, default=str)
            logger.info(f"Saved model info to {info_path}")

    @classmethod
    def load(cls, load_path: Path | str) -> "LDATrainer":
        """
        Load trained model from disk.

        Args:
            load_path: Directory containing saved model files

        Returns:
            LDATrainer instance with loaded model
        """
        load_path = Path(load_path)

        if not load_path.exists():
            raise FileNotFoundError(f"Model directory not found: {load_path}")

        # Load LDA model
        model_path = load_path / LDA_MODEL_FILENAME
        with open(model_path, 'rb') as f:
            lda_model = pickle.load(f)
        logger.info(f"Loaded LDA model from {model_path}")

        # Load dictionary
        dict_path = load_path / DICTIONARY_FILENAME
        with open(dict_path, 'rb') as f:
            dictionary = pickle.load(f)
        logger.info(f"Loaded dictionary from {dict_path}")

        # Create trainer instance
        trainer = cls(num_topics=lda_model.num_topics)
        trainer.lda_model = lda_model
        trainer.dictionary = dictionary

        # Load topic labels if available
        labels_path = load_path / TOPIC_LABELS_FILENAME
        if labels_path.exists():
            import json
            with open(labels_path, 'r') as f:
                # Convert string keys back to int
                labels_dict = json.load(f)
                trainer.topic_labels = {int(k): v for k, v in labels_dict.items()}
            logger.info(f"Loaded topic labels from {labels_path}")

        logger.info("Model loaded successfully")
        return trainer

    def get_document_topics(
        self,
        document: str,
        minimum_probability: float = 0.01
    ) -> List[Tuple[int, float]]:
        """
        Get topic distribution for a single document.

        Args:
            document: Text document to analyze
            minimum_probability: Minimum probability threshold

        Returns:
            List of (topic_id, probability) tuples
        """
        if self.lda_model is None or self.dictionary is None:
            raise ValueError("Model not trained or loaded")

        # Preprocess
        processed = self._preprocess_text(document)

        if len(processed) == 0:
            logger.warning("Document is empty after preprocessing")
            return []

        # Convert to bag-of-words
        bow = self.dictionary.doc2bow(processed)

        # Get topic distribution
        topics = self.lda_model.get_document_topics(
            bow,
            minimum_probability=minimum_probability
        )

        return sorted(topics, key=lambda x: x[1], reverse=True)

    def print_topics(self, num_words: int = 10) -> None:
        """
        Print human-readable topic descriptions.

        Args:
            num_words: Number of top words to show per topic
        """
        if self.lda_model is None:
            raise ValueError("Model not trained or loaded")

        print(f"\nDiscovered Topics (n={self.num_topics}):")
        print("=" * 80)

        for topic_id in range(self.num_topics):
            # Get label if available
            label = self.topic_labels.get(topic_id, f"Topic {topic_id}") if self.topic_labels else f"Topic {topic_id}"

            # Get top words
            top_words = self.lda_model.show_topic(topic_id, topn=num_words)
            words_str = ", ".join([f"{word}({weight:.3f})" for word, weight in top_words])

            print(f"\n{label}:")
            print(f"  {words_str}")

        print("\n" + "=" * 80)

    def _preprocess_text(self, text: str) -> List[str]:
        """
        Preprocess text for LDA training.

        Steps:
        1. Lowercase
        2. Remove HTML tags, punctuation, numbers
        3. Remove stopwords
        4. Tokenize
        5. Filter short words

        Args:
            text: Input text

        Returns:
            List of preprocessed tokens
        """
        if not text or len(text.strip()) == 0:
            return []

        # Define custom preprocessing filters
        CUSTOM_FILTERS = [
            lambda x: x.lower(),  # Lowercase
            strip_tags,  # Remove HTML
            strip_punctuation,  # Remove punctuation
            strip_multiple_whitespaces,  # Normalize whitespace
            strip_numeric,  # Remove numbers
            remove_stopwords,  # Remove common stopwords
            strip_short,  # Remove short words (< 3 chars)
        ]

        # Apply gensim preprocessing
        tokens = preprocess_string(text, CUSTOM_FILTERS)

        # Additional filtering: remove custom financial stopwords
        tokens = [t for t in tokens if t not in self.stopwords]

        return tokens

    def _load_stopwords(self, custom_stopwords: Optional[List[str]] = None) -> set:
        """
        Load stopword list (NLTK + custom financial terms).

        Args:
            custom_stopwords: Additional user-provided stopwords

        Returns:
            Set of stopwords
        """
        stopwords_set = set(FINANCIAL_STOPWORDS)

        # Add NLTK English stopwords if available
        if NLTK_AVAILABLE:
            try:
                nltk_stopwords = stopwords.words('english')
                stopwords_set.update(nltk_stopwords)
            except LookupError:
                logger.warning(
                    "NLTK stopwords not downloaded. "
                    "Run: python -m nltk.downloader stopwords"
                )

        # Add custom stopwords
        if custom_stopwords:
            stopwords_set.update(custom_stopwords)

        logger.info(f"Loaded {len(stopwords_set)} stopwords")
        return stopwords_set

"""
Topic Modeling Constants and Configuration

This module defines constants for LDA-based topic modeling
of SEC filing risk sections (Item 1A).
"""

from typing import List

# ===========================
# Module Version
# ===========================
TOPIC_MODELING_MODULE_VERSION = "0.1.0"

# ===========================
# Default LDA Parameters
# ===========================
DEFAULT_NUM_TOPICS = 15
"""Default number of topics to discover (can range from 10-30 for Item 1A sections)"""

DEFAULT_PASSES = 10
"""Number of training passes through the corpus"""

DEFAULT_ITERATIONS = 100
"""Number of iterations during training"""

DEFAULT_RANDOM_STATE = 42
"""Random seed for reproducibility"""

DEFAULT_ALPHA = "auto"
"""Document-topic density (auto = learned from data)"""

DEFAULT_ETA = "auto"
"""Topic-word density (auto = learned from data)"""

DEFAULT_MIN_PROBABILITY = 0.01
"""Minimum probability threshold for topic assignment"""

DEFAULT_PER_WORD_TOPICS = True
"""Whether to compute per-word topic distributions"""

# ===========================
# Preprocessing Parameters
# ===========================
MIN_WORD_LENGTH = 3
"""Minimum word length to include in vocabulary"""

MAX_WORD_LENGTH = 30
"""Maximum word length to include in vocabulary"""

MIN_DOCUMENT_FREQUENCY = 2
"""Minimum number of documents a word must appear in"""

MAX_DOCUMENT_FREQUENCY = 0.7
"""Maximum fraction of documents a word can appear in"""

NO_BELOW = 2
"""Filter out tokens appearing in less than no_below documents"""

NO_ABOVE = 0.7
"""Filter out tokens appearing in more than no_above fraction of documents"""

KEEP_N = 10000
"""Keep only the top N most frequent tokens"""

# ===========================
# Common Risk Topics
# ===========================
# These are example topic labels discovered from SEC 10-K Item 1A analysis
# The actual topics will be learned from your corpus
COMMON_RISK_TOPICS: List[str] = [
    "cybersecurity_data_privacy",
    "regulatory_compliance",
    "supply_chain_logistics",
    "market_competition",
    "financial_liquidity",
    "intellectual_property",
    "legal_litigation",
    "operational_disruption",
    "economic_conditions",
    "technology_innovation",
    "environmental_climate",
    "geopolitical_trade",
    "human_capital_talent",
    "customer_concentration",
    "product_liability",
]

# ===========================
# Financial Domain Stopwords
# ===========================
# Additional stopwords specific to SEC filings (beyond standard English stopwords)
FINANCIAL_STOPWORDS: List[str] = [
    # Legal/Boilerplate
    "may", "could", "would", "might", "pursuant", "thereof", "herein", "hereof",
    "therein", "hereby", "thereto", "whereas", "aforementioned",
    # Common SEC terms
    "sec", "securities", "exchange", "commission", "filing", "form",
    "item", "part", "section", "include", "including", "includes",
    # Generic business terms that don't add topic value
    "business", "company", "companies", "operations", "operating",
    "result", "results", "period", "periods", "year", "years",
    "fiscal", "quarter", "annual", "market", "markets",
    # Risk disclosure boilerplate
    "risk", "risks", "factor", "factors", "discussion", "analysis",
    "forward", "looking", "statements", "actual", "future",
    "estimate", "estimates", "believe", "believes", "expect", "expects",
]

# ===========================
# Model Persistence
# ===========================
LDA_MODEL_FILENAME = "lda_model.pkl"
"""Filename for saved LDA model"""

DICTIONARY_FILENAME = "lda_dictionary.pkl"
"""Filename for saved gensim Dictionary"""

CORPUS_FILENAME = "lda_corpus.pkl"
"""Filename for saved document-term matrix"""

TOPIC_LABELS_FILENAME = "topic_labels.json"
"""Filename for human-readable topic labels"""

# ===========================
# Feature Engineering
# ===========================
TOPIC_FEATURE_PREFIX = "topic_"
"""Prefix for topic exposure features (e.g., topic_0, topic_1, ...)"""

DOMINANT_TOPIC_THRESHOLD = 0.25
"""Minimum probability to consider a topic as dominant for a document"""

# ===========================
# Training Recommendations
# ===========================
RECOMMENDED_MIN_CORPUS_SIZE = 50
"""Minimum number of documents recommended for training LDA"""

RECOMMENDED_OPTIMAL_CORPUS_SIZE = 200
"""Optimal number of documents for reliable topic discovery"""

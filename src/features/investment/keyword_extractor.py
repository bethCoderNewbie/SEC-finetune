"""
Keyword Extractor.

Combines scikit-learn TF-IDF with KeyBERT for keyword/keyphrase extraction.
TF-IDF is fit on all section texts within a filing for corpus-relative scoring.
KeyBERT uses the all-MiniLM-L6-v2 sentence-transformer model.
"""

import logging
from typing import Dict, List, Optional, Tuple

from sklearn.feature_extraction.text import TfidfVectorizer, ENGLISH_STOP_WORDS

from src.config import settings
from .schemas import KeywordResult

logger = logging.getLogger(__name__)



class KeywordExtractor:
    """
    TF-IDF + KeyBERT keyword extractor.

    Usage:
        extractor = KeywordExtractor()
        # Fit TF-IDF on all section texts in the filing
        extractor.fit_tfidf(["section1 text...", "section2 text..."])
        # Extract keywords for a single section
        result = extractor.extract("section1 text...", section_index=0)
    """

    def __init__(self, config=None):
        self._config = config or settings.investment
        self._vectorizer: Optional[TfidfVectorizer] = None
        self._tfidf_matrix = None
        self._feature_names: Optional[List[str]] = None
        self._keybert_model = None
        # Build combined stopwords from config
        finance_terms = set(self._config.stopwords.finance_terms)
        if self._config.stopwords.replace_defaults:
            base = finance_terms
        else:
            base = ENGLISH_STOP_WORDS | finance_terms
        config_extra = set(getattr(self._config, "tfidf_finance_stopwords", []) or [])
        self._stop_words = list(base | config_extra)

    def fit_tfidf(self, section_texts: List[str]) -> None:
        """
        Fit TF-IDF vectorizer on all section texts in the filing.

        Args:
            section_texts: List of all section texts to fit on.
        """
        self._vectorizer = TfidfVectorizer(
            max_features=self._config.tfidf_max_features,
            ngram_range=(self._config.tfidf_ngram_min, self._config.tfidf_ngram_max),
            stop_words=self._stop_words,
            token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z]+\b",  # exclude all-numeric tokens
            lowercase=True,
            sublinear_tf=self._config.tfidf_sublinear_tf,
        )
        self._tfidf_matrix = self._vectorizer.fit_transform(section_texts)
        self._feature_names = self._vectorizer.get_feature_names_out().tolist()
        logger.info(
            "Fit TF-IDF on %d sections, vocabulary size: %d",
            len(section_texts),
            len(self._feature_names),
        )

    def _ensure_keybert(self):
        """Lazy-load KeyBERT model."""
        if self._keybert_model is not None:
            return
        try:
            from keybert import KeyBERT

            self._keybert_model = KeyBERT(model=self._config.keybert_model)
            logger.info("Loaded KeyBERT model: %s", self._config.keybert_model)
        except ImportError:
            logger.warning(
                "keybert not installed. Install with: pip install keybert. "
                "Falling back to TF-IDF only."
            )
            self._keybert_model = None
        except Exception as e:
            logger.warning("Failed to load KeyBERT: %s", e)
            self._keybert_model = None

    def extract(
        self,
        text: str,
        section_index: Optional[int] = None,
        skip_keybert: bool = False,
    ) -> KeywordResult:
        """
        Extract keywords from a section.

        Args:
            text: Section text.
            section_index: Index into the TF-IDF matrix from fit_tfidf().
                          If None, fits a standalone vectorizer on [text].
            skip_keybert: If True, skip KeyBERT extraction.

        Returns:
            KeywordResult with TF-IDF keywords, KeyBERT keyphrases, and combined.
        """
        if not text or not text.strip():
            return KeywordResult()

        # --- TF-IDF keywords (scored tuples) ---
        tfidf_scored = self._extract_tfidf(text, section_index)
        tfidf_keywords = [kw for kw, _ in tfidf_scored]
        tfidf_scores = {kw: score for kw, score in tfidf_scored}

        # --- KeyBERT keyphrases (scored tuples) ---
        keybert_keyphrases: List[str] = []
        keybert_scores: Dict[str, float] = {}
        if not skip_keybert:
            self._ensure_keybert()
            if self._keybert_model is not None:
                keybert_scored = self._extract_keybert(text)
                keybert_keyphrases = [kw for kw, _ in keybert_scored]
                keybert_scores = {kw: score for kw, score in keybert_scored}

        # --- Combined (union, deduplicated) with source tracking ---
        seen: Dict[str, str] = {}  # lowercase -> source
        combined: List[str] = []
        combined_source: Dict[str, str] = {}

        tfidf_lower = {kw.lower() for kw in tfidf_keywords}
        keybert_lower = {kw.lower() for kw in keybert_keyphrases}

        for kw in tfidf_keywords:
            kw_lower = kw.lower()
            if kw_lower not in seen:
                source = "both" if kw_lower in keybert_lower else "tfidf"
                seen[kw_lower] = source
                combined.append(kw)
                combined_source[kw] = source

        for kw in keybert_keyphrases:
            kw_lower = kw.lower()
            if kw_lower not in seen:
                seen[kw_lower] = "keybert"
                combined.append(kw)
                combined_source[kw] = "keybert"

        return KeywordResult(
            tfidf_keywords=tfidf_keywords,
            keybert_keyphrases=keybert_keyphrases,
            combined=combined,
            tfidf_scores=tfidf_scores if tfidf_scores else None,
            keybert_scores=keybert_scores if keybert_scores else None,
            combined_source=combined_source if combined_source else None,
        )

    def _extract_tfidf(self, text: str, section_index: Optional[int]) -> List[Tuple[str, float]]:
        """Extract top-N TF-IDF keywords."""
        top_n = self._config.tfidf_top_n

        if section_index is not None and self._tfidf_matrix is not None:
            # Use pre-fitted matrix
            row = self._tfidf_matrix[section_index].toarray().flatten()
        elif self._vectorizer is not None:
            # Transform using fitted vectorizer
            row = self._vectorizer.transform([text]).toarray().flatten()
        else:
            # Fit standalone
            vec = TfidfVectorizer(
                max_features=self._config.tfidf_max_features,
                ngram_range=(self._config.tfidf_ngram_min, self._config.tfidf_ngram_max),
                stop_words=self._stop_words,
                token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z]+\b",
                lowercase=True,
                sublinear_tf=self._config.tfidf_sublinear_tf,
            )
            row = vec.fit_transform([text]).toarray().flatten()
            self._feature_names = vec.get_feature_names_out().tolist()

        if self._feature_names is None:
            return []

        # Get top-N by score, return (keyword, score) tuples
        top_indices = row.argsort()[::-1][:top_n]
        return [(self._feature_names[i], float(row[i])) for i in top_indices if row[i] > 0]

    def _extract_keybert(self, text: str) -> List[Tuple[str, float]]:
        """Extract keyphrases using KeyBERT, returning (keyphrase, score) tuples."""
        try:
            keywords = self._keybert_model.extract_keywords(
                text,
                top_n=self._config.keybert_top_n,
                keyphrase_ngram_range=(
                    self._config.keybert_ngram_min,
                    self._config.keybert_ngram_max,
                ),
            )
            return keywords  # Already List[Tuple[str, float]] from KeyBERT
        except Exception as e:
            logger.warning("KeyBERT extraction failed: %s", e)
            return []

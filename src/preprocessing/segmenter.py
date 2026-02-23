"""
Segmenter module for SEC 10-K Risk Factors
Splits the Risk Factors section into individual risk segments
"""

import re
import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any, Union

from pydantic import BaseModel, ConfigDict

from src.config import settings

try:
    from sentence_transformers import SentenceTransformer, util
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

logger = logging.getLogger(__name__)

# Lazy-init spaCy sentencizer (Fix 3A) — blank model, no downloaded data required
_sentencizer = None


def _get_sentencizer():
    global _sentencizer
    if _sentencizer is None:
        import spacy
        nlp = spacy.blank("en")
        nlp.add_pipe("sentencizer")
        _sentencizer = nlp
    return _sentencizer


# Import data models from models package
from .models.segmentation import RiskSegment, SegmentedRisks


class RiskSegmenter:
    """Segments Risk Factors section into individual risk segments"""

    # Fix 3B: require at least 5 semantic segments before preferring over header-based
    SEMANTIC_MIN_SEGMENTS = 5

    def __init__(
        self,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        semantic_model_name: str = "all-MiniLM-L6-v2",
        similarity_threshold: float = 0.5
    ):
        """
        Initialize the segmenter

        Args:
            min_length: Minimum characters for a valid segment (default from settings)
            max_length: Maximum characters for a segment (default from settings)
            semantic_model_name: SentenceTransformer model name for semantic segmentation
            similarity_threshold: Cosine similarity threshold to detect semantic breaks
        """
        # pylint: disable=no-member
        self.min_length = (
            min_length if min_length is not None
            else settings.preprocessing.min_segment_length
        )
        self.max_length = (
            max_length if max_length is not None
            else settings.preprocessing.max_segment_length
        )
        # pylint: enable=no-member
        self.similarity_threshold = similarity_threshold

        self.semantic_model = None
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self.semantic_model = SentenceTransformer(semantic_model_name)
            except (OSError, ValueError, RuntimeError) as e:
                logger.warning(
                    "Could not load SentenceTransformer model '%s'. "
                    "Semantic segmentation will not be available. Error: %s",
                    semantic_model_name, e
                )

    def segment_risks(self, text: str) -> List[str]:
        """
        Split the Risk Factors text into individual risk segments

        Args:
            text: The cleaned Risk Factors section text

        Returns:
            List[str]: List of individual risk segments
        """
        if not text:
            return []

        # Try semantic segmentation first if model is available
        segments = []
        if self.semantic_model:
            segments = self._segment_by_semantic_breaks(text)
            # Fix 3B: require SEMANTIC_MIN_SEGMENTS before preferring semantic segmentation
            if len(segments) >= self.SEMANTIC_MIN_SEGMENTS:
                logger.info("Using semantic segmentation. Found %d segments.", len(segments))
            else:
                logger.info(
                    "Semantic segmentation yielded %d segments (< %d), falling back.",
                    len(segments), self.SEMANTIC_MIN_SEGMENTS
                )
                segments = self._segment_by_headers(text)
        else:
            logger.info("Semantic model not loaded, falling back to heuristic segmentation.")
            segments = self._segment_by_headers(text)

        # If header-based segmentation doesn't work well, try paragraph-based
        # Keep the original heuristic as a fallback if needed
        if len(segments) < 3:
            logger.info(
                "Header-based segmentation yielded too few segments, "
                "trying paragraph-based."
            )
            segments = self._segment_by_paragraphs(text)

        # Filter and clean segments
        segments = self._filter_segments(segments)

        # Split overly long segments
        segments = self._split_long_segments(segments)

        return segments

    def segment_extracted_section(
        self,
        extracted_section: Any,
        cleaned_text: Optional[str] = None
    ) -> SegmentedRisks:
        """
        Segment an ExtractedSection and preserve all metadata

        Args:
            extracted_section: ExtractedSection object from extractor
            cleaned_text: Optional pre-cleaned text. If None, uses extracted_section.text

        Returns:
            SegmentedRisks with segments and preserved metadata
        """
        # Use cleaned text if provided, otherwise use raw text from section
        text_to_segment = cleaned_text if cleaned_text else extracted_section.text

        # Segment the text
        segment_texts = self.segment_risks(text_to_segment)

        # Fix 6B: build chunk_id and resolve parent_subsection from node_subsections
        node_subsections = getattr(extracted_section, 'node_subsections', [])
        segments = [
            RiskSegment(
                chunk_id=f"1A_{i+1:03d}",
                parent_subsection=self._resolve_subsection(
                    text, text_to_segment, node_subsections
                ),
                text=text,
            )
            for i, text in enumerate(segment_texts)
        ]

        # Fix 6C: promote fiscal_year from metadata
        parsed_meta = getattr(extracted_section, 'metadata', {})
        fiscal_year = parsed_meta.get('fiscal_year')

        # Build SegmentedRisks with preserved metadata
        return SegmentedRisks(
            segments=segments,
            sic_code=getattr(extracted_section, 'sic_code', None),
            sic_name=getattr(extracted_section, 'sic_name', None),
            cik=getattr(extracted_section, 'cik', None),
            ticker=getattr(extracted_section, 'ticker', None),
            company_name=getattr(extracted_section, 'company_name', None),
            form_type=getattr(extracted_section, 'form_type', None),
            fiscal_year=fiscal_year,
            section_title=getattr(extracted_section, 'title', None),
            section_identifier=getattr(extracted_section, 'identifier', None),
            metadata=parsed_meta,
            accession_number=getattr(extracted_section, 'accession_number', None),
            filed_as_of_date=getattr(extracted_section, 'filed_as_of_date', None),
        )

    def _segment_by_headers(self, text: str) -> List[str]:
        """
        Segment by risk headers/titles

        Many 10-K filings have risk factors with bold headers or numbered items
        """
        segments = []

        # Pattern for risk headers (e.g., bullet points, numbered items, bold text indicators)
        # This is a heuristic - adjust based on your actual filing format
        header_patterns = [
            r'\n\s*[•●○■▪]\s+',  # Bullet points
            r'\n\s*\d+\.\s+',     # Numbered items (1. 2. 3.)
            r'\n\s*Risk \d+:',    # "Risk 1:", "Risk 2:"
            r'\n\s*[A-Z][A-Z\s]{10,}\n',  # ALL CAPS HEADERS
        ]

        # Try to split by headers
        split_pattern = '|'.join(header_patterns)
        potential_segments = re.split(split_pattern, text)

        if len(potential_segments) > 1:
            segments = [seg.strip() for seg in potential_segments if seg.strip()]

        return segments

    def _segment_by_paragraphs(self, text: str) -> List[str]:
        """
        Segment by paragraphs as a fallback

        This is less accurate but works when header-based segmentation fails
        """
        # Split by double newlines (paragraph breaks)
        paragraphs = text.split('\n\n')

        segments = []
        current_segment = []

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            current_segment.append(para)
            segment_text = '\n\n'.join(current_segment)

            # If we've accumulated enough text, treat it as a segment
            if len(segment_text) >= self.min_length * 3:  # Use a higher threshold for paragraphs
                segments.append(segment_text)
                current_segment = []

        # Add any remaining text as the last segment
        if current_segment:
            segments.append('\n\n'.join(current_segment))

        return segments

    def _filter_segments(self, segments: List[str]) -> List[str]:
        """
        Filter segments based on length and content quality

        Args:
            segments: List of raw segments

        Returns:
            List[str]: Filtered segments
        """
        filtered = []

        for segment in segments:
            segment = segment.strip()

            # Skip if too short
            if len(segment) < self.min_length:
                continue

            # Skip if it's just a header or title (very short sentences)
            if len(segment.split()) < 10:
                continue

            # Skip common non-risk content
            if self._is_non_risk_content(segment):
                continue

            filtered.append(segment)

        return filtered

    def _is_non_risk_content(self, text: str) -> bool:
        """
        Check if text is likely non-risk content (headers, TOC, etc.)

        Args:
            text: Text to check

        Returns:
            bool: True if likely non-risk content
        """
        text_lower = text.lower()

        # Common non-risk phrases
        non_risk_indicators = [
            'table of contents',
            'page ',
            'item 1a',
            'risk factors',
            'forward-looking statements',
        ]

        for indicator in non_risk_indicators:
            if indicator in text_lower and len(text) < 200:
                return True

        return False

    def _resolve_subsection(
        self,
        chunk_text: str,
        full_text: str,
        node_subsections: list
    ) -> Optional[str]:
        """
        Return the parent_subsection for a chunk using doc-order text position (Fix 6B).

        Walks node_subsections (ordered list of (node_text, subsection_title)) and
        returns the subsection of the latest node whose text starts at or before
        the chunk's position in full_text.
        """
        if not node_subsections:
            return None
        key = chunk_text[:50]
        chunk_start = full_text.find(key)
        if chunk_start == -1:
            return node_subsections[-1][1]
        current: Optional[str] = None
        for node_text, subsection in node_subsections:
            node_key = node_text[:50]
            node_start = full_text.find(node_key)
            if node_start == -1:
                continue
            if node_start <= chunk_start:
                current = subsection
            else:
                break
        return current

    def _get_sentences(self, text: str) -> List[str]:
        """Split text into sentences using spaCy sentencizer (Fix 3A)."""
        nlp = _get_sentencizer()
        doc = nlp(text)
        return [sent.text.strip() for sent in doc.sents if sent.text.strip()]

    def _split_long_segments(self, segments: List[str]) -> List[str]:
        """
        Split segments that are too long

        Args:
            segments: List of segments

        Returns:
            List[str]: Segments with long ones split
        """
        result = []

        for segment in segments:
            if len(segment) <= self.max_length:
                result.append(segment)
            else:
                # Split long segment into chunks
                chunks = self._split_into_chunks(segment, self.max_length)
                result.extend(chunks)

        return result

    def _split_into_chunks(self, text: str, max_length: int) -> List[str]:
        """
        Split text into chunks at sentence boundaries

        Args:
            text: Text to split
            max_length: Maximum length for each chunk

        Returns:
            List[str]: List of chunks
        """
        # Fix 3A: use spaCy sentencizer (handles financial abbreviations correctly)
        sentences = self._get_sentences(text)

        chunks = []
        current_chunk = []
        current_length = 0

        for sentence in sentences:
            sentence_length = len(sentence)

            if current_length + sentence_length > max_length and current_chunk:
                # Start new chunk
                chunks.append(' '.join(current_chunk).strip())
                current_chunk = [sentence]
                current_length = sentence_length
            else:
                current_chunk.append(sentence)
                current_length += sentence_length

        # Add remaining text
        if current_chunk:
            chunks.append(' '.join(current_chunk).strip())

        return chunks

    def _segment_by_semantic_breaks(self, text: str) -> List[str]:
        """
        Segment text by identifying semantic breaks using sentence embeddings.

        Args:
            text: The cleaned Risk Factors section text.

        Returns:
            List[str]: List of individual risk segments based on semantic similarity.
        """
        if not SENTENCE_TRANSFORMERS_AVAILABLE or self.semantic_model is None:
            return []  # Fallback if model not available

        # Fix 3A: use spaCy sentencizer (handles financial abbreviations correctly)
        sentences = self._get_sentences(text)

        if len(sentences) < 2:
            return sentences

        # Generate embeddings for all sentences
        embeddings = self.semantic_model.encode(sentences, convert_to_tensor=True)

        # Calculate cosine similarity between adjacent sentences
        cosine_scores = util.cos_sim(embeddings[:-1], embeddings[1:])
        # Extract diagonal and convert to numpy
        cosine_scores = cosine_scores.diag().cpu().numpy()

        # Identify break points where similarity drops significantly
        # A low similarity score between adjacent sentences indicates a potential topic shift
        break_points = [0]  # Start of the first segment
        for i, score in enumerate(cosine_scores):
            if score < self.similarity_threshold:
                break_points.append(i + 1)  # Mark the beginning of a new segment

        break_points.append(len(sentences))  # End of the last segment

        segments = []
        for i in range(len(break_points) - 1):
            start_idx = break_points[i]
            end_idx = break_points[i+1]
            segment_sentences = sentences[start_idx:end_idx]
            if segment_sentences:
                segment = " ".join(segment_sentences)
                segments.append(segment)

        return segments


def segment_risk_factors(text: str) -> List[str]:
    """
    Convenience function to segment risk factors text

    Args:
        text: The cleaned Risk Factors section text

    Returns:
        List[str]: List of individual risk segments
    """
    segmenter = RiskSegmenter()
    return segmenter.segment_risks(text)


if __name__ == "__main__":
    print("Segmenter module loaded successfully")

"""
Segmenter module for SEC 10-K Risk Factors
Splits the Risk Factors section into individual risk segments
"""

import re
from typing import List
import numpy as np
from src.config import MIN_SEGMENT_LENGTH, MAX_SEGMENT_LENGTH

try:
    from sentence_transformers import SentenceTransformer, util
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False


class RiskSegmenter:
    """Segments Risk Factors section into individual risk segments"""

    def __init__(
        self,
        min_length: int = MIN_SEGMENT_LENGTH,
        max_length: int = MAX_SEGMENT_LENGTH,
        semantic_model_name: str = "all-MiniLM-L6-v2",
        similarity_threshold: float = 0.5
    ):
        """
        Initialize the segmenter

        Args:
            min_length: Minimum characters for a valid segment
            max_length: Maximum characters for a segment
            semantic_model_name: Name of the SentenceTransformer model to use for semantic segmentation
            similarity_threshold: Cosine similarity threshold to detect semantic breaks
        """
        self.min_length = min_length
        self.max_length = max_length
        self.similarity_threshold = similarity_threshold

        self.semantic_model = None
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self.semantic_model = SentenceTransformer(semantic_model_name)
            except Exception as e:
                print(f"Warning: Could not load SentenceTransformer model '{semantic_model_name}'. "
                      f"Semantic segmentation will not be available. Error: {e}")

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
            if len(segments) > 1: # If semantic segmentation yields at least 2 segments, use it
                print(f"Using semantic segmentation. Found {len(segments)} segments.")
            else: # Fallback if semantic segmentation didn't produce enough segments
                print("Semantic segmentation yielded too few segments, falling back to heuristic methods.")
                segments = self._segment_by_headers(text)
        else:
            print("Semantic model not loaded, falling back to heuristic segmentation.")
            segments = self._segment_by_headers(text)


        # If header-based segmentation doesn't work well, try paragraph-based
        if len(segments) < 3: # Keep the original heuristic as a fallback if needed
            print("Header-based segmentation yielded too few segments, trying paragraph-based.")
            segments = self._segment_by_paragraphs(text)

        # Filter and clean segments
        segments = self._filter_segments(segments)

        # Split overly long segments
        segments = self._split_long_segments(segments)

        return segments

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
        # Split by sentences
        sentences = re.split(r'([.!?]\s+)', text)

        chunks = []
        current_chunk = []
        current_length = 0

        for i in range(0, len(sentences), 2):
            sentence = sentences[i]
            if i + 1 < len(sentences):
                sentence += sentences[i + 1]  # Add punctuation back

            sentence_length = len(sentence)

            if current_length + sentence_length > max_length and current_chunk:
                # Start new chunk
                chunks.append(''.join(current_chunk).strip())
                current_chunk = [sentence]
                current_length = sentence_length
            else:
                current_chunk.append(sentence)
                current_length += sentence_length

        # Add remaining text
        if current_chunk:
            chunks.append(''.join(current_chunk).strip())

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
            return [] # Fallback if model not available

        sentences = re.split(r'(?<=[.!?])\s+', text) # Split by sentence, keeping punctuation
        sentences = [s.strip() for s in sentences if s.strip()]

        if len(sentences) < 2:
            return sentences

        # Generate embeddings for all sentences
        embeddings = self.semantic_model.encode(sentences, convert_to_tensor=True)

        # Calculate cosine similarity between adjacent sentences
        cosine_scores = util.cos_sim(embeddings[:-1], embeddings[1:])
        cosine_scores = cosine_scores.diag().cpu().numpy() # Extract diagonal and convert to numpy

        # Identify break points where similarity drops significantly
        # A low similarity score between adjacent sentences indicates a potential topic shift
        break_points = [0] # Start of the first segment
        for i, score in enumerate(cosine_scores):
            if score < self.similarity_threshold:
                break_points.append(i + 1) # Mark the beginning of a new segment

        break_points.append(len(sentences)) # End of the last segment

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

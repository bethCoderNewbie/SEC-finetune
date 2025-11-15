"""
Inference module for risk categorization
Uses zero-shot classification to categorize risk segments
"""

import yaml
from typing import List, Dict, Optional
from pathlib import Path
from transformers import pipeline
from src.config import RISK_TAXONOMY_PATH, ZERO_SHOT_MODEL


class RiskClassifier:
    """Zero-shot classifier for risk segments"""

    def __init__(
        self,
        taxonomy_path: Path = RISK_TAXONOMY_PATH,
        model_name: str = ZERO_SHOT_MODEL,
        device: int = -1  # -1 for CPU, 0 for GPU
    ):
        """
        Initialize the risk classifier

        Args:
            taxonomy_path: Path to risk_taxonomy.yaml
            model_name: Name of the Hugging Face model to use
            device: Device to run model on (-1 for CPU, 0+ for GPU)
        """
        self.taxonomy_path = taxonomy_path
        self.model_name = model_name
        self.device = device

        # Load risk categories from taxonomy
        self.categories = self._load_categories()

        # Initialize the zero-shot classification pipeline
        print(f"Loading model: {model_name}")
        print("This may take a moment on first run...")
        self.classifier = pipeline(
            "zero-shot-classification",
            model=model_name,
            device=device
        )

    def _load_categories(self) -> List[str]:
        """
        Load risk categories from taxonomy YAML

        Returns:
            List[str]: List of category names
        """
        with open(self.taxonomy_path, 'r') as f:
            taxonomy = yaml.safe_load(f)

        categories = [cat['name'] for cat in taxonomy['categories']]
        return categories

    def classify_segment(
        self,
        text: str,
        multi_label: bool = False,
        threshold: float = 0.5
    ) -> Dict:
        """
        Classify a single risk segment

        Args:
            text: The risk segment text
            multi_label: Whether to allow multiple labels
            threshold: Confidence threshold (for multi-label)

        Returns:
            dict: Classification results with 'label', 'score', and optionally 'all_scores'
        """
        if not text or len(text.strip()) < 10:
            return {
                'label': 'Unknown',
                'score': 0.0,
                'all_scores': {}
            }

        # Truncate very long texts (model limit is typically 512 tokens)
        max_chars = 2000
        if len(text) > max_chars:
            text = text[:max_chars] + "..."

        try:
            result = self.classifier(
                text,
                candidate_labels=self.categories,
                multi_label=multi_label
            )

            # Format results
            top_label = result['labels'][0]
            top_score = result['scores'][0]

            all_scores = dict(zip(result['labels'], result['scores']))

            classification_result = {
                'label': top_label,
                'score': float(top_score),
                'all_scores': all_scores
            }

            # For multi-label, include all labels above threshold
            if multi_label:
                classification_result['all_labels'] = [
                    label for label, score in all_scores.items()
                    if score >= threshold
                ]

            return classification_result

        except Exception as e:
            print(f"Error classifying segment: {e}")
            return {
                'label': 'Error',
                'score': 0.0,
                'all_scores': {},
                'error': str(e)
            }

    def classify_segments(
        self,
        segments: List[str],
        multi_label: bool = False,
        threshold: float = 0.5,
        show_progress: bool = True
    ) -> List[Dict]:
        """
        Classify multiple risk segments

        Args:
            segments: List of risk segment texts
            multi_label: Whether to allow multiple labels
            threshold: Confidence threshold
            show_progress: Whether to print progress

        Returns:
            List[dict]: List of classification results
        """
        results = []

        for i, segment in enumerate(segments):
            if show_progress:
                print(f"Classifying segment {i + 1}/{len(segments)}...")

            result = self.classify_segment(segment, multi_label, threshold)
            result['segment_index'] = i
            result['segment_text'] = segment
            results.append(result)

        return results

    def get_category_descriptions(self) -> Dict[str, str]:
        """
        Get descriptions for all categories

        Returns:
            dict: Mapping of category name to description
        """
        with open(self.taxonomy_path, 'r') as f:
            taxonomy = yaml.safe_load(f)

        descriptions = {
            cat['name']: cat.get('description', '')
            for cat in taxonomy['categories']
        }
        return descriptions


def classify_risk_segments(
    segments: List[str],
    model_name: str = ZERO_SHOT_MODEL,
    multi_label: bool = False
) -> List[Dict]:
    """
    Convenience function to classify risk segments

    Args:
        segments: List of risk segment texts
        model_name: Model to use for classification
        multi_label: Whether to allow multiple labels

    Returns:
        List[dict]: Classification results
    """
    classifier = RiskClassifier(model_name=model_name)
    return classifier.classify_segments(segments, multi_label=multi_label)


if __name__ == "__main__":
    print("Inference module loaded successfully")
    print(f"Default model: {ZERO_SHOT_MODEL}")

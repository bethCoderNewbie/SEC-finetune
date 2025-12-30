"""
Drift Detection Script using Topic Modeling.

This script implements the "Change Detection" feature.
It compares topic models trained on two different datasets (e.g., Year N vs Year N+1)
to identify new or shifting risks.

Methodology:
1. Train/Load LDA model for Period A (Reference).
2. Train/Load LDA model for Period B (Target).
3. Compare topics using Jaccard Similarity of their top N words.
4. Report "New Topics" (low max similarity to any reference topic).

Usage:
    python scripts/04_feature_engineering/detect_drift.py --ref data/processed/2022 --target data/processed/2023
"""

import argparse
import logging
from pathlib import Path
from typing import List, Dict, Set, Tuple
import sys

import numpy as np
import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.features.topic_modeling import LDATrainer
from src.config import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_top_words(trainer: LDATrainer, topic_id: int, topn: int = 20) -> Set[str]:
    """Get set of top words for a given topic."""
    return {word for word, _ in trainer.lda_model.show_topic(topic_id, topn=topn)}

def calculate_jaccard(set_a: Set[str], set_b: Set[str]) -> float:
    """Calculate Jaccard similarity between two sets."""
    intersection = len(set_a.intersection(set_b))
    union = len(set_a.union(set_b))
    return intersection / union if union > 0 else 0.0

def detect_topic_drift(
    ref_trainer: LDATrainer, 
    target_trainer: LDATrainer, 
    similarity_threshold: float = 0.2
) -> List[Dict]:
    """
    Identify topics in target_trainer that are distinct from all topics in ref_trainer.
    """
    drift_report = []
    
    logger.info(f"Comparing {target_trainer.num_topics} target topics against {ref_trainer.num_topics} reference topics...")
    
    for target_id in range(target_trainer.num_topics):
        target_words = get_top_words(target_trainer, target_id)
        
        # Find best match in reference model
        best_match_id = -1
        max_similarity = -1.0
        
        for ref_id in range(ref_trainer.num_topics):
            ref_words = get_top_words(ref_trainer, ref_id)
            sim = calculate_jaccard(target_words, ref_words)
            
            if sim > max_similarity:
                max_similarity = sim
                best_match_id = ref_id
                
        # Determine if this is a "New Risk"
        is_new = max_similarity < similarity_threshold
        
        drift_report.append({
            "target_topic_id": target_id,
            "target_top_words": list(target_words),
            "best_match_ref_id": best_match_id,
            "similarity_score": max_similarity,
            "is_new_risk": is_new
        })
        
    return drift_report

def main():
    parser = argparse.ArgumentParser(description="Detect Risk Drift between two time periods")
    parser.add_argument('--ref-model', type=Path, required=True, help="Path to reference LDA model (e.g. 2022)")
    parser.add_argument('--target-model', type=Path, required=True, help="Path to target LDA model (e.g. 2023)")
    parser.add_argument('--threshold', type=float, default=None, help="Similarity threshold below which a topic is considered 'New'")
    
    args = parser.parse_args()
    
    # Use config default if not provided
    threshold = args.threshold if args.threshold is not None else settings.risk_analysis.drift_threshold
    
    if not args.ref_model.exists() or not args.target_model.exists():
        logger.error("Model paths do not exist.")
        return

    # Load models
    logger.info("Loading models...")
    try:
        ref_trainer = LDATrainer.load(args.ref_model)
        target_trainer = LDATrainer.load(args.target_model)
    except Exception as e:
        logger.error(f"Failed to load models: {e}")
        return

    # Detect Drift
    report = detect_topic_drift(ref_trainer, target_trainer, threshold)
    
    # Print Report
    print("\n" + "="*80)
    print("RISK DRIFT DETECTION REPORT")
    print("="*80)
    
    new_risks = [r for r in report if r['is_new_risk']]
    
    print(f"\nFound {len(new_risks)} potentially NEW risk topics (Similarity < {threshold})")
    
    for drift in new_risks:
        print(f"\n[NEW TOPIC DETECTED] Target Topic #{drift['target_topic_id']}")
        print(f"  Top Words: {', '.join(list(drift['target_top_words'])[:10])}")
        print(f"  Closest Reference Topic: #{drift['best_match_ref_id']} (Sim: {drift['similarity_score']:.2f})")
        
    if not new_risks:
        print("\nNo significant drift detected. Risk landscape appears stable.")

if __name__ == "__main__":
    main()

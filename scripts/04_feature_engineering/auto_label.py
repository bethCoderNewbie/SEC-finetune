"""
Auto-labeling script for SEC Risk Factors using Zero-Shot Classification.

This script implements the "Teacher" phase of the training pipeline.
It uses a pre-trained NLI model (the Teacher) to classify risk segments.

Key Feature:
It dynamically selects the correct SASB Risk Taxonomy based on the company's
SIC code found in the filing metadata. This ensures "Oil & Gas" companies
are evaluated on environmental risks, while "Tech" companies are evaluated
on data security.

Output:
A JSONL file where each line is a labeled risk segment, suitable for
fine-tuning a Student model.

Usage:
    python scripts/04_feature_engineering/auto_label.py
"""

import argparse
import json
import logging
from pathlib import Path
import sys
from typing import List, Dict

from tqdm import tqdm

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import settings, RunContext
from src.preprocessing.parser import ParsedFiling
from src.preprocessing.segmenter import RiskSegmenter
from src.analysis.taxonomies.taxonomy_manager import TaxonomyManager

try:
    from transformers import pipeline
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


def auto_label_segments(
    segments: List[str],
    candidate_labels: List[str],
    classifier,
    multi_label: bool = True
) -> List[Dict]:
    """
    Classify a list of segments using the provided classifier pipeline and labels.
    """
    if not segments:
        return []

    labeled_data = []
    
    # We process the whole list at once (pipeline handles batching internally usually, 
    # or we can loop. For simplicity and progress tracking, we loop in chunks).
    batch_size = 16
    
    for i in range(0, len(segments), batch_size):
        batch = segments[i:i + batch_size]
        try:
            results = classifier(batch, candidate_labels, multi_label=multi_label)
            
            if isinstance(results, dict):
                results = [results]
                
            for res in results:
                scored_labels = [
                    {"name": label, "score": score} 
                    for label, score in zip(res['labels'], res['scores'])
                ]
                
                labeled_data.append({
                    "text": res['sequence'],
                    "labels": scored_labels,
                    "top_label": scored_labels[0]['name'],
                    "top_score": scored_labels[0]['score']
                })
        except Exception as e:
            logger.error(f"Classification batch failed: {e}")
            
    return labeled_data


def extract_risk_text(parsed_data: Dict) -> str:
    """
    Heuristic extraction of 'Item 1A. Risk Factors' text from parsed structure.
    """
    risk_text = ""
    elements = parsed_data.get('elements', [])
    capturing = False
    
    for el in elements:
        text = el.get('text', '')
        # Simple heuristic for TopSectionTitle
        # A better way is to use the 'tree' structure if available and robust
        if 'Item 1A' in text and 'Risk Factors' in text and len(text) < 100:
            capturing = True
            continue
        
        if capturing and ('Item 1B' in text or 'Item 2' in text):
            break
            
        if capturing:
            risk_text += text + "\n"
            
    return risk_text


def main():
    parser = argparse.ArgumentParser(description="Auto-label risk segments with dynamic SASB topics")
    parser.add_argument('--input-dir', type=Path, default=PARSED_DATA_DIR)
    # output-dir is now handled by RunContext
    # model is now handled by settings.risk_analysis
    parser.add_argument('--limit', type=int, default=None, help="Limit files for testing")
    
    args = parser.parse_args()
    
    if not TRANSFORMERS_AVAILABLE:
        logger.error("Transformers library not found. Please pip install transformers[torch]")
        return

    ensure_directories()
    
    # Initialize RunContext
    run_context = RunContext(name="auto_label_sasb")
    run_context.create()
    
    # Save Run Config
    run_config = {
        "input_dir": str(args.input_dir),
        "model": settings.risk_analysis.labeling_model,
        "batch_size": settings.risk_analysis.labeling_batch_size,
        "limit": args.limit,
        "transformers_version": "latest" # You could grab actual version if needed
    }
    run_context.save_config(run_config)
    
    logger.info(f"Starting run: {run_context.run_id}")
    logger.info(f"Output directory: {run_context.output_dir}")
    
    # Initialize components
    taxonomy_manager = TaxonomyManager()
    segmenter = RiskSegmenter()
    
    # Load Classifier (Global)
    model_name = settings.risk_analysis.labeling_model
    logger.info(f"Loading model: {model_name}...")
    
    # Device selection logic from config
    device_config = settings.risk_analysis.device
    if device_config == "auto":
        device = 0 if sys.platform != "darwin" else -1 # Simple auto-detect
    elif device_config == "cuda":
        device = 0
    else:
        device = -1

    try:
        classifier = pipeline("zero-shot-classification", model=model_name, device=device)
    except Exception as e:
        logger.warning(f"Device init failed, using CPU: {e}")
        classifier = pipeline("zero-shot-classification", model=model_name)

    # Find files
    input_files = list(args.input_dir.glob("*.json"))
    if not input_files:
        logger.warning(f"No parsed files in {args.input_dir}")
        return
        
    if args.limit:
        input_files = input_files[:args.limit]

    total_labeled = 0
    output_file = run_context.output_dir / "sasb_labeled_risks.jsonl"
    
    # Process files
    with open(output_file, 'w', encoding='utf-8') as f_out:
        for file_path in tqdm(input_files, desc="Processing filings"):
            try:
                # 1. Load Data
                data = ParsedFiling.load_from_pickle(file_path)
                metadata = data.get('metadata', {})
                sic_code = metadata.get('sic_code')
                
                # 2. Determine Labels
                industry = taxonomy_manager.get_industry_for_sic(sic_code)
                if not industry:
                    logger.debug(f"Skipping {file_path.name}: SIC {sic_code} not in SASB map.")
                    continue
                    
                topics_map = taxonomy_manager.get_topics_for_sic(sic_code)
                candidate_labels = list(topics_map.keys())
                
                if not candidate_labels:
                    continue

                logger.info(f"Processing {file_path.name} (SIC: {sic_code} -> {industry})")

                # 3. Extract & Segment
                risk_text = extract_risk_text(data)
                if not risk_text:
                    continue
                    
                segments = segmenter.segment_risks(risk_text)
                if not segments:
                    continue
                
                # 4. Classify
                results = auto_label_segments(
                    segments, 
                    candidate_labels, 
                    classifier,
                    multi_label=settings.risk_analysis.labeling_multi_label
                )
                
                # 5. Save/Append
                for res in results:
                    # Add metadata for context
                    res['metadata'] = {
                        'source_file': file_path.name,
                        'sic_code': sic_code,
                        'sasb_industry': industry,
                        'company_name': metadata.get('company_name'),
                        'cik': metadata.get('cik')
                    }
                    f_out.write(json.dumps(res) + "\n")
                    total_labeled += 1
                    
            except Exception as e:
                logger.error(f"Error processing {file_path.name}: {e}")
                continue

    logger.info(f"Completed. Total labeled segments: {total_labeled}")
    logger.info(f"Output saved to: {output_file}")

if __name__ == "__main__":
    main()
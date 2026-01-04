"""
Extract Sentiment Features from Preprocessed Segments

Pure feature engineering script - operates on already preprocessed data.
Part of the separated pipeline architecture for production MLOps.

Input:  data/processed/*_segmented_risks.json (SegmentedRisks)
Output: data/features/sentiment/*_sentiment.json (with metadata)

Usage:
    # Single file
    python scripts/feature_engineering/extract_sentiment_features.py --input data/processed/AAPL_10K_segmented_risks.json

    # Batch mode
    python scripts/feature_engineering/extract_sentiment_features.py --batch
    python scripts/feature_engineering/extract_sentiment_features.py --batch --resume
    python scripts/feature_engineering/extract_sentiment_features.py --batch --workers 4
"""

import argparse
import json
import logging
import time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Optional, List, Dict, Any

from src.preprocessing.models import SegmentedRisks
from src.features.sentiment import SentimentAnalyzer, SentimentFeatures
from src.config import PROCESSED_DATA_DIR, settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Output directory for sentiment features
SENTIMENT_OUTPUT_DIR = Path("data/features/sentiment")


def extract_sentiment_from_file(
    input_file: Path,
    output_dir: Optional[Path] = None,
    quiet: bool = False
) -> Dict[str, Any]:
    """
    Extract sentiment features from a single preprocessed file.

    Args:
        input_file: Path to *_segmented_risks.json file
        output_dir: Optional output directory (default: data/features/sentiment)
        quiet: Suppress output

    Returns:
        Dictionary with status and metadata
    """
    try:
        start_time = time.time()

        if not quiet:
            print(f"Processing: {input_file.name}")

        # Load preprocessed segments
        segmented_risks = SegmentedRisks.load_from_json(input_file)

        if len(segmented_risks.segments) == 0:
            return {
                'file': input_file.name,
                'status': 'warning',
                'error': 'No segments found in file',
                'elapsed_time': time.time() - start_time
            }

        # Extract sentiment features
        analyzer = SentimentAnalyzer()
        segment_texts = segmented_risks.get_texts()
        sentiment_features = analyzer.extract_features_batch(segment_texts)

        # Build output data with metadata
        output_data = {
            'version': '1.0',
            'source_file': input_file.name,
            # Metadata from preprocessing
            'sic_code': segmented_risks.sic_code,
            'sic_name': segmented_risks.sic_name,
            'cik': segmented_risks.cik,
            'ticker': segmented_risks.ticker,
            'company_name': segmented_risks.company_name,
            'form_type': segmented_risks.form_type,
            # Sentiment configuration
            'sentiment_config': {
                'dictionary': 'Loughran-McDonald',
                'active_categories': settings.sentiment.active_categories,
                'case_sensitive': settings.sentiment.text_processing.case_sensitive,
            },
            # Aggregate statistics
            'aggregate_sentiment': {
                'num_segments': len(sentiment_features),
                'avg_negative_ratio': sum(f.negative_ratio for f in sentiment_features) / len(sentiment_features),
                'avg_positive_ratio': sum(f.positive_ratio for f in sentiment_features) / len(sentiment_features),
                'avg_uncertainty_ratio': sum(f.uncertainty_ratio for f in sentiment_features) / len(sentiment_features),
                'avg_sentiment_word_ratio': sum(f.sentiment_word_ratio for f in sentiment_features) / len(sentiment_features),
            },
            # Per-segment features
            'segment_features': [f.to_dict() for f in sentiment_features],
        }

        # Save output
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f"{input_file.stem.replace('_segmented_risks', '')}_sentiment.json"

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)

            if not quiet:
                print(f"  → Saved to: {output_file}")

        elapsed = time.time() - start_time

        return {
            'file': input_file.name,
            'status': 'success',
            'num_segments': len(sentiment_features),
            'sic_code': segmented_risks.sic_code,
            'company_name': segmented_risks.company_name,
            'elapsed_time': elapsed,
            'error': None
        }

    except Exception as e:
        logger.exception("Error processing %s", input_file.name)
        return {
            'file': input_file.name,
            'status': 'error',
            'error': str(e),
            'elapsed_time': 0
        }


def process_file_worker(args: tuple) -> Dict[str, Any]:
    """
    Worker function for parallel processing.

    Args:
        args: Tuple of (input_file, output_dir, quiet)

    Returns:
        Processing result dictionary
    """
    input_file, output_dir, quiet = args
    return extract_sentiment_from_file(input_file, output_dir, quiet)


def is_already_processed(input_file: Path, output_dir: Path) -> bool:
    """
    Check if sentiment features have already been extracted for this file.

    Args:
        input_file: Path to input *_segmented_risks.json file
        output_dir: Output directory for sentiment features

    Returns:
        True if output file exists
    """
    output_file = output_dir / f"{input_file.stem.replace('_segmented_risks', '')}_sentiment.json"
    return output_file.exists()


def filter_unprocessed_files(input_files: List[Path], output_dir: Path, quiet: bool = False) -> List[Path]:
    """
    Filter out files that have already been processed.

    Args:
        input_files: List of input file paths
        output_dir: Output directory
        quiet: Suppress output

    Returns:
        List of unprocessed files
    """
    unprocessed = [f for f in input_files if not is_already_processed(f, output_dir)]

    skipped = len(input_files) - len(unprocessed)
    if skipped > 0 and not quiet:
        print(f"Resume mode: Skipping {skipped} already processed files")

    return unprocessed


def run_batch_extraction(
    input_files: List[Path],
    output_dir: Path,
    max_workers: Optional[int] = None,
    quiet: bool = False
) -> List[Dict[str, Any]]:
    """
    Extract sentiment features from multiple files in parallel.

    Args:
        input_files: List of input file paths
        output_dir: Output directory
        max_workers: Number of parallel workers (None = CPU count)
        quiet: Minimize output

    Returns:
        List of processing results
    """
    if not input_files:
        if not quiet:
            print("No files to process")
        return []

    total_files = len(input_files)

    if not quiet:
        print(f"\nBatch Sentiment Extraction: {total_files} files")
        print(f"Max workers: {max_workers if max_workers else 'auto (CPU count)'}")
        print("=" * 80)

    # Prepare arguments
    task_args = [(f, output_dir, quiet) for f in input_files]

    results = []
    successful = 0
    warnings = 0
    failed = 0

    start_time = time.time()

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {
            executor.submit(process_file_worker, args): args[0]
            for args in task_args
        }

        for i, future in enumerate(as_completed(future_to_file), 1):
            result = future.result()
            results.append(result)

            if result['status'] == 'success':
                successful += 1
                if not quiet:
                    print(f"[{i}/{total_files}] OK: {result['file']} "
                          f"({result['num_segments']} segments, {result['elapsed_time']:.1f}s)")
            elif result['status'] == 'warning':
                warnings += 1
                if not quiet:
                    print(f"[{i}/{total_files}] WARN: {result['file']} - {result['error']}")
            else:
                failed += 1
                if not quiet:
                    print(f"[{i}/{total_files}] FAIL: {result['file']} - {result['error']}")

    total_time = time.time() - start_time

    # Summary
    if not quiet:
        print("\n" + "=" * 80)
        print("Sentiment Extraction Complete!")
        print(f"  Total files: {total_files}")
        print(f"  Successful: {successful}")
        if warnings > 0:
            print(f"  Warnings: {warnings}")
        print(f"  Failed: {failed}")
        print(f"  Total time: {total_time:.1f}s")
        if total_files > 0:
            print(f"  Avg time per file: {total_time / total_files:.1f}s")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Extract sentiment features from preprocessed SEC filings"
    )
    parser.add_argument(
        '--input',
        type=str,
        help='Input file path (single file mode)'
    )
    parser.add_argument(
        '--batch',
        action='store_true',
        help='Process all files in PROCESSED_DATA_DIR'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=None,
        help='Number of concurrent workers for batch mode (default: CPU count)'
    )
    parser.add_argument(
        '--resume',
        action='store_true',
        help='Skip files that have already been processed'
    )
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Minimize output for better performance in batch mode'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default=str(SENTIMENT_OUTPUT_DIR),
        help='Output directory for sentiment features (default: data/features/sentiment)'
    )

    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.batch:
        # Batch mode: process all segmented_risks.json files
        input_files = sorted(PROCESSED_DATA_DIR.glob("*_segmented_risks.json"))

        if not input_files:
            print(f"No *_segmented_risks.json files found in {PROCESSED_DATA_DIR}")
            return

        # Filter out already processed files if resume mode
        if args.resume:
            input_files = filter_unprocessed_files(input_files, output_dir, quiet=args.quiet)
            if not input_files:
                print("All files have already been processed. Nothing to do.")
                return

        results = run_batch_extraction(
            input_files,
            output_dir=output_dir,
            max_workers=args.workers,
            quiet=args.quiet
        )

        # Save batch summary
        if results:
            summary_path = output_dir / "batch_sentiment_summary.json"
            summary_data = {
                'version': '1.0',
                'total_files': len(results),
                'successful': sum(1 for r in results if r['status'] == 'success'),
                'warnings': sum(1 for r in results if r['status'] == 'warning'),
                'failed': sum(1 for r in results if r['status'] == 'error'),
                'results': results
            }
            with open(summary_path, 'w', encoding='utf-8') as f:
                json.dump(summary_data, f, indent=2)
            if not args.quiet:
                print(f"\nBatch summary saved to: {summary_path}")

    elif args.input:
        # Single file mode
        input_file = Path(args.input)
        if not input_file.exists():
            print(f"Error: Input file not found: {input_file}")
            return

        if args.resume and is_already_processed(input_file, output_dir):
            print(f"Resume mode: {input_file.name} already processed. Skipping.")
            return

        result = extract_sentiment_from_file(input_file, output_dir=output_dir, quiet=args.quiet)

        if result['status'] == 'success':
            print(f"\n✅ Success: Extracted sentiment for {result['num_segments']} segments")
        else:
            print(f"\n❌ Error: {result['error']}")

    else:
        # Default: process first file in PROCESSED_DATA_DIR
        input_files = list(PROCESSED_DATA_DIR.glob("*_segmented_risks.json"))
        if not input_files:
            print(f"No *_segmented_risks.json files found in {PROCESSED_DATA_DIR}")
            return

        input_file = input_files[0]
        if args.resume and is_already_processed(input_file, output_dir):
            print(f"Resume mode: {input_file.name} already processed. Skipping.")
            return

        print(f"Using first file found: {input_file.name}\n")
        result = extract_sentiment_from_file(input_file, output_dir=output_dir, quiet=args.quiet)

        if result['status'] == 'success':
            print(f"\n✅ Success: Extracted sentiment for {result['num_segments']} segments")
        else:
            print(f"\n❌ Error: {result['error']}")


if __name__ == "__main__":
    main()

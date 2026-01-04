"""
Feature Engineering Pipeline Orchestrator

Runs multiple feature extraction steps in sequence on preprocessed data.
Part of the separated pipeline architecture for production MLOps.

Supported Features:
    - sentiment: Loughran-McDonald sentiment analysis
    - readability: Flesch-Kincaid, FOG, SMOG indices (future)
    - topics: LDA topic modeling (future)

Usage:
    # Run all features
    python scripts/feature_engineering/run_feature_pipeline.py --batch

    # Run specific features only
    python scripts/feature_engineering/run_feature_pipeline.py --batch --features sentiment

    # With resume support
    python scripts/feature_engineering/run_feature_pipeline.py --batch --resume

    # Parallel processing
    python scripts/feature_engineering/run_feature_pipeline.py --batch --workers 4
"""

import argparse
import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Feature extractor configuration
AVAILABLE_FEATURES = {
    'sentiment': {
        'script': 'scripts/feature_engineering/extract_sentiment_features.py',
        'description': 'Loughran-McDonald sentiment analysis',
        'output_dir': 'data/features/sentiment',
        'available': True,
    },
    'readability': {
        'script': 'scripts/feature_engineering/extract_readability_metrics.py',
        'description': 'Readability indices (Flesch-Kincaid, FOG, SMOG)',
        'output_dir': 'data/features/readability',
        'available': False,  # TODO: Implement
    },
    'topics': {
        'script': 'scripts/feature_engineering/extract_topic_features.py',
        'description': 'LDA topic modeling',
        'output_dir': 'data/features/topics',
        'available': False,  # TODO: Implement
    },
}


def run_feature_extractor(
    feature_name: str,
    batch: bool = True,
    workers: int = None,
    resume: bool = False,
    quiet: bool = False,
    additional_args: List[str] = None
) -> Dict[str, Any]:
    """
    Run a feature extraction script.

    Args:
        feature_name: Name of feature extractor ('sentiment', 'readability', etc.)
        batch: Run in batch mode
        workers: Number of parallel workers
        resume: Skip already processed files
        quiet: Minimize output
        additional_args: Additional command-line arguments

    Returns:
        Dictionary with execution result
    """
    config = AVAILABLE_FEATURES.get(feature_name)
    if not config:
        raise ValueError(f"Unknown feature: {feature_name}")

    if not config['available']:
        logger.warning(f"Feature '{feature_name}' not yet implemented. Skipping.")
        return {
            'feature': feature_name,
            'status': 'skipped',
            'reason': 'not_implemented',
            'elapsed_time': 0
        }

    script_path = Path(config['script'])
    if not script_path.exists():
        logger.error(f"Script not found: {script_path}")
        return {
            'feature': feature_name,
            'status': 'error',
            'reason': 'script_not_found',
            'elapsed_time': 0
        }

    # Build command
    cmd = [sys.executable, str(script_path)]

    if batch:
        cmd.append('--batch')

    if workers:
        cmd.extend(['--workers', str(workers)])

    if resume:
        cmd.append('--resume')

    if quiet:
        cmd.append('--quiet')

    if additional_args:
        cmd.extend(additional_args)

    # Run command
    logger.info(f"Running {feature_name} extraction: {' '.join(cmd)}")
    start_time = time.time()

    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=not quiet,
            text=True
        )

        elapsed = time.time() - start_time

        if not quiet and result.stdout:
            print(result.stdout)

        return {
            'feature': feature_name,
            'status': 'success',
            'elapsed_time': elapsed,
            'returncode': result.returncode
        }

    except subprocess.CalledProcessError as e:
        elapsed = time.time() - start_time
        logger.error(f"Feature extraction failed for {feature_name}: {e}")
        if not quiet and e.stderr:
            print(e.stderr, file=sys.stderr)

        return {
            'feature': feature_name,
            'status': 'error',
            'reason': str(e),
            'elapsed_time': elapsed,
            'returncode': e.returncode
        }


def run_pipeline(
    features: List[str],
    batch: bool = True,
    workers: int = None,
    resume: bool = False,
    quiet: bool = False
) -> List[Dict[str, Any]]:
    """
    Run feature extraction pipeline for multiple features.

    Args:
        features: List of feature names to extract
        batch: Run in batch mode
        workers: Number of parallel workers
        resume: Skip already processed files
        quiet: Minimize output

    Returns:
        List of execution results for each feature
    """
    if not quiet:
        print("\n" + "=" * 80)
        print("Feature Engineering Pipeline")
        print("=" * 80)
        print(f"Features to extract: {', '.join(features)}")
        print(f"Batch mode: {batch}")
        print(f"Workers: {workers if workers else 'auto'}")
        print(f"Resume: {resume}")
        print("=" * 80 + "\n")

    results = []
    total_start = time.time()

    for i, feature in enumerate(features, 1):
        if not quiet:
            print(f"\n[{i}/{len(features)}] Extracting {feature} features...")

        result = run_feature_extractor(
            feature,
            batch=batch,
            workers=workers,
            resume=resume,
            quiet=quiet
        )
        results.append(result)

        if not quiet:
            status_emoji = {
                'success': '✅',
                'error': '❌',
                'skipped': '⏭️'
            }.get(result['status'], '❓')

            print(f"{status_emoji} {feature}: {result['status']} "
                  f"(elapsed: {result['elapsed_time']:.1f}s)")

    total_elapsed = time.time() - total_start

    # Summary
    if not quiet:
        print("\n" + "=" * 80)
        print("Pipeline Complete!")
        print("=" * 80)

        successful = sum(1 for r in results if r['status'] == 'success')
        skipped = sum(1 for r in results if r['status'] == 'skipped')
        failed = sum(1 for r in results if r['status'] == 'error')

        print(f"Total features: {len(results)}")
        print(f"Successful: {successful}")
        if skipped > 0:
            print(f"Skipped: {skipped}")
        if failed > 0:
            print(f"Failed: {failed}")
        print(f"Total time: {total_elapsed:.1f}s")
        print("=" * 80 + "\n")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Feature Engineering Pipeline Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available Features:
  sentiment   - Loughran-McDonald sentiment analysis (AVAILABLE)
  readability - Readability indices (TODO)
  topics      - LDA topic modeling (TODO)

Examples:
  # Run all available features
  python scripts/feature_engineering/run_feature_pipeline.py --batch

  # Run specific features only
  python scripts/feature_engineering/run_feature_pipeline.py --batch --features sentiment

  # With resume and parallel processing
  python scripts/feature_engineering/run_feature_pipeline.py --batch --resume --workers 4
        """
    )

    parser.add_argument(
        '--features',
        nargs='+',
        choices=list(AVAILABLE_FEATURES.keys()),
        default=None,
        help='Features to extract (default: all available features)'
    )
    parser.add_argument(
        '--batch',
        action='store_true',
        help='Process all files in batch mode'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=None,
        help='Number of concurrent workers (default: CPU count)'
    )
    parser.add_argument(
        '--resume',
        action='store_true',
        help='Skip files that have already been processed'
    )
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Minimize output'
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help='List available features and exit'
    )

    args = parser.parse_args()

    # List features if requested
    if args.list:
        print("\nAvailable Features:")
        print("=" * 80)
        for name, config in AVAILABLE_FEATURES.items():
            status = "✅ AVAILABLE" if config['available'] else "⏳ TODO"
            print(f"{name:15} {status:20} - {config['description']}")
        print("=" * 80)
        return

    # Determine which features to run
    if args.features:
        features = args.features
    else:
        # Default: run all available features
        features = [name for name, config in AVAILABLE_FEATURES.items() if config['available']]

    if not features:
        print("No features to extract. Use --list to see available features.")
        return

    # Run pipeline
    results = run_pipeline(
        features,
        batch=args.batch,
        workers=args.workers,
        resume=args.resume,
        quiet=args.quiet
    )

    # Exit with error if any feature failed
    if any(r['status'] == 'error' for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()

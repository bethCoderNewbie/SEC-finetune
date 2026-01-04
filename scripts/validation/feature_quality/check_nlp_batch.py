#!/usr/bin/env python
"""
Generate batch validation reports for Sentiment and Readability metrics with QA thresholds.

This script:
1. Loads all segmented risk JSON files from a run directory
2. Calculates sentiment and readability metrics for each file in parallel
3. Validates against QA thresholds from configs/qa_validation/features.yaml
4. Generates consolidated report with per-file and aggregate results
5. Supports checkpoint/resume for crash recovery

Usage:
    # Basic usage (sequential)
    python scripts/validation/feature_quality/check_nlp_batch.py \
        --run-dir data/processed/20251212_161906_preprocessing_ea45dd2

    # Parallel processing with 8 workers
    python scripts/validation/feature_quality/check_nlp_batch.py \
        --run-dir data/processed/20251212_161906_preprocessing_ea45dd2 \
        --max-workers 8

    # Generate markdown report
    python scripts/validation/feature_quality/check_nlp_batch.py \
        --run-dir data/processed/20251212_161906_preprocessing_ea45dd2 \
        --format markdown \
        --output reports/nlp_validation_batch_20251227.md

Exit Codes:
    0 - All checks passed (or acceptable warnings)
    1 - Critical validation failures detected
"""

import argparse
import datetime
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config.qa_validation import ThresholdRegistry, ValidationResult
from src.features.sentiment import SentimentAnalyzer
from src.features.dictionaries import LMDictionaryManager
from src.features.readability import ReadabilityAnalyzer
from src.utils.checkpoint import CheckpointManager
from src.utils.parallel import ParallelProcessor
from src.utils.metadata import RunMetadata


# =============================================================================
# Global worker state
# =============================================================================

_worker_sentiment_analyzer: Optional[SentimentAnalyzer] = None
_worker_readability_analyzer: Optional[ReadabilityAnalyzer] = None
_worker_lm_manager: Optional[LMDictionaryManager] = None


def _init_worker() -> None:
    """Initialize analyzers once per worker process."""
    global _worker_sentiment_analyzer, _worker_readability_analyzer, _worker_lm_manager
    _worker_sentiment_analyzer = SentimentAnalyzer()
    _worker_readability_analyzer = ReadabilityAnalyzer()
    _worker_lm_manager = LMDictionaryManager.get_instance()


# =============================================================================
# Metric Calculation Functions
# =============================================================================

def calculate_file_metrics(file_path: Path) -> Dict[str, Any]:
    """
    Calculate sentiment and readability metrics for a single file.

    Args:
        file_path: Path to segmented risks JSON file

    Returns:
        Dict with calculated metrics or error information
    """
    start_time = time.time()

    try:
        # Load JSON
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        segments = data.get("segments", [])
        if not segments:
            return {
                "file": file_path.name,
                "status": "error",
                "error": "No segments found in file",
                "elapsed_time": time.time() - start_time
            }

        # Use global analyzers if available (worker mode)
        sentiment_analyzer = _worker_sentiment_analyzer or SentimentAnalyzer()
        readability_analyzer = _worker_readability_analyzer or ReadabilityAnalyzer()
        lm_manager = _worker_lm_manager or LMDictionaryManager.get_instance()

        # Calculate Sentiment Metrics
        sent_metrics = {}

        # 1. LM Hit Rate
        all_text = " ".join(seg["text"] for seg in segments)
        tokens = sentiment_analyzer.tokenize(all_text)

        if tokens:
            lm_hits = sum(1 for t in tokens if lm_manager.get_word_categories(t))
            sent_metrics['lm_hit_rate'] = (lm_hits / len(tokens))  # Store as decimal (0.0 - 1.0)
        else:
            sent_metrics['lm_hit_rate'] = 0.0

        # 2. Zero Vector Rate
        zero_count = sum(1 for seg in segments if seg.get("sentiment", {}).get("total_sentiment_words", 0) == 0)
        sent_metrics['zero_vector_rate'] = (zero_count / len(segments))  # Store as decimal
        sent_metrics['zero_vector_count'] = zero_count

        # 3. Polarity Ratios
        agg = data.get("aggregate_sentiment", {})
        sent_metrics['avg_negative'] = agg.get("avg_negative_ratio", 0)
        sent_metrics['avg_positive'] = agg.get("avg_positive_ratio", 0)
        sent_metrics['avg_uncertainty'] = agg.get("avg_uncertainty_ratio", 0)
        sent_metrics['negative_gt_positive'] = sent_metrics['avg_negative'] > sent_metrics['avg_positive']

        # 4. Uncertainty-Negative Correlation
        uncertainty_counts = [seg.get("sentiment", {}).get("uncertainty_count", 0) for seg in segments]
        negative_counts = [seg.get("sentiment", {}).get("negative_count", 0) for seg in segments]

        if len(segments) > 1:
            try:
                corr_matrix = np.corrcoef(uncertainty_counts, negative_counts)
                sent_metrics['unc_neg_corr'] = corr_matrix[0, 1]
            except:
                sent_metrics['unc_neg_corr'] = 0.0
        else:
            sent_metrics['unc_neg_corr'] = 0.0

        # Calculate Readability Metrics
        read_metrics = {}

        # Filter for long segments (>200 chars) for reliability
        long_segments = [seg["text"] for seg in segments if len(seg["text"]) > 200]

        if long_segments:
            fog_scores = []
            indices = {'fk': [], 'fog': [], 'ari': []}
            deltas = []
            obfuscation_scores = []
            complexity_proxies = []

            for text in long_segments:
                features = readability_analyzer.extract_features(text)

                fog_scores.append(features.gunning_fog_index)

                indices['fk'].append(features.flesch_kincaid_grade)
                indices['fog'].append(features.gunning_fog_index)
                indices['ari'].append(features.automated_readability_index)

                delta = features.pct_complex_words - features.pct_complex_words_adjusted
                deltas.append(delta)

                obfuscation_scores.append(features.obfuscation_score)

                proxy = (features.avg_sentence_length / 50 * 50 + features.pct_complex_words_adjusted)
                complexity_proxies.append(proxy)

            # Aggregates
            read_metrics['avg_fog'] = np.mean(fog_scores)
            read_metrics['min_fog'] = np.min(fog_scores)
            read_metrics['max_fog'] = np.max(fog_scores)

            try:
                read_metrics['fk_fog_corr'] = np.corrcoef(indices['fk'], indices['fog'])[0, 1]
            except:
                read_metrics['fk_fog_corr'] = 0.0

            try:
                read_metrics['fk_ari_corr'] = np.corrcoef(indices['fk'], indices['ari'])[0, 1]
            except:
                read_metrics['fk_ari_corr'] = 0.0

            read_metrics['avg_adjustment_delta'] = np.mean(deltas)
            read_metrics['avg_obfuscation'] = np.mean(obfuscation_scores)

            try:
                read_metrics['obfuscation_complexity_corr'] = np.corrcoef(obfuscation_scores, complexity_proxies)[0, 1]
            except:
                read_metrics['obfuscation_complexity_corr'] = 0.0
        else:
            # No long segments
            read_metrics = {
                'avg_fog': 0.0,
                'min_fog': 0.0,
                'max_fog': 0.0,
                'fk_fog_corr': 0.0,
                'fk_ari_corr': 0.0,
                'avg_adjustment_delta': 0.0,
                'avg_obfuscation': 0.0,
                'obfuscation_complexity_corr': 0.0
            }

        return {
            "file": file_path.name,
            "file_path": str(file_path),
            "status": "success",
            "sentiment_metrics": sent_metrics,
            "readability_metrics": read_metrics,
            "num_segments": len(segments),
            "num_long_segments": len(long_segments),
            "elapsed_time": time.time() - start_time,
            "error": None
        }

    except Exception as e:
        return {
            "file": file_path.name,
            "file_path": str(file_path),
            "status": "error",
            "sentiment_metrics": {},
            "readability_metrics": {},
            "elapsed_time": time.time() - start_time,
            "error": str(e)
        }


def validate_file_metrics_worker(args: Tuple[Path]) -> Dict[str, Any]:
    """Worker function for parallel metric calculation and validation."""
    file_path = args[0]
    return calculate_file_metrics(file_path)


# =============================================================================
# Validation Against QA Thresholds
# =============================================================================

def validate_metrics_against_thresholds(metrics_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate calculated metrics against QA thresholds from config.

    Args:
        metrics_result: Result from calculate_file_metrics

    Returns:
        Dict with validation results
    """
    if metrics_result['status'] == 'error':
        return {
            **metrics_result,
            "overall_status": "ERROR",
            "validation_results": [],
            "blocking_failures": []
        }

    sent_metrics = metrics_result['sentiment_metrics']
    read_metrics = metrics_result['readability_metrics']

    validation_results = []

    # Sentiment Validations
    threshold = ThresholdRegistry.get("lm_hit_rate")
    if threshold:
        result = ValidationResult.from_threshold(
            threshold,
            sent_metrics.get('lm_hit_rate', 0)
        )
        validation_results.append(result.model_dump())

    threshold = ThresholdRegistry.get("zero_vector_rate")
    if threshold:
        result = ValidationResult.from_threshold(
            threshold,
            sent_metrics.get('zero_vector_rate', 0)
        )
        validation_results.append(result.model_dump())

    threshold = ThresholdRegistry.get("polarity_ratio_negative_gt_positive")
    if threshold:
        result = ValidationResult.from_threshold(
            threshold,
            sent_metrics.get('negative_gt_positive', False)
        )
        validation_results.append(result.model_dump())

    threshold = ThresholdRegistry.get("uncertainty_negative_correlation")
    if threshold:
        result = ValidationResult.from_threshold(
            threshold,
            sent_metrics.get('unc_neg_corr', 0)
        )
        validation_results.append(result.model_dump())

    # Readability Validations
    threshold = ThresholdRegistry.get("gunning_fog_avg")
    if threshold:
        result = ValidationResult.from_threshold(
            threshold,
            read_metrics.get('avg_fog', 0)
        )
        validation_results.append(result.model_dump())

    threshold = ThresholdRegistry.get("gunning_fog_min")
    if threshold:
        result = ValidationResult.from_threshold(
            threshold,
            read_metrics.get('min_fog', 0)
        )
        validation_results.append(result.model_dump())

    threshold = ThresholdRegistry.get("gunning_fog_max")
    if threshold:
        result = ValidationResult.from_threshold(
            threshold,
            read_metrics.get('max_fog', 0)
        )
        validation_results.append(result.model_dump())

    threshold = ThresholdRegistry.get("metric_correlation_fk_fog")
    if threshold:
        result = ValidationResult.from_threshold(
            threshold,
            read_metrics.get('fk_fog_corr', 0)
        )
        validation_results.append(result.model_dump())

    threshold = ThresholdRegistry.get("metric_correlation_fk_ari")
    if threshold:
        result = ValidationResult.from_threshold(
            threshold,
            read_metrics.get('fk_ari_corr', 0)
        )
        validation_results.append(result.model_dump())

    threshold = ThresholdRegistry.get("financial_adjustment_delta")
    if threshold:
        result = ValidationResult.from_threshold(
            threshold,
            read_metrics.get('avg_adjustment_delta', 0)
        )
        validation_results.append(result.model_dump())

    threshold = ThresholdRegistry.get("obfuscation_score_avg")
    if threshold:
        result = ValidationResult.from_threshold(
            threshold,
            read_metrics.get('avg_obfuscation', 0)
        )
        validation_results.append(result.model_dump())

    threshold = ThresholdRegistry.get("obfuscation_complexity_correlation")
    if threshold:
        result = ValidationResult.from_threshold(
            threshold,
            read_metrics.get('obfuscation_complexity_corr', 0)
        )
        validation_results.append(result.model_dump())

    # Determine overall status
    blocking_failures = [
        r for r in validation_results
        if r['status'] == 'FAIL' and ThresholdRegistry.get(r['threshold_name'])
        and ThresholdRegistry.get(r['threshold_name']).blocking
    ]
    warnings = [r for r in validation_results if r['status'] == 'WARN']

    if blocking_failures:
        overall_status = "FAIL"
    elif warnings:
        overall_status = "WARN"
    else:
        overall_status = "PASS"

    return {
        **metrics_result,
        "overall_status": overall_status,
        "validation_results": validation_results,
        "blocking_failures": [r['threshold_name'] for r in blocking_failures]
    }


# =============================================================================
# Report Generation
# =============================================================================

def generate_consolidated_json_report(
    run_dir: Path,
    per_file_results: List[Dict],
    metadata: Dict
) -> Dict[str, Any]:
    """Generate consolidated JSON report."""
    # Count statuses
    passed = sum(1 for r in per_file_results if r['overall_status'] == 'PASS')
    warned = sum(1 for r in per_file_results if r['overall_status'] == 'WARN')
    failed = sum(1 for r in per_file_results if r['overall_status'] == 'FAIL')
    errors = sum(1 for r in per_file_results if r['status'] == 'error')

    # Aggregate sentiment metrics across all files
    all_sent = [r['sentiment_metrics'] for r in per_file_results if r['status'] == 'success']
    if all_sent:
        avg_lm_hit_rate = np.mean([s.get('lm_hit_rate', 0) for s in all_sent])
        avg_zero_vector_rate = np.mean([s.get('zero_vector_rate', 0) for s in all_sent])
        avg_unc_neg_corr = np.mean([s.get('unc_neg_corr', 0) for s in all_sent])
    else:
        avg_lm_hit_rate = avg_zero_vector_rate = avg_unc_neg_corr = 0.0

    # Aggregate readability metrics
    all_read = [r['readability_metrics'] for r in per_file_results if r['status'] == 'success']
    if all_read:
        avg_fog = np.mean([r.get('avg_fog', 0) for r in all_read])
        avg_fk_fog_corr = np.mean([r.get('fk_fog_corr', 0) for r in all_read])
    else:
        avg_fog = avg_fk_fog_corr = 0.0

    # Overall status
    if failed > 0:
        overall_status = "FAIL"
    elif warned > 0:
        overall_status = "WARN"
    else:
        overall_status = "PASS"

    return {
        "status": overall_status,
        "timestamp": datetime.datetime.now().isoformat(),
        "run_directory": str(run_dir),
        "metadata": metadata,
        "total_files": len(per_file_results),
        "files_validated": len([r for r in per_file_results if r['status'] == 'success']),
        "overall_summary": {
            "passed": passed,
            "warned": warned,
            "failed": failed,
            "errors": errors
        },
        "aggregate_metrics": {
            "avg_lm_hit_rate": avg_lm_hit_rate,
            "avg_zero_vector_rate": avg_zero_vector_rate,
            "avg_unc_neg_corr": avg_unc_neg_corr,
            "avg_gunning_fog": avg_fog,
            "avg_fk_fog_corr": avg_fk_fog_corr
        },
        "per_file_results": per_file_results
    }


def generate_markdown_report(report: Dict) -> str:
    """Generate markdown report from consolidated JSON report."""
    meta = report["metadata"]
    summary = report["overall_summary"]
    agg = report["aggregate_metrics"]

    md = f"""# NLP Validation Report (Batch)

**Status**: `{report['status']}`
**Source**: Batch validation of segmented risk files

## 0. Run Environment (Metadata)

| Key | Value |
|-----|-------|
| **Timestamp** | `{meta['timestamp']}` |
| **Researcher** | `{meta['researcher']}` |
| **Git Commit** | `{meta['git_commit']}` (Branch: `{meta['git_branch']}`) |
| **Python** | `{meta['python_version']}` |
| **Platform** | `{meta['platform']}` |
| **Run Directory** | `{report['run_directory']}` |

---

## 1. Executive Summary

This report validates {report['total_files']} segmented risk files against NLP feature QA metrics.

**File Status Summary**:
*   ✅ **Passed**: {summary['passed']}
*   ⚠️ **Warned**: {summary['warned']}
*   ❌ **Failed**: {summary['failed']}
*   🔴 **Errors**: {summary['errors']}

### Aggregate Metrics (Across All Files)

| Category | Metric | Avg Value | Target | Status |
|----------|--------|-----------|--------|--------|
| **Sentiment** | LM Dictionary Hit Rate | {agg['avg_lm_hit_rate']*100:.2f}% | >2% | {'✅ PASS' if agg['avg_lm_hit_rate'] > 0.02 else '❌ FAIL'} |
| **Sentiment** | Zero-Vector Rate | {agg['avg_zero_vector_rate']*100:.2f}% | <50% | {'✅ PASS' if agg['avg_zero_vector_rate'] < 0.50 else '❌ FAIL'} |
| **Sentiment** | Uncertainty-Neg Correlation | {agg['avg_unc_neg_corr']:.2f} | >0.3 | {'✅ PASS' if agg['avg_unc_neg_corr'] > 0.3 else '❌ FAIL'} |
| **Readability** | Avg Gunning Fog | {agg['avg_gunning_fog']:.1f} | 14-22 | {'✅ PASS' if 14 <= agg['avg_gunning_fog'] <= 22 else '❌ FAIL'} |
| **Readability** | FK-Fog Correlation | {agg['avg_fk_fog_corr']:.2f} | >0.7 | {'✅ PASS' if agg['avg_fk_fog_corr'] > 0.7 else '❌ FAIL'} |

---

## 2. Failed Files

"""

    failed_files = [r for r in report['per_file_results'] if r['overall_status'] in ['FAIL', 'ERROR']]
    if failed_files:
        md += f"Total failed files: {len(failed_files)}\n\n"
        for result in failed_files[:20]:  # Limit to first 20
            md += f"### {result['file']}\n\n"
            md += f"**Status**: {result['overall_status']}\n\n"
            if result['status'] == 'error':
                md += f"**Error**: {result['error']}\n\n"
            else:
                md += "**Failed Validations**:\n"
                for val in result.get('validation_results', []):
                    if val['status'] in ['FAIL', 'WARN']:
                        md += f"*   {val['status']}: {val['display_name']} (Actual: {val['actual']}, Target: {val['target']})\n"
                md += "\n"
    else:
        md += "No failed files! All files passed NLP validation checks.\n\n"

    md += """
---

## 3. Summary

"""

    if report['status'] == 'PASS':
        md += "All files passed NLP validation. Feature extraction pipelines are performing well.\n"
    elif report['status'] == 'WARN':
        md += f"{summary['warned']} files have warnings but no blocking failures. Review metrics for potential improvements.\n"
    else:
        md += f"{summary['failed']} files failed NLP validation. Review failed metrics and fix feature extraction issues.\n"

    return md


def print_summary(report: Dict, verbose: bool = False) -> None:
    """Print human-readable summary."""
    print(f"\n{'='*60}")
    print(f"NLP Validation: {report['status']}")
    print(f"{'='*60}")
    print(f"  Run directory: {report['run_directory']}")
    print(f"  Total files: {report['total_files']}")
    print(f"  Validated: {report['files_validated']}")

    summary = report['overall_summary']
    print(f"\n  File Status:")
    print(f"    Passed: {summary['passed']}")
    print(f"    Warned: {summary['warned']}")
    print(f"    Failed: {summary['failed']}")
    print(f"    Errors: {summary['errors']}")

    agg = report['aggregate_metrics']
    print(f"\n  Aggregate Metrics:")
    print(f"    LM Hit Rate: {agg['avg_lm_hit_rate']*100:.2f}%")
    print(f"    Zero Vector Rate: {agg['avg_zero_vector_rate']*100:.2f}%")
    print(f"    Avg Gunning Fog: {agg['avg_gunning_fog']:.1f}")

    if verbose and report.get('per_file_results'):
        print(f"\n{'='*60}")
        print("Per-File Results:")
        print(f"{'='*60}")
        for result in report['per_file_results'][:50]:  # Limit output
            status_icon = {
                'PASS': '[PASS]',
                'WARN': '[WARN]',
                'FAIL': '[FAIL]',
                'ERROR': '[ERR ]'
            }.get(result['overall_status'], '[----]')

            print(f"  {status_icon} {result['file']}")
            if result['status'] == 'error':
                print(f"         Error: {result['error']}")

    print(f"\n{'='*60}")
    if report['status'] == 'PASS':
        print("Result: ALL CHECKS PASSED")
    elif report['status'] == 'WARN':
        print("Result: PASSED WITH WARNINGS")
    else:
        print("Result: CHECKS FAILED")
    print(f"{'='*60}")


# =============================================================================
# Batch Orchestrator (REFACTORED to use shared utilities)
# =============================================================================

def batch_generate_validation_report(
    run_dir: Path,
    output_path: Optional[Path] = None,
    output_format: str = "json",
    max_workers: Optional[int] = None,
    checkpoint_interval: int = 10,
    resume: bool = False,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    Generate batch NLP validation report with parallel processing.

    Args:
        run_dir: Directory containing segmented risk JSON files
        output_path: Output path for report
        output_format: "json" or "markdown"
        max_workers: Number of parallel workers
        checkpoint_interval: Save checkpoint every N files
        resume: Resume from checkpoint
        verbose: Verbose output

    Returns:
        Consolidated report dict
    """
    # Gather metadata
    metadata = RunMetadata.gather()

    # Setup paths
    if output_path is None:
        ext = "json" if output_format == "json" else "md"
        output_path = run_dir / f"nlp_validation_report.{ext}"

    checkpoint = CheckpointManager(run_dir / "_nlp_validation_checkpoint.json")

    # Find all segmented risk JSON files
    json_files = sorted([
        f for f in run_dir.glob("*segmented*.json")
        if not f.name.startswith("_")
    ])

    if not json_files:
        return {
            "status": "ERROR",
            "message": f"No segmented risk JSON files found in: {run_dir}",
            "timestamp": datetime.datetime.now().isoformat(),
            "run_directory": str(run_dir),
            "metadata": metadata
        }

    total_files_found = len(json_files)
    print(f"Found {total_files_found} segmented risk files in: {run_dir}")

    # Resume from checkpoint if requested
    processed_files = []
    all_results = []
    current_metrics = {}

    if resume and checkpoint.exists():
        validated_set, all_results, current_metrics = checkpoint.load()
        processed_files = list(validated_set)
        json_files = [f for f in json_files if f.name not in validated_set]
        if validated_set:
            print(f"Resuming: {len(processed_files)} files already validated, {len(json_files)} remaining")

    if not json_files:
        print("All files already validated!")
        if all_results:
            report = generate_consolidated_json_report(run_dir, all_results, metadata)
            if output_format == "markdown":
                md_content = generate_markdown_report(report)
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(md_content)
            else:
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(report, f, indent=2, default=str)
            return report

    # Create parallel processor
    processor = ParallelProcessor(
        max_workers=max_workers,
        initializer=_init_worker,
        max_tasks_per_child=50
    )

    # Determine processing mode
    use_parallel = processor.should_use_parallel(len(json_files), max_workers)
    if use_parallel:
        workers = max_workers or min(os.cpu_count() or 4, len(json_files))
        print(f"Using {workers} parallel workers")
    else:
        print("Using sequential processing")

    # Process files with checkpoint callback
    start_time = time.time()

    def checkpoint_callback(idx: int, result: Dict):
        """Calculate metrics, validate, and checkpoint."""
        validated_result = validate_metrics_against_thresholds(result)
        all_results.append(validated_result)
        processed_files.append(validated_result['file'])

        if idx % checkpoint_interval == 0:
            current_metrics = {
                "total_files": total_files_found,
                "processed": len(processed_files)
            }
            checkpoint.save(processed_files, all_results, current_metrics)

    # Prepare task arguments
    task_args = [(f,) for f in json_files]

    # Process batch
    results = processor.process_batch(
        items=task_args,
        worker_func=validate_file_metrics_worker,
        progress_callback=checkpoint_callback,
        verbose=verbose
    )

    # Ensure all results are captured
    for result in results:
        if result['file'] not in processed_files:
            validated_result = validate_metrics_against_thresholds(result)
            all_results.append(validated_result)
            processed_files.append(validated_result['file'])

    elapsed_time = time.time() - start_time
    print(f"\nCompleted in {elapsed_time:.2f} seconds")

    # Generate report
    report = generate_consolidated_json_report(run_dir, all_results, metadata)

    # Save report
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_format == "markdown":
        md_content = generate_markdown_report(report)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
    else:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, default=str)

    print(f"Report saved to: {output_path}")

    # Clean up checkpoint
    checkpoint.cleanup()

    return report


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Generate batch NLP validation report with QA thresholds",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "--run-dir",
        type=Path,
        required=True,
        help="Directory containing segmented risk JSON files"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output path for report (default: {run-dir}/nlp_validation_report.{ext})"
    )
    parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="json",
        help="Output format: json or markdown (default: json)"
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        help="Number of parallel workers (default: CPU count, use 1 for sequential)"
    )
    parser.add_argument(
        "--checkpoint-interval",
        type=int,
        default=10,
        help="Save checkpoint every N files (default: 10)"
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from checkpoint if exists"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed progress per file"
    )

    args = parser.parse_args()

    # Validate run directory
    if not args.run_dir.exists():
        print(f"Error: Directory not found: {args.run_dir}")
        sys.exit(1)

    if not args.run_dir.is_dir():
        print(f"Error: Not a directory: {args.run_dir}")
        sys.exit(1)

    # Run batch validation
    print(f"Starting batch NLP validation on: {args.run_dir}")
    report = batch_generate_validation_report(
        run_dir=args.run_dir,
        output_path=args.output,
        output_format=args.format,
        max_workers=args.max_workers,
        checkpoint_interval=args.checkpoint_interval,
        resume=args.resume,
        verbose=args.verbose
    )

    # Handle error case
    if report.get("status") == "ERROR":
        print(f"Error: {report.get('message', 'Unknown error')}")
        sys.exit(1)

    # Print summary
    print_summary(report, verbose=args.verbose)

    # Exit code: fail if critical failures
    if report['status'] == 'FAIL':
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()

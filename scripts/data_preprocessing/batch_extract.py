"""
Batch extract risk factors sections from parsed SEC filings

Pipeline Step: Parse → **Extract** → Clean → Segment → Sentiment

This script takes parsed JSON files (from batch_parse.py) and extracts
the risk factors section (Item 1A) with metadata preservation.

Usage:
    # Basic usage (creates new run folder with timestamp)
    python scripts/data_preprocessing/batch_extract.py
    python scripts/data_preprocessing/batch_extract.py --run-name my_extraction_run

    # Specify input directory (parsed files)
    python scripts/data_preprocessing/batch_extract.py --input-dir data/interim/parsed/20251212_171015_batch_parse_ea45dd2

    # Resume mode - skip files already extracted in ANY run
    python scripts/data_preprocessing/batch_extract.py --resume
    python scripts/data_preprocessing/batch_extract.py --resume --run-name ver1

    # Continue a specific previous run (reuse existing run folder)
    python scripts/data_preprocessing/batch_extract.py --continue-run 20251212_171015_batch_parse_ea45dd2

    # Performance options
    python scripts/data_preprocessing/batch_extract.py --quiet                    # Minimal output
    python scripts/data_preprocessing/batch_extract.py --checkpoint-interval 5    # Save progress every 5 files
    python scripts/data_preprocessing/batch_extract.py --workers 4                # Parallel processing

    # Overwrite existing files
    python scripts/data_preprocessing/batch_extract.py --overwrite

    # Combined example
    python scripts/data_preprocessing/batch_extract.py --run-name production --resume --quiet

Output Structure:
    data/interim/extracted/{run_id}_{run_name}_{git_sha}/
    ├── AAPL_10K_2021_{run_id}_extracted_risks.json
    ├── MSFT_10K_2022_{run_id}_extracted_risks.json
    ├── metrics.json
    └── _checkpoint.json  (removed on completion)
"""

import argparse
import json
import re
import time
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set, Dict, Any, Tuple
from concurrent.futures import ProcessPoolExecutor, as_completed

from src.preprocessing.parser import ParsedFiling
from src.preprocessing.extractor import SECSectionExtractor, ExtractedSection
from src.config import settings, RunContext

# Directory shortcuts
PARSED_DATA_DIR = settings.paths.parsed_data_dir
EXTRACTED_DATA_DIR = settings.paths.extracted_data_dir

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global worker object for multiprocessing
_worker_extractor: Optional[SECSectionExtractor] = None


def _init_worker() -> None:
    """Initialize worker process with reusable extractor object."""
    global _worker_extractor
    _worker_extractor = SECSectionExtractor()


# =============================================================================
# Resume & Smart Sampling Helpers
# =============================================================================

def is_file_extracted(input_file: Path, output_dir: Path, run_id: Optional[str] = None) -> bool:
    """
    Check if a file has already been extracted by checking for output in output_dir.

    Args:
        input_file: Path to input parsed JSON file
        output_dir: Directory containing extracted files
        run_id: Optional run identifier for filename matching

    Returns:
        True if the extracted output file exists, False otherwise
    """
    # Extract original stem from parsed filename
    # Convention: {original_stem}_{run_id}_parsed.json → {original_stem}_{run_id}_extracted_risks.json
    # Input: AAPL_10K_2021_20251212_200149_parsed.json
    # Output: AAPL_10K_2021_{run_id}_extracted_risks.json
    original_stem = _get_original_stem(input_file.stem)

    run_suffix = f"_{run_id}" if run_id else ""
    output_filename = f"{original_stem}{run_suffix}_extracted_risks.json"
    output_path = output_dir / output_filename
    return output_path.exists()


def _get_original_stem(parsed_stem: str) -> str:
    """
    Extract original file stem from parsed filename.

    Convention: {original_stem}_{run_id}_parsed
    Input: AAPL_10K_2021_20251212_200149_parsed
    Output: AAPL_10K_2021
    """
    # Remove _parsed suffix
    stem = parsed_stem.replace("_parsed", "")
    # Remove run_id (timestamp pattern YYYYMMDD_HHMMSS)
    stem = re.sub(r'_\d{8}_\d{6}$', '', stem)
    return stem


def get_extracted_files_set(output_dir: Path, run_id: Optional[str] = None) -> Set[str]:
    """
    Get set of all already extracted file stems for fast lookup.

    Args:
        output_dir: Directory containing extracted files
        run_id: Optional run identifier for filename matching (None = check ANY run)

    Returns:
        Set of original file stems that have been extracted
    """
    extracted = set()
    if not output_dir.exists():
        return extracted

    # Pattern: {stem}_{run_id}_extracted_risks.json
    if run_id:
        pattern = f"*_{run_id}_extracted_risks.json"
    else:
        pattern = "*_extracted_risks.json"

    for f in output_dir.glob(pattern):
        # Extract original stem
        stem = f.stem.replace("_extracted_risks", "")
        # Remove run_id (timestamp pattern)
        stem = re.sub(r'_\d{8}_\d{6}$', '', stem)
        extracted.add(stem)

    return extracted


def get_extracted_files_set_all_runs(base_dir: Path) -> Set[str]:
    """
    Get set of all already extracted file stems across ALL run folders.

    Args:
        base_dir: Base directory containing run folders (e.g., data/interim/extracted/)

    Returns:
        Set of original file stems that have been extracted in any run
    """
    extracted = set()
    if not base_dir.exists():
        return extracted

    for run_folder in base_dir.iterdir():
        if run_folder.is_dir():
            extracted.update(get_extracted_files_set(run_folder, run_id=None))

    return extracted


def filter_unextracted_files(
    parsed_files: List[Path],
    output_dir: Path,
    run_id: Optional[str] = None,
    quiet: bool = False,
    check_all_runs: bool = False,
    base_dir: Optional[Path] = None
) -> List[Path]:
    """
    Filter out already extracted files efficiently using batch lookup.

    Args:
        parsed_files: List of input parsed JSON file paths
        output_dir: Directory containing extracted files for current run
        run_id: Optional run identifier
        quiet: If True, suppress output
        check_all_runs: If True, check ALL run folders in base_dir
        base_dir: Base directory containing all run folders

    Returns:
        List of unextracted files
    """
    if check_all_runs and base_dir:
        extracted_stems = get_extracted_files_set_all_runs(base_dir)
    else:
        extracted_stems = get_extracted_files_set(output_dir, run_id)

    # Compare original stems
    unextracted = []
    for f in parsed_files:
        original_stem = _get_original_stem(f.stem)
        if original_stem not in extracted_stems:
            unextracted.append(f)

    skipped = len(parsed_files) - len(unextracted)
    if skipped > 0 and not quiet:
        print(f"Resume mode: Skipping {skipped} already extracted files")

    return unextracted


def save_checkpoint(checkpoint_path: Path, processed_files: List[str], metrics: dict) -> None:
    """Save checkpoint for crash recovery."""
    checkpoint_data = {
        "processed_files": processed_files,
        "metrics": metrics,
        "timestamp": datetime.now().isoformat()
    }
    with open(checkpoint_path, 'w', encoding='utf-8') as f:
        json.dump(checkpoint_data, f, indent=2)


def load_checkpoint(checkpoint_path: Path) -> Optional[dict]:
    """Load checkpoint if exists."""
    if not checkpoint_path.exists():
        return None
    with open(checkpoint_path, 'r', encoding='utf-8') as f:
        return json.load(f)


# =============================================================================
# Core Extraction Logic
# =============================================================================

def extract_single_file(
    parsed_file: Path,
    output_dir: Path,
    run_id: Optional[str] = None,
    overwrite: bool = False
) -> Dict[str, Any]:
    """
    Extract risk factors from a single parsed filing.

    Args:
        parsed_file: Path to parsed JSON file
        output_dir: Directory to save extracted section
        run_id: Optional run identifier for filename
        overwrite: Whether to overwrite existing files

    Returns:
        Dictionary with extraction result
    """
    start_time = time.time()
    original_stem = _get_original_stem(parsed_file.stem)

    try:
        # Load parsed filing dict
        filing_data = ParsedFiling.load_from_json(parsed_file)
        metadata = filing_data.get('metadata', {})

        # Extract risk factors section using dict-based method
        extractor = SECSectionExtractor()
        risk_section = extractor.extract_risk_factors_from_dict(filing_data)

        if not risk_section:
            return {
                'file': parsed_file.name,
                'original_stem': original_stem,
                'status': 'warning',
                'section_length': 0,
                'num_subsections': 0,
                'sic_code': metadata.get('sic_code'),
                'cik': metadata.get('cik'),
                'elapsed_time': time.time() - start_time,
                'error': 'Risk Factors section not found'
            }

        # Construct output path
        run_suffix = f"_{run_id}" if run_id else ""
        output_filename = f"{original_stem}{run_suffix}_extracted_risks.json"
        output_path = output_dir / output_filename

        # Check if exists
        if output_path.exists() and not overwrite:
            return {
                'file': parsed_file.name,
                'original_stem': original_stem,
                'status': 'skipped',
                'section_length': 0,
                'num_subsections': 0,
                'sic_code': risk_section.sic_code,
                'cik': risk_section.cik,
                'elapsed_time': time.time() - start_time,
                'error': 'File already exists'
            }

        # Save extracted section
        risk_section.save_to_json(output_path, overwrite=overwrite)

        return {
            'file': parsed_file.name,
            'original_stem': original_stem,
            'status': 'success',
            'section_length': len(risk_section),
            'num_subsections': len(risk_section.subsections),
            'sic_code': risk_section.sic_code,
            'cik': risk_section.cik,
            'elapsed_time': time.time() - start_time,
            'error': None
        }

    except Exception as e:
        logger.exception("Error extracting %s", parsed_file.name)
        return {
            'file': parsed_file.name,
            'original_stem': original_stem,
            'status': 'error',
            'section_length': 0,
            'num_subsections': 0,
            'sic_code': None,
            'cik': None,
            'elapsed_time': time.time() - start_time,
            'error': str(e)
        }


def extract_single_file_fast(args: Tuple[Path, Path, Optional[str], bool]) -> Dict[str, Any]:
    """
    Worker function for parallel extraction using pre-initialized extractor.

    Args:
        args: Tuple of (parsed_file, output_dir, run_id, overwrite)

    Returns:
        Dictionary with extraction result
    """
    global _worker_extractor
    parsed_file, output_dir, run_id, overwrite = args

    start_time = time.time()
    original_stem = _get_original_stem(parsed_file.stem)

    try:
        # Load parsed filing dict
        filing_data = ParsedFiling.load_from_json(parsed_file)
        metadata = filing_data.get('metadata', {})

        # Extract risk factors section using dict-based method
        risk_section = _worker_extractor.extract_risk_factors_from_dict(filing_data)

        if not risk_section:
            return {
                'file': parsed_file.name,
                'original_stem': original_stem,
                'status': 'warning',
                'section_length': 0,
                'num_subsections': 0,
                'sic_code': metadata.get('sic_code'),
                'cik': metadata.get('cik'),
                'elapsed_time': time.time() - start_time,
                'error': 'Risk Factors section not found'
            }

        # Construct output path
        run_suffix = f"_{run_id}" if run_id else ""
        output_filename = f"{original_stem}{run_suffix}_extracted_risks.json"
        output_path = output_dir / output_filename

        # Check if exists
        if output_path.exists() and not overwrite:
            return {
                'file': parsed_file.name,
                'original_stem': original_stem,
                'status': 'skipped',
                'section_length': 0,
                'num_subsections': 0,
                'sic_code': risk_section.sic_code,
                'cik': risk_section.cik,
                'elapsed_time': time.time() - start_time,
                'error': 'File already exists'
            }

        # Save extracted section
        risk_section.save_to_json(output_path, overwrite=overwrite)

        return {
            'file': parsed_file.name,
            'original_stem': original_stem,
            'status': 'success',
            'section_length': len(risk_section),
            'num_subsections': len(risk_section.subsections),
            'sic_code': risk_section.sic_code,
            'cik': risk_section.cik,
            'elapsed_time': time.time() - start_time,
            'error': None
        }

    except Exception as e:
        logger.exception("Error extracting %s", parsed_file.name)
        return {
            'file': parsed_file.name,
            'original_stem': original_stem,
            'status': 'error',
            'section_length': 0,
            'num_subsections': 0,
            'sic_code': None,
            'cik': None,
            'elapsed_time': time.time() - start_time,
            'error': str(e)
        }


# =============================================================================
# Batch Processing
# =============================================================================

def batch_extract_sections(
    input_dir: Path = None,
    output_dir: Path = None,
    pattern: str = "*_parsed.json",
    overwrite: bool = False,
    run_context: RunContext = None,
    resume: bool = False,
    checkpoint_interval: int = 10,
    quiet: bool = False,
    explicit_run_id: Optional[str] = None,
    max_workers: Optional[int] = None
):
    """
    Extract risk factors sections from all parsed files in a directory.

    Args:
        input_dir: Directory containing parsed JSON files
        output_dir: Directory to save extracted sections
        pattern: File pattern to match (default: *_parsed.json)
        overwrite: Whether to overwrite existing files
        run_context: Optional RunContext for metric logging
        resume: Whether to skip already extracted files
        checkpoint_interval: Save checkpoint every N files
        quiet: Minimize output
        explicit_run_id: Optional explicit run_id (for --continue-run)
        max_workers: Number of parallel workers (None = CPU count)
    """
    # Use defaults if not provided
    if input_dir is None:
        input_dir = PARSED_DATA_DIR
    if output_dir is None:
        output_dir = EXTRACTED_DATA_DIR

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Find all parsed files
    parsed_files = sorted(list(input_dir.glob(pattern)))

    if not parsed_files:
        print(f"No files matching '{pattern}' found in: {input_dir}")
        return

    total_found = len(parsed_files)
    run_id = explicit_run_id or (run_context.run_id if run_context else None)

    # Resume: filter out already extracted files (check ALL run folders)
    if resume and not overwrite:
        base_dir = output_dir.parent if output_dir else EXTRACTED_DATA_DIR
        parsed_files = filter_unextracted_files(
            parsed_files,
            output_dir,
            run_id=run_id,
            quiet=quiet,
            check_all_runs=True,
            base_dir=base_dir
        )
        if not parsed_files:
            print("All files have already been extracted. Nothing to do.")
            return

    if not quiet:
        print(f"Found {total_found} file(s) total")
        if resume:
            print(f"Processing {len(parsed_files)} unextracted file(s)")
        print(f"Output directory: {output_dir}")
        if run_context and run_context.git_sha:
            print(f"Git SHA: {run_context.git_sha}")
        print("=" * 80)

    # Checkpoint setup
    checkpoint_path = output_dir / "_checkpoint.json"
    processed_files: List[str] = []

    # Counters
    success_count = 0
    warning_count = 0
    error_count = 0
    skipped_count = 0

    # Use run_id for consistent naming
    if run_id is None:
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    start_time = time.time()

    # Determine if we should use parallel processing
    use_parallel = max_workers != 1 and len(parsed_files) > 1

    if use_parallel:
        # Parallel processing
        if max_workers is None:
            max_workers = min(os.cpu_count() or 4, len(parsed_files))

        if not quiet:
            print(f"Using {max_workers} parallel workers")

        task_args = [(f, output_dir, run_id, overwrite) for f in parsed_files]

        with ProcessPoolExecutor(
            max_workers=max_workers,
            initializer=_init_worker,
            max_tasks_per_child=50
        ) as executor:
            future_to_file = {
                executor.submit(extract_single_file_fast, args): args[0]
                for args in task_args
            }

            for idx, future in enumerate(as_completed(future_to_file), 1):
                result = future.result()

                # Update counters
                if result['status'] == 'success':
                    success_count += 1
                elif result['status'] == 'warning':
                    warning_count += 1
                elif result['status'] == 'skipped':
                    skipped_count += 1
                else:
                    error_count += 1

                processed_files.append(result['file'])

                # Progress output
                if not quiet:
                    _print_result(result, idx, len(parsed_files))
                elif idx % 10 == 0 or idx == len(parsed_files):
                    print(f"Progress: {idx}/{len(parsed_files)}", end='\r')

                # Checkpoint
                if idx % checkpoint_interval == 0:
                    current_metrics = _build_metrics(
                        len(parsed_files), success_count, warning_count,
                        error_count, skipped_count, run_id
                    )
                    save_checkpoint(checkpoint_path, processed_files, current_metrics)

    else:
        # Sequential processing
        for idx, parsed_file in enumerate(parsed_files, 1):
            if not quiet:
                print(f"\n[{idx}/{len(parsed_files)}] Processing: {parsed_file.name}")

            result = extract_single_file(parsed_file, output_dir, run_id, overwrite)

            # Update counters
            if result['status'] == 'success':
                success_count += 1
            elif result['status'] == 'warning':
                warning_count += 1
            elif result['status'] == 'skipped':
                skipped_count += 1
            else:
                error_count += 1

            processed_files.append(result['file'])

            # Progress output
            if not quiet:
                _print_single_result(result)
            elif idx % 10 == 0 or idx == len(parsed_files):
                print(f"Progress: {idx}/{len(parsed_files)}", end='\r')

            # Checkpoint
            if idx % checkpoint_interval == 0:
                current_metrics = _build_metrics(
                    len(parsed_files), success_count, warning_count,
                    error_count, skipped_count, run_id
                )
                save_checkpoint(checkpoint_path, processed_files, current_metrics)

    # Clear progress line in quiet mode
    if quiet:
        print()

    total_time = time.time() - start_time

    # Final metrics
    metrics = _build_metrics(
        len(parsed_files), success_count, warning_count,
        error_count, skipped_count, run_id
    )
    metrics['total_time_seconds'] = total_time

    # Save metrics to RunContext if available
    if run_context:
        run_context.save_metrics(metrics)
        if not quiet:
            print(f"\nMetrics saved to: {run_context.output_dir / 'metrics.json'}")

    # Remove checkpoint on successful completion
    if checkpoint_path.exists():
        checkpoint_path.unlink()

    # Summary
    if not quiet:
        print("\n" + "=" * 80)
        print("Batch extraction complete!")
        print(f"  Successful: {success_count}")
        if warning_count > 0:
            print(f"  Warnings: {warning_count}")
        if skipped_count > 0:
            print(f"  Skipped: {skipped_count}")
        print(f"  Errors: {error_count}")
        print(f"  Total: {len(parsed_files)}")
        print(f"  Time: {total_time:.1f}s ({len(parsed_files)/total_time:.2f} files/sec)")
        print(f"\nExtracted files saved to: {output_dir}")
    else:
        print(f"Complete: {success_count}/{len(parsed_files)} successful")


def _print_result(result: dict, idx: int, total: int) -> None:
    """Print result for parallel processing."""
    if result['status'] == 'success':
        sic_info = f", SIC={result.get('sic_code', 'N/A')}" if result.get('sic_code') else ""
        print(f"[{idx}/{total}] OK: {result['original_stem']} "
              f"({result['section_length']:,} chars, {result['num_subsections']} subsections{sic_info})")
    elif result['status'] == 'warning':
        print(f"[{idx}/{total}] WARN: {result['original_stem']} - {result['error']}")
    elif result['status'] == 'skipped':
        print(f"[{idx}/{total}] SKIP: {result['original_stem']} - {result['error']}")
    else:
        print(f"[{idx}/{total}] FAIL: {result['original_stem']} - {result['error']}")


def _print_single_result(result: dict) -> None:
    """Print result for sequential processing."""
    if result['status'] == 'success':
        print(f"  [OK] Extracted {result['section_length']:,} characters")
        print(f"  [OK] Found {result['num_subsections']} subsections")
        if result.get('sic_code'):
            print(f"  [OK] SIC: {result['sic_code']}, CIK: {result['cik']}")
    elif result['status'] == 'warning':
        print(f"  [WARN] {result['error']}")
    elif result['status'] == 'skipped':
        print(f"  [SKIP] {result['error']}")
    else:
        print(f"  [ERROR] {result['error']}")


def _build_metrics(total: int, success: int, warning: int, error: int, skipped: int, run_id: str) -> dict:
    """Build metrics dictionary."""
    return {
        "total_files": total,
        "successful": success,
        "warnings": warning,
        "errors": error,
        "skipped": skipped,
        "run_id": run_id
    }


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Batch extract risk factors sections from parsed SEC filings"
    )
    parser.add_argument(
        '--input-dir',
        type=str,
        help=f'Input directory containing parsed JSON files (default: {PARSED_DATA_DIR})'
    )
    parser.add_argument(
        '--pattern',
        type=str,
        default='*_parsed.json',
        help='File pattern to match (default: *_parsed.json)'
    )
    parser.add_argument(
        '--overwrite',
        action='store_true',
        help='Overwrite existing extracted files'
    )
    parser.add_argument(
        '--run-name',
        type=str,
        default='batch_extract',
        help='Name for this execution run'
    )
    parser.add_argument(
        '--resume',
        action='store_true',
        help='Skip files that have already been extracted (smart sampling)'
    )
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Minimize output for better performance'
    )
    parser.add_argument(
        '--checkpoint-interval',
        type=int,
        default=10,
        help='Save checkpoint every N files (default: 10)'
    )
    parser.add_argument(
        '--continue-run',
        type=str,
        default=None,
        metavar='RUN_FOLDER',
        help='Continue a previous run by specifying its folder name'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=None,
        help='Number of parallel workers (default: CPU count, use 1 for sequential)'
    )

    args = parser.parse_args()

    # Determine input directory
    if args.input_dir:
        input_dir = Path(args.input_dir)
    else:
        # Find most recent parsed run folder
        if PARSED_DATA_DIR.exists():
            run_folders = sorted([f for f in PARSED_DATA_DIR.iterdir() if f.is_dir()], reverse=True)
            if run_folders:
                input_dir = run_folders[0]
                print(f"Using most recent parsed run: {input_dir.name}")
            else:
                input_dir = PARSED_DATA_DIR
        else:
            input_dir = PARSED_DATA_DIR

    # Handle --continue-run: reuse existing run folder
    if args.continue_run:
        output_dir = EXTRACTED_DATA_DIR / args.continue_run
        if not output_dir.exists():
            print(f"Error: Run folder not found: {output_dir}")
            print(f"Available runs in {EXTRACTED_DATA_DIR}:")
            if EXTRACTED_DATA_DIR.exists():
                for folder in sorted(EXTRACTED_DATA_DIR.iterdir()):
                    if folder.is_dir():
                        print(f"  - {folder.name}")
            return

        # Extract run_id from folder name
        parts = args.continue_run.split('_')
        run_id = f"{parts[0]}_{parts[1]}" if len(parts) >= 2 else args.continue_run

        if not args.quiet:
            print(f"Continuing run: {args.continue_run}")
            print(f"Run ID: {run_id}")
            print(f"Output Directory: {output_dir}")

        batch_extract_sections(
            input_dir=input_dir,
            output_dir=output_dir,
            pattern=args.pattern,
            overwrite=args.overwrite,
            run_context=None,
            resume=True,
            checkpoint_interval=args.checkpoint_interval,
            quiet=args.quiet,
            explicit_run_id=run_id,
            max_workers=args.workers
        )
        return

    # Initialize new RunContext
    run = RunContext(
        name=args.run_name,
        auto_git_sha=True,
        base_dir=EXTRACTED_DATA_DIR
    )
    run.create()

    if not args.quiet:
        print(f"Run ID: {run.run_id}")
        print(f"Output Directory: {run.output_dir}")
        if run.git_sha:
            print(f"Git SHA: {run.git_sha}")
        print(f"Input Directory: {input_dir}")

    batch_extract_sections(
        input_dir=input_dir,
        output_dir=run.output_dir,
        pattern=args.pattern,
        overwrite=args.overwrite,
        run_context=run,
        resume=args.resume,
        checkpoint_interval=args.checkpoint_interval,
        quiet=args.quiet,
        max_workers=args.workers
    )


if __name__ == "__main__":
    main()

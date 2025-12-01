"""
Run complete preprocessing pipeline: Parse → Extract → Clean → Segment → Sentiment Analysis

Usage:
    # Single file mode
    python scripts/02_data_preprocessing/run_preprocessing_pipeline.py
    python scripts/02_data_preprocessing/run_preprocessing_pipeline.py --input data/raw/AAPL_10K.html
    python scripts/02_data_preprocessing/run_preprocessing_pipeline.py --input data/raw/AAPL_10K.html --no-sentiment

    # Batch mode (concurrent processing)
    python scripts/02_data_preprocessing/run_preprocessing_pipeline.py --batch
    python scripts/02_data_preprocessing/run_preprocessing_pipeline.py --batch --workers 4
    python scripts/02_data_preprocessing/run_preprocessing_pipeline.py --batch --no-sentiment
    python scripts/02_data_preprocessing/run_preprocessing_pipeline.py --batch --resume  # Skip already processed files
    python scripts/02_data_preprocessing/run_preprocessing_pipeline.py --batch --quiet  # Minimal output
    python scripts/02_data_preprocessing/run_preprocessing_pipeline.py --batch --chunk-size 50  # Process in chunks
"""

import argparse
import json
import time
import os
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Optional
from src.preprocessing.parser import SECFilingParser, ParsedFiling
from src.preprocessing.extractor import SECSectionExtractor, ExtractedSection
from src.preprocessing.cleaning import TextCleaner
from src.preprocessing.segmenter import RiskSegmenter
from src.features.sentiment import SentimentAnalyzer
from src.config import RAW_DATA_DIR, PARSED_DATA_DIR, EXTRACTED_DATA_DIR, PROCESSED_DATA_DIR, settings, ensure_directories

# Global worker objects - initialized once per process for efficiency
_worker_parser = None
_worker_extractor = None
_worker_cleaner = None
_worker_segmenter = None
_worker_analyzer = None


def _init_worker(extract_sentiment: bool = True):
    """
    Initialize worker process with reusable objects.
    Called once per worker process to avoid repeated initialization overhead.
    """
    global _worker_parser, _worker_extractor, _worker_cleaner, _worker_segmenter, _worker_analyzer

    _worker_parser = SECFilingParser()
    _worker_extractor = SECSectionExtractor()
    _worker_cleaner = TextCleaner()
    _worker_segmenter = RiskSegmenter(
        min_length=settings.preprocessing.min_segment_length,
        max_length=settings.preprocessing.max_segment_length
    )
    if extract_sentiment:
        _worker_analyzer = SentimentAnalyzer()
    else:
        _worker_analyzer = None


def is_file_processed(input_file: Path) -> bool:
    """
    Check if a file has already been preprocessed by checking for output in PROCESSED_DATA_DIR.

    Args:
        input_file: Path to input HTML file

    Returns:
        True if the processed output file exists, False otherwise
    """
    output_filename = input_file.stem + "_segmented_risks.json"
    output_path = PROCESSED_DATA_DIR / output_filename
    return output_path.exists()


def get_processed_files_set() -> set:
    """
    Get set of all already processed file stems for fast lookup.
    More efficient than checking each file individually.

    Returns:
        Set of file stems that have been processed
    """
    processed = set()
    if PROCESSED_DATA_DIR.exists():
        for f in PROCESSED_DATA_DIR.glob("*_segmented_risks.json"):
            # Extract original stem by removing "_segmented_risks" suffix
            stem = f.stem.replace("_segmented_risks", "")
            processed.add(stem)
    return processed


def filter_unprocessed_files(html_files: list, quiet: bool = False) -> list:
    """
    Filter out already processed files efficiently using batch lookup.

    Args:
        html_files: List of input HTML file paths
        quiet: If True, suppress output

    Returns:
        List of unprocessed files
    """
    processed_stems = get_processed_files_set()
    unprocessed = [f for f in html_files if f.stem not in processed_stems]

    skipped = len(html_files) - len(unprocessed)
    if skipped > 0 and not quiet:
        print(f"Resume mode: Skipping {skipped} already processed files")

    return unprocessed


def run_pipeline(input_file: Path, save_intermediates: bool = True, extract_sentiment: bool = True):
    """
    Run the full preprocessing pipeline on a single filing

    Args:
        input_file: Path to input HTML file
        save_intermediates: Whether to save intermediate results
        extract_sentiment: Whether to extract sentiment features (default: True)
    """
    print(f"Preprocessing Pipeline for: {input_file.name}")
    print("=" * 80)

    # Step 1: Parse
    print("\n[1/5] Parsing SEC filing...")
    parser = SECFilingParser()
    filing = parser.parse_filing(
        input_file,
        form_type="10-K",
        save_output=save_intermediates
    )
    print(f"  [OK] Parsed {len(filing)} semantic elements")
    print(f"  [OK] Found {filing.metadata['num_sections']} sections")

    # Step 2: Extract
    print("\n[2/5] Extracting risk factors section...")
    extractor = SECSectionExtractor()
    risk_section = extractor.extract_risk_factors(filing)

    if risk_section:
        print(f"  [OK] Extracted '{risk_section.title}'")
        print(f"  [OK] Section length: {len(risk_section):,} characters")
        print(f"  [OK] Found {len(risk_section.subsections)} risk subsections")
        print(f"  [OK] Contains {risk_section.metadata['num_elements']} semantic elements")

        # Save extracted section if requested
        if save_intermediates:
            output_filename = input_file.stem + "_extracted_risks.json"
            output_path = EXTRACTED_DATA_DIR / output_filename
            risk_section.save_to_json(output_path, overwrite=True)
            print(f"  [OK] Saved to: {output_path}")
    else:
        print("  [WARN] Risk Factors section not found in filing")
        risk_section = None

    # Step 3: Clean
    print("\n[3/5] Cleaning extracted text...")
    cleaned_section = None
    if risk_section:
        # Initialize text cleaner using config settings
        cleaner = TextCleaner()

        # Clean the extracted text
        cleaned_text = cleaner.clean_text(risk_section.text, deep_clean=False)

        print(f"  [OK] Cleaned text from {len(risk_section.text):,} to {len(cleaned_text):,} characters")

        # Create a new ExtractedSection with cleaned text
        cleaned_section = ExtractedSection(
            text=cleaned_text,
            identifier=risk_section.identifier,
            title=risk_section.title,
            subsections=risk_section.subsections,
            elements=risk_section.elements,
            metadata={
                **risk_section.metadata,
                'cleaned': True,
                'cleaning_settings': {
                    'remove_html_tags': settings.preprocessing.remove_html_tags,
                    'normalize_whitespace': settings.preprocessing.normalize_whitespace,
                    'remove_page_numbers': settings.preprocessing.remove_page_numbers,
                }
            }
        )

        # Save cleaned section if requested
        if save_intermediates:
            output_filename = input_file.stem + "_cleaned_risks.json"
            output_path = EXTRACTED_DATA_DIR / output_filename
            cleaned_section.save_to_json(output_path, overwrite=True)
            print(f"  [OK] Saved cleaned section to: {output_path}")
    else:
        print("  [SKIP] No extracted section to clean")

    # Step 4: Segment
    print("\n[4/5] Segmenting into risk factors...")
    risk_segments = None
    if cleaned_section:
        # Initialize segmenter using config settings
        segmenter = RiskSegmenter(
            min_length=settings.preprocessing.min_segment_length,
            max_length=settings.preprocessing.max_segment_length
        )

        # Segment the cleaned text into individual risks
        risk_segments = segmenter.segment_risks(cleaned_section.text)

        print(f"  [OK] Segmented into {len(risk_segments)} risk factors")
        print(f"  [OK] Average segment length: {sum(len(s) for s in risk_segments) // len(risk_segments):,} characters")

        # Step 5: Sentiment Analysis
        sentiment_features_list = None
        if extract_sentiment:
            print("\n[5/5] Extracting sentiment features...")
            analyzer = SentimentAnalyzer()

            # Extract sentiment features for all segments (batch processing)
            sentiment_features_list = analyzer.extract_features_batch(risk_segments)

            print(f"  [OK] Extracted sentiment features for {len(sentiment_features_list)} segments")

            # Compute aggregate sentiment statistics
            avg_negative = sum(f.negative_ratio for f in sentiment_features_list) / len(sentiment_features_list)
            avg_uncertainty = sum(f.uncertainty_ratio for f in sentiment_features_list) / len(sentiment_features_list)
            avg_positive = sum(f.positive_ratio for f in sentiment_features_list) / len(sentiment_features_list)

            print(f"  [OK] Average sentiment ratios across all segments:")
            print(f"       Negative:    {avg_negative:.4f}")
            print(f"       Uncertainty: {avg_uncertainty:.4f}")
            print(f"       Positive:    {avg_positive:.4f}")
        else:
            print("\n[5/5] Sentiment analysis skipped (use without --no-sentiment to enable)")

        # Save segments if requested
        if save_intermediates:
            output_filename = input_file.stem + "_segmented_risks.json"
            output_path = PROCESSED_DATA_DIR / output_filename
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Create structured output
            segments_data = {
                'filing_name': input_file.name,
                'ticker': input_file.stem.split('_')[0] if '_' in input_file.stem else input_file.stem,
                'section_title': cleaned_section.title,
                'section_identifier': cleaned_section.identifier,
                'num_segments': len(risk_segments),
                'segmentation_settings': {
                    'min_segment_length': settings.preprocessing.min_segment_length,
                    'max_segment_length': settings.preprocessing.max_segment_length,
                },
                'sentiment_analysis_enabled': extract_sentiment,
            }

            # Add aggregate sentiment if available
            if sentiment_features_list:
                segments_data['aggregate_sentiment'] = {
                    'avg_negative_ratio': avg_negative,
                    'avg_uncertainty_ratio': avg_uncertainty,
                    'avg_positive_ratio': avg_positive,
                    'avg_sentiment_word_ratio': sum(f.sentiment_word_ratio for f in sentiment_features_list) / len(sentiment_features_list),
                }

            # Build segments with optional sentiment features
            segments_data['segments'] = []
            for i, segment in enumerate(risk_segments, start=1):
                segment_dict = {
                    'id': i,
                    'text': segment,
                    'length': len(segment),
                    'word_count': len(segment.split())
                }

                # Add sentiment features if available
                if sentiment_features_list:
                    sentiment = sentiment_features_list[i - 1]
                    segment_dict['sentiment'] = {
                        'negative_count': sentiment.negative_count,
                        'positive_count': sentiment.positive_count,
                        'uncertainty_count': sentiment.uncertainty_count,
                        'litigious_count': sentiment.litigious_count,
                        'constraining_count': sentiment.constraining_count,
                        'negative_ratio': sentiment.negative_ratio,
                        'positive_ratio': sentiment.positive_ratio,
                        'uncertainty_ratio': sentiment.uncertainty_ratio,
                        'litigious_ratio': sentiment.litigious_ratio,
                        'constraining_ratio': sentiment.constraining_ratio,
                        'total_sentiment_words': sentiment.total_sentiment_words,
                        'sentiment_word_ratio': sentiment.sentiment_word_ratio,
                    }

                segments_data['segments'].append(segment_dict)

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(segments_data, f, indent=2, ensure_ascii=False)

            print(f"  [OK] Saved segments to: {output_path}")
    else:
        print("  [SKIP] No cleaned section to segment")

    print("\n" + "=" * 80)
    print("Pipeline complete!")

    return filing, risk_section, cleaned_section, risk_segments, sentiment_features_list


def process_single_file(args: tuple) -> dict:
    """
    Worker function for concurrent processing.

    Args:
        args: Tuple of (input_file, save_intermediates, extract_sentiment)

    Returns:
        Dictionary with processing result
    """
    input_file, save_intermediates, extract_sentiment = args

    try:
        start_time = time.time()
        filing, risk_section, cleaned_section, risk_segments, sentiment_features = run_pipeline(
            input_file,
            save_intermediates=save_intermediates,
            extract_sentiment=extract_sentiment
        )
        elapsed = time.time() - start_time

        return {
            'file': input_file.name,
            'status': 'success',
            'num_segments': len(risk_segments) if risk_segments else 0,
            'elapsed_time': elapsed,
            'error': None
        }
    except Exception as e:
        return {
            'file': input_file.name,
            'status': 'error',
            'num_segments': 0,
            'elapsed_time': 0,
            'error': str(e)
        }


def process_single_file_fast(args: tuple) -> dict:
    """
    Optimized worker function using pre-initialized global objects.
    Reduces latency by avoiding repeated object creation.

    Args:
        args: Tuple of (input_file, save_intermediates)

    Returns:
        Dictionary with processing result
    """
    global _worker_parser, _worker_extractor, _worker_cleaner, _worker_segmenter, _worker_analyzer

    input_file, save_intermediates = args

    try:
        start_time = time.time()

        # Step 1: Parse
        filing = _worker_parser.parse_filing(
            input_file,
            form_type="10-K",
            save_output=save_intermediates
        )

        # Step 2: Extract
        risk_section = _worker_extractor.extract_risk_factors(filing)

        if not risk_section:
            return {
                'file': input_file.name,
                'status': 'warning',
                'num_segments': 0,
                'elapsed_time': time.time() - start_time,
                'error': 'Risk Factors section not found'
            }

        # Save extracted section
        if save_intermediates:
            output_filename = input_file.stem + "_extracted_risks.json"
            output_path = EXTRACTED_DATA_DIR / output_filename
            risk_section.save_to_json(output_path, overwrite=True)

        # Step 3: Clean
        cleaned_text = _worker_cleaner.clean_text(risk_section.text, deep_clean=False)

        cleaned_section = ExtractedSection(
            text=cleaned_text,
            identifier=risk_section.identifier,
            title=risk_section.title,
            subsections=risk_section.subsections,
            elements=risk_section.elements,
            metadata={
                **risk_section.metadata,
                'cleaned': True,
                'cleaning_settings': {
                    'remove_html_tags': settings.preprocessing.remove_html_tags,
                    'normalize_whitespace': settings.preprocessing.normalize_whitespace,
                    'remove_page_numbers': settings.preprocessing.remove_page_numbers,
                }
            }
        )

        # Save cleaned section
        if save_intermediates:
            output_filename = input_file.stem + "_cleaned_risks.json"
            output_path = EXTRACTED_DATA_DIR / output_filename
            cleaned_section.save_to_json(output_path, overwrite=True)

        # Step 4: Segment
        risk_segments = _worker_segmenter.segment_risks(cleaned_section.text)

        if not risk_segments:
            return {
                'file': input_file.name,
                'status': 'warning',
                'num_segments': 0,
                'elapsed_time': time.time() - start_time,
                'error': 'No segments extracted'
            }

        # Step 5: Sentiment Analysis (if enabled)
        sentiment_features_list = None
        if _worker_analyzer:
            sentiment_features_list = _worker_analyzer.extract_features_batch(risk_segments)

        # Save final output
        if save_intermediates:
            output_filename = input_file.stem + "_segmented_risks.json"
            output_path = PROCESSED_DATA_DIR / output_filename
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Build output data
            segments_data = {
                'filing_name': input_file.name,
                'ticker': input_file.stem.split('_')[0] if '_' in input_file.stem else input_file.stem,
                'section_title': cleaned_section.title,
                'section_identifier': cleaned_section.identifier,
                'num_segments': len(risk_segments),
                'segmentation_settings': {
                    'min_segment_length': settings.preprocessing.min_segment_length,
                    'max_segment_length': settings.preprocessing.max_segment_length,
                },
                'sentiment_analysis_enabled': _worker_analyzer is not None,
            }

            # Add aggregate sentiment
            if sentiment_features_list:
                n = len(sentiment_features_list)
                segments_data['aggregate_sentiment'] = {
                    'avg_negative_ratio': sum(f.negative_ratio for f in sentiment_features_list) / n,
                    'avg_uncertainty_ratio': sum(f.uncertainty_ratio for f in sentiment_features_list) / n,
                    'avg_positive_ratio': sum(f.positive_ratio for f in sentiment_features_list) / n,
                    'avg_sentiment_word_ratio': sum(f.sentiment_word_ratio for f in sentiment_features_list) / n,
                }

            # Build segments
            segments_data['segments'] = []
            for i, segment in enumerate(risk_segments, start=1):
                segment_dict = {
                    'id': i,
                    'text': segment,
                    'length': len(segment),
                    'word_count': len(segment.split())
                }

                if sentiment_features_list:
                    sentiment = sentiment_features_list[i - 1]
                    segment_dict['sentiment'] = {
                        'negative_count': sentiment.negative_count,
                        'positive_count': sentiment.positive_count,
                        'uncertainty_count': sentiment.uncertainty_count,
                        'litigious_count': sentiment.litigious_count,
                        'constraining_count': sentiment.constraining_count,
                        'negative_ratio': sentiment.negative_ratio,
                        'positive_ratio': sentiment.positive_ratio,
                        'uncertainty_ratio': sentiment.uncertainty_ratio,
                        'litigious_ratio': sentiment.litigious_ratio,
                        'constraining_ratio': sentiment.constraining_ratio,
                        'total_sentiment_words': sentiment.total_sentiment_words,
                        'sentiment_word_ratio': sentiment.sentiment_word_ratio,
                    }

                segments_data['segments'].append(segment_dict)

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(segments_data, f, indent=2, ensure_ascii=False)

        elapsed = time.time() - start_time

        return {
            'file': input_file.name,
            'status': 'success',
            'num_segments': len(risk_segments),
            'elapsed_time': elapsed,
            'error': None
        }

    except Exception as e:
        return {
            'file': input_file.name,
            'status': 'error',
            'num_segments': 0,
            'elapsed_time': 0,
            'error': str(e)
        }


def run_batch_pipeline(
    input_files: list[Path],
    save_intermediates: bool = True,
    extract_sentiment: bool = True,
    max_workers: Optional[int] = None,
    quiet: bool = False,
    chunk_size: Optional[int] = None
) -> list[dict]:
    """
    Run the preprocessing pipeline on multiple files concurrently with optimizations.

    Args:
        input_files: List of paths to input HTML files
        save_intermediates: Whether to save intermediate results
        extract_sentiment: Whether to extract sentiment features
        max_workers: Maximum number of concurrent workers (default: number of CPUs)
        quiet: If True, minimize output for better performance
        chunk_size: If set, process files in chunks to manage memory

    Returns:
        List of processing results for each file
    """
    if not input_files:
        if not quiet:
            print("No files to process")
        return []

    total_files = len(input_files)

    if not quiet:
        print(f"\nBatch Processing: {total_files} files")
        print(f"Max workers: {max_workers if max_workers else 'auto (CPU count)'}")
        print(f"Mode: {'Optimized (fast)' if True else 'Standard'}")
        if chunk_size:
            print(f"Chunk size: {chunk_size}")
        print("=" * 80)

    # Determine optimal worker count
    if max_workers is None:
        max_workers = min(os.cpu_count() or 4, len(input_files))

    # Prepare arguments for each file (fast mode uses 2-tuple)
    task_args = [(f, save_intermediates) for f in input_files]

    results = []
    successful = 0
    failed = 0
    warnings = 0

    start_time = time.time()

    # Process in chunks if specified
    if chunk_size and len(input_files) > chunk_size:
        chunks = [task_args[i:i + chunk_size] for i in range(0, len(task_args), chunk_size)]
        total_chunks = len(chunks)

        for chunk_idx, chunk in enumerate(chunks, 1):
            if not quiet:
                print(f"\nProcessing chunk {chunk_idx}/{total_chunks} ({len(chunk)} files)")

            chunk_results = _process_chunk(
                chunk, extract_sentiment, max_workers, quiet,
                len(results), total_files
            )
            results.extend(chunk_results)

            # Update counters
            for r in chunk_results:
                if r['status'] == 'success':
                    successful += 1
                elif r['status'] == 'warning':
                    warnings += 1
                else:
                    failed += 1
    else:
        # Process all at once
        chunk_results = _process_chunk(
            task_args, extract_sentiment, max_workers, quiet, 0, total_files
        )
        results.extend(chunk_results)

        for r in chunk_results:
            if r['status'] == 'success':
                successful += 1
            elif r['status'] == 'warning':
                warnings += 1
            else:
                failed += 1

    total_time = time.time() - start_time

    # Summary
    if not quiet:
        print("\n" + "=" * 80)
        print(f"Batch Processing Complete!")
        print(f"  Total files: {total_files}")
        print(f"  Successful: {successful}")
        if warnings > 0:
            print(f"  Warnings: {warnings}")
        print(f"  Failed: {failed}")
        print(f"  Total time: {total_time:.1f}s")
        if total_files > 0:
            print(f"  Avg time per file: {total_time / total_files:.1f}s")
            print(f"  Throughput: {total_files / total_time:.2f} files/sec")

    return results


def _process_chunk(
    task_args: list,
    extract_sentiment: bool,
    max_workers: int,
    quiet: bool,
    offset: int,
    total_files: int
) -> list[dict]:
    """
    Process a chunk of files using ProcessPoolExecutor with worker initialization.

    Args:
        task_args: List of (input_file, save_intermediates) tuples
        extract_sentiment: Whether to extract sentiment features
        max_workers: Number of workers
        quiet: If True, minimize output
        offset: Number of files already processed
        total_files: Total number of files being processed

    Returns:
        List of processing results
    """
    results = []

    # Use initializer to set up worker processes once
    with ProcessPoolExecutor(
        max_workers=max_workers,
        initializer=_init_worker,
        initargs=(extract_sentiment,),
        max_tasks_per_child=50  # Restart workers periodically to prevent memory leaks
    ) as executor:
        # Submit all tasks
        future_to_file = {
            executor.submit(process_single_file_fast, args): args[0]
            for args in task_args
        }

        # Process completed tasks as they finish
        for i, future in enumerate(as_completed(future_to_file), 1):
            result = future.result()
            results.append(result)

            current = offset + i

            if quiet:
                # Minimal progress indicator
                if current % 10 == 0 or current == total_files:
                    print(f"Progress: {current}/{total_files}", end='\r')
            else:
                if result['status'] == 'success':
                    print(f"[{current}/{total_files}] OK: {result['file']} "
                          f"({result['num_segments']} segments, {result['elapsed_time']:.1f}s)")
                elif result['status'] == 'warning':
                    print(f"[{current}/{total_files}] WARN: {result['file']} - {result['error']}")
                else:
                    print(f"[{current}/{total_files}] FAIL: {result['file']} - {result['error']}")

    if quiet and (offset + len(task_args)) == total_files:
        print()  # New line after progress

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Run complete preprocessing pipeline"
    )
    parser.add_argument(
        '--input',
        type=str,
        help='Input HTML file path (single file mode)'
    )
    parser.add_argument(
        '--batch',
        action='store_true',
        help='Process all HTML files in RAW_DATA_DIR concurrently'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=None,
        help='Number of concurrent workers for batch mode (default: CPU count)'
    )
    parser.add_argument(
        '--no-save',
        action='store_true',
        help='Do not save intermediate results'
    )
    parser.add_argument(
        '--no-sentiment',
        action='store_true',
        help='Skip sentiment analysis step'
    )
    parser.add_argument(
        '--resume',
        action='store_true',
        help='Skip files that have already been processed (check output directory)'
    )
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Minimize output for better performance in batch mode'
    )
    parser.add_argument(
        '--chunk-size',
        type=int,
        default=None,
        help='Process files in chunks of this size to manage memory'
    )

    args = parser.parse_args()

    ensure_directories()

    if args.batch:
        # Batch mode: process all HTML files concurrently
        html_files = sorted(RAW_DATA_DIR.glob("*.html"))
        if not html_files:
            print(f"No HTML files found in {RAW_DATA_DIR}")
            return

        # Filter out already processed files efficiently
        if args.resume:
            html_files = filter_unprocessed_files(html_files, quiet=args.quiet)
            if not html_files:
                print("All files have already been processed. Nothing to do.")
                return

        results = run_batch_pipeline(
            html_files,
            save_intermediates=not args.no_save,
            extract_sentiment=not args.no_sentiment,
            max_workers=args.workers,
            quiet=args.quiet,
            chunk_size=args.chunk_size
        )

        # Save batch results summary
        if results:
            summary_path = PROCESSED_DATA_DIR / "batch_processing_summary.json"
            with open(summary_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2)
            if not args.quiet:
                print(f"\nBatch summary saved to: {summary_path}")

    elif args.input:
        # Single file mode with specified input
        input_file = Path(args.input)
        if args.resume and is_file_processed(input_file):
            print(f"Resume mode: {input_file.name} already processed. Skipping.")
            return
        run_pipeline(input_file, save_intermediates=not args.no_save, extract_sentiment=not args.no_sentiment)
    else:
        # Single file mode: use first file in RAW_DATA_DIR
        html_files = list(RAW_DATA_DIR.glob("*.html"))
        if not html_files:
            print(f"No HTML files found in {RAW_DATA_DIR}")
            return
        input_file = html_files[0]
        if args.resume and is_file_processed(input_file):
            print(f"Resume mode: {input_file.name} already processed. Skipping.")
            return
        print(f"Using first file found: {input_file.name}\n")
        run_pipeline(input_file, save_intermediates=not args.no_save, extract_sentiment=not args.no_sentiment)


if __name__ == "__main__":
    main()

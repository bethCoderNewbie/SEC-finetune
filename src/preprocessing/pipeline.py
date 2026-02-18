"""
Preprocessing Pipeline for SEC Filings

Orchestrates the complete preprocessing flow:
1. Parse - Parse HTML filing into semantic structure
2. Extract - Extract specific sections with metadata
3. Clean - Clean and normalize text
4. Segment - Split into individual risk segments

All metadata (sic_code, sic_name, cik, ticker, company_name) is preserved
throughout the pipeline.

Efficiency optimizations:
- Global worker objects reused across files (CLI pipeline pattern)
- HTML sanitization removed (unnecessary preprocessing overhead)
- Models loaded once per worker, not per file (~50x efficiency gain)
"""

import logging
import time
from pathlib import Path
from typing import Optional, Union, List, Dict, Any

from pydantic import BaseModel, ConfigDict, Field

# Import processing classes (models are defined within these modules)
from .parser import SECFilingParser
from .cleaning import TextCleaner
from .extractor import SECSectionExtractor
from .segmenter import RiskSegmenter, SegmentedRisks
from .constants import SectionIdentifier
# Import parallel processing utility
from src.utils.parallel import ParallelProcessor
# Import memory-aware resource allocation
from src.utils.memory_semaphore import MemorySemaphore, FileCategory
# Import resume and progress utilities
from src.utils.resume import ResumeFilter
from src.utils.progress_logger import ProgressLogger
# Import shared worker pool and resource tracker
from src.utils.worker_pool import (
    init_preprocessing_worker,
    get_worker_parser,
    get_worker_cleaner,
    get_worker_extractor,
    get_worker_segmenter,
)
from src.utils.resource_tracker import ResourceTracker

logger = logging.getLogger(__name__)


class PipelineConfig(BaseModel):
    """
    Configuration for the preprocessing pipeline (Pydantic V2)

    Attributes:
        remove_html: Whether to remove HTML tags from text
        deep_clean: Whether to apply NLP-based deep cleaning
        use_lemmatization: Whether to lemmatize words
        remove_stopwords: Whether to remove stop words
        remove_punctuation: Whether to remove punctuation
        remove_numbers: Whether to remove numbers
        min_segment_length: Minimum segment length (None = use default from settings)
        max_segment_length: Maximum segment length (None = use default from settings)
        semantic_model_name: SentenceTransformer model for semantic segmentation
        similarity_threshold: Cosine similarity threshold for semantic breaks

    Note:
        HTML sanitization has been removed (unnecessary preprocessing overhead).
        The sec-parser library handles raw HTML directly and efficiently.
    """
    model_config = ConfigDict(
        validate_assignment=True,
        extra='forbid',  # Raise error on unknown fields
    )

    # Cleaning options
    remove_html: bool = Field(default=True, description="Remove HTML tags from text")
    deep_clean: bool = Field(default=False, description="Apply NLP-based deep cleaning")
    use_lemmatization: bool = Field(default=False, description="Lemmatize words")
    remove_stopwords: bool = Field(default=False, description="Remove stop words")
    remove_punctuation: bool = Field(default=False, description="Remove punctuation")
    remove_numbers: bool = Field(default=False, description="Remove numbers")

    # Segmentation options
    min_segment_length: Optional[int] = Field(
        default=None,
        description="Minimum segment length (None = use default from settings)"
    )
    max_segment_length: Optional[int] = Field(
        default=None,
        description="Maximum segment length (None = use default from settings)"
    )
    semantic_model_name: str = Field(
        default="all-MiniLM-L6-v2",
        description="SentenceTransformer model for semantic segmentation"
    )
    similarity_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Cosine similarity threshold for semantic breaks"
    )


def _process_filing_with_global_workers(
    file_path: Path,
    form_type: str,
    config: PipelineConfig,
    save_output: Optional[Path],
    overwrite: bool,
    save_intermediates: bool = False,
    tracker: Optional[ResourceTracker] = None,
) -> Optional[SegmentedRisks]:
    """
    Process a SEC filing using global worker objects (efficient model reuse).

    Workers are provided by :mod:`src.utils.worker_pool` (initialised once
    per worker process via ``init_preprocessing_worker``).

    Flow (sanitization removed):
    1. Parse HTML → ParsedFiling (with metadata)
    2. Extract section → ExtractedSection (with metadata)
    3. Clean text → cleaned text
    4. Segment → SegmentedRisks (with metadata)

    Args:
        file_path: Path to the HTML filing file
        form_type: Type of SEC form ("10-K" or "10-Q")
        config: Pipeline configuration
        save_output: Optional path to save the result as JSON
        overwrite: Whether to overwrite existing output file
        save_intermediates: Save parsed/extracted outputs to interim dirs
        tracker: Optional ResourceTracker for per-step timing/memory

    Returns:
        SegmentedRisks with segments and preserved metadata, or None if extraction fails
    """
    from contextlib import nullcontext

    logger.info("Processing filing: %s", file_path.name)

    # Determine section based on form type
    if form_type.upper() in ["10-K", "10K"]:
        section = SectionIdentifier.ITEM_1A_RISK_FACTORS
    else:
        section = SectionIdentifier.ITEM_1A_RISK_FACTORS_10Q

    # Step 1: Parse HTML filing (no sanitization)
    logger.info("Step 1/4: Parsing HTML filing...")
    with tracker.track_module("parser") if tracker else nullcontext():
        parsed = get_worker_parser().parse_filing(
            file_path, form_type, save_output=save_intermediates
        )

    logger.info(
        "Parsed %d elements. Metadata: CIK=%s, SIC=%s (%s)",
        len(parsed),
        parsed.metadata.get('cik'),
        parsed.metadata.get('sic_code'),
        parsed.metadata.get('sic_name'),
    )

    # Step 2: Extract section (metadata flows through)
    logger.info("Step 2/4: Extracting section '%s'...", section.value)
    with tracker.track_module("extractor") if tracker else nullcontext():
        extracted = get_worker_extractor().extract_section(parsed, section)

    if extracted is None:
        logger.warning("Section '%s' not found in filing", section.value)
        return None

    logger.info(
        "Extracted section: %d chars, %d subsections",
        len(extracted.text),
        len(extracted.subsections),
    )

    if save_intermediates:
        from src.config import settings as _cfg  # lazy import (avoids circular at module level)
        extracted_dir = _cfg.paths.extracted_data_dir
        extracted_dir.mkdir(parents=True, exist_ok=True)
        extracted_path = extracted_dir / f"{file_path.stem}_extracted_risks.json"
        extracted.save_to_json(extracted_path, overwrite=True)
        logger.info("Saved extracted section to: %s", extracted_path)

    # Step 3: Clean text
    logger.info("Step 3/4: Cleaning text...")
    with tracker.track_module("cleaner") if tracker else nullcontext():
        if config.remove_html:
            cleaned_text = get_worker_cleaner().remove_html_tags(extracted.text)
        else:
            cleaned_text = extracted.text

        cleaned_text = get_worker_cleaner().clean_text(
            cleaned_text,
            deep_clean=config.deep_clean
        )
    logger.info("Cleaned text: %d chars", len(cleaned_text))

    # Step 4: Segment (metadata preserved)
    logger.info("Step 4/4: Segmenting risks...")
    with tracker.track_module("segmenter") if tracker else nullcontext():
        result = get_worker_segmenter().segment_extracted_section(
            extracted,
            cleaned_text=cleaned_text
        )
    logger.info("Created %d segments", len(result))

    # Save if requested
    if save_output:
        output_path = result.save_to_json(save_output, overwrite=overwrite)
        logger.info("Saved result to: %s", output_path)

    return result


# Module-level worker function for parallel processing
def _process_single_filing_worker(args: tuple) -> Dict[str, Any]:
    """
    Worker function for parallel batch processing with elapsed time tracking.

    Uses global worker objects provided by :mod:`src.utils.worker_pool`,
    initialised once per worker process via ``init_preprocessing_worker``.

    Args:
        args: Tuple of (file_path, config_dict, form_type, output_dir, overwrite, save_intermediates)

    Returns:
        Dict with status, result, elapsed_time, and resource_usage
    """
    file_path, config_dict, form_type, output_dir, overwrite, save_intermediates = args
    file_path = Path(file_path)

    # Get file size for logging
    file_size_mb = file_path.stat().st_size / (1024 * 1024) if file_path.exists() else 0

    tracker = ResourceTracker()

    try:
        # Reconstruct pipeline config from dict
        config = PipelineConfig(**config_dict) if config_dict else PipelineConfig()

        # Generate output path if output_dir is provided
        save_output = None
        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            save_output = output_dir / f"{file_path.stem}_segmented.json"

        # Process the file using global workers (no per-file instantiation)
        result = _process_filing_with_global_workers(
            file_path=file_path,
            form_type=form_type,
            config=config,
            save_output=save_output,
            overwrite=overwrite,
            save_intermediates=save_intermediates,
            tracker=tracker,
        )

        usage = tracker.finalize()

        if result:
            return {
                'status': 'success',
                'file': file_path.name,
                'result': result,  # Include actual SegmentedRisks object
                'num_segments': len(result),
                'sic_code': result.sic_code,
                'company_name': result.company_name,
                'elapsed_time': usage.elapsed_time(),
                'file_size_mb': file_size_mb,
                'resource_usage': usage.to_dict(),
            }
        else:
            return {
                'status': 'warning',
                'file': file_path.name,
                'result': None,
                'error': 'No result returned from processing',
                'elapsed_time': usage.elapsed_time(),
                'file_size_mb': file_size_mb,
                'resource_usage': usage.to_dict(),
            }

    except Exception as e:
        usage = tracker.finalize()
        logger.error(
            "Failed to process %s (%.1fs): %s", file_path.name, usage.elapsed_time(), e
        )
        return {
            'status': 'error',
            'file': file_path.name,
            'result': None,
            'error': str(e),
            'elapsed_time': usage.elapsed_time(),
            'file_size_mb': file_size_mb,
            'resource_usage': usage.to_dict(),
        }


class SECPreprocessingPipeline:
    """
    Complete preprocessing pipeline for SEC filings

    Flow: Parse → Extract → Clean → Segment

    All metadata is preserved through the pipeline:
    - sic_code: Standard Industrial Classification code
    - sic_name: SIC industry name (e.g., "PHARMACEUTICAL PREPARATIONS")
    - cik: Central Index Key
    - ticker: Stock ticker symbol
    - company_name: Company name

    Efficiency optimizations:
    - Uses global worker objects in batch mode (models loaded once per worker)
    - HTML sanitization removed (unnecessary overhead)

    Example:
        >>> pipeline = SECPreprocessingPipeline()
        >>> result = pipeline.process_filing(
        ...     "data/raw/AAPL_10K.html",
        ...     form_type="10-K"
        ... )
        >>> print(f"Company: {result.company_name}")
        >>> print(f"SIC: {result.sic_code} - {result.sic_name}")
        >>> print(f"Segments: {len(result.segments)}")
    """

    def __init__(self, config: Optional[PipelineConfig] = None):
        """
        Initialize the preprocessing pipeline

        Args:
            config: Pipeline configuration. Uses defaults if not provided.

        Note:
            When used in batch mode, global worker objects are used instead
            for efficiency (models loaded once per worker, not per file).
        """
        self.config = config or PipelineConfig()

        # Initialize components
        self.parser = SECFilingParser()
        self.cleaner = TextCleaner(
            use_lemmatization=self.config.use_lemmatization,
            remove_stopwords=self.config.remove_stopwords,
            remove_punctuation=self.config.remove_punctuation,
            remove_numbers=self.config.remove_numbers,
        )
        self.extractor = SECSectionExtractor()
        self.segmenter = RiskSegmenter(
            min_length=self.config.min_segment_length,
            max_length=self.config.max_segment_length,
            semantic_model_name=self.config.semantic_model_name,
            similarity_threshold=self.config.similarity_threshold,
        )

    def process_filing(
        self,
        file_path: Union[str, Path],
        form_type: str = "10-K",
        section: SectionIdentifier = SectionIdentifier.ITEM_1A_RISK_FACTORS,
        save_output: Optional[Union[str, Path]] = None,
        overwrite: bool = False,
        save_intermediates: bool = False,
    ) -> Optional[SegmentedRisks]:
        """
        Process a SEC filing through the complete pipeline

        Flow (sanitization removed for efficiency):
        1. Parse HTML → ParsedFiling (with metadata)
        2. Extract section → ExtractedSection (with metadata)
        3. Clean text → cleaned text
        4. Segment → SegmentedRisks (with metadata)

        Args:
            file_path: Path to the HTML filing file
            form_type: Type of SEC form ("10-K" or "10-Q")
            section: Section to extract (default: Risk Factors)
            save_output: Optional path to save the result as JSON
            overwrite: Whether to overwrite existing output file

        Returns:
            SegmentedRisks with segments and preserved metadata, or None if extraction fails

        Example:
            >>> pipeline = SECPreprocessingPipeline()
            >>> result = pipeline.process_filing("AAPL_10K.html")
            >>> print(f"Found {len(result)} risk segments")
            >>> print(f"SIC: {result.sic_name}")
        """
        file_path = Path(file_path)
        logger.info("Processing filing: %s", file_path.name)

        # Step 1: Parse HTML filing (no sanitization)
        logger.info("Step 1/4: Parsing HTML filing...")
        parsed = self.parser.parse_filing(file_path, form_type, save_output=save_intermediates)

        logger.info(
            "Parsed %d elements. Metadata: CIK=%s, SIC=%s (%s)",
            len(parsed),
            parsed.metadata.get('cik'),
            parsed.metadata.get('sic_code'),
            parsed.metadata.get('sic_name'),
        )

        # Step 2: Extract section (metadata flows through)
        logger.info("Step 2/4: Extracting section '%s'...", section.value)
        extracted = self.extractor.extract_section(parsed, section)

        if extracted is None:
            logger.warning("Section '%s' not found in filing", section.value)
            return None

        logger.info(
            "Extracted section: %d chars, %d subsections",
            len(extracted.text),
            len(extracted.subsections),
        )

        if save_intermediates:
            from src.config import settings as _cfg
            extracted_dir = _cfg.paths.extracted_data_dir
            extracted_dir.mkdir(parents=True, exist_ok=True)
            extracted_path = extracted_dir / f"{file_path.stem}_extracted_risks.json"
            extracted.save_to_json(extracted_path, overwrite=True)
            logger.info("Saved extracted section to: %s", extracted_path)

        # Step 3: Clean text
        logger.info("Step 3/4: Cleaning text...")
        if self.config.remove_html:
            cleaned_text = self.cleaner.remove_html_tags(extracted.text)
        else:
            cleaned_text = extracted.text

        cleaned_text = self.cleaner.clean_text(
            cleaned_text,
            deep_clean=self.config.deep_clean
        )
        logger.info("Cleaned text: %d chars", len(cleaned_text))

        # Step 4: Segment (metadata preserved)
        logger.info("Step 4/4: Segmenting risks...")
        result = self.segmenter.segment_extracted_section(
            extracted,
            cleaned_text=cleaned_text
        )
        logger.info("Created %d segments", len(result))

        # Save if requested
        if save_output:
            output_path = result.save_to_json(save_output, overwrite=overwrite)
            logger.info("Saved result to: %s", output_path)

        return result

    def process_and_validate(
        self,
        file_path: Union[str, Path],
        form_type: str = "10-K",
        section: SectionIdentifier = SectionIdentifier.ITEM_1A_RISK_FACTORS,
        validator=None
    ) -> tuple[Optional[SegmentedRisks], str, Optional[dict]]:
        """
        Process a filing and validate the result inline (for quarantine pattern).

        This method enables inline validation during processing to support
        the quarantine pattern. Files that fail validation are NOT written
        to production directories.

        Args:
            file_path: Path to the HTML filing file
            form_type: Type of SEC form ("10-K" or "10-Q")
            section: Section to extract (default: Risk Factors)
            validator: HealthCheckValidator instance (if None, creates one)

        Returns:
            Tuple of (result, status, validation_report):
            - result: SegmentedRisks if processing succeeded, None if failed
            - status: "PASS" or "FAIL" (validation status)
            - validation_report: Validation report dict (if validation performed)

        Example:
            >>> pipeline = SECPreprocessingPipeline()
            >>> result, status, report = pipeline.process_and_validate("AAPL_10K.html")
            >>> if status == "FAIL":
            ...     # Quarantine the file
            ...     quarantine_file(result, report)
            ... else:
            ...     # Write to production
            ...     result.save_to_json("output.json")
        """
        # Process the filing
        try:
            result = self.process_filing(
                file_path=file_path,
                form_type=form_type,
                section=section,
                save_output=None,  # Don't save yet (wait for validation)
                overwrite=False
            )

            if result is None:
                return None, "FAIL", {"reason": "extraction_failed"}

        except Exception as e:
            logger.error(f"Processing failed: {e}")
            return None, "FAIL", {"reason": "processing_error", "error": str(e)}

        # Validate the result
        if validator is None:
            from src.config.qa_validation import HealthCheckValidator
            validator = HealthCheckValidator()

        # Convert result to dict for validation
        data_dict = result.model_dump()
        validation_report = validator.check_single(data_dict)

        status = validation_report["status"]

        return result, status, validation_report

    def process_risk_factors(
        self,
        file_path: Union[str, Path],
        form_type: str = "10-K",
        save_output: Optional[Union[str, Path]] = None,
        overwrite: bool = False,
        save_intermediates: bool = False,
    ) -> Optional[SegmentedRisks]:
        """
        Convenience method to process Risk Factors section

        Args:
            file_path: Path to the HTML filing file
            form_type: Type of SEC form ("10-K" or "10-Q")
            save_output: Optional path to save the result as JSON
            overwrite: Whether to overwrite existing output file

        Returns:
            SegmentedRisks with risk segments and metadata
        """
        if form_type.upper() in ["10-K", "10K"]:
            section = SectionIdentifier.ITEM_1A_RISK_FACTORS
        else:
            section = SectionIdentifier.ITEM_1A_RISK_FACTORS_10Q

        return self.process_filing(
            file_path,
            form_type=form_type,
            section=section,
            save_output=save_output,
            overwrite=overwrite,
            save_intermediates=save_intermediates,
        )

    def process_batch(
        self,
        file_paths: List[Union[str, Path]],
        form_type: str = "10-K",
        output_dir: Optional[Union[str, Path]] = None,
        overwrite: bool = False,
        max_workers: Optional[int] = None,
        verbose: bool = True,
        save_intermediates: bool = False,
        resume: bool = False,
        progress_log: Optional[Path] = None,
    ) -> List[SegmentedRisks]:
        """
        Process multiple filings with optional parallel processing

        Args:
            file_paths: List of paths to HTML filing files
            form_type: Type of SEC form ("10-K" or "10-Q")
            output_dir: Optional directory to save results
            overwrite: Whether to overwrite existing files
            max_workers: Number of parallel workers (None=auto, 1=sequential)
            verbose: Print progress information
            save_intermediates: Save parsed and extracted outputs to interim dirs
            resume: Skip files whose output already exists in output_dir
            progress_log: Optional path for a persistent progress log file

        Returns:
            List of SegmentedRisks objects (successful results only)

        Note:
            Uses ParallelProcessor for efficient batch processing.
            Set max_workers=1 for sequential processing.
        """
        if not file_paths:
            logger.warning("No file paths provided for batch processing")
            return []

        # Resume: filter out files already processed (output exists in output_dir)
        if resume and output_dir:
            resume_filter = ResumeFilter(
                output_dir=Path(output_dir),
                output_suffix="_segmented.json",
            )
            file_paths = resume_filter.filter_unprocessed(
                [Path(p) for p in file_paths],
                quiet=not verbose,
            )
            if not file_paths:
                logger.info("Resume mode: all files already processed, nothing to do")
                return []

        # Convert config to dict for serialization (needed for parallel processing)
        config_dict = self.config.model_dump() if self.config else {}

        # Pre-classify files for adaptive timeout (Phase 1: Memory Semaphore)
        semaphore = MemorySemaphore()
        file_estimates = []
        max_timeout = 1200  # Default for unclassified

        try:
            file_estimates = [
                semaphore.get_resource_estimate(Path(fp))
                for fp in file_paths
            ]
            max_timeout = max(est.recommended_timeout_sec for est in file_estimates)

            # Log file classification statistics
            small_count = sum(1 for e in file_estimates if e.category == FileCategory.SMALL)
            medium_count = sum(1 for e in file_estimates if e.category == FileCategory.MEDIUM)
            large_count = sum(1 for e in file_estimates if e.category == FileCategory.LARGE)

            logger.info(
                f"Adaptive timeout: {max_timeout}s for {len(file_paths)} files "
                f"(Small: {small_count}, Medium: {medium_count}, Large: {large_count})"
            )

            if large_count > 0:
                total_large_mb = sum(
                    e.estimated_memory_mb for e in file_estimates
                    if e.category == FileCategory.LARGE
                )
                logger.info(
                    f"Large files detected: {large_count} files, "
                    f"estimated peak memory: {total_large_mb:.0f}MB total"
                )

        except Exception as e:
            logger.warning(f"File classification failed, using default timeout: {e}")
            max_timeout = 1200

        # Prepare arguments for worker function
        worker_args = [
            (file_path, config_dict, form_type, output_dir, overwrite, save_intermediates)
            for file_path in file_paths
        ]

        # Use ParallelProcessor for batch processing with adaptive timeout
        processor = ParallelProcessor(
            max_workers=max_workers,
            initializer=init_preprocessing_worker,  # Shared worker pool (Phase 5.1)
            max_tasks_per_child=50,  # Restart workers periodically for memory management
            task_timeout=max_timeout  # Adaptive timeout based on largest file
        )

        # Optional persistent progress log
        progress_logger: Optional[ProgressLogger] = None
        if progress_log:
            progress_logger = ProgressLogger(progress_log, console=verbose)
            progress_logger.section(f"Batch Pipeline: {len(file_paths)} files")

        def _on_progress(idx: int, result: dict) -> None:
            """Forward per-file results to ProgressLogger when enabled."""
            if progress_logger is None:
                return
            status = result.get('status', 'unknown')
            file_name = result.get('file', 'unknown')
            elapsed = result.get('elapsed_time', 0)
            if status == 'success':
                progress_logger.log(
                    f"[{idx}/{len(file_paths)}] OK: {file_name} -> "
                    f"{result.get('num_segments', 0)} segments, {elapsed:.1f}s"
                )
            elif status == 'warning':
                progress_logger.warning(
                    f"[{idx}/{len(file_paths)}] {file_name} - {result.get('error', '')}"
                )
            else:
                progress_logger.error(
                    f"[{idx}/{len(file_paths)}] FAILED: {file_name} - {result.get('error', '')}"
                )

        # Process files (handles both sequential and parallel modes)
        processing_results = processor.process_batch(
            items=worker_args,
            worker_func=_process_single_filing_worker,
            progress_callback=_on_progress if progress_logger else None,
            verbose=verbose,
        )

        # Extract results by status
        successful = [r for r in processing_results if r.get('status') == 'success']
        warnings = [r for r in processing_results if r.get('status') == 'warning']
        errors = [r for r in processing_results if r.get('status') == 'error']

        # Log summary
        logger.info(
            "Batch processing complete: %d successful, %d warnings, %d errors (total: %d)",
            len(successful), len(warnings), len(errors), len(file_paths)
        )

        if progress_logger:
            progress_logger.section("Batch Complete", char="=")
            progress_logger.log(f"Total: {len(file_paths)}", timestamp=False)
            progress_logger.log(f"Successful: {len(successful)}", timestamp=False)
            if warnings:
                progress_logger.log(f"Warnings: {len(warnings)}", timestamp=False)
            if errors:
                progress_logger.log(f"Errors: {len(errors)}", timestamp=False)
            progress_logger.close()

        if verbose and (warnings or errors):
            if warnings:
                logger.warning("Files with warnings: %s", [r['file'] for r in warnings])
            if errors:
                logger.error("Files with errors: %s", [r['file'] for r in errors])

        # Extract SegmentedRisks objects from successful results
        results = [r['result'] for r in successful if r.get('result') is not None]

        return results


def process_filing(
    file_path: Union[str, Path],
    form_type: str = "10-K",
    deep_clean: bool = False,
    save_output: Optional[Union[str, Path]] = None,
) -> Optional[SegmentedRisks]:
    """
    Convenience function to process a single SEC filing

    Args:
        file_path: Path to the HTML filing file
        form_type: Type of SEC form ("10-K" or "10-Q")
        deep_clean: Whether to apply NLP-based deep cleaning
        save_output: Optional path to save the result

    Returns:
        SegmentedRisks with segments and metadata

    Example:
        >>> from src.preprocessing.pipeline import process_filing
        >>> result = process_filing("data/raw/AAPL_10K.html")
        >>> print(f"Company: {result.company_name}")
        >>> print(f"SIC: {result.sic_code} - {result.sic_name}")
        >>> for seg in result.segments[:3]:
        ...     print(f"- {seg.text[:100]}...")
    """
    config = PipelineConfig(deep_clean=deep_clean)
    pipeline = SECPreprocessingPipeline(config)
    return pipeline.process_risk_factors(
        file_path,
        form_type=form_type,
        save_output=save_output,
    )


if __name__ == "__main__":
    import sys

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("SEC Preprocessing Pipeline")
    print("=" * 50)
    print("\nFlow: Parse → Extract → Clean → Segment")
    print("\nOptimizations:")
    print("  - Global worker objects (models loaded once per worker)")
    print("  - HTML sanitization removed (unnecessary overhead)")
    print("\nMetadata preserved throughout:")
    print("  - sic_code, sic_name")
    print("  - cik, ticker, company_name")
    print("  - form_type")

    # Example usage
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        form_type = sys.argv[2] if len(sys.argv) > 2 else "10-K"

        result = process_filing(file_path, form_type=form_type)

        if result:
            print(f"\n{'=' * 50}")
            print(f"Company: {result.company_name}")
            print(f"CIK: {result.cik}")
            print(f"SIC Code: {result.sic_code}")
            print(f"SIC Name: {result.sic_name}")
            print(f"Form Type: {result.form_type}")
            print(f"Total Segments: {len(result)}")
            print(f"\nFirst 3 segments:")
            for seg in result.segments[:3]:
                preview = seg.text[:150].replace('\n', ' ')
                print(f"  [{seg.index}] {preview}...")
        else:
            print("Failed to process filing")
    else:
        print("\nUsage: python -m src.preprocessing.pipeline <file_path> [form_type]")
        print("Example: python -m src.preprocessing.pipeline data/raw/AFL_10K_2025.html")

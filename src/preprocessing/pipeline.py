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
from .constants import SectionIdentifier, OutputSuffix, PipelineStep
from .models.extraction import ExtractedSection
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


def _sections_for_form_type(form_type: str) -> List[str]:
    """Return the ordered list of section IDs for the given form type."""
    from src.config import settings as _cfg
    if form_type.upper() in ("10-K", "10K"):
        return list(_cfg.sec_sections.sections_10k.keys())
    elif form_type.upper() in ("10-Q", "10Q"):
        return list(_cfg.sec_sections.sections_10q.keys())
    return ["part1item1a"]


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
    output_dir: Optional[Path],
    overwrite: bool,
    sections: Optional[List[str]] = None,
    save_intermediates: bool = False,
    intermediates_dir: Optional[Path] = None,
    tracker: Optional[ResourceTracker] = None,
) -> Dict[str, Optional[SegmentedRisks]]:
    """
    Process a SEC filing using global worker objects (efficient model reuse).

    Workers are provided by :mod:`src.utils.worker_pool` (initialised once
    per worker process via ``init_preprocessing_worker``).

    Flow (sanitization removed):
    1. Parse HTML → ParsedFiling (with metadata) — once per filing
    2-4. For each section: Extract → Clean → Segment

    Args:
        file_path: Path to the HTML filing file
        form_type: Type of SEC form ("10-K" or "10-Q")
        config: Pipeline configuration
        output_dir: Optional directory to save segmented outputs
        overwrite: Whether to overwrite existing output files
        sections: Section IDs to extract (None = all for form_type)
        save_intermediates: Save parsed/extracted outputs to interim dirs
        intermediates_dir: When set, save parsed + extracted into subdirs here
        tracker: Optional ResourceTracker for per-step timing/memory

    Returns:
        Dict mapping section_id → SegmentedRisks (None if section not found)
    """
    from contextlib import nullcontext

    if sections is None:
        sections = _sections_for_form_type(form_type)

    logger.info("Processing filing: %s", file_path.name)

    # Step 1: Parse HTML filing (once — no sanitization)
    logger.info("Step 1: Parsing HTML filing...")
    # ADR-011 Rule 9: Stage 1 pre-seek is valid only for single-section extraction.
    # Multi-section requests must parse the full Document 1 HTML.
    preseek_id = sections[0] if len(sections) == 1 else None
    with tracker.track_module(PipelineStep.PARSE) if tracker else nullcontext():
        if intermediates_dir:
            parser_save: Union[Path, bool] = intermediates_dir / "parsed" / (file_path.stem + OutputSuffix.PARSED)
            parser_save.parent.mkdir(parents=True, exist_ok=True)
        elif save_intermediates:
            parser_save = True   # existing behaviour: saves to default parsed_data_dir
        else:
            parser_save = False
        parsed = get_worker_parser().parse_filing(file_path, form_type, save_output=parser_save,
                                                  section_id=preseek_id)

    logger.info(
        "Parsed %d elements. Metadata: CIK=%s, SIC=%s (%s)",
        len(parsed),
        parsed.metadata.get('cik'),
        parsed.metadata.get('sic_code'),
        parsed.metadata.get('sic_name'),
    )

    # Steps 2-4: Loop over sections
    results: Dict[str, Optional[SegmentedRisks]] = {}

    for section_id in sections:
        try:
            section_enum = SectionIdentifier(section_id)
        except ValueError:
            logger.warning("Unknown section '%s', skipping", section_id)
            continue

        # Step 2: Extract section (metadata flows through)
        logger.info("Extracting section '%s'...", section_id)
        with tracker.track_module(PipelineStep.EXTRACT) if tracker else nullcontext():
            extracted = get_worker_extractor().extract_section(parsed, section_enum)

        if extracted is None:
            results[section_id] = None
            logger.info("Section '%s' not found in filing, skipping", section_id)
            continue

        logger.info(
            "Extracted section '%s': %d chars, %d subsections",
            section_id, len(extracted.text), len(extracted.subsections),
        )

        # Determine extracted dir
        if intermediates_dir:
            ext_dir: Optional[Path] = intermediates_dir / "extracted"
        elif save_intermediates:
            from src.config import settings as _cfg  # lazy import (avoids circular at module level)
            ext_dir = _cfg.paths.extracted_data_dir
        else:
            ext_dir = None

        if ext_dir is not None:
            ext_dir.mkdir(parents=True, exist_ok=True)
            extracted.save_to_json(
                ext_dir / (file_path.stem + OutputSuffix.section_extracted(section_id)),
                overwrite=True,
            )

        # Step 3: Clean text
        logger.info("Cleaning text for section '%s'...", section_id)
        with tracker.track_module(PipelineStep.CLEAN) if tracker else nullcontext():
            if config.remove_html:
                cleaned_text = get_worker_cleaner().remove_html_tags(extracted.text)
            else:
                cleaned_text = extracted.text

            cleaned_text = get_worker_cleaner().clean_text(
                cleaned_text,
                deep_clean=config.deep_clean
            )
        logger.info("Cleaned text: %d chars", len(cleaned_text))
        raw_chars     = len(extracted.text)
        cleaned_chars = len(cleaned_text)

        if intermediates_dir and ext_dir is not None:
            cleaned_section = extracted.model_copy(update={
                'text': cleaned_text,
                'metadata': {**extracted.metadata, 'cleaned': True},
            })
            cleaned_section.save_to_json(
                ext_dir / (file_path.stem + OutputSuffix.section_cleaned(section_id)),
                overwrite=True,
            )

        # Step 4: Segment (metadata preserved)
        logger.info("Segmenting section '%s'...", section_id)
        with tracker.track_module(PipelineStep.SEGMENT) if tracker else nullcontext():
            result = get_worker_segmenter().segment_extracted_section(
                extracted,
                cleaned_text=cleaned_text
            )
        logger.info("Section '%s': created %d segments", section_id, len(result))
        result.raw_section_char_count     = raw_chars
        result.cleaned_section_char_count = cleaned_chars

        # Save segmented output
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            result.save_to_json(
                output_dir / (file_path.stem + OutputSuffix.section_segmented(section_id)),
                overwrite=overwrite,
            )

        results[section_id] = result

    return results


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

        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

        # Process the file using global workers (no per-file instantiation)
        results = _process_filing_with_global_workers(
            file_path=file_path,
            form_type=form_type,
            config=config,
            output_dir=output_dir,
            overwrite=overwrite,
            sections=_sections_for_form_type(form_type),
            save_intermediates=save_intermediates,
            intermediates_dir=output_dir if save_intermediates else None,
            tracker=tracker,
        )

        usage = tracker.finalize()

        successful = {sid: r for sid, r in results.items() if r is not None}
        total_segments = sum(len(r) for r in successful.values())

        if successful:
            first = next(iter(successful.values()))
            primary_section = next(iter(successful))
            primary_path = (
                output_dir / (file_path.stem + OutputSuffix.section_segmented(primary_section))
                if output_dir else None
            )
            return {
                'status': 'success',
                'file': file_path.name,
                'result': successful,
                'num_segments': total_segments,
                'sections_extracted': list(successful.keys()),
                'output_path': str(primary_path) if primary_path else None,
                'sic_code': first.sic_code,
                'company_name': first.company_name,
                'elapsed_time': usage.elapsed_time(),
                'file_size_mb': file_size_mb,
                'resource_usage': usage.to_dict(),
            }
        else:
            return {
                'status': 'warning',
                'file': file_path.name,
                'result': None,
                'error': 'No sections extracted from filing',
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
        >>> results = pipeline.process_filing(
        ...     "data/raw/AAPL_10K.html",
        ...     form_type="10-K"
        ... )
        >>> for section_id, result in results.items():
        ...     if result:
        ...         print(f"{section_id}: {len(result)} segments")
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
        sections: Optional[List[SectionIdentifier]] = None,
        save_output_dir: Optional[Union[str, Path]] = None,
        overwrite: bool = False,
        save_intermediates: bool = False,
        intermediates_dir: Optional[Path] = None,
    ) -> Dict[str, Optional[SegmentedRisks]]:
        """
        Process a SEC filing through the complete pipeline for all specified sections.

        Flow (sanitization removed for efficiency):
        1. Parse HTML → ParsedFiling (with metadata) — once per filing
        2-4. For each section: Extract → Clean → Segment

        Args:
            file_path: Path to the HTML filing file
            form_type: Type of SEC form ("10-K" or "10-Q")
            sections: Sections to extract (None = all sections for form_type)
            save_output_dir: Optional directory to save segmented outputs
            overwrite: Whether to overwrite existing output files
            save_intermediates: Save parsed/extracted to their default dirs
            intermediates_dir: When set, save parsed + extracted into subdirs
                here (parsed/ and extracted/) instead of the default dirs.
                Takes precedence over save_intermediates.

        Returns:
            Dict mapping section_id → SegmentedRisks (None if section not found)
        """
        file_path = Path(file_path)
        logger.info("Processing filing: %s", file_path.name)

        # Resolve sections: if None, use all sections for this form type
        if sections is None:
            section_ids = _sections_for_form_type(form_type)
            section_list: List[SectionIdentifier] = []
            for sid in section_ids:
                try:
                    section_list.append(SectionIdentifier(sid))
                except ValueError:
                    logger.warning("Unknown section '%s' in config, skipping", sid)
        else:
            section_list = list(sections)

        # Step 1: Parse HTML filing (once — no sanitization)
        logger.info("Step 1: Parsing HTML filing...")
        # ADR-011 Rule 9: pre-seek only for single-section requests.
        preseek_id = section_list[0].value if len(section_list) == 1 else None
        if intermediates_dir:
            parsed_dir = intermediates_dir / "parsed"
            parsed_dir.mkdir(parents=True, exist_ok=True)
            parser_save: Union[Path, bool] = parsed_dir / (file_path.stem + OutputSuffix.PARSED)
        else:
            parser_save = save_intermediates  # True → default parsed_data_dir, False → skip
        parsed = self.parser.parse_filing(file_path, form_type, save_output=parser_save,
                                          section_id=preseek_id)

        logger.info(
            "Parsed %d elements. Metadata: CIK=%s, SIC=%s (%s)",
            len(parsed),
            parsed.metadata.get('cik'),
            parsed.metadata.get('sic_code'),
            parsed.metadata.get('sic_name'),
        )

        # Resolve output dir
        output_dir = Path(save_output_dir) if save_output_dir else None

        # Steps 2-4: Loop over sections
        results: Dict[str, Optional[SegmentedRisks]] = {}

        for section in section_list:
            section_id = section.value

            # Step 2: Extract section (metadata flows through)
            logger.info("Extracting section '%s'...", section_id)
            extracted = self.extractor.extract_section(parsed, section)

            if extracted is None:
                results[section_id] = None
                logger.info("Section '%s' not found in filing, skipping", section_id)
                continue

            logger.info(
                "Extracted section '%s': %d chars, %d subsections",
                section_id, len(extracted.text), len(extracted.subsections),
            )

            # Determine ext_dir
            if intermediates_dir:
                ext_dir: Optional[Path] = intermediates_dir / "extracted"
            elif save_intermediates:
                from src.config import settings as _cfg  # lazy import
                ext_dir = _cfg.paths.extracted_data_dir
            else:
                ext_dir = None

            if ext_dir is not None:
                ext_dir.mkdir(parents=True, exist_ok=True)
                extracted.save_to_json(
                    ext_dir / (file_path.stem + OutputSuffix.section_extracted(section_id)),
                    overwrite=True,
                )
                logger.info("Saved extracted section '%s' to: %s", section_id, ext_dir)

            # Step 3: Clean text
            logger.info("Cleaning text for section '%s'...", section_id)
            if self.config.remove_html:
                cleaned_text = self.cleaner.remove_html_tags(extracted.text)
            else:
                cleaned_text = extracted.text

            cleaned_text = self.cleaner.clean_text(
                cleaned_text,
                deep_clean=self.config.deep_clean
            )
            logger.info("Cleaned text: %d chars", len(cleaned_text))

            if intermediates_dir and ext_dir is not None:
                cleaned_section = extracted.model_copy(update={
                    'text': cleaned_text,
                    'metadata': {**extracted.metadata, 'cleaned': True},
                })
                clean_path = ext_dir / (file_path.stem + OutputSuffix.section_cleaned(section_id))
                cleaned_section.save_to_json(clean_path, overwrite=True)
                logger.info("Saved cleaned section '%s' to: %s", section_id, clean_path)

            # Step 4: Segment (metadata preserved)
            logger.info("Segmenting section '%s'...", section_id)
            result = self.segmenter.segment_extracted_section(
                extracted,
                cleaned_text=cleaned_text
            )
            logger.info("Section '%s': created %d segments", section_id, len(result))

            # Save segmented output
            if output_dir:
                output_dir.mkdir(parents=True, exist_ok=True)
                seg_path = output_dir / (file_path.stem + OutputSuffix.section_segmented(section_id))
                result.save_to_json(seg_path, overwrite=overwrite)
                logger.info("Saved segmented section '%s' to: %s", section_id, seg_path)

            results[section_id] = result

        return results

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
        """
        # Process the filing
        try:
            results = self.process_filing(
                file_path=file_path,
                form_type=form_type,
                sections=[section],
                save_output_dir=None,
                overwrite=False,
            )
            result = results.get(section.value)

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
        intermediates_dir: Optional[Path] = None,
    ) -> Optional[SegmentedRisks]:
        """
        Backward-compatible wrapper: process Risk Factors section only.

        Args:
            file_path: Path to the HTML filing file
            form_type: Type of SEC form ("10-K" or "10-Q")
            save_output: Optional exact path to save the result as JSON
            overwrite: Whether to overwrite existing output file
            save_intermediates: Save parsed/extracted to their default dirs
            intermediates_dir: When set, save parsed + extracted into subdirs here.

        Returns:
            SegmentedRisks with risk segments and metadata
        """
        if form_type.upper() in ("10-K", "10K"):
            section = SectionIdentifier.ITEM_1A_RISK_FACTORS
        else:
            section = SectionIdentifier.ITEM_1A_RISK_FACTORS_10Q

        results = self.process_filing(
            file_path,
            form_type=form_type,
            sections=[section],
            save_output_dir=Path(save_output).parent if save_output else None,
            overwrite=overwrite,
            save_intermediates=save_intermediates,
            intermediates_dir=intermediates_dir,
        )
        result = results.get(section.value)
        # Honour legacy exact save_output path (section_segmented gives different name)
        if result and save_output:
            result.save_to_json(save_output, overwrite=overwrite)
        return result

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
            List of SegmentedRisks objects (successful results only, all sections flattened)

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
                output_suffix=OutputSuffix.section_segmented("part1item1a"),
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

        # Flatten all SegmentedRisks objects from successful results
        results: List[SegmentedRisks] = []
        for r in successful:
            if r.get('result'):
                results.extend(r['result'].values())

        return results


def process_filing(
    file_path: Union[str, Path],
    form_type: str = "10-K",
    deep_clean: bool = False,
    save_output: Optional[Union[str, Path]] = None,
) -> Optional[SegmentedRisks]:
    """
    Convenience function to process a single SEC filing (Risk Factors only)

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
    # Running this module directly (python src/preprocessing/pipeline.py) is not
    # recommended — it triggers a RuntimeWarning because the package __init__.py
    # already imports this module before runpy can execute it as __main__.
    #
    # Use the proper entry point instead:
    #   python -m src.preprocessing <file_path> [form_type]
    print("Use the package entry point to avoid import conflicts:")
    print("  python -m src.preprocessing <file_path> [form_type]")
    print("  python -m src.preprocessing data/raw/AAPL_10K_2025.html")

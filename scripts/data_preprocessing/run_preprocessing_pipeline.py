"""
Run complete preprocessing pipeline: Parse -> Extract -> Clean -> Segment -> Sentiment Analysis

ARCHITECTURAL NOTE:
    This script currently mixes two concerns for convenience:
    - Preprocessing (structural): Parse -> Extract -> Clean -> Segment
    - Feature Engineering (semantic): Sentiment Analysis

    For production MLOps workflows, use the separated pipeline:
    1. scripts/data_preprocessing/run_preprocessing.py (structural only)
    2. scripts/feature_engineering/extract_sentiment_features.py (semantic only)

    This combined script is maintained for backward compatibility and experimental work.
    See: thoughts/shared/research/2025-12-28_19-30_preprocessing_script_deduplication.md

Pipeline Flow (with metadata preservation):
    1. Parse   -> ParsedFiling (sic_code, sic_name, cik, company_name)
    2. Extract -> ExtractedSection (metadata preserved) — one pass per section
    3. Clean   -> cleaned text
    4. Segment -> SegmentedRisks (metadata preserved)
    5. Sentiment -> sentiment features (optional, feature engineering step)

Output layout (batch mode):
    data/processed/
    ├── .manifest.json                         # StateManifest: cross-run hash tracking
    └── {YYYYMMDD_HHMMSS}_preprocessing_{git_sha}/
        ├── _progress.log                      # ProgressLogger output
        ├── _checkpoint.json                   # CheckpointManager (deleted on success)
        ├── RUN_REPORT.md                      # MarkdownReportGenerator report
        ├── batch_summary_{run_id}_...json     # JSON summary (naming.py convention)
        ├── parsed/
        │   └── {stem}_parsed.json
        ├── extracted/
        │   ├── {stem}_{section_id}_extracted.json
        │   └── {stem}_{section_id}_cleaned.json
        └── {stem}_{section_id}_segmented.json  # One per section found

Usage:
    # Single file mode
    python scripts/data_preprocessing/run_preprocessing_pipeline.py
    python scripts/data_preprocessing/run_preprocessing_pipeline.py --input data/raw/AAPL_10K.html
    python scripts/data_preprocessing/run_preprocessing_pipeline.py --input data/raw/AAPL_10K.html --no-sentiment

    # Batch mode (concurrent processing)
    python scripts/data_preprocessing/run_preprocessing_pipeline.py --batch
    python scripts/data_preprocessing/run_preprocessing_pipeline.py --batch --workers 4
    python scripts/data_preprocessing/run_preprocessing_pipeline.py --batch --no-sentiment
    python scripts/data_preprocessing/run_preprocessing_pipeline.py --batch --resume
    python scripts/data_preprocessing/run_preprocessing_pipeline.py --batch --quiet
    python scripts/data_preprocessing/run_preprocessing_pipeline.py --batch --chunk-size 100

Migration Path:
    For separated pipeline (recommended for production):
    1. python scripts/data_preprocessing/run_preprocessing.py --batch
    2. python scripts/feature_engineering/extract_sentiment_features.py --batch
    Or use: python scripts/feature_engineering/run_feature_pipeline.py --batch
"""

import argparse
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

# Preprocessing classes
from src.preprocessing.constants import OutputSuffix, PipelineStep, SectionIdentifier
from src.preprocessing.parser import SECFilingParser, ParsedFiling
from src.preprocessing.extractor import SECSectionExtractor, ExtractedSection
from src.preprocessing.cleaning import TextCleaner
from src.preprocessing.segmenter import RiskSegmenter, SegmentedRisks, RiskSegment
from src.features.sentiment import SentimentAnalyzer
from src.config import settings, ensure_directories

# Path aliases — replaces deprecated legacy constants
RAW_DATA_DIR       = settings.paths.raw_data_dir
PARSED_DATA_DIR    = settings.paths.parsed_data_dir
EXTRACTED_DATA_DIR = settings.paths.extracted_data_dir
PROCESSED_DATA_DIR = settings.paths.processed_data_dir

# src/utils — full integration
from src.utils.checkpoint import CheckpointManager
from src.utils.dead_letter_queue import DeadLetterQueue
from src.utils.memory_semaphore import MemorySemaphore, FileCategory
from src.utils.metadata import RunMetadata
from src.utils.naming import parse_run_dir_metadata, format_output_filename
from src.utils.parallel import ParallelProcessor
from src.utils.progress_logger import ProgressLogger
from src.utils.reporting import MarkdownReportGenerator
from src.utils.resource_tracker import ResourceTracker
from src.utils.resume import ResumeFilter
from src.utils.state_manager import StateManifest
from src.utils.worker_pool import (
    init_preprocessing_worker,
    get_worker_parser,
    get_worker_cleaner,
    get_worker_extractor,
    get_worker_segmenter,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Sentiment worker — kept local (not in shared worker_pool)
_worker_analyzer: Optional[SentimentAnalyzer] = None


def _sections_for_form_type(form_type: str) -> List[str]:
    """Return the ordered list of section IDs for the given form type."""
    if form_type.upper() in ("10-K", "10K"):
        return list(settings.sec_sections.sections_10k.keys())
    elif form_type.upper() in ("10-Q", "10Q"):
        return list(settings.sec_sections.sections_10q.keys())
    return ["part1item1a"]


def _init_worker(extract_sentiment: bool = True) -> None:
    """
    Initialize worker process with reusable objects.

    Core preprocessing workers (parser, extractor, cleaner, segmenter) are
    delegated to :func:`src.utils.worker_pool.init_preprocessing_worker` to
    avoid duplication with the pipeline module. The sentiment analyzer is kept
    local because it is specific to this combined script.
    """
    global _worker_analyzer
    init_preprocessing_worker()  # parser, cleaner, extractor, segmenter
    _worker_analyzer = SentimentAnalyzer() if extract_sentiment else None


# ---------------------------------------------------------------------------
# Single-file pipeline (used by --input and default modes)
# ---------------------------------------------------------------------------

def run_pipeline(
    input_file: Path,
    save_intermediates: bool = True,
    extract_sentiment: bool = True,
    output_dir: Optional[Path] = None,
    from_intermediates_dir: Optional[Path] = None,
) -> Tuple[Optional[ParsedFiling], Dict[str, Optional[SegmentedRisks]]]:
    """
    Run the full preprocessing pipeline on a single filing.

    Pipeline Flow:
        1. Parse   -> ParsedFiling (with metadata: sic_code, sic_name, cik, company_name)
        2-4. For each section: Extract -> Clean -> Segment
        5. Sentiment -> sentiment features (optional)

    Args:
        input_file: Path to input HTML file
        save_intermediates: Whether to save intermediate results
        extract_sentiment: Whether to extract sentiment features (default: True)
        output_dir: Optional directory to save outputs
        from_intermediates_dir: Optional path to a prior run directory whose
            extracted/ sub-directory contains pre-extracted section JSONs.
            When set, each section is loaded from disk instead of being re-parsed
            and re-extracted.  Sections whose JSON is absent fall back to normal
            parse + extract.

    Returns:
        Tuple of (ParsedFiling or None, Dict[section_id, SegmentedRisks])
    """
    print(f"Preprocessing Pipeline for: {input_file.name}")
    print("=" * 80)

    # Initialize shared objects (once for all sections)
    extractor = SECSectionExtractor()
    cleaner = TextCleaner()
    segmenter = RiskSegmenter(
        min_length=settings.preprocessing.min_segment_length,
        max_length=settings.preprocessing.max_segment_length,
    )
    analyzer = SentimentAnalyzer() if extract_sentiment else None

    # filing is lazy-parsed: only needed for sections not already on disk.
    filing = None
    parser_obj = SECFilingParser()

    def _ensure_filing():
        nonlocal filing
        if filing is not None:
            return filing
        print("\n[1/N] Parsing SEC filing...")
        parsed_path = None
        if save_intermediates and output_dir:
            parsed_path = output_dir / "parsed" / (input_file.stem + OutputSuffix.PARSED)
            parsed_path.parent.mkdir(parents=True, exist_ok=True)
        filing = parser_obj.parse_filing(
            input_file,
            form_type="10-K",
            save_output=parsed_path if parsed_path else save_intermediates,
        )
        print(f"  [OK] Parsed {len(filing)} semantic elements")
        print(f"  [OK] Found {filing.metadata['num_sections']} sections")
        print(f"  [OK] Metadata extracted:")
        print(f"       - CIK: {filing.metadata.get('cik', 'N/A')}")
        print(f"       - Company: {filing.metadata.get('company_name', 'N/A')}")
        print(f"       - SIC Code: {filing.metadata.get('sic_code', 'N/A')}")
        print(f"       - SIC Name: {filing.metadata.get('sic_name', 'N/A')}")
        return filing

    sections = _sections_for_form_type("10-K")
    dest_dir = output_dir if output_dir is not None else PROCESSED_DATA_DIR
    all_results: Dict[str, Optional[SegmentedRisks]] = {}

    for section_id in sections:
        try:
            section_enum = SectionIdentifier(section_id)
        except ValueError:
            logger.warning("Unknown section '%s', skipping", section_id)
            continue

        # Step 1+2: load pre-extracted JSON or fall back to parse + extract
        extracted = None
        if from_intermediates_dir:
            ext_path = (
                from_intermediates_dir / "extracted"
                / (input_file.stem + OutputSuffix.section_extracted(section_id))
            )
            if ext_path.exists():
                extracted = ExtractedSection.load_from_json(ext_path)
                print(f"\n  [OK] Loaded pre-extracted '{section_id}' from {ext_path.name}")

        if extracted is None:
            # Step 2: Extract section (metadata flows through)
            print(f"\n  Extracting section '{section_id}'...")
            extracted = extractor.extract_section(_ensure_filing(), section_enum)

        if extracted is None:
            print(f"  [SKIP] Section '{section_id}' not found in filing")
            all_results[section_id] = None
            continue

        print(f"  [OK] Extracted '{extracted.title}' ({len(extracted.text):,} chars, "
              f"{len(extracted.subsections)} subsections)")

        # Save extracted section if requested
        if save_intermediates:
            dest = output_dir / "extracted" if output_dir else EXTRACTED_DATA_DIR
            dest.mkdir(parents=True, exist_ok=True)
            output_path = dest / (input_file.stem + OutputSuffix.section_extracted(section_id))
            extracted.save_to_json(output_path, overwrite=True)
            print(f"  [OK] Saved extracted to: {output_path}")

        # Step 3: Clean text
        cleaned_text = cleaner.clean_text(extracted.text, deep_clean=False)
        print(f"  [OK] Cleaned text from {len(extracted.text):,} to {len(cleaned_text):,} characters")

        # Use model_copy to preserve ALL fields (ADR-010/DEI: accession_number,
        # filed_as_of_date, amendment_flag, entity_filer_category, ein, node_subsections).
        cleaned_section = extracted.model_copy(update={
            'text': cleaned_text,
            'metadata': {
                **extracted.metadata,
                'cleaned': True,
                'cleaning_settings': {
                    'remove_html_tags': settings.preprocessing.remove_html_tags,
                    'normalize_whitespace': settings.preprocessing.normalize_whitespace,
                    'remove_page_numbers': settings.preprocessing.remove_page_numbers,
                }
            },
        })

        if save_intermediates:
            dest = output_dir / "extracted" if output_dir else EXTRACTED_DATA_DIR
            dest.mkdir(parents=True, exist_ok=True)
            output_path = dest / (input_file.stem + OutputSuffix.section_cleaned(section_id))
            cleaned_section.save_to_json(output_path, overwrite=True)
            print(f"  [OK] Saved cleaned section to: {output_path}")

        # Step 4: Segment (metadata preserved via SegmentedRisks)
        segmented_risks = segmenter.segment_extracted_section(
            cleaned_section,
            cleaned_text=cleaned_text
        )
        print(f"  [OK] Segmented '{section_id}' into {len(segmented_risks)} segments")

        # Step 5: Sentiment Analysis (optional)
        sentiment_features_list = None
        if analyzer and len(segmented_risks) > 0:
            segment_texts = segmented_risks.get_texts()
            sentiment_features_list = analyzer.extract_features_batch(segment_texts)
            print(f"  [OK] Extracted sentiment features for {len(sentiment_features_list)} segments")

        # Save final output
        if save_intermediates and len(segmented_risks) > 0:
            dest_dir.mkdir(parents=True, exist_ok=True)
            output_path = dest_dir / (input_file.stem + OutputSuffix.section_segmented(section_id))
            output_data = _build_output_data(
                input_file=input_file,
                segmented_risks=segmented_risks,
                sentiment_features_list=sentiment_features_list,
                extract_sentiment=extract_sentiment,
            )
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            print(f"  [OK] Saved segments to: {output_path}")

        all_results[section_id] = segmented_risks

    found = sum(1 for r in all_results.values() if r is not None)
    print("\n" + "=" * 80)
    print("Pipeline complete!")
    print(f"Sections processed: {found}/{len(sections)}")

    return filing, all_results


# ---------------------------------------------------------------------------
# Output builder (shared by single-file and batch modes)
# ---------------------------------------------------------------------------

def _build_output_data(
    input_file: Path,
    segmented_risks: SegmentedRisks,
    sentiment_features_list: Optional[List] = None,
    extract_sentiment: bool = True
) -> Dict[str, Any]:
    """
    Build the output data structure for the final _segmented.json.

    Schema (v2.1):
        version / filing_name / document_info / processing_metadata / section_metadata /
        num_segments / sentiment_analysis_enabled / [aggregate_sentiment] / segments

    document_info carries filing-level identity fields (cik, ticker, sic_code, etc.)
    plus the Tier-2 DEI sub-dict extracted from the XBRL ix:hidden block.

    Args:
        input_file: Input file path
        segmented_risks: SegmentedRisks object with segments and metadata
        sentiment_features_list: Optional list of sentiment features per segment
        extract_sentiment: Whether sentiment analysis was enabled

    Returns:
        Dictionary ready for JSON serialization
    """
    num_tables = (
        segmented_risks.metadata.get('element_type_counts', {}).get('TableElement', 0)
    )

    try:
        finbert_model = settings.models.default_model  # pylint: disable=no-member
    except Exception:  # pragma: no cover
        finbert_model = "ProsusAI/finbert"

    output_data = {
        'version': '2.1',
        'filing_name': input_file.name,
        'document_info': {
            'company_name':        segmented_risks.company_name,
            'ticker':              segmented_risks.ticker,
            'cik':                 segmented_risks.cik,
            'sic_code':            segmented_risks.sic_code,
            'sic_name':            segmented_risks.sic_name,
            'form_type':           segmented_risks.form_type,
            'fiscal_year':         segmented_risks.fiscal_year,
            'accession_number':    segmented_risks.accession_number,
            'filed_as_of_date':    segmented_risks.filed_as_of_date,
            'amendment_flag':      segmented_risks.amendment_flag,
            'entity_filer_category': segmented_risks.entity_filer_category,
            'ein':                 segmented_risks.ein,
            'dei':                 segmented_risks.metadata.get('dei') or {},
        },
        'processing_metadata': {
            'parser_version': '1.0',
            'finbert_model': finbert_model,
            'chunking_strategy': 'sentence_level',
            'max_tokens_per_chunk': 512,
        },
        'section_metadata': {
            'identifier': segmented_risks.section_identifier,
            'title': segmented_risks.section_title,
            'cleaning_settings': {
                'removed_html_tags':    settings.preprocessing.remove_html_tags,
                'normalized_whitespace': settings.preprocessing.normalize_whitespace,
                'removed_page_numbers': settings.preprocessing.remove_page_numbers,
                'discarded_tables':     True,
            },
            'stats': {
                'total_chunks': segmented_risks.total_segments,
                'num_tables':   num_tables,
            },
        },
        'num_segments': segmented_risks.total_segments,
        'sentiment_analysis_enabled': extract_sentiment,
    }

    if sentiment_features_list and len(sentiment_features_list) > 0:
        n = len(sentiment_features_list)
        output_data['aggregate_sentiment'] = {
            'avg_negative_ratio':       sum(f.negative_ratio    for f in sentiment_features_list) / n,
            'avg_uncertainty_ratio':    sum(f.uncertainty_ratio for f in sentiment_features_list) / n,
            'avg_positive_ratio':       sum(f.positive_ratio    for f in sentiment_features_list) / n,
            'avg_sentiment_word_ratio': sum(f.sentiment_word_ratio for f in sentiment_features_list) / n,
        }

    output_data['segments'] = []
    for i, seg in enumerate(segmented_risks.segments):
        segment_dict = {
            'id':               seg.chunk_id,
            'parent_subsection': seg.parent_subsection,
            'text':             seg.text,
            'length':           seg.char_count,
            'word_count':       seg.word_count,
        }
        if sentiment_features_list and i < len(sentiment_features_list):
            sentiment = sentiment_features_list[i]
            segment_dict['sentiment'] = {
                'negative_count':        sentiment.negative_count,
                'positive_count':        sentiment.positive_count,
                'uncertainty_count':     sentiment.uncertainty_count,
                'litigious_count':       sentiment.litigious_count,
                'constraining_count':    sentiment.constraining_count,
                'negative_ratio':        sentiment.negative_ratio,
                'positive_ratio':        sentiment.positive_ratio,
                'uncertainty_ratio':     sentiment.uncertainty_ratio,
                'litigious_ratio':       sentiment.litigious_ratio,
                'constraining_ratio':    sentiment.constraining_ratio,
                'total_sentiment_words': sentiment.total_sentiment_words,
                'sentiment_word_ratio':  sentiment.sentiment_word_ratio,
            }
        output_data['segments'].append(segment_dict)

    return output_data


# ---------------------------------------------------------------------------
# Batch worker (module-level so it can be pickled for ProcessPoolExecutor)
# ---------------------------------------------------------------------------

def process_single_file_fast(args: Tuple) -> Dict[str, Any]:
    """
    Optimized worker function using pre-initialized global objects.

    Wraps each pipeline step in ResourceTracker.track_module() so per-step
    wall-clock time and peak RSS memory are captured in the result dict.

    Args:
        args: Tuple of (input_file, save_intermediates, output_dir[, from_intermediates_dir])
            - output_dir: stamped run directory (e.g. data/processed/20260218_..._preprocessing_0b83409/)
            - from_intermediates_dir: optional path to a prior run directory whose
              extracted/ sub-directory contains pre-extracted JSONs.  When set the
              worker loads ExtractedSection directly from those files and skips the
              Parse step (and per-section Extract step) for sections already on disk.

    Returns:
        Dict with keys: file, input_path, output_path, status, num_segments,
        sections_extracted, sic_code, sic_name, cik, elapsed_time, file_size_mb,
        resource_usage, error
    """
    if len(args) == 4:
        input_file, save_intermediates, output_dir, from_intermediates_dir = args
    else:
        input_file, save_intermediates, output_dir = args
        from_intermediates_dir = None

    input_file = Path(input_file)
    output_dir = Path(output_dir)
    from_intermediates_dir = Path(from_intermediates_dir) if from_intermediates_dir else None
    file_size_mb = input_file.stat().st_size / (1024 * 1024) if input_file.exists() else 0

    tracker = ResourceTracker()

    # filing is lazy-initialised: only parsed when at least one section has no
    # pre-extracted JSON available (or from_intermediates_dir is not set).
    filing = None

    def _ensure_filing():
        nonlocal filing
        if filing is not None:
            return filing
        with tracker.track_module(PipelineStep.PARSE):
            parsed_path = None
            if save_intermediates:
                parsed_path = output_dir / "parsed" / (input_file.stem + OutputSuffix.PARSED)
                parsed_path.parent.mkdir(parents=True, exist_ok=True)
            filing = get_worker_parser().parse_filing(
                input_file,
                form_type="10-K",
                save_output=parsed_path if parsed_path else save_intermediates,
            )
        return filing

    try:
        ext_dir = output_dir / "extracted"
        sections = _sections_for_form_type("10-K")
        all_segmented: Dict[str, SegmentedRisks] = {}
        first_output_path: Optional[Path] = None

        # Steps 1-2: Parse (lazy) + Extract — or load from intermediates
        for section_id in sections:
            try:
                section_enum = SectionIdentifier(section_id)
            except ValueError:
                logger.warning("Unknown section '%s', skipping", section_id)
                continue

            # Step 1+2 combined: try loading from pre-extracted JSON first
            section_result = None
            if from_intermediates_dir:
                ext_path = (
                    from_intermediates_dir / "extracted"
                    / (input_file.stem + OutputSuffix.section_extracted(section_id))
                )
                if ext_path.exists():
                    with tracker.track_module(PipelineStep.EXTRACT):
                        section_result = ExtractedSection.load_from_json(ext_path)
                    logger.info(
                        "Loaded pre-extracted '%s' from %s", section_id, ext_path.name
                    )

            if section_result is None:
                # Fall back: parse HTML (lazy) then extract
                cur_filing = _ensure_filing()

            # Step 2: Extract (only when no pre-extracted JSON was loaded)
            if section_result is None:
                with tracker.track_module(PipelineStep.EXTRACT):
                    section_result = get_worker_extractor().extract_section(
                        cur_filing, section_enum
                    )

            if not section_result:
                continue

            if save_intermediates:
                ext_dir.mkdir(parents=True, exist_ok=True)
                section_result.save_to_json(
                    ext_dir / (input_file.stem + OutputSuffix.section_extracted(section_id)),
                    overwrite=True,
                )

            # Step 3: Clean
            with tracker.track_module(PipelineStep.CLEAN):
                cleaned_text = get_worker_cleaner().clean_text(section_result.text, deep_clean=False)

            # Use model_copy to preserve ALL fields (including ADR-010/DEI fields:
            # accession_number, filed_as_of_date, amendment_flag, entity_filer_category,
            # ein, node_subsections). Manual construction would silently drop them.
            cleaned_section = section_result.model_copy(update={
                'text': cleaned_text,
                'metadata': {
                    **section_result.metadata,
                    'cleaned': True,
                    'cleaning_settings': {
                        'remove_html_tags': settings.preprocessing.remove_html_tags,
                        'normalize_whitespace': settings.preprocessing.normalize_whitespace,
                        'remove_page_numbers': settings.preprocessing.remove_page_numbers,
                    }
                },
            })

            if save_intermediates:
                ext_dir.mkdir(parents=True, exist_ok=True)
                cleaned_section.save_to_json(
                    ext_dir / (input_file.stem + OutputSuffix.section_cleaned(section_id)),
                    overwrite=True,
                )

            # Step 4: Segment
            with tracker.track_module(PipelineStep.SEGMENT):
                segmented_risks = get_worker_segmenter().segment_extracted_section(
                    cleaned_section,
                    cleaned_text=cleaned_text
                )

            if len(segmented_risks) == 0:
                continue

            # Step 5: Sentiment (if worker is enabled)
            sentiment_features_list = None
            if _worker_analyzer:
                with tracker.track_module(PipelineStep.SENTIMENT):
                    sentiment_features_list = _worker_analyzer.extract_features_batch(
                        segmented_risks.get_texts()
                    )

            # Save segmented output into stamped run directory
            if save_intermediates:
                output_dir.mkdir(parents=True, exist_ok=True)
                section_output_path = output_dir / (
                    input_file.stem + OutputSuffix.section_segmented(section_id)
                )
                output_data = _build_output_data(
                    input_file=input_file,
                    segmented_risks=segmented_risks,
                    sentiment_features_list=sentiment_features_list,
                    extract_sentiment=(_worker_analyzer is not None),
                )
                with open(section_output_path, 'w', encoding='utf-8') as f:
                    json.dump(output_data, f, indent=2, ensure_ascii=False)
                if first_output_path is None:
                    first_output_path = section_output_path

            all_segmented[section_id] = segmented_risks

        usage = tracker.finalize()

        if not all_segmented:
            # filing may be None when all sections were attempted via pre-extracted
            # JSONs but none were found; fall back to None-safe metadata access.
            _meta = filing.metadata if filing is not None else {}
            return {
                'file': input_file.name,
                'input_path': str(input_file),
                'output_path': None,
                'status': 'warning',
                'num_segments': 0,
                'sections_extracted': [],
                'sic_code': _meta.get('sic_code'),
                'sic_name': _meta.get('sic_name'),
                'cik': _meta.get('cik'),
                'elapsed_time': usage.elapsed_time(),
                'file_size_mb': file_size_mb,
                'resource_usage': usage.to_dict(),
                'error': 'No sections extracted from filing',
            }

        first_result = next(iter(all_segmented.values()))
        total_segments = sum(len(r) for r in all_segmented.values())

        return {
            'file': input_file.name,
            'input_path': str(input_file),
            'output_path': str(first_output_path) if first_output_path else None,
            'status': 'success',
            'num_segments': total_segments,
            'sections_extracted': list(all_segmented.keys()),
            'sic_code': first_result.sic_code,
            'sic_name': first_result.sic_name,
            'cik': first_result.cik,
            'elapsed_time': usage.elapsed_time(),
            'file_size_mb': file_size_mb,
            'resource_usage': usage.to_dict(),
            'error': None,
        }

    except Exception as e:
        logger.exception("Error processing %s", input_file.name)
        usage = tracker.finalize()
        return {
            'file': input_file.name,
            'input_path': str(input_file),
            'output_path': None,
            'status': 'error',
            'num_segments': 0,
            'sections_extracted': [],
            'sic_code': None,
            'sic_name': None,
            'cik': None,
            'elapsed_time': usage.elapsed_time(),
            'file_size_mb': file_size_mb,
            'resource_usage': usage.to_dict(),
            'error': str(e),
        }


# ---------------------------------------------------------------------------
# Batch pipeline orchestrator
# ---------------------------------------------------------------------------

def run_batch_pipeline(
    input_files: List[Path],
    run_dir: Path,
    manifest: StateManifest,
    run_id: str,
    save_intermediates: bool = True,
    extract_sentiment: bool = True,
    max_workers: Optional[int] = None,
    quiet: bool = False,
    chunk_size: Optional[int] = None,
    task_timeout: int = 1200,
    from_intermediates_dir: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """
    Run the preprocessing pipeline on multiple files via ParallelProcessor.

    src/utils integration:
        CheckpointManager  — crash recovery; saves every chunk_size files
        ResumeFilter       — within-run output-existence check
        MemorySemaphore    — adaptive per-batch timeout from file-size estimates
        ResourceTracker    — per-file timing/memory (inside process_single_file_fast)
        StateManifest      — records success/failure after each file (caller-owned)
        ProgressLogger     — real-time console + file logging to run_dir/_progress.log
        ParallelProcessor  — single long-lived pool (no per-chunk model reload)
        DeadLetterQueue    — timeout/exception quarantine (inside ParallelProcessor)

    Args:
        input_files: HTML files to process (pre-filtered by manifest.should_process)
        run_dir: Stamped output directory for this run
        manifest: StateManifest instance (caller saves at end of main())
        run_id: Run identifier string (YYYYMMDD_HHMMSS)
        save_intermediates: Save intermediate + final outputs
        extract_sentiment: Run Loughran-McDonald sentiment analysis
        max_workers: Worker count (None = CPU count)
        quiet: Suppress console output
        chunk_size: Save checkpoint + manifest every N completed files
        task_timeout: Per-file timeout floor in seconds (MemorySemaphore may raise it)
        from_intermediates_dir: Optional path to a prior run directory.  When set,
            workers load ExtractedSection objects directly from its extracted/ sub-
            directory, skipping the Parse (and per-section Extract) step for each
            section whose JSON is already present.  Sections with no JSON fall back
            to normal parse + extract.

    Returns:
        List of per-file result dicts (includes any prior checkpoint data)
    """
    if not input_files:
        if not quiet:
            print("No files to process")
        return []

    total_requested = len(input_files)

    # ProgressLogger writes to run_dir so all run artefacts are co-located
    progress_log_path = run_dir / "_progress.log"
    progress_logger = ProgressLogger(
        log_path=progress_log_path,
        console=not quiet,
        quiet=quiet,
    )

    if not quiet:
        print(f"\nBatch Processing: {total_requested} files")
        print(f"Max workers: {max_workers if max_workers else 'auto (CPU count)'}")
        print(f"Run directory: {run_dir}")
        print(f"Progress log:  {progress_log_path}")
        print("=" * 80)

    progress_logger.section(f"Batch Pipeline: {total_requested} files")

    # --- CheckpointManager: resume mid-run after a crash ---
    checkpoint = CheckpointManager(run_dir / "_checkpoint.json")
    prior_results: List[Dict] = []
    already_done: set = set()

    if checkpoint.exists():
        already_done, prior_results, _ = checkpoint.load()
        if already_done and not quiet:
            print(f"Checkpoint resume: skipping {len(already_done)} already-completed files")

    # --- ResumeFilter: skip files already written to run_dir ---
    resume_filter = ResumeFilter(
        output_dir=run_dir,
        output_suffix=OutputSuffix.section_segmented("part1item1a"),
    )
    within_run_stems = resume_filter.get_processed_stems()

    before = len(input_files)
    input_files = [
        f for f in input_files
        if f.name not in already_done and f.stem not in within_run_stems
    ]
    skipped = before - len(input_files)
    if skipped > 0 and not quiet:
        print(f"Within-run resume: skipping {skipped} files already written")

    if not input_files:
        if not quiet:
            print("All files already processed. Nothing to do.")
        progress_logger.close()
        return prior_results

    # --- MemorySemaphore: derive adaptive timeout from file-size estimates ---
    adaptive_timeout = task_timeout
    try:
        semaphore = MemorySemaphore()
        estimates = [semaphore.get_resource_estimate(Path(fp)) for fp in input_files]
        adaptive_timeout = max(est.recommended_timeout_sec for est in estimates)
        small_c  = sum(1 for e in estimates if e.category == FileCategory.SMALL)
        medium_c = sum(1 for e in estimates if e.category == FileCategory.MEDIUM)
        large_c  = sum(1 for e in estimates if e.category == FileCategory.LARGE)
        logger.info(
            "Adaptive timeout: %ds for %d files (S:%d M:%d L:%d)",
            adaptive_timeout, len(input_files), small_c, medium_c, large_c,
        )
        if large_c > 0:
            peak_mb = sum(e.estimated_memory_mb for e in estimates if e.category == FileCategory.LARGE)
            logger.info("Large files: %d, estimated peak memory: %.0f MB", large_c, peak_mb)
    except Exception as e:
        logger.warning("File classification failed, using floor timeout %ds: %s", task_timeout, e)

    # --- Build task args: (file, save_intermediates, output_dir[, from_intermediates_dir]) ---
    task_args = [
        (f, save_intermediates, run_dir, from_intermediates_dir)
        for f in input_files
    ]

    # --- Tracking state (mutated inside _on_progress closure) ---
    all_results: List[Dict] = list(prior_results)
    successful    = sum(1 for r in prior_results if r.get('status') == 'success')
    failed        = sum(1 for r in prior_results if r.get('status') == 'error')
    warning_count = sum(1 for r in prior_results if r.get('status') == 'warning')
    global_offset = len(already_done) + skipped

    start_time = time.time()

    def _on_progress(idx: int, result: dict) -> None:
        nonlocal successful, failed, warning_count
        all_results.append(result)

        status    = result.get('status', 'unknown')
        file_name = result.get('file', 'unknown')
        elapsed   = result.get('elapsed_time', 0)
        display_idx = global_offset + idx
        display_total = global_offset + len(task_args)

        # Update counters and progress logger
        if status == 'success':
            successful += 1
            sic_tag = f", SIC={result['sic_code']}" if result.get('sic_code') else ""
            progress_logger.log(
                f"[{display_idx}/{display_total}] OK: {file_name}"
                f" -> {result.get('num_segments', 0)} segs, {elapsed:.1f}s{sic_tag}"
            )
        elif status == 'warning':
            warning_count += 1
            progress_logger.warning(
                f"[{display_idx}/{display_total}] WARN: {file_name}"
                f" - {result.get('error', '')}"
            )
        else:
            failed += 1
            progress_logger.error(
                f"[{display_idx}/{display_total}] FAIL: {file_name}"
                f" - {result.get('error', '')}"
            )

        # StateManifest: record outcome for cross-run tracking
        if status == 'success' and result.get('output_path') and result.get('input_path'):
            manifest.record_success(
                input_path=Path(result['input_path']),
                output_path=Path(result['output_path']),
                run_id=run_id,
            )
        elif result.get('input_path'):
            manifest.record_failure(
                input_path=Path(result['input_path']),
                run_id=run_id,
                reason=result.get('error', 'unknown'),
            )

        # Periodic checkpoint + manifest save every chunk_size completions
        if chunk_size and idx % chunk_size == 0:
            manifest.save()
            checkpoint.save(
                processed_files=[r['file'] for r in all_results],
                results=all_results,
                metrics={'successful': successful, 'failed': failed, 'warnings': warning_count},
            )
            if not quiet:
                print(f"\n  [Checkpoint saved at {idx}/{len(task_args)} files]", flush=True)

    # --- ParallelProcessor: single long-lived pool for the full batch ---
    processor = ParallelProcessor(
        max_workers=max_workers,
        initializer=_init_worker,
        initargs=(extract_sentiment,),
        max_tasks_per_child=50,
        task_timeout=adaptive_timeout,
    )

    processor.process_batch(
        items=task_args,
        worker_func=process_single_file_fast,
        progress_callback=_on_progress,
        verbose=False,   # progress handled entirely by _on_progress + ProgressLogger
    )

    total_time = time.time() - start_time

    # --- Final manifest save + checkpoint cleanup on success ---
    manifest.save()
    checkpoint.cleanup()

    # --- Summary ---
    progress_logger.section("Batch Complete", char="=")
    progress_logger.log(f"Total: {global_offset + len(task_args)}", timestamp=False)
    progress_logger.log(f"Successful: {successful}", timestamp=False)
    if warning_count:
        progress_logger.log(f"Warnings: {warning_count}", timestamp=False)
    progress_logger.log(f"Failed: {failed}", timestamp=False)
    progress_logger.log(f"Total time: {total_time:.1f}s", timestamp=False)
    if len(task_args) > 0:
        progress_logger.log(f"Avg time/file: {total_time / len(task_args):.1f}s", timestamp=False)
    progress_logger.close()

    if not quiet:
        print("\n" + "=" * 80)
        print("Batch Processing Complete!")
        print(f"  Successful: {successful}")
        if warning_count:
            print(f"  Warnings:   {warning_count}")
        print(f"  Failed:     {failed}")
        print(f"  Total time: {total_time:.1f}s")

    return all_results


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Run complete preprocessing pipeline: Parse -> Extract -> Clean -> Segment"
    )
    parser.add_argument(
        '--input', type=str,
        help='Input HTML file path (single file mode)'
    )
    parser.add_argument(
        '--batch', action='store_true',
        help='Process all HTML files in RAW_DATA_DIR concurrently'
    )
    parser.add_argument(
        '--workers', type=int, default=None,
        help='Number of concurrent workers for batch mode (default: CPU count)'
    )
    parser.add_argument(
        '--no-save', action='store_true',
        help='Do not save intermediate or final results'
    )
    parser.add_argument(
        '--no-sentiment', action='store_true',
        help='Skip sentiment analysis step'
    )
    parser.add_argument(
        '--resume', action='store_true',
        help=(
            'Hash-based resume: skip files whose content is unchanged since the last '
            'successful run (tracked via StateManifest at data/processed/.manifest.json). '
            'Also resumes mid-run from checkpoint if the run directory already exists.'
        )
    )
    parser.add_argument(
        '--quiet', action='store_true',
        help='Minimize console output'
    )
    parser.add_argument(
        '--chunk-size', type=int, default=None,
        help=(
            'Save manifest + checkpoint every N completed files. '
            'The worker pool is NOT restarted between chunks. '
            'Recommended: 100-200 for large batches.'
        )
    )
    parser.add_argument(
        '--timeout', type=int, default=1200,
        help=(
            'Per-file timeout floor in seconds (default: 1200). '
            'MemorySemaphore will raise this for batches containing large files.'
        )
    )
    parser.add_argument(
        '--from-intermediates', type=str, default=None, metavar='DIR',
        help=(
            'Path to a prior run directory that contains an extracted/ sub-directory '
            'with pre-extracted section JSONs.  When set the pipeline loads '
            'ExtractedSection objects directly from those files and skips the '
            'expensive Parse step (and per-section Extract step) for each section '
            'whose JSON already exists.  Sections with no JSON fall back to normal '
            'parse + extract.  Useful for re-segmenting after a run where the '
            'segmented outputs had null metadata fields.'
        )
    )

    args = parser.parse_args()
    ensure_directories()

    from_intermediates_dir = Path(args.from_intermediates) if args.from_intermediates else None
    if from_intermediates_dir and not from_intermediates_dir.exists():
        print(f"ERROR: --from-intermediates path does not exist: {from_intermediates_dir}")
        return

    # --- RunMetadata + stamped run directory (naming.py convention) ---
    run_meta = RunMetadata.gather()
    run_id   = datetime.fromisoformat(run_meta["timestamp"]).strftime("%Y%m%d_%H%M%S")
    git_sha  = run_meta["git_commit"]
    run_dir  = PROCESSED_DATA_DIR / f"{run_id}_preprocessing_{git_sha}"
    run_dir.mkdir(parents=True, exist_ok=True)

    # --- StateManifest: cross-run hash tracking ---
    manifest = StateManifest(PROCESSED_DATA_DIR / ".manifest.json")
    manifest.load()
    manifest.update_run_config(run_meta)

    if args.batch:
        html_files = sorted(RAW_DATA_DIR.glob("*.html"))
        if not html_files:
            print(f"No HTML files found in {RAW_DATA_DIR}")
            return

        # Hash-based cross-run resume: skip files unchanged since last success
        if args.resume:
            html_files = [f for f in html_files if manifest.should_process(f)]
            if not html_files:
                print("All files unchanged since last successful run. Nothing to do.")
                return

        start_iso = datetime.now().isoformat()

        results = run_batch_pipeline(
            input_files=html_files,
            run_dir=run_dir,
            manifest=manifest,
            run_id=run_id,
            save_intermediates=not args.no_save,
            extract_sentiment=not args.no_sentiment,
            max_workers=args.workers,
            quiet=args.quiet,
            chunk_size=args.chunk_size,
            task_timeout=args.timeout,
            from_intermediates_dir=from_intermediates_dir,
        )

        end_iso = datetime.now().isoformat()

        # Prune deleted source files from manifest, then final atomic save
        manifest.prune_deleted_files(RAW_DATA_DIR)
        manifest.save()

        # Metrics
        total_files  = len(html_files)
        successful   = sum(1 for r in results if r.get('status') == 'success')
        warnings_cnt = sum(1 for r in results if r.get('status') == 'warning')
        failed_cnt   = sum(1 for r in results if r.get('status') == 'error')

        # --- MarkdownReportGenerator ---
        generator = MarkdownReportGenerator()
        report_md = generator.generate_run_report(
            run_id=run_id,
            run_name="preprocessing",
            metrics={
                'total_files':       total_files,
                'successful':        successful,
                'failed_or_skipped': failed_cnt + warnings_cnt,
                'quarantined':       failed_cnt,
                'form_type':         '10-K/10-Q',
                'run_id':            run_id,
            },
            output_dir=run_dir,
            manifest_stats=manifest.get_statistics(),
            failed_files=manifest.get_failed_files(),
            git_sha=git_sha,
            config_snapshot=run_meta,
            start_time=start_iso,
            end_time=end_iso,
        )
        (run_dir / "RUN_REPORT.md").write_text(report_md)

        # --- batch_summary JSON: name follows naming.py convention ---
        # parse_run_dir_metadata reads the stamped dir name we created
        run_dir_meta = parse_run_dir_metadata(run_dir)
        summary_name = format_output_filename("batch_summary", run_dir_meta)
        summary_path = run_dir / summary_name
        summary_data = {
            'version':     '3.0',
            'run_id':      run_id,
            'git_sha':     git_sha,
            'total_files': total_files,
            'successful':  successful,
            'warnings':    warnings_cnt,
            'failed':      failed_cnt,
            'run_dir':     str(run_dir),
            'manifest':    str(PROCESSED_DATA_DIR / ".manifest.json"),
            'results':     results,
        }
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary_data, f, indent=2)

        if not args.quiet:
            print(f"\nRun directory: {run_dir}")
            print(f"Run report:    {run_dir / 'RUN_REPORT.md'}")
            print(f"Summary JSON:  {summary_path}")
            print(f"Manifest:      {PROCESSED_DATA_DIR / '.manifest.json'}")

    elif args.input:
        input_file = Path(args.input)
        if args.resume and not manifest.should_process(input_file):
            print(f"Resume mode: {input_file.name} is unchanged since last run. Skipping.")
            return
        run_pipeline(
            input_file,
            save_intermediates=not args.no_save,
            extract_sentiment=not args.no_sentiment,
            output_dir=run_dir,
            from_intermediates_dir=from_intermediates_dir,
        )

    else:
        html_files = list(RAW_DATA_DIR.glob("*.html"))
        if not html_files:
            print(f"No HTML files found in {RAW_DATA_DIR}")
            return
        input_file = html_files[0]
        if args.resume and not manifest.should_process(input_file):
            print(f"Resume mode: {input_file.name} is unchanged since last run. Skipping.")
            return
        print(f"Using first file found: {input_file.name}\n")
        run_pipeline(
            input_file,
            save_intermediates=not args.no_save,
            extract_sentiment=not args.no_sentiment,
            output_dir=run_dir,
            from_intermediates_dir=from_intermediates_dir,
        )


if __name__ == "__main__":
    main()

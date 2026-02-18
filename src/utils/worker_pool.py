"""Shared worker initialization for all preprocessing scripts.

Centralizes global worker objects so every script that uses
ProcessPoolExecutor shares the same initialization path — eliminating
duplicated ``_init_worker()`` definitions across:

- ``src/preprocessing/pipeline.py``
- ``scripts/data_preprocessing/run_preprocessing_pipeline.py``

Usage (as ProcessPoolExecutor initializer):
    from src.utils.worker_pool import init_preprocessing_worker
    from src.utils.worker_pool import get_worker_parser, get_worker_cleaner

    with ProcessPoolExecutor(initializer=init_preprocessing_worker) as ex:
        future = ex.submit(my_worker_func, args)

    # Inside my_worker_func (runs in subprocess):
    parsed = get_worker_parser().parse_filing(file_path)

Memory impact (per worker process):
    - SECFilingParser (sec-parser):       ~20 MB
    - TextCleaner (spaCy):               ~200 MB
    - SECSectionExtractor:                ~5 MB
    - RiskSegmenter (SentenceTransformer): ~80 MB
    Total: ~300 MB per worker, amortised over 50 tasks → ~6 MB / file
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level globals (set by init_preprocessing_worker in each subprocess)
# ---------------------------------------------------------------------------

# Use TYPE_CHECKING-style forward refs to keep import cost at module load to zero.
# The actual imports happen only inside init_preprocessing_worker().
_worker_parser = None
_worker_cleaner = None
_worker_extractor = None
_worker_segmenter = None


# ---------------------------------------------------------------------------
# Initializer — called once per worker process by ProcessPoolExecutor
# ---------------------------------------------------------------------------

def init_preprocessing_worker(
    load_parser: bool = True,
    load_cleaner: bool = True,
    load_extractor: bool = True,
    load_segmenter: bool = True,
) -> None:
    """
    Initialize global worker objects once per worker process.

    Called via ``ProcessPoolExecutor(initializer=init_preprocessing_worker)``.
    Objects survive for up to ``max_tasks_per_child`` tasks (default 50)
    before the worker is recycled, giving a ~50x reduction in model-load
    overhead compared to instantiating per file.

    Args:
        load_parser: Load SECFilingParser (default True).
        load_cleaner: Load TextCleaner with spaCy (default True).
        load_extractor: Load SECSectionExtractor (default True).
        load_segmenter: Load RiskSegmenter with SentenceTransformer (default True).
    """
    global _worker_parser, _worker_cleaner, _worker_extractor, _worker_segmenter

    logger.info("Initializing preprocessing worker (models loaded once per process)")

    if load_parser:
        from src.preprocessing.parser import SECFilingParser
        _worker_parser = SECFilingParser()
        logger.debug("Loaded SECFilingParser")

    if load_cleaner:
        from src.preprocessing.cleaning import TextCleaner
        _worker_cleaner = TextCleaner()
        logger.debug("Loaded TextCleaner (spaCy)")

    if load_extractor:
        from src.preprocessing.extractor import SECSectionExtractor
        _worker_extractor = SECSectionExtractor()
        logger.debug("Loaded SECSectionExtractor")

    if load_segmenter:
        from src.preprocessing.segmenter import RiskSegmenter
        _worker_segmenter = RiskSegmenter()
        logger.debug("Loaded RiskSegmenter (SentenceTransformer)")

    logger.info("Worker initialization complete")


# ---------------------------------------------------------------------------
# Getters — raise informative error if called before initialization
# ---------------------------------------------------------------------------

def get_worker_parser():
    """Return the worker-process SECFilingParser.

    Raises:
        RuntimeError: If called before ``init_preprocessing_worker()``.
    """
    if _worker_parser is None:
        raise RuntimeError(
            "Worker parser is not initialized. "
            "Ensure init_preprocessing_worker() is set as the "
            "ProcessPoolExecutor initializer."
        )
    return _worker_parser


def get_worker_cleaner():
    """Return the worker-process TextCleaner.

    Raises:
        RuntimeError: If called before ``init_preprocessing_worker()``.
    """
    if _worker_cleaner is None:
        raise RuntimeError(
            "Worker cleaner is not initialized. "
            "Ensure init_preprocessing_worker() is set as the "
            "ProcessPoolExecutor initializer."
        )
    return _worker_cleaner


def get_worker_extractor():
    """Return the worker-process SECSectionExtractor.

    Raises:
        RuntimeError: If called before ``init_preprocessing_worker()``.
    """
    if _worker_extractor is None:
        raise RuntimeError(
            "Worker extractor is not initialized. "
            "Ensure init_preprocessing_worker() is set as the "
            "ProcessPoolExecutor initializer."
        )
    return _worker_extractor


def get_worker_segmenter():
    """Return the worker-process RiskSegmenter.

    Raises:
        RuntimeError: If called before ``init_preprocessing_worker()``.
    """
    if _worker_segmenter is None:
        raise RuntimeError(
            "Worker segmenter is not initialized. "
            "Ensure init_preprocessing_worker() is set as the "
            "ProcessPoolExecutor initializer."
        )
    return _worker_segmenter

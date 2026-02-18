"""Unit tests for src/utils/worker_pool.py — init_preprocessing_worker and getters."""

import pytest
from unittest.mock import patch, MagicMock

import src.utils.worker_pool as worker_pool_module
from src.utils.worker_pool import (
    init_preprocessing_worker,
    get_worker_parser,
    get_worker_cleaner,
    get_worker_extractor,
    get_worker_segmenter,
)


@pytest.fixture(autouse=True)
def reset_worker_globals():
    """Reset module-level worker globals before and after each test."""
    worker_pool_module._worker_parser = None
    worker_pool_module._worker_cleaner = None
    worker_pool_module._worker_extractor = None
    worker_pool_module._worker_segmenter = None
    yield
    worker_pool_module._worker_parser = None
    worker_pool_module._worker_cleaner = None
    worker_pool_module._worker_extractor = None
    worker_pool_module._worker_segmenter = None


class TestGettersBeforeInit:
    """Getters must raise RuntimeError when called before initialization."""

    def test_get_parser_raises_before_init(self):
        with pytest.raises(RuntimeError, match="not initialized"):
            get_worker_parser()

    def test_get_cleaner_raises_before_init(self):
        with pytest.raises(RuntimeError, match="not initialized"):
            get_worker_cleaner()

    def test_get_extractor_raises_before_init(self):
        with pytest.raises(RuntimeError, match="not initialized"):
            get_worker_extractor()

    def test_get_segmenter_raises_before_init(self):
        with pytest.raises(RuntimeError, match="not initialized"):
            get_worker_segmenter()


class TestInitPreprocessingWorker:
    """Tests for init_preprocessing_worker()."""

    def test_all_workers_loaded_by_default(self):
        mock_parser = MagicMock()
        mock_cleaner = MagicMock()
        mock_extractor = MagicMock()
        mock_segmenter = MagicMock()

        with patch("src.preprocessing.parser.SECFilingParser", return_value=mock_parser), \
             patch("src.preprocessing.cleaning.TextCleaner", return_value=mock_cleaner), \
             patch("src.preprocessing.extractor.SECSectionExtractor", return_value=mock_extractor), \
             patch("src.preprocessing.segmenter.RiskSegmenter", return_value=mock_segmenter):
            init_preprocessing_worker()

        assert worker_pool_module._worker_parser is not None
        assert worker_pool_module._worker_cleaner is not None
        assert worker_pool_module._worker_extractor is not None
        assert worker_pool_module._worker_segmenter is not None

    def test_load_parser_false_skips_parser(self):
        with patch("src.preprocessing.cleaning.TextCleaner"), \
             patch("src.preprocessing.extractor.SECSectionExtractor"), \
             patch("src.preprocessing.segmenter.RiskSegmenter"):
            init_preprocessing_worker(load_parser=False)

        assert worker_pool_module._worker_parser is None
        assert worker_pool_module._worker_cleaner is not None

    def test_load_cleaner_false_skips_cleaner(self):
        with patch("src.preprocessing.parser.SECFilingParser"), \
             patch("src.preprocessing.extractor.SECSectionExtractor"), \
             patch("src.preprocessing.segmenter.RiskSegmenter"):
            init_preprocessing_worker(load_cleaner=False)

        assert worker_pool_module._worker_cleaner is None
        assert worker_pool_module._worker_parser is not None

    def test_load_extractor_false_skips_extractor(self):
        with patch("src.preprocessing.parser.SECFilingParser"), \
             patch("src.preprocessing.cleaning.TextCleaner"), \
             patch("src.preprocessing.segmenter.RiskSegmenter"):
            init_preprocessing_worker(load_extractor=False)

        assert worker_pool_module._worker_extractor is None

    def test_load_segmenter_false_skips_segmenter(self):
        with patch("src.preprocessing.parser.SECFilingParser"), \
             patch("src.preprocessing.cleaning.TextCleaner"), \
             patch("src.preprocessing.extractor.SECSectionExtractor"):
            init_preprocessing_worker(load_segmenter=False)

        assert worker_pool_module._worker_segmenter is None

    def test_all_flags_false_loads_nothing(self):
        init_preprocessing_worker(
            load_parser=False,
            load_cleaner=False,
            load_extractor=False,
            load_segmenter=False,
        )
        assert worker_pool_module._worker_parser is None
        assert worker_pool_module._worker_cleaner is None
        assert worker_pool_module._worker_extractor is None
        assert worker_pool_module._worker_segmenter is None


class TestGettersAfterInit:
    """Getters return the objects set during initialization."""

    def test_get_parser_returns_initialized_object(self):
        sentinel = object()
        worker_pool_module._worker_parser = sentinel
        assert get_worker_parser() is sentinel

    def test_get_cleaner_returns_initialized_object(self):
        sentinel = object()
        worker_pool_module._worker_cleaner = sentinel
        assert get_worker_cleaner() is sentinel

    def test_get_extractor_returns_initialized_object(self):
        sentinel = object()
        worker_pool_module._worker_extractor = sentinel
        assert get_worker_extractor() is sentinel

    def test_get_segmenter_returns_initialized_object(self):
        sentinel = object()
        worker_pool_module._worker_segmenter = sentinel
        assert get_worker_segmenter() is sentinel

    def test_error_message_mentions_init_function(self):
        with pytest.raises(RuntimeError, match="init_preprocessing_worker"):
            get_worker_parser()

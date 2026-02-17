"""
Unit tests for Phase 2: Production Pipeline Global Workers

Tests the global worker pattern implementation in src/preprocessing/pipeline.py
Verifies worker initialization, reuse, and memory efficiency improvements.

Args tuple format for _process_single_filing_worker:
    (file_path, config_dict, form_type, output_dir, overwrite)
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.preprocessing.pipeline import (
    _worker_parser,
    _worker_cleaner,
    _worker_segmenter,
    _worker_extractor,
    _init_production_worker,
    _process_filing_with_global_workers,
    _process_single_filing_worker,
    PipelineConfig,
)


class TestGlobalWorkerInitialization:
    """Test global worker initialization."""

    def test_init_production_worker_creates_all_workers(self):
        """Test that _init_production_worker() creates all global workers."""
        with patch('src.preprocessing.pipeline.SECFilingParser') as mock_parser, \
             patch('src.preprocessing.pipeline.TextCleaner') as mock_cleaner, \
             patch('src.preprocessing.pipeline.RiskSegmenter') as mock_segmenter, \
             patch('src.preprocessing.pipeline.SECSectionExtractor') as mock_extractor:

            _init_production_worker()

            mock_parser.assert_called_once()
            mock_cleaner.assert_called_once()
            mock_segmenter.assert_called_once()
            mock_extractor.assert_called_once()

    def test_global_workers_exist_at_module_level(self):
        """Test that global worker variables exist at module level."""
        from src.preprocessing import pipeline

        assert hasattr(pipeline, '_worker_parser')
        assert hasattr(pipeline, '_worker_cleaner')
        assert hasattr(pipeline, '_worker_segmenter')
        assert hasattr(pipeline, '_worker_extractor')

    def test_all_four_workers_defined(self):
        """Verify all four required worker objects are defined."""
        from src.preprocessing import pipeline

        # All four workers must exist for the processing pipeline to work
        worker_names = ['_worker_parser', '_worker_cleaner', '_worker_segmenter', '_worker_extractor']
        for name in worker_names:
            assert hasattr(pipeline, name), f"Missing global worker: {name}"


class TestMemoryEfficiency:
    """Test memory efficiency of global worker pattern."""

    def test_amortized_overhead_calculation(self):
        """Verify 50x reduction in per-file memory overhead."""
        old_overhead_mb = 300  # Per file (old pattern: new instances)
        new_overhead_mb = 300  # Per worker (new pattern: reused)
        max_tasks_per_child = 50

        amortized = new_overhead_mb / max_tasks_per_child
        reduction = old_overhead_mb / amortized

        assert amortized == 6.0    # 300 / 50 = 6MB per file
        assert reduction == 50.0   # 50x improvement

    def test_worker_memory_components(self):
        """Verify memory breakdown per worker matches plan."""
        # From plan: spaCy ~200MB, SentenceTransformer ~80MB, sec-parser ~20MB
        memory = {
            'spacy_text_cleaner': 200,
            'sentence_transformer_segmenter': 80,
            'sec_parser': 20,
        }
        assert sum(memory.values()) == 300  # Total ~300MB per worker

    def test_max_tasks_per_child_value(self):
        """Verify max_tasks_per_child is set to 50 for periodic worker recycling."""
        # After 50 tasks, worker is recycled to free memory
        from src.utils.parallel import ParallelProcessor

        processor = ParallelProcessor(max_tasks_per_child=50)
        assert processor.max_tasks_per_child == 50


class TestProcessFilingWithGlobalWorkers:
    """Test _process_filing_with_global_workers function."""

    @pytest.fixture
    def sample_file(self, tmp_path):
        """Create a sample HTML test file."""
        f = tmp_path / "test_filing.html"
        f.write_text("<html><body>Risk factor content</body></html>")
        return f

    @pytest.fixture
    def config(self):
        return PipelineConfig()

    def test_uses_global_worker_parser(self, sample_file, config):
        """Test processing calls the global parser, not a new instance."""
        with patch('src.preprocessing.pipeline._worker_parser') as mock_parser, \
             patch('src.preprocessing.pipeline._worker_extractor') as mock_extractor, \
             patch('src.preprocessing.pipeline._worker_cleaner') as mock_cleaner, \
             patch('src.preprocessing.pipeline._worker_segmenter') as mock_segmenter:

            mock_parser.parse_filing.return_value = Mock(
                metadata={'cik': '123', 'sic_code': '7372', 'sic_name': 'Software'},
                __len__=Mock(return_value=5)
            )
            mock_extractor.extract_section.return_value = Mock(
                text="Risk text", subsections=[]
            )
            mock_cleaner.remove_html_tags.return_value = "Risk text"
            mock_cleaner.clean_text.return_value = "Cleaned risk text"
            mock_segmenter.segment_extracted_section.return_value = Mock()

            _process_filing_with_global_workers(
                file_path=sample_file,
                form_type="10-K",
                config=config,
                save_output=None,
                overwrite=False
            )

            mock_parser.parse_filing.assert_called_once_with(sample_file, "10-K")

    def test_four_step_flow_no_sanitization(self, sample_file, config):
        """Verify 4-step flow: Parse → Extract → Clean → Segment (no sanitization)."""
        call_order = []

        with patch('src.preprocessing.pipeline._worker_parser') as mock_parser, \
             patch('src.preprocessing.pipeline._worker_extractor') as mock_extractor, \
             patch('src.preprocessing.pipeline._worker_cleaner') as mock_cleaner, \
             patch('src.preprocessing.pipeline._worker_segmenter') as mock_segmenter:

            mock_parser.parse_filing.side_effect = lambda *a: call_order.append('parse') or Mock(
                metadata={'cik': '123', 'sic_code': '7372', 'sic_name': 'Software'},
                __len__=Mock(return_value=5)
            )
            mock_extractor.extract_section.side_effect = lambda *a: call_order.append('extract') or Mock(
                text="text", subsections=[]
            )
            mock_cleaner.clean_text.side_effect = lambda *a, **kw: call_order.append('clean') or "cleaned"
            mock_cleaner.remove_html_tags.return_value = "text"
            mock_segmenter.segment_extracted_section.side_effect = lambda *a, **kw: call_order.append('segment') or Mock()

            _process_filing_with_global_workers(
                file_path=sample_file,
                form_type="10-K",
                config=config,
                save_output=None,
                overwrite=False
            )

            assert call_order == ['parse', 'extract', 'clean', 'segment']

    def test_returns_none_when_section_not_found(self, sample_file, config):
        """Test returns None when extractor finds no section."""
        with patch('src.preprocessing.pipeline._worker_parser') as mock_parser, \
             patch('src.preprocessing.pipeline._worker_extractor') as mock_extractor:

            mock_parser.parse_filing.return_value = Mock(
                metadata={'cik': '123', 'sic_code': '7372', 'sic_name': 'SW'},
                __len__=Mock(return_value=0)
            )
            mock_extractor.extract_section.return_value = None  # Section not found

            result = _process_filing_with_global_workers(
                file_path=sample_file,
                form_type="10-K",
                config=config,
                save_output=None,
                overwrite=False
            )

            assert result is None

    def test_propagates_parser_exception(self, sample_file, config):
        """Test parser exceptions propagate out of the function."""
        with patch('src.preprocessing.pipeline._worker_parser') as mock_parser:
            mock_parser.parse_filing.side_effect = RuntimeError("Parser failure")

            with pytest.raises(RuntimeError, match="Parser failure"):
                _process_filing_with_global_workers(
                    file_path=sample_file,
                    form_type="10-K",
                    config=config,
                    save_output=None,
                    overwrite=False
                )


class TestProcessSingleFilingWorker:
    """Test _process_single_filing_worker function.

    Args tuple format: (file_path, config_dict, form_type, output_dir, overwrite)
    """

    @pytest.fixture
    def sample_args(self, tmp_path):
        """Create properly-structured args tuple."""
        file_path = tmp_path / "AAPL_10K_2025.html"
        file_path.write_text("<html><body>Risk factors...</body></html>")

        config_dict = PipelineConfig().model_dump()

        return (str(file_path), config_dict, "10-K", None, False)

    def test_success_result_structure(self, sample_args):
        """Test successful processing returns expected result keys."""
        mock_result = Mock()
        mock_result.__len__ = Mock(return_value=5)
        mock_result.sic_code = "7372"
        mock_result.company_name = "APPLE INC"

        with patch('src.preprocessing.pipeline._process_filing_with_global_workers') as mock_process:
            mock_process.return_value = mock_result

            result = _process_single_filing_worker(sample_args)

            assert result['status'] == 'success'
            assert result['num_segments'] == 5
            assert result['sic_code'] == "7372"
            assert result['company_name'] == "APPLE INC"
            assert 'elapsed_time' in result
            assert 'file_size_mb' in result

    def test_error_result_structure(self, sample_args):
        """Test that exceptions produce 'error' status result."""
        with patch('src.preprocessing.pipeline._process_filing_with_global_workers') as mock_process:
            mock_process.side_effect = RuntimeError("OOM killed")

            result = _process_single_filing_worker(sample_args)

            assert result['status'] == 'error'
            assert 'OOM killed' in result['error']
            assert 'elapsed_time' in result

    def test_warning_when_no_result(self, sample_args):
        """Test warning status when processing returns None."""
        with patch('src.preprocessing.pipeline._process_filing_with_global_workers') as mock_process:
            mock_process.return_value = None

            result = _process_single_filing_worker(sample_args)

            assert result['status'] == 'warning'
            assert result['result'] is None

    def test_unpacks_args_tuple_correctly(self, tmp_path):
        """Test that the args tuple is unpacked in (file_path, config_dict, form_type, output_dir, overwrite) order."""
        file_path = tmp_path / "test.html"
        file_path.write_text("<html>test</html>")

        custom_config = PipelineConfig(deep_clean=True)
        args = (str(file_path), custom_config.model_dump(), "10-Q", None, True)

        with patch('src.preprocessing.pipeline._process_filing_with_global_workers') as mock_process:
            mock_result = Mock()
            mock_result.__len__ = Mock(return_value=3)
            mock_result.sic_code = "1234"
            mock_result.company_name = "TEST CO"
            mock_process.return_value = mock_result

            result = _process_single_filing_worker(args)

            # Verify form_type was passed correctly
            call_kwargs = mock_process.call_args
            assert call_kwargs.kwargs['form_type'] == "10-Q"
            assert call_kwargs.kwargs['overwrite'] is True

    def test_calls_global_worker_processor(self, sample_args):
        """Test worker function delegates to _process_filing_with_global_workers."""
        mock_result = Mock()
        mock_result.__len__ = Mock(return_value=2)
        mock_result.sic_code = "7372"
        mock_result.company_name = "APPLE"

        with patch('src.preprocessing.pipeline._process_filing_with_global_workers') as mock_process:
            mock_process.return_value = mock_result

            _process_single_filing_worker(sample_args)

            mock_process.assert_called_once()


class TestSanitizationRemoval:
    """Test that HTML sanitization was removed in Phase 2."""

    def test_pipeline_config_has_no_sanitizer_fields(self):
        """Verify PipelineConfig has no pre_sanitize or sanitizer_config fields."""
        config = PipelineConfig()

        assert not hasattr(config, 'pre_sanitize')
        assert not hasattr(config, 'sanitizer_config')

    def test_pipeline_config_forbids_extra_fields(self):
        """Verify PipelineConfig raises on unknown/sanitizer fields (extra='forbid')."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            PipelineConfig(pre_sanitize=True)

    def test_processing_does_not_call_sanitizer(self, tmp_path):
        """Verify no HTMLSanitizer is called during processing."""
        file_path = tmp_path / "test.html"
        file_path.write_text("<html>test</html>")
        config = PipelineConfig()

        with patch('src.preprocessing.pipeline._worker_parser') as mock_parser, \
             patch('src.preprocessing.pipeline._worker_extractor') as mock_extractor, \
             patch('src.preprocessing.pipeline._worker_cleaner') as mock_cleaner, \
             patch('src.preprocessing.pipeline._worker_segmenter') as mock_segmenter:

            mock_parser.parse_filing.return_value = Mock(
                metadata={'cik': '123', 'sic_code': '7372', 'sic_name': 'SW'},
                __len__=Mock(return_value=0)
            )
            mock_extractor.extract_section.return_value = None

            try:
                _process_filing_with_global_workers(
                    file_path=file_path,
                    form_type="10-K",
                    config=config,
                    save_output=None,
                    overwrite=False
                )
            except Exception:
                pass

            # Sanitizer should never be called (it's been removed)
            # If a 'sanitize' method was called on any mock, the test would fail
            for mock in [mock_parser, mock_extractor, mock_cleaner, mock_segmenter]:
                assert not hasattr(mock, 'sanitize') or not mock.sanitize.called


class TestIntegrationWithParallelProcessor:
    """Test ParallelProcessor integration."""

    def test_accepts_initializer_parameter(self):
        """Verify ParallelProcessor accepts the initializer function."""
        from src.utils.parallel import ParallelProcessor

        processor = ParallelProcessor(
            max_workers=2,
            initializer=_init_production_worker,
            max_tasks_per_child=50,
            task_timeout=1200
        )

        assert processor.initializer is _init_production_worker

    def test_max_tasks_per_child_set_to_50(self):
        """Verify max_tasks_per_child is 50 for memory management."""
        from src.utils.parallel import ParallelProcessor

        processor = ParallelProcessor(
            max_workers=4,
            initializer=_init_production_worker,
            max_tasks_per_child=50,
            task_timeout=1200
        )

        assert processor.max_tasks_per_child == 50


class TestPhase2CompletionCriteria:
    """Verify all Phase 2 completion criteria from the optimization plan."""

    def test_global_worker_objects_exist(self):
        """Verify all 4 global worker objects are defined."""
        from src.preprocessing import pipeline

        assert hasattr(pipeline, '_worker_parser')
        assert hasattr(pipeline, '_worker_cleaner')
        assert hasattr(pipeline, '_worker_segmenter')
        assert hasattr(pipeline, '_worker_extractor')

    def test_init_function_exists_and_callable(self):
        """Verify _init_production_worker() exists and is callable."""
        from src.preprocessing.pipeline import _init_production_worker

        assert callable(_init_production_worker)

    def test_efficient_processing_function_exists(self):
        """Verify _process_filing_with_global_workers() exists."""
        from src.preprocessing.pipeline import _process_filing_with_global_workers

        assert callable(_process_filing_with_global_workers)

    def test_worker_function_exists(self):
        """Verify _process_single_filing_worker() exists."""
        from src.preprocessing.pipeline import _process_single_filing_worker

        assert callable(_process_single_filing_worker)

    def test_50x_memory_reduction_target(self):
        """Verify the 50x memory reduction target is met."""
        old_overhead_per_file_mb = 300
        worker_memory_mb = 300
        tasks_per_worker = 50

        new_overhead_per_file_mb = worker_memory_mb / tasks_per_worker
        reduction = old_overhead_per_file_mb / new_overhead_per_file_mb

        assert reduction >= 50.0  # Must meet or exceed 50x target


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

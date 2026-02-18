"""Unit tests for src/utils/resource_tracker.py — ResourceTracker."""

import time
import pytest
from unittest.mock import patch, MagicMock

from src.utils.resource_tracker import ResourceTracker, ResourceSnapshot, ResourceUsage


class TestResourceSnapshot:
    """Tests for ResourceSnapshot data class."""

    def test_capture_returns_snapshot(self):
        snap = ResourceSnapshot.capture()
        assert isinstance(snap, ResourceSnapshot)
        assert snap.timestamp > 0
        assert snap.memory_mb >= 0.0

    def test_capture_handles_psutil_failure(self):
        with patch("psutil.Process", side_effect=Exception("psutil error")):
            snap = ResourceSnapshot.capture()
        assert snap.memory_mb == 0.0
        assert snap.timestamp > 0


class TestResourceUsage:
    """Tests for ResourceUsage data class."""

    def test_elapsed_time_uses_end_time(self):
        start = time.time() - 5.0
        usage = ResourceUsage(start_time=start, end_time=time.time())
        assert 4.9 < usage.elapsed_time() < 6.0

    def test_elapsed_time_uses_now_when_not_finalized(self):
        start = time.time() - 2.0
        usage = ResourceUsage(start_time=start)
        assert usage.elapsed_time() >= 2.0

    def test_to_dict_contains_required_keys(self):
        usage = ResourceUsage(
            start_time=time.time() - 1.0,
            end_time=time.time(),
            peak_memory_mb=500.0,
            avg_memory_mb=400.0,
            module_timings={"parser": 0.5, "cleaner": 0.2},
        )
        d = usage.to_dict()
        assert "elapsed_time" in d
        assert "peak_memory_mb" in d
        assert "avg_memory_mb" in d
        assert "module_timings" in d

    def test_to_dict_rounds_memory_to_one_decimal(self):
        usage = ResourceUsage(
            start_time=time.time(),
            peak_memory_mb=512.3456,
            avg_memory_mb=400.1234,
        )
        d = usage.to_dict()
        assert d["peak_memory_mb"] == 512.3
        assert d["avg_memory_mb"] == 400.1

    def test_to_dict_rounds_timings_to_three_decimals(self):
        usage = ResourceUsage(
            start_time=time.time(),
            module_timings={"parser": 1.23456789},
        )
        d = usage.to_dict()
        assert d["module_timings"]["parser"] == 1.235


class TestResourceTrackerInit:
    """Tests for ResourceTracker initialization."""

    def test_creates_usage_with_start_time(self):
        before = time.time()
        tracker = ResourceTracker()
        after = time.time()
        assert before <= tracker.usage.start_time <= after

    def test_takes_baseline_snapshot_on_init(self):
        tracker = ResourceTracker()
        assert len(tracker.usage.snapshots) >= 1


class TestTrackModule:
    """Tests for ResourceTracker.track_module() context manager."""

    def test_records_module_timing(self):
        tracker = ResourceTracker()
        with tracker.track_module("parser"):
            time.sleep(0.01)

        assert "parser" in tracker.usage.module_timings
        assert tracker.usage.module_timings["parser"] >= 0.01

    def test_records_multiple_modules(self):
        tracker = ResourceTracker()
        with tracker.track_module("parser"):
            time.sleep(0.005)
        with tracker.track_module("cleaner"):
            time.sleep(0.005)

        assert "parser" in tracker.usage.module_timings
        assert "cleaner" in tracker.usage.module_timings

    def test_takes_snapshots_around_module(self):
        tracker = ResourceTracker()
        snapshots_before = len(tracker.usage.snapshots)

        with tracker.track_module("extractor"):
            pass

        # Should have added at least 2 snapshots (before + after)
        assert len(tracker.usage.snapshots) >= snapshots_before + 2

    def test_records_timing_even_on_exception(self):
        tracker = ResourceTracker()

        with pytest.raises(ValueError):
            with tracker.track_module("parser"):
                raise ValueError("boom")

        assert "parser" in tracker.usage.module_timings

    def test_nested_modules_are_independent(self):
        tracker = ResourceTracker()
        with tracker.track_module("outer"):
            with tracker.track_module("inner"):
                time.sleep(0.005)

        assert "outer" in tracker.usage.module_timings
        assert "inner" in tracker.usage.module_timings


class TestFinalize:
    """Tests for ResourceTracker.finalize()."""

    def test_sets_end_time(self):
        tracker = ResourceTracker()
        before = time.time()
        usage = tracker.finalize()
        after = time.time()

        assert before <= usage.end_time <= after

    def test_returns_resource_usage(self):
        tracker = ResourceTracker()
        usage = tracker.finalize()
        assert isinstance(usage, ResourceUsage)

    def test_computes_peak_memory(self):
        tracker = ResourceTracker()
        with tracker.track_module("parser"):
            pass
        usage = tracker.finalize()
        assert usage.peak_memory_mb >= 0.0

    def test_computes_avg_memory(self):
        tracker = ResourceTracker()
        with tracker.track_module("parser"):
            pass
        usage = tracker.finalize()
        assert usage.avg_memory_mb >= 0.0
        assert usage.avg_memory_mb <= usage.peak_memory_mb + 1  # avg ≤ peak

    def test_elapsed_time_positive(self):
        tracker = ResourceTracker()
        time.sleep(0.01)
        usage = tracker.finalize()
        assert usage.elapsed_time() >= 0.01

    def test_to_dict_after_finalize(self):
        tracker = ResourceTracker()
        with tracker.track_module("parser"):
            time.sleep(0.005)
        with tracker.track_module("cleaner"):
            time.sleep(0.005)

        d = tracker.finalize().to_dict()

        assert d["elapsed_time"] > 0
        assert "parser" in d["module_timings"]
        assert "cleaner" in d["module_timings"]
        assert d["peak_memory_mb"] >= 0.0

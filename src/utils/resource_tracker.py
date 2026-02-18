"""Per-module resource tracking for preprocessing workers.

Tracks wall-clock time and RSS memory for each pipeline step
(parser, extractor, cleaner, segmenter) via a lightweight context manager.
Results are returned as a plain dict so they can be included in the
worker result dict and written to batch summary JSON.

Usage:
    from src.utils.resource_tracker import ResourceTracker

    tracker = ResourceTracker()

    with tracker.track_module("parser"):
        parsed = parser.parse_filing(file_path)

    with tracker.track_module("extractor"):
        extracted = extractor.extract_section(parsed, section)

    usage = tracker.finalize()
    print(usage.to_dict())
    # {
    #   "elapsed_time": 14.2,
    #   "peak_memory_mb": 1240.0,
    #   "avg_memory_mb": 870.3,
    #   "module_timings": {"parser": 11.1, "extractor": 2.4, ...}
    # }
"""

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ResourceSnapshot:
    """RSS memory and timestamp captured at a single instant."""

    timestamp: float
    memory_mb: float

    @staticmethod
    def capture() -> "ResourceSnapshot":
        """Capture current process RSS memory."""
        try:
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / (1024 ** 2)
        except Exception:
            memory_mb = 0.0
        return ResourceSnapshot(timestamp=time.time(), memory_mb=memory_mb)


@dataclass
class ResourceUsage:
    """Aggregated resource usage for a complete pipeline run."""

    start_time: float
    end_time: Optional[float] = None
    peak_memory_mb: float = 0.0
    avg_memory_mb: float = 0.0
    module_timings: Dict[str, float] = field(default_factory=dict)
    snapshots: List[ResourceSnapshot] = field(default_factory=list)

    def elapsed_time(self) -> float:
        """Wall-clock seconds from start to end (or now if not finalised)."""
        end = self.end_time or time.time()
        return end - self.start_time

    def to_dict(self) -> Dict[str, Any]:
        """Serialisable dict for inclusion in batch result JSON."""
        return {
            "elapsed_time": self.elapsed_time(),
            "peak_memory_mb": round(self.peak_memory_mb, 1),
            "avg_memory_mb": round(self.avg_memory_mb, 1),
            "module_timings": {k: round(v, 3) for k, v in self.module_timings.items()},
        }


# ---------------------------------------------------------------------------
# Tracker
# ---------------------------------------------------------------------------

class ResourceTracker:
    """
    Lightweight resource tracker for preprocessing pipeline steps.

    Creates a ``ResourceUsage`` object and provides a context manager
    (``track_module``) that records wall-clock time and memory snapshots
    for each named step.

    Example:
        tracker = ResourceTracker()

        with tracker.track_module("parser"):
            parsed = parser.parse_filing(file_path)

        with tracker.track_module("cleaner"):
            cleaned = cleaner.clean_text(text)

        usage = tracker.finalize()
        result["resource_usage"] = usage.to_dict()
    """

    def __init__(self) -> None:
        self.usage = ResourceUsage(start_time=time.time())
        self._snapshot()  # Baseline at construction

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    @contextmanager
    def track_module(self, module_name: str):
        """
        Context manager that records elapsed time and memory for *module_name*.

        Args:
            module_name: Human-readable step name (e.g. ``"parser"``).

        Yields:
            None — just wraps the block.
        """
        self._snapshot()
        start = time.time()
        try:
            yield
        finally:
            elapsed = time.time() - start
            self.usage.module_timings[module_name] = elapsed
            self._snapshot()

    # ------------------------------------------------------------------
    # Finalise
    # ------------------------------------------------------------------

    def finalize(self) -> ResourceUsage:
        """
        Close tracking and compute aggregate memory statistics.

        Returns:
            Completed :class:`ResourceUsage` object.
        """
        self._snapshot()
        self.usage.end_time = time.time()

        if self.usage.snapshots:
            memories = [s.memory_mb for s in self.usage.snapshots]
            self.usage.peak_memory_mb = max(memories)
            self.usage.avg_memory_mb = sum(memories) / len(memories)

        return self.usage

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _snapshot(self) -> None:
        snap = ResourceSnapshot.capture()
        self.usage.snapshots.append(snap)
        if snap.memory_mb > self.usage.peak_memory_mb:
            self.usage.peak_memory_mb = snap.memory_mb

"""
Memory-aware resource allocation for preprocessing pipeline.

This module provides memory-based throttling to prevent OOM crashes when
processing large batches of SEC filings. It estimates per-file memory
consumption and checks available RAM before allocating workers.

Key Features:
- File size classification (SMALL, MEDIUM, LARGE)
- Memory requirement estimation based on file size
- Adaptive timeout recommendations
- Worker pool allocation (shared vs isolated)
- Memory availability checking with safety margins

Usage:
    from src.utils.memory_semaphore import MemorySemaphore, FileCategory

    semaphore = MemorySemaphore(safety_margin=0.2)
    estimate = semaphore.get_resource_estimate(file_path)

    if semaphore.can_allocate(estimate.estimated_memory_mb):
        # Safe to process
        process_file(file_path, timeout=estimate.recommended_timeout_sec)
    else:
        # Wait for memory to become available
        if semaphore.wait_for_memory(estimate.estimated_memory_mb):
            process_file(file_path)
"""

import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

# Try to import psutil, but make it optional for testing
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    logger.warning("psutil not installed - memory monitoring will use fallback estimates")


class FileCategory(Enum):
    """File size categories for resource allocation."""
    SMALL = "small"    # <20MB
    MEDIUM = "medium"  # 20-50MB
    LARGE = "large"    # >50MB


@dataclass
class ResourceEstimate:
    """
    Estimated resource requirements for processing a file.

    Attributes:
        file_size_mb: File size in megabytes
        category: FileCategory classification
        estimated_memory_mb: Estimated peak memory consumption
        recommended_timeout_sec: Recommended processing timeout
        worker_pool: Recommended worker pool ("shared" or "isolated")
    """
    file_size_mb: float
    category: FileCategory
    estimated_memory_mb: float
    recommended_timeout_sec: int
    worker_pool: str  # "shared" or "isolated"

    def __repr__(self) -> str:
        return (
            f"ResourceEstimate("
            f"size={self.file_size_mb:.1f}MB, "
            f"category={self.category.value}, "
            f"memory={self.estimated_memory_mb:.0f}MB, "
            f"timeout={self.recommended_timeout_sec}s, "
            f"pool={self.worker_pool})"
        )


class MemorySemaphore:
    """
    Memory-aware semaphore for throttling worker allocation.

    Prevents OOM by estimating per-file memory consumption and checking
    available RAM before allocating workers.

    Memory Estimation Formula (based on research):
        Parser: 10x file size (BeautifulSoup DOM overhead)
        Cleaner: 2x file size (spaCy Doc object)
        Worker overhead: 500MB (models + Python runtime)
        Total: (file_size_mb * 12) + 500MB

    Example:
        68MB file -> (68 * 12) + 500 = 1,316MB estimated peak

    Research Evidence:
        - 68MB file: 700-1000MB parser peak (10-15x multiplier)
        - 50MB section: 100-150MB cleaner peak (2-3x multiplier)
        - Conservative estimate uses 12x total + 500MB overhead
    """

    # Memory estimation multipliers (based on research document)
    PARSER_MULTIPLIER = 10  # BeautifulSoup DOM is ~10x raw HTML size
    CLEANER_MULTIPLIER = 2   # spaCy Doc is ~2x text size
    WORKER_OVERHEAD_MB = 500  # Models + Python runtime

    # File size thresholds (MB)
    SMALL_THRESHOLD = 20
    MEDIUM_THRESHOLD = 50

    # Timeout multipliers by category (seconds)
    TIMEOUT_MAP = {
        FileCategory.SMALL: 600,   # 10 minutes
        FileCategory.MEDIUM: 1200, # 20 minutes
        FileCategory.LARGE: 2400,  # 40 minutes
    }

    def __init__(self, safety_margin: float = 0.2):
        """
        Initialize memory semaphore.

        Args:
            safety_margin: Reserve this fraction of total RAM (default: 0.2 = 20%)
                          This prevents the system from using all available memory
                          and maintains headroom for OS and other processes.

        Example:
            # Reserve 20% of RAM (default)
            semaphore = MemorySemaphore()

            # More conservative (reserve 30%)
            semaphore = MemorySemaphore(safety_margin=0.3)
        """
        if not 0 <= safety_margin <= 0.5:
            raise ValueError("safety_margin must be between 0 and 0.5")

        self.safety_margin = safety_margin

        if HAS_PSUTIL:
            self.total_memory_mb = psutil.virtual_memory().total / (1024**2)
            self.reserved_memory_mb = self.total_memory_mb * safety_margin
            logger.info(
                f"MemorySemaphore initialized: "
                f"total={self.total_memory_mb:.0f}MB, "
                f"reserved={self.reserved_memory_mb:.0f}MB ({safety_margin:.0%})"
            )
        else:
            # Fallback: assume 16GB system
            self.total_memory_mb = 16 * 1024
            self.reserved_memory_mb = self.total_memory_mb * safety_margin
            logger.warning(
                f"psutil not available - using fallback: "
                f"assumed_total={self.total_memory_mb:.0f}MB"
            )

    @staticmethod
    def estimate_file_memory(file_size_mb: float) -> float:
        """
        Estimate peak memory consumption for processing a file.

        Formula:
            estimated_memory = (file_size_mb * 12) + 500MB

        Where:
            - 12x multiplier accounts for:
              * Parser DOM overhead: ~10x
              * Cleaner spaCy Doc: ~2x
            - 500MB base overhead for worker models

        Args:
            file_size_mb: File size in megabytes

        Returns:
            Estimated peak memory in MB

        Example:
            >>> MemorySemaphore.estimate_file_memory(68)  # 68MB file
            1316  # 68 * 12 + 500 = 1,316MB estimated
        """
        base_estimate = (file_size_mb * 12) + MemorySemaphore.WORKER_OVERHEAD_MB
        return base_estimate

    @staticmethod
    def classify_file(file_path: Path) -> FileCategory:
        """
        Classify file by size category.

        Categories:
            - SMALL: < 20MB
            - MEDIUM: 20-50MB
            - LARGE: > 50MB

        Args:
            file_path: Path to file

        Returns:
            FileCategory enum

        Example:
            >>> from pathlib import Path
            >>> MemorySemaphore.classify_file(Path("small.html"))  # 15MB
            FileCategory.SMALL
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        size_mb = file_path.stat().st_size / (1024**2)

        if size_mb > MemorySemaphore.MEDIUM_THRESHOLD:
            return FileCategory.LARGE
        elif size_mb > MemorySemaphore.SMALL_THRESHOLD:
            return FileCategory.MEDIUM
        else:
            return FileCategory.SMALL

    @staticmethod
    def get_resource_estimate(file_path: Path) -> ResourceEstimate:
        """
        Get complete resource estimate for a file.

        Provides:
            - File size
            - Category classification
            - Estimated memory requirement
            - Recommended timeout
            - Recommended worker pool (shared vs isolated)

        Args:
            file_path: Path to file

        Returns:
            ResourceEstimate with memory, timeout, worker pool recommendations

        Example:
            >>> estimate = MemorySemaphore.get_resource_estimate(Path("large.html"))
            >>> print(estimate)
            ResourceEstimate(size=68.2MB, category=large, memory=1318MB,
                           timeout=2400s, pool=isolated)
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        size_mb = file_path.stat().st_size / (1024**2)
        category = MemorySemaphore.classify_file(file_path)
        estimated_memory = MemorySemaphore.estimate_file_memory(size_mb)

        # Adaptive timeout based on category
        timeout = MemorySemaphore.TIMEOUT_MAP[category]

        # Worker pool allocation
        # Large files get isolated to dedicated workers to prevent interference
        worker_pool = "isolated" if category == FileCategory.LARGE else "shared"

        return ResourceEstimate(
            file_size_mb=size_mb,
            category=category,
            estimated_memory_mb=estimated_memory,
            recommended_timeout_sec=timeout,
            worker_pool=worker_pool
        )

    def can_allocate(self, estimated_memory_mb: float) -> bool:
        """
        Check if sufficient memory is available for allocation.

        This checks if allocating the requested memory would leave enough
        headroom (based on safety_margin) for system stability.

        Args:
            estimated_memory_mb: Estimated memory requirement

        Returns:
            True if allocation is safe, False if would risk OOM

        Example:
            >>> semaphore = MemorySemaphore(safety_margin=0.2)
            >>> semaphore.can_allocate(1000)  # Check if 1GB is available
            True
        """
        if HAS_PSUTIL:
            available_mb = psutil.virtual_memory().available / (1024**2)
        else:
            # Fallback: assume 50% is available
            available_mb = self.total_memory_mb * 0.5

        # Require available memory > estimated + reserved margin
        required_mb = estimated_memory_mb + self.reserved_memory_mb

        can_allocate = available_mb > required_mb

        if not can_allocate:
            logger.debug(
                f"Memory check failed: "
                f"available={available_mb:.0f}MB, "
                f"required={required_mb:.0f}MB "
                f"(requested={estimated_memory_mb:.0f}MB + "
                f"reserved={self.reserved_memory_mb:.0f}MB)"
            )

        return can_allocate

    def wait_for_memory(
        self,
        estimated_memory_mb: float,
        timeout: int = 300,
        check_interval: int = 5
    ) -> bool:
        """
        Wait for sufficient memory to become available.

        Polls memory availability every `check_interval` seconds until
        either memory becomes available or timeout is reached.

        Args:
            estimated_memory_mb: Required memory
            timeout: Max wait time in seconds (default: 300 = 5 minutes)
            check_interval: Check every N seconds (default: 5)

        Returns:
            True if memory became available, False if timeout

        Example:
            >>> semaphore = MemorySemaphore()
            >>> if not semaphore.can_allocate(1500):
            ...     print("Waiting for memory...")
            ...     if semaphore.wait_for_memory(1500, timeout=300):
            ...         print("Memory available!")
            ...     else:
            ...         print("Timeout - insufficient memory")
        """
        elapsed = 0
        wait_start = time.time()

        logger.info(
            f"Waiting for memory: need {estimated_memory_mb:.0f}MB, "
            f"timeout={timeout}s"
        )

        while elapsed < timeout:
            if self.can_allocate(estimated_memory_mb):
                logger.info(
                    f"Memory available after {elapsed}s wait "
                    f"(needed {estimated_memory_mb:.0f}MB)"
                )
                return True

            time.sleep(check_interval)
            elapsed = int(time.time() - wait_start)

            # Log every 30 seconds
            if elapsed % 30 == 0 and elapsed > 0:
                status = self.get_memory_status()
                logger.info(
                    f"Still waiting for memory ({elapsed}s elapsed): "
                    f"available={status['available_mb']:.0f}MB, "
                    f"needed={estimated_memory_mb:.0f}MB"
                )

        logger.warning(
            f"Memory wait timeout after {timeout}s "
            f"(needed {estimated_memory_mb:.0f}MB)"
        )
        return False

    def get_memory_status(self) -> Dict[str, Any]:
        """
        Get current memory status for monitoring.

        Returns:
            Dict with total, available, used, percent, safe_threshold_mb

        Example:
            >>> semaphore = MemorySemaphore()
            >>> status = semaphore.get_memory_status()
            >>> print(f"Memory: {status['available_mb']:.0f}MB available "
            ...       f"({status['percent']:.1f}% used)")
        """
        if HAS_PSUTIL:
            mem = psutil.virtual_memory()
            return {
                'total_mb': mem.total / (1024**2),
                'available_mb': mem.available / (1024**2),
                'used_mb': mem.used / (1024**2),
                'percent': mem.percent,
                'safe_threshold_mb': self.total_memory_mb * (1 - self.safety_margin)
            }
        else:
            # Fallback estimates
            return {
                'total_mb': self.total_memory_mb,
                'available_mb': self.total_memory_mb * 0.5,  # Assume 50% available
                'used_mb': self.total_memory_mb * 0.5,
                'percent': 50.0,
                'safe_threshold_mb': self.total_memory_mb * (1 - self.safety_margin)
            }


# Convenience function for quick estimates
def get_file_estimate(file_path: Path) -> ResourceEstimate:
    """
    Convenience function to get resource estimate for a file.

    Args:
        file_path: Path to file

    Returns:
        ResourceEstimate

    Example:
        >>> from src.utils.memory_semaphore import get_file_estimate
        >>> estimate = get_file_estimate(Path("large_filing.html"))
        >>> print(f"This file needs {estimate.estimated_memory_mb:.0f}MB")
    """
    return MemorySemaphore.get_resource_estimate(file_path)

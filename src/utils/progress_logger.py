"""
Real-time progress logging utility for batch processing scripts.

Provides thread-safe and process-safe logging with automatic flushing
to ensure real-time visibility of progress in long-running batch jobs.

Features:
- Auto-flush to file and console
- Timestamped log entries
- Support for progress updates (carriage return style)
- Thread-safe and process-safe file writes
- Context manager support
- Drop-in replacement for print() with flush=True

Usage:
    # Basic usage
    logger = ProgressLogger("output/dir/progress.log")
    logger.log("Processing started")
    logger.log(f"Processing file {i}/{total}: {filename}")
    logger.close()

    # Context manager (recommended)
    with ProgressLogger("output/dir/progress.log") as logger:
        for i, file in enumerate(files, 1):
            logger.log(f"[{i}/{len(files)}] Processing: {file.name}")
            # ... processing logic

    # Disable console output for quiet mode
    logger = ProgressLogger("output/dir/progress.log", console=False)

    # Progress updates (overwrites last line in console)
    logger = ProgressLogger("output/dir/progress.log")
    for i in range(100):
        logger.progress(f"Progress: {i}/100")  # Overwrites in console
    logger.log("Complete!")  # Newline after progress updates
"""

import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, TextIO


class ProgressLogger:
    """
    Thread-safe and process-safe progress logger with auto-flush.

    Writes timestamped logs to file and optionally to console with automatic
    flushing to ensure real-time visibility.

    Attributes:
        log_path: Path to log file
        console: Whether to also output to console
        quiet: If True and console=True, minimize console output
        _file: File handle for log file
        _lock: Thread lock for safe concurrent writes
        _last_was_progress: Track if last output was progress update
    """

    def __init__(
        self,
        log_path: Path | str,
        console: bool = True,
        quiet: bool = False,
        append: bool = True
    ):
        """
        Initialize progress logger.

        Args:
            log_path: Path to log file (created if doesn't exist)
            console: If True, also output to console (default: True)
            quiet: If True and console=True, minimize console output (default: False)
            append: If True, append to existing file; if False, overwrite (default: True)
        """
        self.log_path = Path(log_path)
        self.console = console
        self.quiet = quiet
        self._lock = threading.Lock()
        self._last_was_progress = False

        # Create parent directory if it doesn't exist
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        # Open file with line buffering (buffering=1) for auto-flush per line
        mode = 'a' if append else 'w'
        self._file: Optional[TextIO] = open(
            self.log_path,
            mode=mode,
            encoding='utf-8',
            buffering=1  # Line buffering
        )

        # Write header if new file
        if not append or self.log_path.stat().st_size == 0:
            self._write_to_file(f"=== Progress Log Started: {datetime.now().isoformat()} ===\n")

    def log(self, message: str, timestamp: bool = True) -> None:
        """
        Log a message with optional timestamp.

        Args:
            message: Message to log
            timestamp: If True, prepend timestamp to message (default: True)
        """
        with self._lock:
            # Format message with timestamp
            if timestamp:
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                formatted = f"[{ts}] {message}"
            else:
                formatted = message

            # Write to file
            self._write_to_file(formatted + '\n')

            # Write to console if enabled
            if self.console:
                # If last output was progress update, add newline first
                if self._last_was_progress:
                    print()  # Move to new line
                    self._last_was_progress = False

                print(formatted, flush=True)

    def progress(self, message: str, timestamp: bool = False) -> None:
        """
        Log a progress update (overwrites last line in console).

        In console, uses carriage return to overwrite previous progress.
        In log file, writes as normal line for permanent record.

        Args:
            message: Progress message to display
            timestamp: If True, prepend timestamp (default: False for progress)
        """
        with self._lock:
            # Format message with optional timestamp
            if timestamp:
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                formatted = f"[{ts}] {message}"
            else:
                formatted = message

            # Write to file (permanent record)
            self._write_to_file(formatted + '\n')

            # Write to console with carriage return if enabled
            if self.console and not self.quiet:
                # Clear line and write progress
                print(f'\r{formatted}', end='', flush=True)
                self._last_was_progress = True

    def _write_to_file(self, content: str) -> None:
        """
        Write content to file (internal method, assumes lock is held).

        Args:
            content: Content to write
        """
        if self._file and not self._file.closed:
            self._file.write(content)
            self._file.flush()  # Explicit flush for immediate visibility

    def section(self, title: str, char: str = "=", width: int = 80) -> None:
        """
        Log a section header for better organization.

        Args:
            title: Section title
            char: Character to use for separator line (default: "=")
            width: Width of separator line (default: 80)
        """
        separator = char * width
        self.log(separator, timestamp=False)
        self.log(title, timestamp=True)
        self.log(separator, timestamp=False)

    def error(self, message: str) -> None:
        """
        Log an error message with ERROR prefix.

        Args:
            message: Error message
        """
        self.log(f"ERROR: {message}", timestamp=True)

    def warning(self, message: str) -> None:
        """
        Log a warning message with WARNING prefix.

        Args:
            message: Warning message
        """
        self.log(f"WARNING: {message}", timestamp=True)

    def success(self, message: str) -> None:
        """
        Log a success message with SUCCESS prefix.

        Args:
            message: Success message
        """
        self.log(f"SUCCESS: {message}", timestamp=True)

    def close(self) -> None:
        """Close the log file."""
        with self._lock:
            if self._file and not self._file.closed:
                # If last output was progress, add newline
                if self._last_was_progress and self.console:
                    print()  # Move to new line

                self._write_to_file(f"=== Progress Log Ended: {datetime.now().isoformat()} ===\n")
                self._file.close()
                self._file = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False  # Don't suppress exceptions

    def __del__(self):
        """Destructor to ensure file is closed."""
        if hasattr(self, '_file') and self._file and not self._file.closed:
            self.close()


class BatchProgressLogger(ProgressLogger):
    """
    Extended progress logger specifically for batch processing.

    Adds convenience methods for common batch processing patterns like
    file counting, success/error tracking, and summary reporting.
    """

    def __init__(self, log_path: Path | str, total_items: int, **kwargs):
        """
        Initialize batch progress logger.

        Args:
            log_path: Path to log file
            total_items: Total number of items to process
            **kwargs: Additional arguments passed to ProgressLogger
        """
        super().__init__(log_path, **kwargs)
        self.total_items = total_items
        self.current_item = 0
        self.success_count = 0
        self.error_count = 0
        self.warning_count = 0

        # Log initialization
        self.section(f"Batch Processing: {total_items} items", char="=")

    def log_item_start(self, item_name: str) -> None:
        """
        Log the start of processing an item.

        Args:
            item_name: Name of item being processed
        """
        self.current_item += 1
        self.log(f"[{self.current_item}/{self.total_items}] Processing: {item_name}")

    def log_item_success(self, item_name: str, details: str = "") -> None:
        """
        Log successful processing of an item.

        Args:
            item_name: Name of item processed
            details: Optional additional details
        """
        self.success_count += 1
        msg = f"[{self.current_item}/{self.total_items}] SUCCESS: {item_name}"
        if details:
            msg += f" - {details}"
        self.log(msg)

    def log_item_error(self, item_name: str, error: str) -> None:
        """
        Log error processing an item.

        Args:
            item_name: Name of item that failed
            error: Error message
        """
        self.error_count += 1
        self.error(f"[{self.current_item}/{self.total_items}] FAILED: {item_name} - {error}")

    def log_item_warning(self, item_name: str, warning: str) -> None:
        """
        Log warning for an item.

        Args:
            item_name: Name of item
            warning: Warning message
        """
        self.warning_count += 1
        self.warning(f"[{self.current_item}/{self.total_items}] WARNING: {item_name} - {warning}")

    def log_summary(self) -> None:
        """Log a summary of batch processing results."""
        self.section("Batch Processing Summary", char="=")
        self.log(f"Total items: {self.total_items}", timestamp=False)
        self.log(f"Processed: {self.current_item}", timestamp=False)
        self.log(f"Successful: {self.success_count}", timestamp=False)
        self.log(f"Warnings: {self.warning_count}", timestamp=False)
        self.log(f"Errors: {self.error_count}", timestamp=False)

        if self.total_items > 0:
            success_rate = (self.success_count / self.total_items) * 100
            self.log(f"Success rate: {success_rate:.1f}%", timestamp=False)

    def update_progress(self, current: Optional[int] = None) -> None:
        """
        Update progress indicator.

        Args:
            current: Current item number (uses internal counter if not provided)
        """
        if current is not None:
            self.current_item = current

        pct = (self.current_item / self.total_items * 100) if self.total_items > 0 else 0
        self.progress(
            f"Progress: {self.current_item}/{self.total_items} ({pct:.1f}%) | "
            f"Success: {self.success_count} | Errors: {self.error_count}"
        )


# Convenience function for simple use cases
def create_progress_logger(
    output_dir: Path | str,
    log_filename: str = "_progress.log",
    **kwargs
) -> ProgressLogger:
    """
    Create a progress logger with standard naming.

    Args:
        output_dir: Directory to place log file
        log_filename: Name of log file (default: "_progress.log")
        **kwargs: Additional arguments passed to ProgressLogger

    Returns:
        Initialized ProgressLogger instance

    Example:
        logger = create_progress_logger("data/interim/parsed/run123")
        logger.log("Processing started")
    """
    output_dir = Path(output_dir)
    log_path = output_dir / log_filename
    return ProgressLogger(log_path, **kwargs)

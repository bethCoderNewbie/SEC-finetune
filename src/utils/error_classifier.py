"""Worker error classification for the preprocessing pipeline.

Provides ``classify_worker_exception()`` and helpers consumed by:

- ``src/utils/parallel.py``   — sets ``error_type`` in result dicts and DLQ reason
- ``src/utils/worker_pool.py`` — drives GPU health flag via ``is_cuda_error()``
- Worker functions             — decide on GPU fallback before re-raising

Error type taxonomy
-------------------
cuda_error   CUDA kernel failure (cudaErrorLaunchFailure, cudaErrorIllegalInstruction, …)
             Corrupts the CUDA context in the worker; GPU calls will keep failing.
             Retry action: ``--no-sentiment`` (CPU-only sentiment) or skip sentiment.

cuda_oom     CUDA out-of-memory (torch.cuda.OutOfMemoryError, CUDA OOM in message).
             GPU context is still valid; retry with smaller batch or ``--no-sentiment``.

cpu_oom      System RAM exhausted (MemoryError, Linux OOM-kill signal).
             Retry action: single-threaded ``--workers 1`` or reduce ``--chunk-size``.

timeout      Task exceeded wall-clock limit (concurrent.futures.TimeoutError).
             Retry action: increase ``--timeout`` or route to isolated worker pool.

exception    All other Python exceptions (parsing errors, assertion failures, …).
             Retry action: inspect traceback; may be data-specific.
"""

import logging
from concurrent.futures import TimeoutError as FuturesTimeoutError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pattern tables
# ---------------------------------------------------------------------------

# Substrings matched (lowercased) in the exception message to detect CUDA errors.
_CUDA_ERROR_PATTERNS: tuple[str, ...] = (
    "cuda error",
    "cudnn error",
    "device-side assertion",
    "launch failure",
    "illegal memory access",
    "unspecified launch failure",
    "cudaerrornoinit",
    "cudaerror",
)

# Substrings matched to distinguish CUDA OOM from other CUDA errors.
_CUDA_OOM_PATTERNS: tuple[str, ...] = (
    "cuda out of memory",
    "out of memory",          # torch OOM message also contains "cuda"
)

# Substrings matched for system (CPU/RAM) OOM.
_CPU_OOM_PATTERNS: tuple[str, ...] = (
    "cannot allocate memory",
    "memoryerror",
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify_worker_exception(exc: BaseException) -> str:
    """Return a canonical error-type string for a worker exception.

    Args:
        exc: The exception raised by the worker function or caught by
            ``ParallelProcessor._process_parallel``.

    Returns:
        One of: ``"cuda_error"``, ``"cuda_oom"``, ``"cpu_oom"``,
        ``"timeout"``, ``"exception"``.

    Examples::

        classify_worker_exception(TimeoutError())          # "timeout"
        classify_worker_exception(RuntimeError(
            "CUDA error: unspecified launch failure"))      # "cuda_error"
        classify_worker_exception(torch.cuda.OutOfMemoryError(
            "CUDA out of memory"))                         # "cuda_oom"
        classify_worker_exception(MemoryError())           # "cpu_oom"
        classify_worker_exception(ValueError("bad input")) # "exception"
    """
    if isinstance(exc, FuturesTimeoutError):
        return "timeout"

    msg = str(exc).lower()
    type_name = type(exc).__name__.lower()

    # --- CUDA OOM (must be checked before generic CUDA) ---
    if ("cuda" in msg or "cuda" in type_name) and any(p in msg for p in _CUDA_OOM_PATTERNS):
        return "cuda_oom"

    # --- CUDA kernel / context errors ---
    if any(p in msg for p in _CUDA_ERROR_PATTERNS) or "cuda" in type_name:
        return "cuda_error"

    # --- CPU / system OOM ---
    if isinstance(exc, MemoryError) or any(p in msg for p in _CPU_OOM_PATTERNS):
        return "cpu_oom"

    return "exception"


def is_cuda_error(exc: BaseException) -> bool:
    """Return True if the exception is any kind of CUDA error (kernel or OOM)."""
    return classify_worker_exception(exc) in ("cuda_error", "cuda_oom")


def is_fatal_for_worker(error_type: str) -> bool:
    """Return True for error types that leave the worker GPU context corrupted.

    After a fatal-for-worker error the worker's GPU state is unrecoverable
    without process restart.  This is used by ``worker_pool.mark_worker_gpu_failed()``
    to prevent subsequent tasks from attempting GPU operations.

    Args:
        error_type: Value returned by ``classify_worker_exception()``.

    Returns:
        True for ``"cuda_error"`` (context corruption).
        False for ``"cuda_oom"`` (context is intact; clearing cache may help).
    """
    return error_type == "cuda_error"


RETRY_GUIDANCE: dict[str, str] = {
    "cuda_error": (
        "CUDA context corrupted in worker process. "
        "Retry with --no-sentiment to use CPU-only sentiment, "
        "or set CUDA_LAUNCH_BLOCKING=1 for a detailed stack trace."
    ),
    "cuda_oom":  (
        "CUDA out-of-memory. "
        "Retry with --no-sentiment (CPU mode) or reduce --workers."
    ),
    "cpu_oom":   (
        "System RAM exhausted. "
        "Retry with --workers 1 or reduce --chunk-size."
    ),
    "timeout":   (
        "Task exceeded wall-clock limit. "
        "Retry with --timeout <higher> or route to isolated worker pool."
    ),
    "exception": (
        "Unhandled Python exception. "
        "Inspect the DLQ entry for a full traceback."
    ),
}

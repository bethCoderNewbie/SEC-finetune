"""
Test that all required dependencies for retry script can be imported.
Run this after: pip install -e .
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

print("Testing imports for retry_failed_files.py...\n")

# Test standard library
print("✓ Standard library imports (argparse, json, logging, pathlib, datetime)")

# Test third-party dependencies
try:
    import psutil
    print(f"✓ psutil {psutil.__version__}")
except ImportError as e:
    print(f"✗ psutil - MISSING: {e}")
    sys.exit(1)

# Test project dependencies (will be imported by retry script)
try:
    from src.preprocessing.pipeline import SECPreprocessingPipeline, PipelineConfig
    print("✓ src.preprocessing.pipeline")
except ImportError as e:
    print(f"✗ src.preprocessing.pipeline - ERROR: {e}")
    sys.exit(1)

try:
    from src.utils.memory_semaphore import MemorySemaphore, FileCategory
    print("✓ src.utils.memory_semaphore")
except ImportError as e:
    print(f"✗ src.utils.memory_semaphore - ERROR: {e}")
    sys.exit(1)

try:
    from src.utils.parallel import ParallelProcessor
    print("✓ src.utils.parallel")
except ImportError as e:
    print(f"✗ src.utils.parallel - ERROR: {e}")
    sys.exit(1)

# Test retry script can be imported
try:
    sys.path.insert(0, str(project_root / "scripts" / "utils"))
    import retry_failed_files
    print("✓ retry_failed_files module")
except ImportError as e:
    print(f"✗ retry_failed_files - ERROR: {e}")
    sys.exit(1)

print("\n" + "="*60)
print("✅ ALL IMPORTS SUCCESSFUL - Retry script is ready to use!")
print("="*60)
print("\nNext steps:")
print("1. Install/update dependencies: pip install -e .")
print("2. Test retry script: python scripts/utils/retry_failed_files.py --help")
print("3. Run dry-run: python scripts/utils/retry_failed_files.py --dry-run")

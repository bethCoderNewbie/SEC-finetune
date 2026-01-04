"""
Example demonstrating the ProgressLogger utility for real-time batch processing monitoring.

This example shows how to use the ProgressLogger and BatchProgressLogger utilities
to provide real-time visibility into long-running batch operations.

Usage:
    # Basic demo
    python examples/05_progress_logging_demo.py

    # Monitor progress in real-time (PowerShell)
    Get-Content data/interim/_demo_progress.log -Wait

    # Monitor progress in real-time (Git Bash)
    tail -f data/interim/_demo_progress.log
"""

import time
from pathlib import Path
from src.utils.progress_logger import ProgressLogger, BatchProgressLogger, create_progress_logger


def demo_basic_progress_logger():
    """Demonstrate basic ProgressLogger usage."""
    print("\n=== Demo 1: Basic ProgressLogger ===")

    # Create output directory
    output_dir = Path("data/interim")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize logger with context manager (recommended)
    with ProgressLogger(output_dir / "_demo_progress.log", console=True) as logger:
        logger.section("Basic Progress Logger Demo")

        # Log various message types
        logger.log("Starting demo processing...")
        time.sleep(0.5)

        logger.log("Processing step 1 of 3")
        time.sleep(0.5)

        logger.warning("Step 2 encountered a minor issue, but continuing")
        time.sleep(0.5)

        logger.success("Step 3 completed successfully")

        # Progress updates (overwrites in console)
        logger.log("\nSimulating progress updates:")
        for i in range(1, 11):
            logger.progress(f"Progress: {i}/10 items processed")
            time.sleep(0.2)

        logger.log("\nAll progress updates complete!")

    print("\n[OK] Basic demo complete. Check data/interim/_demo_progress.log")


def demo_batch_progress_logger():
    """Demonstrate BatchProgressLogger for batch processing."""
    print("\n=== Demo 2: BatchProgressLogger ===")

    # Create output directory
    output_dir = Path("data/interim")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Simulate batch processing
    items = [f"file_{i:03d}.html" for i in range(1, 21)]

    with BatchProgressLogger(
        log_path=output_dir / "_demo_batch_progress.log",
        total_items=len(items),
        console=True
    ) as logger:
        for item in items:
            # Simulate processing
            logger.log_item_start(item)
            time.sleep(0.1)

            # Simulate different outcomes
            if "05" in item or "15" in item:
                # Simulate warning
                logger.log_item_warning(item, "Section not found, using default")
            elif "10" in item:
                # Simulate error
                logger.log_item_error(item, "Invalid format detected")
            else:
                # Simulate success
                logger.log_item_success(item, "Parsed 42 elements in 0.3s")

            # Update progress every few items
            if logger.current_item % 5 == 0:
                logger.update_progress()

        # Log final summary
        logger.log_summary()

    print("\n[OK] Batch demo complete. Check data/interim/_demo_batch_progress.log")


def demo_quiet_mode():
    """Demonstrate quiet mode (log only, no console output)."""
    print("\n=== Demo 3: Quiet Mode (Log File Only) ===")

    # Create output directory
    output_dir = Path("data/interim")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize logger in quiet mode (console=False)
    with ProgressLogger(
        output_dir / "_demo_quiet_progress.log",
        console=False  # No console output
    ) as logger:
        logger.section("Quiet Mode Demo")
        logger.log("This message only goes to the log file, not console")
        logger.log("Perfect for automated scripts or background processing")

        for i in range(5):
            logger.progress(f"Background progress: {i+1}/5")
            time.sleep(0.2)

        logger.success("Quiet processing complete")

    print("[OK] Quiet demo complete. All output in data/interim/_demo_quiet_progress.log")
    print("  (Nothing was printed to console during processing)")


def demo_convenience_function():
    """Demonstrate the convenience function for quick setup."""
    print("\n=== Demo 4: Convenience Function ===")

    # Create logger using convenience function
    logger = create_progress_logger(
        output_dir="data/interim",
        log_filename="_demo_convenience.log"
    )

    logger.section("Convenience Function Demo")
    logger.log("Created using create_progress_logger() helper")
    logger.log("Perfect for quick one-liners in scripts")

    # Simulate some work
    for i in range(3):
        logger.log(f"Processing item {i+1}")
        time.sleep(0.2)

    logger.success("Demo complete")
    logger.close()

    print("\n[OK] Convenience demo complete. Check data/interim/_demo_convenience.log")


def demo_real_world_integration():
    """Demonstrate integration pattern for real batch scripts."""
    print("\n=== Demo 5: Real-World Integration Pattern ===")

    output_dir = Path("data/interim")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Simulate a real batch processing script
    files = [f"SEC_FILING_{i:03d}.html" for i in range(1, 16)]
    quiet = False  # Could come from argparse

    with BatchProgressLogger(
        log_path=output_dir / "_demo_integration.log",
        total_items=len(files),
        console=not quiet,
        quiet=quiet
    ) as logger:
        logger.log(f"Starting batch processing of {len(files)} files")
        logger.log(f"Output directory: {output_dir}")

        success_count = 0
        error_count = 0

        for file in files:
            logger.log_item_start(file)

            try:
                # Simulate file processing
                time.sleep(0.1)

                # Simulate occasional errors
                if "007" in file:
                    raise ValueError("Malformed HTML structure")

                # Simulate success
                logger.log_item_success(file, "42 segments extracted")
                success_count += 1

            except Exception as e:
                logger.log_item_error(file, str(e))
                error_count += 1

            # Update progress periodically
            if logger.current_item % 3 == 0:
                logger.update_progress()

        # Final summary
        logger.log_summary()
        logger.log(f"\nFinal counts: {success_count} successful, {error_count} failed")

    print("\n[OK] Integration demo complete. Check data/interim/_demo_integration.log")


if __name__ == "__main__":
    print("=" * 80)
    print("Progress Logger Demonstration")
    print("=" * 80)
    print("\nThis demo shows how to use ProgressLogger for real-time monitoring")
    print("of batch processing scripts.\n")
    print("TIP: In another terminal, monitor logs in real-time:")
    print("  PowerShell: Get-Content data/interim/_demo_*.log -Wait")
    print("  Git Bash:   tail -f data/interim/_demo_*.log")
    print("=" * 80)

    # Run all demos
    demo_basic_progress_logger()
    demo_batch_progress_logger()
    demo_quiet_mode()
    demo_convenience_function()
    demo_real_world_integration()

    print("\n" + "=" * 80)
    print("All demos complete!")
    print("=" * 80)
    print("\nLog files created in data/interim/:")
    log_dir = Path("data/interim")
    for log_file in sorted(log_dir.glob("_demo_*.log")):
        print(f"  - {log_file.name}")
    print("\nYou can review these files to see the logged output.")
    print("=" * 80)

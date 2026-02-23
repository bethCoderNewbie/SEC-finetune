"""
CLI entry point for the SEC preprocessing pipeline.

Output layout:
    data/processed/
    ├── .manifest.json                         # StateManifest: cross-run hash tracking
    └── {YYYYMMDD_HHMMSS}_preprocessing_{git_sha}/
        ├── _progress.log                      # ProgressLogger output (batch mode)
        ├── RUN_REPORT.md                      # MarkdownReportGenerator report (batch mode)
        ├── batch_summary_{run_id}_....json    # JSON summary (batch mode)
        └── {stem}_segmented_risks.json        # Per-filing output

Usage:
    # Single file (positional — backward compatible)
    python -m src.preprocessing data/raw/AAPL_10K_2025.html
    python -m src.preprocessing data/raw/AAPL_10K_2025.html 10-Q

    # Single file (flag-based)
    python -m src.preprocessing --input data/raw/AAPL_10K_2025.html
    python -m src.preprocessing --input data/raw/AAPL_10K_2025.html --form-type 10-Q
    python -m src.preprocessing --input data/raw/AFL_10K_2025.html --resume

    # Batch mode
    python -m src.preprocessing --batch
    python -m src.preprocessing --batch --workers 4
    python -m src.preprocessing --batch --resume
    python -m src.preprocessing --batch --quiet
"""

import argparse
import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Optional

from .pipeline import SECPreprocessingPipeline
from src.config import settings, ensure_directories
from src.utils.metadata import RunMetadata
from src.utils.naming import parse_run_dir_metadata, format_output_filename
from src.utils.progress_logger import ProgressLogger
from src.utils.reporting import MarkdownReportGenerator
from src.utils.state_manager import StateManifest

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-file worker
# ---------------------------------------------------------------------------

def _process_one(file_path: Path, form_type: str, run_dir: Path) -> dict:
    """Process one filing, save all outputs (parsed, extracted, segmented) to run_dir."""
    start = time.time()
    out_path = run_dir / f"{file_path.stem}_segmented_risks.json"
    try:
        result = SECPreprocessingPipeline().process_risk_factors(
            file_path,
            form_type=form_type,
            save_output=out_path,
            overwrite=True,
            intermediates_dir=run_dir,
        )
        elapsed = time.time() - start
        if result:
            return {
                'status': 'success',
                'file': file_path.name,
                'input_path': str(file_path),
                'output_path': str(out_path),
                'num_segments': len(result),
                'company': result.company_name,
                'fiscal_year': result.fiscal_year,
                'sic_code': result.sic_code,
                'elapsed_time': elapsed,
            }
        return {
            'status': 'warning',
            'file': file_path.name,
            'input_path': str(file_path),
            'error': 'No risk factors found',
            'elapsed_time': elapsed,
        }
    except Exception as exc:
        return {
            'status': 'error',
            'file': file_path.name,
            'input_path': str(file_path),
            'error': str(exc),
            'elapsed_time': time.time() - start,
        }


# ---------------------------------------------------------------------------
# Single-file mode
# ---------------------------------------------------------------------------

def _run_single(
    input_file: Path,
    form_type: str,
    run_dir: Path,
    manifest: StateManifest,
    run_id: str,
    resume: bool,
    quiet: bool,
) -> None:
    """Process a single file with full run-awareness."""
    if resume and not manifest.should_process(input_file):
        print(f"Resume mode: {input_file.name} unchanged since last run. Skipping.")
        return

    out_path = run_dir / f"{input_file.stem}_segmented_risks.json"
    if not quiet:
        print(f"Processing: {input_file.name}")
        print(f"Run dir:    {run_dir}")

    start = time.time()
    try:
        result = SECPreprocessingPipeline().process_risk_factors(
            input_file,
            form_type=form_type,
            save_output=out_path,
            overwrite=True,
            intermediates_dir=run_dir,
        )
        elapsed = time.time() - start

        if result:
            manifest.record_success(
                input_path=input_file,
                output_path=out_path,
                run_id=run_id,
            )
            manifest.save()
            if not quiet:
                print(f"\n{'=' * 50}")
                print(f"Company:     {result.company_name}")
                print(f"CIK:         {result.cik}")
                print(f"SIC Code:    {result.sic_code}")
                print(f"SIC Name:    {result.sic_name}")
                print(f"Form Type:   {result.form_type}")
                print(f"Fiscal Year: {result.fiscal_year}")
                print(f"Segments:    {len(result)}")
                print(f"Output:      {out_path}")
                print(f"Elapsed:     {elapsed:.1f}s")
                print(f"\nFirst 3 segments:")
                for seg in result.segments[:3]:
                    preview = seg.text[:150].replace('\n', ' ')
                    print(f"  [{seg.chunk_id}] ({seg.parent_subsection or 'intro'}) {preview}...")
        else:
            manifest.record_failure(
                input_path=input_file,
                run_id=run_id,
                reason="No risk factors found",
            )
            manifest.save()
            print("No risk factors found in filing.")

    except Exception as exc:
        manifest.record_failure(input_path=input_file, run_id=run_id, reason=str(exc))
        manifest.save()
        logger.error("Failed to process %s: %s", input_file.name, exc)
        raise


# ---------------------------------------------------------------------------
# Batch mode
# ---------------------------------------------------------------------------

def _run_batch(
    args: argparse.Namespace,
    run_dir: Path,
    run_meta: dict,
    run_id: str,
    git_sha: str,
    manifest: StateManifest,
) -> None:
    """Process all HTML files with progress logging and run reporting."""
    html_files = sorted(settings.paths.raw_data_dir.glob("*.html"))
    if not html_files:
        print(f"No HTML files found in {settings.paths.raw_data_dir}")
        return

    if args.resume:
        html_files = [f for f in html_files if manifest.should_process(f)]
        if not html_files:
            print("All files unchanged since last run. Nothing to do.")
            return

    total = len(html_files)
    form_type = args.form_type
    max_workers = args.workers or 1

    progress_log_path = run_dir / "_progress.log"
    progress_logger = ProgressLogger(
        log_path=progress_log_path,
        console=not args.quiet,
        quiet=args.quiet,
    )

    if not args.quiet:
        print(f"\nBatch Processing: {total} files")
        print(f"Max workers: {max_workers}")
        print(f"Run directory: {run_dir}")
        print(f"Progress log:  {progress_log_path}")
        print("=" * 80)

    progress_logger.section(f"Batch Pipeline: {total} files")

    start_iso = datetime.now().isoformat()
    start_time = time.time()
    successful = 0
    failed = 0
    warning_count = 0
    all_results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_process_one, f, form_type, run_dir): f
            for f in html_files
        }
        for idx, future in enumerate(as_completed(futures), 1):
            result = future.result()
            all_results.append(result)
            status = result.get('status', 'unknown')

            if status == 'success':
                successful += 1
                manifest.record_success(
                    input_path=Path(result['input_path']),
                    output_path=Path(result['output_path']),
                    run_id=run_id,
                )
                progress_logger.log(
                    f"[{idx}/{total}] OK: {result['file']}"
                    f" -> {result.get('num_segments', 0)} segs, {result['elapsed_time']:.1f}s"
                )
            elif status == 'warning':
                warning_count += 1
                manifest.record_failure(
                    input_path=Path(result['input_path']),
                    run_id=run_id,
                    reason=result.get('error', ''),
                )
                progress_logger.warning(
                    f"[{idx}/{total}] WARN: {result['file']} - {result.get('error', '')}"
                )
            else:
                failed += 1
                manifest.record_failure(
                    input_path=Path(result['input_path']),
                    run_id=run_id,
                    reason=result.get('error', ''),
                )
                progress_logger.error(
                    f"[{idx}/{total}] FAIL: {result['file']} - {result.get('error', '')}"
                )

    total_time = time.time() - start_time
    end_iso = datetime.now().isoformat()

    manifest.prune_deleted_files(settings.paths.raw_data_dir)
    manifest.save()

    progress_logger.section("Batch Complete", char="=")
    progress_logger.log(f"Successful: {successful}", timestamp=False)
    if warning_count:
        progress_logger.log(f"Warnings: {warning_count}", timestamp=False)
    progress_logger.log(f"Failed: {failed}", timestamp=False)
    progress_logger.log(f"Total time: {total_time:.1f}s", timestamp=False)
    progress_logger.close()

    # MarkdownReportGenerator
    generator = MarkdownReportGenerator()
    report_md = generator.generate_run_report(
        run_id=run_id,
        run_name="preprocessing",
        metrics={
            'total_files': total,
            'successful': successful,
            'failed_or_skipped': failed + warning_count,
            'quarantined': failed,
            'form_type': form_type,
            'run_id': run_id,
        },
        output_dir=run_dir,
        manifest_stats=manifest.get_statistics(),
        failed_files=manifest.get_failed_files(),
        git_sha=git_sha,
        config_snapshot=run_meta,
        start_time=start_iso,
        end_time=end_iso,
    )
    (run_dir / "RUN_REPORT.md").write_text(report_md)

    # batch_summary JSON (naming.py convention)
    run_dir_meta = parse_run_dir_metadata(run_dir)
    summary_name = format_output_filename("batch_summary", run_dir_meta)
    summary_path = run_dir / summary_name
    with open(summary_path, 'w', encoding='utf-8') as fh:
        json.dump({
            'version': '1.0',
            'run_id': run_id,
            'git_sha': git_sha,
            'total_files': total,
            'successful': successful,
            'warnings': warning_count,
            'failed': failed,
            'run_dir': str(run_dir),
            'manifest': str(settings.paths.processed_data_dir / '.manifest.json'),
            'results': all_results,
        }, fh, indent=2)

    if not args.quiet:
        print("\n" + "=" * 80)
        print("Batch Complete!")
        print(f"  Successful: {successful}")
        if warning_count:
            print(f"  Warnings:   {warning_count}")
        print(f"  Failed:     {failed}")
        print(f"  Total time: {total_time:.1f}s")
        print(f"\nRun directory: {run_dir}")
        print(f"Run report:    {run_dir / 'RUN_REPORT.md'}")
        print(f"Summary JSON:  {summary_path}")
        print(f"Manifest:      {run_dir.parent / '.manifest.json'}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description="SEC preprocessing pipeline: Parse -> Extract -> Clean -> Segment"
    )
    # Positional args for backward compatibility:
    #   python -m src.preprocessing data/raw/AAPL_10K_2025.html [10-K]
    ap.add_argument('file', nargs='?', help='Input HTML file (positional)')
    ap.add_argument('form_type_pos', nargs='?', help=argparse.SUPPRESS)

    # Flag-based args (preferred):
    ap.add_argument('--input', type=str, help='Input HTML file path (single file mode)')
    ap.add_argument('--batch', action='store_true', help='Process all HTML files in RAW_DATA_DIR')
    ap.add_argument('--form-type', type=str, default='10-K', dest='form_type',
                    help='SEC form type (default: 10-K)')
    ap.add_argument('--workers', type=int, default=None,
                    help='Concurrent workers for batch mode (default: 1)')
    ap.add_argument('--resume', action='store_true',
                    help='Skip files unchanged since last successful run')
    ap.add_argument('--quiet', action='store_true', help='Minimize console output')
    ap.add_argument('--output-dir', type=str, default=None, dest='output_dir',
                    help='Base output directory (default: data/processed). '
                         'Use "interim" for data/interim, or any absolute/relative path.')
    args = ap.parse_args()

    ensure_directories()

    # Resolve output base directory
    if args.output_dir == 'interim':
        output_base = settings.paths.interim_data_dir
    elif args.output_dir:
        output_base = Path(args.output_dir)
    else:
        output_base = settings.paths.processed_data_dir
    output_base.mkdir(parents=True, exist_ok=True)

    # RunMetadata + stamped run directory
    run_meta = RunMetadata.gather()
    run_id = datetime.fromisoformat(run_meta["timestamp"]).strftime("%Y%m%d_%H%M%S")
    git_sha = run_meta["git_commit"]
    run_dir = output_base / f"{run_id}_preprocessing_{git_sha}"
    run_dir.mkdir(parents=True, exist_ok=True)

    # StateManifest: cross-run hash tracking (.manifest.json lives in output_base)
    manifest = StateManifest(output_base / ".manifest.json")
    manifest.load()
    manifest.update_run_config(run_meta)

    if args.batch:
        _run_batch(args, run_dir, run_meta, run_id, git_sha, manifest)
    else:
        # Resolve input: --input flag > positional file arg
        input_str = args.input or args.file
        # Legacy positional form_type: python -m src.preprocessing file.html 10-Q
        form_type = args.form_type_pos or args.form_type

        if not input_str:
            ap.print_help()
            sys.exit(0)

        _run_single(
            Path(input_str),
            form_type,
            run_dir,
            manifest,
            run_id,
            args.resume,
            args.quiet,
        )


if __name__ == '__main__':
    main()

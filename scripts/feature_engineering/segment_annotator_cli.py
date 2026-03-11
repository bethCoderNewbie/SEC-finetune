#!/usr/bin/env python3
"""
segment_annotator_cli.py — annotate *_segmented.json files in a preprocessing
run directory and write a flat JSONL file matching the PRD-002 §8 Phase 2 schema.

All numeric defaults are read from configs/features/annotation.yaml (US-007).
Override via SEC_ANNOTATION__* environment variables or explicit CLI flags.

Default section policy (per revised OQ-6):
  Included:      part1item1a, part2item7a, part1item1c
  Opt-in:        part2item7 (requires --part2item7-subsections)
                 part1item1 (use --include-sections to add)
  Hard-excluded: part1item1b, part2item8 (rejected if passed)

Examples:
    # Default (part1item1a + part2item7a + part1item1c)
    python scripts/feature_engineering/segment_annotator_cli.py \\
        --run-dir data/processed/20260303_160207_preprocessing_3bc89d7 \\
        --output data/processed/annotation/labeled.jsonl

    # With selective part2item7 (high-signal MD&A subsections only)
    python scripts/feature_engineering/segment_annotator_cli.py \\
        --run-dir data/processed/20260303_160207_preprocessing_3bc89d7 \\
        --output data/processed/annotation/labeled.jsonl \\
        --include-sections part1item1a part2item7a part1item1c part2item7 \\
        --part2item7-subsections "Liquidity and Capital Resources" \\
                                  "Critical Accounting Estimates"
"""

import argparse
import logging
import sys
from pathlib import Path

from src.config import settings

logger = logging.getLogger(__name__)

_HARD_EXCLUDED = {"part1item1b", "part2item8"}


def _build_parser() -> argparse.ArgumentParser:
    cfg = settings.annotation
    p = argparse.ArgumentParser(
        description="Annotate SegmentedRisks JSON files and write labeled JSONL.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--run-dir",
        required=True,
        type=Path,
        metavar="PATH",
        help="Stamped preprocessing run directory containing *_segmented.json files.",
    )
    p.add_argument(
        "--output",
        required=True,
        type=Path,
        metavar="PATH",
        help="Output JSONL file path.",
    )
    p.add_argument(
        "--include-sections",
        nargs="+",
        default=list(cfg.section_include),
        metavar="SECTION_ID",
        help=(
            f"Section identifiers to annotate. "
            f"Default: {list(cfg.section_include)}. "
            f"Hard-excluded: {sorted(_HARD_EXCLUDED)}."
        ),
    )
    p.add_argument(
        "--part2item7-subsections",
        nargs="+",
        default=None,
        metavar="HEADING",
        help=(
            "When part2item7 is in --include-sections, only retain chunks whose "
            "ancestors[-1] matches one of these heading names. "
            "Required if part2item7 is included (prevents MD&A boilerplate contamination)."
        ),
    )
    p.add_argument(
        "--confidence-threshold",
        type=float,
        default=cfg.confidence_threshold,
        metavar="FLOAT",
        help=f"Default NLI confidence threshold (default: {cfg.confidence_threshold}).",
    )
    p.add_argument(
        "--binary-gate-threshold",
        type=float,
        default=cfg.binary_gate_threshold,
        metavar="FLOAT",
        help=(
            f"Binary risk-relevance gate threshold for part1item1/part2item7 "
            f"(default: {cfg.binary_gate_threshold})."
        ),
    )
    p.add_argument(
        "--merge-lo",
        type=int,
        default=cfg.merge_lo,
        metavar="INT",
        help=f"Ancestor-merge lower bound in words (default: {cfg.merge_lo}).",
    )
    p.add_argument(
        "--merge-hi",
        type=int,
        default=cfg.merge_hi,
        metavar="INT",
        help=f"Ancestor-merge hard ceiling in words (default: {cfg.merge_hi}).",
    )
    p.add_argument(
        "--device",
        type=int,
        default=cfg.device,
        metavar="INT",
        help=f"Inference device: -1=CPU, 0+=GPU index (default: {cfg.device}).",
    )
    p.add_argument(
        "--model",
        default=cfg.model_name,
        metavar="MODEL_NAME",
        help=f"HuggingFace zero-shot-classification model (default: {cfg.model_name}).",
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        help="Enable DEBUG logging.",
    )
    return p


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Validate run-dir
    run_dir: Path = args.run_dir
    if not run_dir.exists():
        logger.error("--run-dir does not exist: %s", run_dir)
        return 1
    if not any(run_dir.glob("*_segmented.json")):
        logger.error("No *_segmented.json files found in %s", run_dir)
        return 1

    # Validate section selection
    section_include: list = args.include_sections
    hard_hit = set(section_include) & _HARD_EXCLUDED
    if hard_hit:
        logger.error(
            "Sections %s are hard-excluded and cannot be annotated. "
            "Remove them from --include-sections.",
            sorted(hard_hit),
        )
        return 1

    if "part2item7" in section_include and args.part2item7_subsections is None:
        logger.warning(
            "part2item7 is included without --part2item7-subsections. "
            "This includes all MD&A chunks and may degrade annotation quality. "
            "Consider filtering to high-signal subsections (e.g. "
            "'Liquidity and Capital Resources' 'Critical Accounting Estimates')."
        )

    # Lazy import to avoid loading torch before arg validation
    from src.analysis.segment_annotator import SegmentAnnotator  # noqa: PLC0415

    annotator = SegmentAnnotator(
        model_name=args.model,
        confidence_threshold=args.confidence_threshold,
        binary_gate_threshold=args.binary_gate_threshold,
        merge_lo=args.merge_lo,
        merge_hi=args.merge_hi,
        device=args.device,
    )

    output_path: Path = args.output
    logger.info(
        "Annotating %s → %s (sections: %s)",
        run_dir, output_path, section_include,
    )

    total = annotator.annotate_run_dir(
        run_dir=run_dir,
        output_path=output_path,
        section_include=section_include,
        part2item7_subsection_filter=args.part2item7_subsections,
    )

    print(f"Done: {total:,} records written to {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

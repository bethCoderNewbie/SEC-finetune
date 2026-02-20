#!/usr/bin/env python
"""
Corpus quality audit — pre-fix diagnostic baseline.

Reads all *_segmented_risks.json files in a run directory and measures the
current scale of 7 known data quality issues. No data is modified.

Usage:
    python scripts/validation/data_quality/check_corpus_quality_audit.py \\
        --run-dir data/processed/<run_dir> [--output audit_report.md]

Exit Codes:
    0 - All critical checks below 1% threshold
    1 - Check A (ToC contamination) or Check B (zero segments) exceed 1%
"""

import argparse
import hashlib
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, NamedTuple, Tuple

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.preprocessing.models.segmentation import SegmentedRisks

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TOC_PATTERN = re.compile(r'\.{3,}.*\d+\s*$', re.MULTILINE)
NUMERIC_TOKEN = re.compile(r'^\d[\d,.\-/]*$')
MODAL_VERBS = {"may", "could", "might"}
RISK_KEYWORDS = {"risk", "adverse", "material", "uncertain", "may", "could", "might", "potential"}
DOMAIN_KEYWORDS = RISK_KEYWORDS - MODAL_VERBS  # stronger signal, non-modal

CRITICAL_THRESHOLD = 0.01  # 1%


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class CheckResult(NamedTuple):
    name: str
    severity: str
    affected_count: int
    total_count: int
    rate: float
    top_offenders: List[Tuple[str, int]]  # (filing_id, count)
    fix_ref: str
    detail: str = ""


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_a_toc_lines(filings: List[SegmentedRisks]) -> CheckResult:
    """Check A: Segments containing ToC dot-leader lines."""
    affected_segments = 0
    total_segments = 0
    offenders: Dict[str, int] = defaultdict(int)

    for filing in filings:
        fid = _filing_id(filing)
        for seg in filing.segments:
            total_segments += 1
            if TOC_PATTERN.search(seg.text):
                affected_segments += 1
                offenders[fid] += 1

    rate = affected_segments / max(total_segments, 1)
    top3 = sorted(offenders.items(), key=lambda x: -x[1])[:3]
    return CheckResult(
        name="A — ToC line contamination",
        severity="Critical",
        affected_count=affected_segments,
        total_count=total_segments,
        rate=rate,
        top_offenders=top3,
        fix_ref="Fix 2A (ToC node filter in extractor)",
    )


def check_b_zero_segments(filings: List[SegmentedRisks]) -> CheckResult:
    """Check B: Filings with zero segments extracted."""
    zero_filings = [f for f in filings if f.total_segments == 0]
    rate = len(zero_filings) / max(len(filings), 1)
    top3 = [(_filing_id(f), 0) for f in zero_filings[:3]]
    return CheckResult(
        name="B — Zero-segment filings",
        severity="Critical",
        affected_count=len(zero_filings),
        total_count=len(filings),
        rate=rate,
        top_offenders=top3,
        fix_ref="Fix 4A (zero segments = FAIL)",
    )


def check_c_numeric_runs(filings: List[SegmentedRisks]) -> CheckResult:
    """Check C: Segments with 4+ consecutive numeric tokens (table noise)."""
    affected_segments = 0
    total_segments = 0
    offenders: Dict[str, int] = defaultdict(int)

    for filing in filings:
        fid = _filing_id(filing)
        for seg in filing.segments:
            total_segments += 1
            tokens = seg.text.split()
            run = 0
            found = False
            for tok in tokens:
                if NUMERIC_TOKEN.match(tok):
                    run += 1
                    if run >= 4:
                        found = True
                        break
                else:
                    run = 0
            if found:
                affected_segments += 1
                offenders[fid] += 1

    rate = affected_segments / max(total_segments, 1)
    top3 = sorted(offenders.items(), key=lambda x: -x[1])[:3]
    return CheckResult(
        name="C — Numeric token runs (4+ consecutive)",
        severity="High",
        affected_count=affected_segments,
        total_count=total_segments,
        rate=rate,
        top_offenders=top3,
        fix_ref="Fix 2B (exclude tables from text)",
    )


def check_d_abbreviation_split(filings: List[SegmentedRisks]) -> CheckResult:
    """Check D: Segments whose first word is ≤3 chars + lowercase (abbreviation split)."""
    affected_segments = 0
    total_segments = 0
    offenders: Dict[str, int] = defaultdict(int)

    for filing in filings:
        fid = _filing_id(filing)
        for seg in filing.segments:
            total_segments += 1
            text = seg.text.strip()
            if not text:
                continue
            tokens = text.split()
            first_word = tokens[0] if tokens else ""
            if first_word and len(first_word) <= 3 and first_word[0].islower():
                affected_segments += 1
                offenders[fid] += 1

    rate = affected_segments / max(total_segments, 1)
    top3 = sorted(offenders.items(), key=lambda x: -x[1])[:3]
    return CheckResult(
        name="D — Abbreviation-split segments (first word ≤3 chars, lowercase)",
        severity="High",
        affected_count=affected_segments,
        total_count=total_segments,
        rate=rate,
        top_offenders=top3,
        fix_ref="Fix 3A (spaCy sentence splitting)",
    )


def check_e_duplicates(filings: List[SegmentedRisks]) -> CheckResult:
    """Check E: SHA-256 segment-level exact duplicates across the corpus."""
    hash_counts: Dict[str, int] = defaultdict(int)
    total_segments = 0
    offenders: Dict[str, int] = defaultdict(int)

    # First pass: count hashes
    seg_hashes: List[Tuple[str, str]] = []  # (filing_id, hash)
    for filing in filings:
        fid = _filing_id(filing)
        for seg in filing.segments:
            total_segments += 1
            normalized = re.sub(r'\s+', ' ', seg.text.lower().strip())
            h = hashlib.sha256(normalized.encode()).hexdigest()
            hash_counts[h] += 1
            seg_hashes.append((fid, h))

    # Second pass: attribute duplicate segments to filings
    dup_segments = 0
    for fid, h in seg_hashes:
        if hash_counts[h] > 1:
            dup_segments += 1
            offenders[fid] += 1

    # dup_segments double-counts (each copy is counted); subtract originals
    dup_excess = sum(count - 1 for count in hash_counts.values() if count > 1)
    rate = dup_excess / max(total_segments, 1)
    top3 = sorted(offenders.items(), key=lambda x: -x[1])[:3]
    return CheckResult(
        name="E — Segment-level exact duplicates",
        severity="High",
        affected_count=dup_excess,
        total_count=total_segments,
        rate=rate,
        top_offenders=top3,
        fix_ref="Fix 4B (segment-level dedup)",
    )


def check_f_modal_only(filings: List[SegmentedRisks]) -> CheckResult:
    """Check F: Filings that pass risk keyword threshold via modal verbs only."""
    affected_filings = 0
    offenders: Dict[str, int] = {}

    for filing in filings:
        fid = _filing_id(filing)
        text = " ".join(seg.text for seg in filing.segments)
        words = re.findall(r'\b\w+\b', text.lower())
        total_hits = sum(1 for w in words if w in RISK_KEYWORDS)
        domain_hits = sum(1 for w in words if w in DOMAIN_KEYWORDS)
        modal_hits = sum(1 for w in words if w in MODAL_VERBS)

        # Passes the >=10 threshold but only via modal verbs (no domain-specific hits)
        if total_hits >= 10 and domain_hits == 0:
            affected_filings += 1
            offenders[fid] = modal_hits

    top3 = sorted(offenders.items(), key=lambda x: -x[1])[:3]
    rate = affected_filings / max(len(filings), 1)
    return CheckResult(
        name="F — Modal-verb-only keyword matches",
        severity="Medium",
        affected_count=affected_filings,
        total_count=len(filings),
        rate=rate,
        top_offenders=top3,
        fix_ref="Fix 4C (strengthen risk keyword set)",
    )


def check_g_yield_delta(filings: List[SegmentedRisks]) -> CheckResult:
    """Check G: yield_ppm_html (current) vs yield_ppm_text (corrected) delta."""
    deltas: List[float] = []
    offenders: Dict[str, int] = {}

    for filing in filings:
        fid = _filing_id(filing)
        file_size_bytes = (
            filing.metadata.get('file_size_bytes') or
            filing.metadata.get('html_size')
        )
        if not file_size_bytes or file_size_bytes <= 0:
            continue

        extracted_chars = sum(seg.char_count for seg in filing.segments)
        if extracted_chars == 0:
            continue

        yield_ppm_html = (extracted_chars / file_size_bytes) * 1_000_000
        # Approximate text-equivalent byte count (SEC HTML ~40% text density)
        approx_text_bytes = max(int(file_size_bytes * 0.4), 1)
        yield_ppm_text = (extracted_chars / approx_text_bytes) * 1_000_000
        delta = yield_ppm_text - yield_ppm_html
        deltas.append(delta)
        offenders[fid] = int(delta)

    if deltas:
        sorted_deltas = sorted(deltas)
        median_delta = sorted_deltas[len(sorted_deltas) // 2]
    else:
        median_delta = 0.0

    # Flag filings where the error is >1000 ppm (materially wrong)
    affected_count = sum(1 for d in deltas if d > 1000)
    top3 = sorted(offenders.items(), key=lambda x: -x[1])[:3]
    rate = affected_count / max(len(filings), 1)
    return CheckResult(
        name="G — yield_ppm denominator error (HTML vs text)",
        severity="Medium",
        affected_count=affected_count,
        total_count=len(filings),
        rate=rate,
        top_offenders=top3,
        fix_ref="Fix 4D (yield_ppm denominator)",
        detail=f"Median delta: {median_delta:,.0f} ppm (text − html)",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _filing_id(filing: SegmentedRisks) -> str:
    parts = [filing.company_name or filing.cik or "unknown"]
    if filing.form_type:
        parts.append(filing.form_type)
    return "_".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------

def render_markdown(results: List[CheckResult], run_dir: Path, n_filings: int) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Corpus Quality Audit",
        "",
        f"**Run dir:** `{run_dir}`  ",
        f"**Generated:** {now}  ",
        f"**Filings scanned:** {n_filings}",
        "",
        "## Summary",
        "",
        "| Check | Severity | Affected | Total | Rate | Critical? |",
        "|-------|----------|----------|-------|------|-----------|",
    ]

    for r in results:
        is_critical = r.severity == "Critical" and r.rate > CRITICAL_THRESHOLD
        flag = "**YES**" if is_critical else "—"
        lines.append(
            f"| {r.name} | {r.severity} | {r.affected_count:,} | {r.total_count:,} "
            f"| {r.rate:.1%} | {flag} |"
        )

    lines += ["", "---", ""]

    for r in results:
        lines += [
            f"## {r.name}",
            "",
            f"**Severity:** {r.severity}  ",
            f"**Affected:** {r.affected_count:,} / {r.total_count:,} ({r.rate:.2%})  ",
            f"**Fix:** {r.fix_ref}",
        ]
        if r.detail:
            lines.append(f"**Note:** {r.detail}")
        if r.top_offenders:
            lines += ["", "**Top 3 offenders:**", ""]
            for fid, count in r.top_offenders:
                lines.append(f"- `{fid}`: {count:,}")
        lines += ["", "---", ""]

    check_a_rate = results[0].rate
    check_b_rate = results[1].rate
    if check_a_rate > CRITICAL_THRESHOLD or check_b_rate > CRITICAL_THRESHOLD:
        lines += [
            "## Exit Status",
            "",
            "> **EXIT 1** — Check A or B exceeded 1% threshold.",
            "",
        ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Corpus quality audit — pre-fix diagnostic baseline."
    )
    parser.add_argument(
        "--run-dir",
        required=True,
        type=Path,
        help="Path to run directory containing *_segmented_risks.json files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write markdown report to this file (default: print to stdout)",
    )
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.exists():
        print(f"ERROR: run-dir does not exist: {run_dir}", file=sys.stderr)
        return 1

    json_files = sorted(run_dir.glob("*_segmented_risks.json"))
    if not json_files:
        print(f"ERROR: No *_segmented_risks.json files found in {run_dir}", file=sys.stderr)
        return 1

    print(f"Loading {len(json_files)} filings from {run_dir}...", file=sys.stderr)
    filings: List[SegmentedRisks] = []
    for path in json_files:
        try:
            filings.append(SegmentedRisks.load_from_json(path))
        except Exception as exc:
            print(f"  WARN: Failed to load {path.name}: {exc}", file=sys.stderr)

    if not filings:
        print("ERROR: All files failed to load.", file=sys.stderr)
        return 1

    print(f"Running 7 checks across {len(filings)} filings...", file=sys.stderr)
    results = [
        check_a_toc_lines(filings),
        check_b_zero_segments(filings),
        check_c_numeric_runs(filings),
        check_d_abbreviation_split(filings),
        check_e_duplicates(filings),
        check_f_modal_only(filings),
        check_g_yield_delta(filings),
    ]

    report = render_markdown(results, run_dir, len(filings))

    if args.output:
        args.output.write_text(report, encoding="utf-8")
        print(f"Report written to: {args.output}", file=sys.stderr)
    else:
        print(report)

    # Exit 1 if check A or B fire above 1%
    if results[0].rate > CRITICAL_THRESHOLD or results[1].rate > CRITICAL_THRESHOLD:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

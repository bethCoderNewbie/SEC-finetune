#!/usr/bin/env python
"""
Segment distribution diagnostic — answers four open questions about the corpus.

Areas investigated:
  A. What types of content produce short (10-19 word) segments?
  B. Token length profile under DeBERTa-v3-base tokenizer.
  C. Zero-shot confidence distribution by word-count bracket.

Usage:
    python scripts/validation/data_quality/check_segment_distribution.py \\
        --run-dir data/processed/<run_dir> [--output report.md]
        [--skip-tokenizer]   # skip DeBERTa token-length profiling (~1 GB download)
        [--skip-zeroshot]    # skip zero-shot confidence sweep (~1.6 GB download)

Exit codes:
    0 — all areas completed (or skipped via flags)
    1 — run-dir missing or no *_segmented.json files found
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Project root
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.preprocessing.constants import PAGE_HEADER_PATTERN, SECTION_PATTERNS
from src.config.qa_validation import HealthCheckValidator

# ---------------------------------------------------------------------------
# Optional heavy imports
# ---------------------------------------------------------------------------

try:
    from transformers import AutoTokenizer, pipeline as hf_pipeline
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SHORT_MIN = 10
SHORT_MAX = 19  # inclusive

LABEL_NAMES = [
    "cybersecurity", "regulatory", "financial", "supply_chain",
    "market", "esg", "macro", "human_capital", "other",
]

# Compiled patterns for Area A heuristics
_CROSS_REF_PAT = re.compile(
    r'(?i)\bsee\b.{0,40}\b(MD&A|item\s*\d|part\s*[IVX])'
    r'|further\s+details?'
    r'|further\s+discussion'
    r'|for\s+additional\s+information',
)

_SECTION_PATS_COMPILED = [
    re.compile(p, re.IGNORECASE)
    for patterns in SECTION_PATTERNS.values()
    for p in patterns
]

_RISK_KEYWORDS = HealthCheckValidator.RISK_KEYWORDS


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_segments(run_dir: Path) -> Tuple[List[Dict[str, Any]], List[Path]]:
    """Load all segments from *_segmented.json files in run_dir.

    Returns (all_segments, file_list).  Each segment dict preserves the
    original JSON fields plus an injected '_source_file' key.
    """
    json_files = sorted(run_dir.glob("*_segmented.json"))
    all_segments: List[Dict[str, Any]] = []
    for path in json_files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"  WARN: Failed to load {path.name}: {exc}", file=sys.stderr)
            continue
        for seg in data.get("segments", data.get("chunks", [])):
            seg["_source_file"] = path.name
            all_segments.append(seg)
    return all_segments, json_files


# ---------------------------------------------------------------------------
# Area A — Short segment content classification
# ---------------------------------------------------------------------------

def _classify_segment(seg: Dict[str, Any]) -> str:
    """Classify a single segment into one of five content types."""
    text = seg.get("text", "")
    words = text.split()

    # 1. cross_reference
    if _CROSS_REF_PAT.search(text):
        return "cross_reference"

    # 2. page_header
    if PAGE_HEADER_PATTERN.search(text):
        return "page_header"

    # 3. section_title_leak
    upper_chars = sum(1 for c in text if c.isupper())
    alpha_chars = sum(1 for c in text if c.isalpha())
    caps_ratio = upper_chars / max(alpha_chars, 1)
    if caps_ratio > 0.4:
        return "section_title_leak"
    if any(p.search(text) for p in _SECTION_PATS_COMPILED):
        return "section_title_leak"

    # 4. genuine_risk
    word_set = {w.lower() for w in words}
    if word_set & _RISK_KEYWORDS:
        return "genuine_risk"

    return "unclassified"


def _null_subsection_rate(segs: List[Dict[str, Any]]) -> float:
    null_count = sum(1 for s in segs if not s.get("parent_subsection"))
    return null_count / max(len(segs), 1)


def area_a(all_segments: List[Dict[str, Any]]) -> str:
    """Area A: classify short (10-19 word) segments by content type."""
    short_segs = [
        s for s in all_segments
        if SHORT_MIN <= s.get("word_count", 0) <= SHORT_MAX
    ]

    if not short_segs:
        return "\n## A. Short Segment Content Classification (10–19 words)\n\n_No segments in range._\n"

    by_type: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for seg in short_segs:
        label = _classify_segment(seg)
        by_type[label].append(seg)

    total = len(short_segs)
    type_order = ["cross_reference", "page_header", "section_title_leak", "genuine_risk", "unclassified"]

    lines = [
        "",
        "## A. Short Segment Content Classification (10–19 words)",
        "",
        f"Total short segments: **{total}** ({total / max(len(all_segments), 1):.1%} of corpus)",
        "",
        "| Type | Count | % of Short | Null Subsection | Example texts (first 120 chars) |",
        "|------|-------|------------|-----------------|----------------------------------|",
    ]

    for label in type_order:
        segs = by_type.get(label, [])
        count = len(segs)
        pct = count / total
        null_rate = _null_subsection_rate(segs)
        examples = "; ".join(
            f'"{s["text"][:120]}"' for s in segs[:3]
        ) if segs else "—"
        lines.append(
            f"| `{label}` | {count} | {pct:.1%} | {null_rate:.1%} | {examples} |"
        )

    lines += [""]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Checkpoint helpers
# ---------------------------------------------------------------------------

def _load_checkpoint(path: Path, total: int) -> Optional[Dict[str, Any]]:
    """Load a checkpoint if it exists and its segment count matches total.

    Returns the checkpoint dict on success, None if missing/stale/corrupt.
    """
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("total_segments") != total:
            print(
                f"  Checkpoint at {path.name} covers {data.get('total_segments'):,} segments "
                f"but corpus has {total:,} — ignoring.",
                file=sys.stderr,
            )
            return None
        return data
    except Exception as exc:
        print(f"  WARN: Could not read checkpoint {path.name}: {exc}", file=sys.stderr)
        return None


def _save_checkpoint(path: Path, data: Dict[str, Any]) -> None:
    """Atomically write checkpoint (tmp-then-rename avoids corrupt files)."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)


# ---------------------------------------------------------------------------
# Area B — Token length profiling
# ---------------------------------------------------------------------------

def area_b(
    all_segments: List[Dict[str, Any]],
    checkpoint_path: Optional[Path] = None,
) -> str:
    """Area B: DeBERTa-v3-base token length profile."""
    if not TRANSFORMERS_AVAILABLE:
        return (
            "\n## B. Token Length Profile (DeBERTa-v3-base)\n\n"
            "_Skipped: `transformers` not installed._\n"
        )

    texts = [s.get("text", "") for s in all_segments]
    word_counts = [s.get("word_count", 0) for s in all_segments]
    total = len(texts)

    # Resume from checkpoint if available
    token_counts: List[int] = []
    resume_from = 0
    if checkpoint_path:
        ckpt = _load_checkpoint(checkpoint_path, total)
        if ckpt:
            token_counts = ckpt["token_counts"]
            resume_from = ckpt["segments_done"]
            print(
                f"  Resuming Area B from checkpoint: {resume_from:,}/{total:,} segments already tokenized.",
                file=sys.stderr,
            )

    print("  Loading microsoft/deberta-v3-base tokenizer...", file=sys.stderr)
    try:
        tokenizer = AutoTokenizer.from_pretrained("microsoft/deberta-v3-base")
    except Exception as exc:
        return (
            "\n## B. Token Length Profile (DeBERTa-v3-base)\n\n"
            f"_Skipped: tokenizer load failed — {exc}_\n"
        )

    print(
        f"  Tokenizing {total - resume_from:,} remaining segments (batch_size=64)...",
        file=sys.stderr,
    )
    interrupted = False
    batch_size = 64
    # Save every 100 batches (6,400 segments) — negligible overhead for the tokenizer
    save_every = 100
    try:
        for i in range(resume_from, total, batch_size):
            batch = texts[i : i + batch_size]
            encoded = tokenizer(
                batch,
                truncation=False,
                add_special_tokens=True,
                return_length=True,
            )
            token_counts.extend(encoded["length"])
            batch_num = (i - resume_from) // batch_size
            if checkpoint_path and batch_num % save_every == 0:
                _save_checkpoint(checkpoint_path, {
                    "total_segments": total,
                    "segments_done": i + len(batch),
                    "token_counts": token_counts,
                })
    except KeyboardInterrupt:
        interrupted = True
        print(
            f"\n  [Interrupted] Partial results: {len(token_counts):,}/{total:,} segments tokenized.",
            file=sys.stderr,
        )
        if checkpoint_path:
            _save_checkpoint(checkpoint_path, {
                "total_segments": total,
                "segments_done": len(token_counts),
                "token_counts": token_counts,
            })
            print(f"  Checkpoint saved → {checkpoint_path.name}", file=sys.stderr)

    if checkpoint_path and not interrupted and checkpoint_path.exists():
        checkpoint_path.unlink()  # clean up on successful completion

    if not token_counts:
        return (
            "\n## B. Token Length Profile (DeBERTa-v3-base)\n\n"
            "_Interrupted before any segments were tokenized._\n"
        )

    sorted_toks = sorted(token_counts)
    n = len(sorted_toks)

    def percentile(p: float) -> int:
        idx = min(int(p / 100 * n), n - 1)
        return sorted_toks[idx]

    p50 = percentile(50)
    p95 = percentile(95)
    p99 = percentile(99)
    p_max = sorted_toks[-1]

    trunc_risk = sum(1 for t in token_counts if 360 <= t <= 512)
    hard_trunc = sum(1 for t in token_counts if t > 512)

    partial_note = (
        f" _(partial: {n:,}/{len(texts):,} segments — interrupted)_"
        if interrupted else ""
    )
    lines = [
        "",
        "## B. Token Length Profile (DeBERTa-v3-base)",
        "",
        f"_n = {n:,} segments{partial_note}_",
        "",
        "| Statistic | Value |",
        "|-----------|-------|",
        f"| p50 | {p50} tokens |",
        f"| p95 | {p95} tokens |",
        f"| p99 | {p99} tokens |",
        f"| max | {p_max} tokens |",
        f"| Truncation risk zone (360–512) | {trunc_risk:,} ({trunc_risk / n:.1%}) |",
        f"| Hard truncation (> 512) | {hard_trunc:,} ({hard_trunc / n:.1%}) |",
    ]

    # Long segment detail: word_count 200–379
    long_segs = [
        (wc, tc)
        for wc, tc in zip(word_counts, token_counts)
        if 200 <= wc <= 379
    ]
    if long_segs:
        lines += [
            "",
            "**200–379 word segments — actual token counts:**",
            "",
            "| words | tokens | tok/word |",
            "|-------|--------|----------|",
        ]
        for wc, tc in sorted(long_segs, key=lambda x: -x[0])[:28]:
            tpw = tc / max(wc, 1)
            lines.append(f"| {wc} | {tc} | {tpw:.2f} |")

    lines += [""]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Area C — Zero-shot confidence by word-count bracket
# ---------------------------------------------------------------------------

_BRACKETS: List[Tuple[str, int, int]] = [
    ("10–19",   10,  19),
    ("20–49",   20,  49),
    ("50–99",   50,  99),
    ("100–199", 100, 199),
    ("200–379", 200, 379),
    ("380+",    380, 10**9),
]


def _bracket(wc: int) -> str:
    for label, lo, hi in _BRACKETS:
        if lo <= wc <= hi:
            return label
    return "other"


def area_c(
    all_segments: List[Dict[str, Any]],
    checkpoint_path: Optional[Path] = None,
) -> str:
    """Area C: zero-shot confidence distribution by word-count bracket."""
    if not TRANSFORMERS_AVAILABLE:
        return (
            "\n## C. Zero-Shot Confidence Distribution by Word-Count Bracket\n\n"
            "_Skipped: `transformers` not installed._\n"
        )

    import torch  # noqa: F401 — availability check

    texts = [s.get("text", "") for s in all_segments]
    word_counts = [s.get("word_count", 0) for s in all_segments]
    total = len(texts)

    # Resume from checkpoint if available
    results_by_bracket: Dict[str, List[Tuple[float, str]]] = defaultdict(list)
    resume_from = 0
    if checkpoint_path:
        ckpt = _load_checkpoint(checkpoint_path, total)
        if ckpt:
            for bracket, pairs in ckpt.get("results_by_bracket", {}).items():
                results_by_bracket[bracket] = [tuple(p) for p in pairs]
            resume_from = ckpt["segments_done"]
            already = sum(len(v) for v in results_by_bracket.values())
            print(
                f"  Resuming Area C from checkpoint: {resume_from:,}/{total:,} segments already classified "
                f"({already:,} results loaded).",
                file=sys.stderr,
            )

    device = 0 if (TRANSFORMERS_AVAILABLE and _cuda_available()) else -1
    device_label = "GPU" if device == 0 else "CPU"
    print(
        f"  Loading facebook/bart-large-mnli ({device_label})...", file=sys.stderr
    )
    try:
        classifier = hf_pipeline(
            "zero-shot-classification",
            model="facebook/bart-large-mnli",
            device=device,
        )
    except Exception as exc:
        return (
            "\n## C. Zero-Shot Confidence Distribution by Word-Count Bracket\n\n"
            f"_Skipped: model load failed — {exc}_\n"
        )

    print(
        f"  Running zero-shot on {total - resume_from:,} remaining segments (batch_size=8)...",
        file=sys.stderr,
    )

    interrupted_c = False
    segments_done = resume_from
    batch_size = 8
    try:
        for i in range(resume_from, total, batch_size):
            batch_texts = texts[i : i + batch_size]
            batch_wcs = word_counts[i : i + batch_size]
            try:
                outputs = classifier(batch_texts, LABEL_NAMES, multi_label=False)
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                print(f"  WARN: batch {i}–{i+batch_size} failed: {exc}", file=sys.stderr)
                continue
            # outputs is a list when batch_texts is a list
            if isinstance(outputs, dict):
                outputs = [outputs]
            for out, wc in zip(outputs, batch_wcs):
                max_idx = out["scores"].index(max(out["scores"]))
                max_conf = out["scores"][max_idx]
                top_label = out["labels"][max_idx]
                bracket_label = _bracket(wc)
                results_by_bracket[bracket_label].append((max_conf, top_label))
            segments_done += len(batch_texts)
            # Save after every batch — GPU inference dominates; file I/O is negligible
            if checkpoint_path:
                _save_checkpoint(checkpoint_path, {
                    "total_segments": total,
                    "segments_done": segments_done,
                    "results_by_bracket": {
                        k: list(v) for k, v in results_by_bracket.items()
                    },
                })
            if (i // batch_size) % 10 == 0:
                print(f"    ... {segments_done:,}/{total:,} done", file=sys.stderr)
    except KeyboardInterrupt:
        interrupted_c = True
        print(
            f"\n  [Interrupted] Partial results: {segments_done:,}/{total:,} segments classified.",
            file=sys.stderr,
        )
        if checkpoint_path:
            print(f"  Checkpoint saved → {checkpoint_path.name}", file=sys.stderr)

    if checkpoint_path and not interrupted_c and checkpoint_path.exists():
        checkpoint_path.unlink()  # clean up on successful completion

    total_classified = sum(len(v) for v in results_by_bracket.values())
    partial_note_c = (
        f" _(partial: {total_classified:,}/{len(texts):,} segments — interrupted)_"
        if interrupted_c else ""
    )
    lines = [
        "",
        "## C. Zero-Shot Confidence Distribution by Word-Count Bracket",
        "",
        f"_Model: `facebook/bart-large-mnli`  QR-03 threshold: 0.70{partial_note_c}_",
        "",
        "| Bracket | n | mean_conf | median_conf | <0.70 (→other) | <0.50 (random) | top_label |",
        "|---------|---|-----------|-------------|----------------|----------------|-----------|",
    ]

    for label, lo, hi in _BRACKETS:
        items = results_by_bracket.get(label, [])
        if not items:
            lines.append(f"| {label} | 0 | — | — | — | — | — |")
            continue
        confs = [c for c, _ in items]
        labels_ = [l for _, l in items]
        n = len(confs)
        mean_c = sum(confs) / n
        sorted_c = sorted(confs)
        median_c = sorted_c[n // 2]
        below_70 = sum(1 for c in confs if c < 0.70) / n
        below_50 = sum(1 for c in confs if c < 0.50) / n
        from collections import Counter
        top_lbl = Counter(labels_).most_common(1)[0][0]
        lines.append(
            f"| {label} | {n} | {mean_c:.3f} | {median_c:.3f} "
            f"| {below_70:.1%} | {below_50:.1%} | {top_lbl} |"
        )

    lines += [""]
    return "\n".join(lines)


def _cuda_available() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------

def render_report(
    run_dir: Path,
    total_segments: int,
    section_a: str,
    section_b: str,
    section_c: str,
) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Segment Distribution Diagnostic",
        "",
        f"**Run dir:** `{run_dir.name}`  ",
        f"**Generated:** {now}  ",
        f"**Total segments:** {total_segments:,}",
        "",
        "---",
        section_a,
        "---",
        section_b,
        "---",
        section_c,
        "---",
        "",
        "## Open Questions Resolved",
        "",
        "| OQ | Question | Status |",
        "|----|----------|--------|",
        "| OQ-1 | Types of content in 10–19 word segments? | See Area A |",
        "| OQ-2 | p50/p95/p99 token length under DeBERTa-v3-base? | See Area B |",
        "| OQ-3 | Segments in 360–512 token truncation risk zone? | See Area B |",
        "| OQ-4 | Zero-shot confidence distribution by word-count bracket? | See Area C |",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Segment distribution diagnostic — four open questions."
    )
    parser.add_argument(
        "--run-dir",
        required=True,
        type=Path,
        help="Path to run directory containing *_segmented.json files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write markdown report to this file (default: print to stdout)",
    )
    parser.add_argument(
        "--skip-tokenizer",
        action="store_true",
        help="Skip DeBERTa-v3-base token length profiling (Area B)",
    )
    parser.add_argument(
        "--skip-zeroshot",
        action="store_true",
        help="Skip facebook/bart-large-mnli zero-shot sweep (Area C)",
    )
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.exists():
        print(f"ERROR: run-dir does not exist: {run_dir}", file=sys.stderr)
        return 1

    json_files = sorted(run_dir.glob("*_segmented.json"))
    if not json_files:
        print(
            f"ERROR: No *_segmented.json files found in {run_dir}", file=sys.stderr
        )
        return 1

    print(
        f"Loading segments from {len(json_files)} files in {run_dir.name}...",
        file=sys.stderr,
    )
    all_segments, _ = load_segments(run_dir)
    if not all_segments:
        print("ERROR: All files failed to load or contained no segments.", file=sys.stderr)
        return 1

    print(f"  {len(all_segments):,} segments loaded.", file=sys.stderr)

    _SKIPPED_B = (
        "\n## B. Token Length Profile (DeBERTa-v3-base)\n\n"
        "_Skipped via --skip-tokenizer flag._\n"
    )
    _SKIPPED_C = (
        "\n## C. Zero-Shot Confidence Distribution by Word-Count Bracket\n\n"
        "_Skipped via --skip-zeroshot flag._\n"
    )
    _INTERRUPTED = "\n\n> **Interrupted by user (Ctrl+C) — partial report below.**\n"

    section_a = section_b = section_c = ""
    try:
        # Area A — always run (no model required)
        print("Running Area A: short segment classification...", file=sys.stderr)
        section_a = area_a(all_segments)

        # Area B — DeBERTa tokenizer
        if args.skip_tokenizer:
            section_b = _SKIPPED_B
        else:
            print("Running Area B: DeBERTa token length profiling...", file=sys.stderr)
            section_b = area_b(
                all_segments,
                checkpoint_path=run_dir / ".seg_dist_b_checkpoint.json",
            )

        # Area C — zero-shot classification
        if args.skip_zeroshot:
            section_c = _SKIPPED_C
        else:
            print("Running Area C: zero-shot confidence sweep...", file=sys.stderr)
            section_c = area_c(
                all_segments,
                checkpoint_path=run_dir / ".seg_dist_c_checkpoint.json",
            )

    except KeyboardInterrupt:
        print("\n[Interrupted] Rendering partial report...", file=sys.stderr)
        # Fill any section that never started
        if not section_a:
            section_a = "\n## A. Short Segment Content Classification (10–19 words)\n\n_Interrupted before this area ran._\n"
        if not section_b:
            section_b = _SKIPPED_B if args.skip_tokenizer else "\n## B. Token Length Profile (DeBERTa-v3-base)\n\n_Interrupted before this area ran._\n"
        if not section_c:
            section_c = _SKIPPED_C if args.skip_zeroshot else "\n## C. Zero-Shot Confidence Distribution by Word-Count Bracket\n\n_Interrupted before this area ran._\n"
        section_a = _INTERRUPTED + section_a

    report = render_report(run_dir, len(all_segments), section_a, section_b, section_c)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
        print(f"Report written to: {args.output}", file=sys.stderr)
    else:
        print(report)

    return 0


if __name__ == "__main__":
    sys.exit(main())

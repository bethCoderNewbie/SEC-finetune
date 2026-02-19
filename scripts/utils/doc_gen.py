#!/usr/bin/env python3
"""
doc_gen.py — Generate structured documentation from skill templates via Claude CLI.

Usage:
  python scripts/utils/doc_gen.py <type> "<description>" [--save] [--slug <slug>]

Types:
  prd     Product Requirements Document  → docs/requirements/PRD-NNN_<slug>.md
  rfc     Request for Comments           → docs/architecture/rfc/RFC-NNN_<slug>.md
  adr     Architecture Decision Record   → docs/architecture/adr/ADR-NNN_<slug>.md
  story   User Story                     → docs/requirements/stories/US-NNN_<slug>.md

Examples:
  python scripts/utils/doc_gen.py prd "Automated daily ingestion from EDGAR"
  python scripts/utils/doc_gen.py rfc "How to integrate classification into the batch pipeline" --save
  python scripts/utils/doc_gen.py adr "Use JSONL as the canonical training output format" --save --slug jsonl_training_output
  python scripts/utils/doc_gen.py story "Pipeline operator can pause a running batch" --save
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"

OUTPUT_DIRS: dict[str, Path] = {
    "prd": REPO_ROOT / "docs" / "requirements",
    "rfc": REPO_ROOT / "docs" / "architecture" / "rfc",
    "adr": REPO_ROOT / "docs" / "architecture" / "adr",
    "story": REPO_ROOT / "docs" / "requirements" / "stories",
}

PREFIXES: dict[str, str] = {
    "prd": "PRD",
    "rfc": "RFC",
    "adr": "ADR",
    "story": "US",
}

FILE_PATTERNS: dict[str, str] = {
    "prd": "PRD-[0-9]*.md",
    "rfc": "RFC-[0-9]*.md",
    "adr": "ADR-[0-9]*.md",
    "story": "US-[0-9]*.md",
}

# Matches the numeric ID in filenames like PRD-003_foo.md or US-021_bar.md
_ID_RE = re.compile(r"^(?:PRD|RFC|ADR|US)-(\d+)")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def next_id(doc_type: str) -> int:
    """Return the next sequential integer ID for this document type."""
    output_dir = OUTPUT_DIRS[doc_type]
    max_id = 0
    for path in output_dir.glob(FILE_PATTERNS[doc_type]):
        m = _ID_RE.match(path.name)
        if m:
            max_id = max(max_id, int(m.group(1)))
    return max_id + 1


def full_id(doc_type: str, n: int) -> str:
    """Format the document ID, e.g. 'PRD-004' or 'US-021'."""
    prefix = PREFIXES[doc_type]
    width = 3  # always zero-pad to 3 digits
    return f"{prefix}-{n:0{width}d}"


def slugify(text: str) -> str:
    """Convert a description string to a lowercase_underscore filename slug (≤40 chars)."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", "_", text.strip())
    return text[:40].rstrip("_")


def build_prompt(doc_type: str, user_input: str, doc_id: str) -> str:
    """Load the skill template and substitute {{INPUT}} and {{DOC_ID}}."""
    skill_file = SKILLS_DIR / f"{doc_type}_generator.md"
    if not skill_file.exists():
        print(f"error: skill template not found: {skill_file}", file=sys.stderr)
        sys.exit(1)
    template = skill_file.read_text()
    return template.replace("{{INPUT}}", user_input).replace("{{DOC_ID}}", doc_id)


def run_claude(prompt: str) -> str:
    """Run `claude -p` with the prompt piped via stdin. Returns the model output."""
    result = subprocess.run(
        ["claude", "-p", "--output-format", "text"],
        input=prompt,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        print("Claude CLI error:", file=sys.stderr)
        print(result.stderr or "(no stderr)", file=sys.stderr)
        sys.exit(result.returncode)
    return result.stdout


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate structured docs from skill templates via the Claude CLI.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "type",
        choices=list(OUTPUT_DIRS),
        metavar="TYPE",
        help="Document type: prd | rfc | adr | story",
    )
    parser.add_argument(
        "input",
        help="Short description of the document to generate (use quotes for multi-word input)",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Auto-save to the correct docs/ location with the next sequential ID",
    )
    parser.add_argument(
        "--slug",
        default="",
        metavar="SLUG",
        help=(
            "Short filename slug (e.g. 'jsonl_output'). "
            "Derived from the input description if omitted."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the assembled prompt without calling Claude (useful for debugging templates)",
    )
    args = parser.parse_args()

    # Determine the document ID before calling Claude so it can be embedded in the prompt.
    n = next_id(args.type)
    doc_id = full_id(args.type, n)

    prompt = build_prompt(args.type, args.input, doc_id)

    if args.dry_run:
        print(f"--- Prompt for {doc_id} ---\n")
        print(prompt)
        return

    print(f"Generating {doc_id} …", file=sys.stderr)
    content = run_claude(prompt)

    if args.save:
        slug = args.slug or slugify(args.input)
        filename = f"{doc_id}_{slug}.md"
        output_path = OUTPUT_DIRS[args.type] / filename
        output_path.write_text(content)
        rel = output_path.relative_to(REPO_ROOT)
        print(f"Saved → {rel}", file=sys.stderr)
    else:
        # Print to stdout so the user can inspect or redirect to a file.
        print(content)


if __name__ == "__main__":
    main()
